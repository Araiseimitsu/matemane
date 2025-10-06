from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from datetime import datetime
import math
from decimal import Decimal, ROUND_HALF_UP

from src.db import get_db
from src.db.models import (
    Movement,
    Item,
    Lot,
    Material,
    Location,
    MovementType,
    AuditLog,
    MaterialShape,
)

router = APIRouter()

# 共通ユーティリティ
def _calculate_weight_per_piece_kg(item: Item) -> float:
    """指定アイテムの1本あたり重量(kg)を算出"""
    material = item.lot.material
    length_cm = item.lot.length_mm / 10

    if material.shape == MaterialShape.ROUND:
        radius_cm = (material.diameter_mm / 2) / 10
        volume_cm3 = math.pi * (radius_cm ** 2) * length_cm
    elif material.shape == MaterialShape.HEXAGON:
        side_cm = (material.diameter_mm / 2) / 10
        volume_cm3 = (3 * math.sqrt(3) / 2) * (side_cm ** 2) * length_cm
    elif material.shape == MaterialShape.SQUARE:
        side_cm = material.diameter_mm / 10
        volume_cm3 = (side_cm ** 2) * length_cm
    else:
        volume_cm3 = 0.0

    return (volume_cm3 * material.current_density) / 1000


def _resolve_quantity_from_weight(weight_kg: float, weight_per_piece_kg: float) -> int:
    """重量から本数を四捨五入で算出"""
    if weight_per_piece_kg <= 0:
        raise ValueError("単重情報が不足しているため重量換算ができません")

    quantity_decimal = (Decimal(str(weight_kg)) / Decimal(str(weight_per_piece_kg)))
    quantity = int(quantity_decimal.quantize(Decimal('1'), rounding=ROUND_HALF_UP))

    if quantity <= 0:
        raise ValueError("重量が小さすぎるため本数を算出できません")

    return quantity

# Pydantic スキーマ
class MovementBase(BaseModel):
    quantity: Optional[int] = Field(None, gt=0, description="移動本数")
    weight_kg: Optional[float] = Field(None, gt=0, description="移動重量(kg)")
    notes: Optional[str] = Field(None, description="備考")

    @model_validator(mode="after")
    def validate_quantity_or_weight(self):
        if self.quantity is None and self.weight_kg is None:
            raise ValueError('数量または重量のいずれかを入力してください')
        return self

class MovementIn(MovementBase):
    """入庫用（指示書番号は任意）"""
    pass

class MovementOut(MovementBase):
    """出庫用"""
    pass

class MovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    movement_type: MovementType
    quantity: int
    weight_kg: Optional[float] = None
    notes: Optional[str]
    processed_by: int
    processed_at: datetime

    # 関連情報（JOINで取得）
    item_management_code: Optional[str] = None
    material_name: Optional[str] = None
    lot_number: Optional[str] = None
    remaining_quantity: Optional[int] = None


# API エンドポイント
@router.get("/", response_model=List[MovementResponse])
async def get_movements(
    skip: int = 0,
    limit: int = 100,
    movement_type: Optional[MovementType] = None,
    item_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """入出庫履歴取得"""
    query = db.query(Movement).options(
        joinedload(Movement.item).joinedload(Item.lot).joinedload(Lot.material)
    )

    if movement_type is not None:
        query = query.filter(Movement.movement_type == movement_type)

    if item_id is not None:
        query = query.filter(Movement.item_id == item_id)

    movements = query.order_by(desc(Movement.processed_at)).offset(skip).limit(limit).all()

    # レスポンス用に関連情報を追加
    result = []
    for movement in movements:
        weight_per_piece = _calculate_weight_per_piece_kg(movement.item)
        weight_kg = round(weight_per_piece * movement.quantity, 3)

        movement_dict = {
            "id": movement.id,
            "item_id": movement.item_id,
            "movement_type": movement.movement_type,
            "quantity": movement.quantity,
            "weight_kg": weight_kg,
            "notes": movement.notes,
            "processed_by": movement.processed_by,
            "processed_at": movement.processed_at,
            "item_management_code": movement.item.management_code,
            "material_name": movement.item.lot.material.name,
            "lot_number": movement.item.lot.lot_number,
            "remaining_quantity": movement.item.current_quantity
        }
        result.append(MovementResponse(**movement_dict))

    return result

@router.post("/in/{item_id}")
async def create_in_movement(
    item_id: int,
    movement_data: MovementIn,
    db: Session = Depends(get_db)
):
    """入庫処理"""
    # アイテム存在確認
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="指定されたアイテムが見つかりません"
        )

    # 無効なアイテムには入庫できないが、在庫数=0のアイテムは入庫可能
    if not item.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="無効なアイテムには入庫できません"
        )

    weight_per_piece = _calculate_weight_per_piece_kg(item)
    resolved_quantity = movement_data.quantity
    input_weight = movement_data.weight_kg

    if resolved_quantity is None:
        if input_weight is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="数量または重量を指定してください"
            )
        try:
            resolved_quantity = _resolve_quantity_from_weight(input_weight, weight_per_piece)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc)
            )

    if resolved_quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="数量は1以上で入力してください"
        )

    calculated_weight = round(resolved_quantity * weight_per_piece, 3)
    raw_input_weight = input_weight if input_weight is not None else calculated_weight
    weight_difference = round(calculated_weight - raw_input_weight, 3)
    normalized_input_weight = round(raw_input_weight, 3)

    # 入庫前の数量を記録
    old_quantity = item.current_quantity

    # アイテムの数量を増加
    item.current_quantity += resolved_quantity

    # 入庫履歴を作成
    movement = Movement(
        item_id=item_id,
        movement_type=MovementType.IN,
        quantity=resolved_quantity,
        notes=movement_data.notes,
        processed_by=1  # TODO: 認証実装後にユーザーIDを設定
    )

    db.add(movement)

    # 監査ログを作成
    audit_log = AuditLog(
        user_id=1,  # TODO: 認証実装後にユーザーIDを設定
        action="入庫",
        target_table="items",
        target_id=item_id,
        old_values=f"数量: {old_quantity}",
        new_values=f"数量: {item.current_quantity}, 入庫本数: {resolved_quantity}, 入庫重量: {calculated_weight}kg",
        created_at=datetime.now()
    )

    db.add(audit_log)
    db.commit()
    db.refresh(movement)

    return {
        "message": "入庫処理が完了しました",
        "movement_id": movement.id,
        "item_id": item_id,
        "old_quantity": old_quantity,
        "new_quantity": item.current_quantity,
        "in_quantity": resolved_quantity,
        "calculated_weight_kg": calculated_weight,
        "input_weight_kg": normalized_input_weight,
        "weight_difference_kg": weight_difference
    }

@router.post("/out/{item_id}")
async def create_out_movement(
    item_id: int,
    movement_data: MovementOut,
    db: Session = Depends(get_db)
):
    """出庫処理"""
    # アイテム存在確認
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="指定されたアイテムが見つかりません"
        )

    if not item.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="無効なアイテムからは出庫できません"
        )

    weight_per_piece = _calculate_weight_per_piece_kg(item)
    resolved_quantity = movement_data.quantity
    input_weight = movement_data.weight_kg

    if resolved_quantity is None:
        if input_weight is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="数量または重量を指定してください"
            )
        try:
            resolved_quantity = _resolve_quantity_from_weight(input_weight, weight_per_piece)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc)
            )

    if resolved_quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="数量は1以上で入力してください"
        )

    if item.current_quantity < resolved_quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"在庫が不足しています。現在庫: {item.current_quantity}本, 出庫要求: {resolved_quantity}本"
        )

    calculated_weight = round(resolved_quantity * weight_per_piece, 3)
    raw_input_weight = input_weight if input_weight is not None else calculated_weight
    weight_difference = round(calculated_weight - raw_input_weight, 3)
    normalized_input_weight = round(raw_input_weight, 3)

    # 出庫前の数量を記録
    old_quantity = item.current_quantity

    # アイテムの数量を減少
    item.current_quantity -= resolved_quantity

    # 出庫履歴を作成
    movement = Movement(
        item_id=item_id,
        movement_type=MovementType.OUT,
        quantity=resolved_quantity,
        notes=movement_data.notes,
        processed_by=1  # TODO: 認証実装後にユーザーIDを設定
    )

    db.add(movement)

    # 監査ログを作成
    audit_log = AuditLog(
        user_id=1,  # TODO: 認証実装後にユーザーIDを設定
        action="出庫",
        target_table="items",
        target_id=item_id,
        old_values=f"数量: {old_quantity}",
        new_values=f"数量: {item.current_quantity}, 出庫本数: {resolved_quantity}, 出庫重量: {calculated_weight}kg",
        created_at=datetime.now()
    )

    db.add(audit_log)
    db.commit()
    db.refresh(movement)

    return {
        "message": "出庫処理が完了しました",
        "movement_id": movement.id,
        "item_id": item_id,
        "old_quantity": old_quantity,
        "new_quantity": item.current_quantity,
        "out_quantity": resolved_quantity,
        "calculated_weight_kg": calculated_weight,
        "input_weight_kg": normalized_input_weight,
        "weight_difference_kg": weight_difference
    }

def get_shape_name(shape_value: str) -> str:
    """形状値を日本語名に変換"""
    shape_map = {
        "round": "丸棒",
        "hexagon": "六角棒",
        "square": "角棒"
    }
    return shape_map.get(shape_value, shape_value)
