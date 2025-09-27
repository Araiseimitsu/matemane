from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from datetime import datetime
import re
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
    instruction_number: Optional[str] = Field(None, description="指示書番号（IS-YYYY-NNNN）")
    notes: Optional[str] = Field(None, description="備考")

    @field_validator('instruction_number')
    @classmethod
    def validate_instruction_number(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            # IS-YYYY-NNNN形式をチェック
            if not re.match(r'^IS-\d{4}-\d{4}$', value):
                raise ValueError('指示書番号はIS-YYYY-NNNN形式で入力してください')
        return value

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
    instruction_number: Optional[str]
    notes: Optional[str]
    processed_by: int
    processed_at: datetime

    # 関連情報（JOINで取得）
    item_management_code: Optional[str] = None
    material_name: Optional[str] = None
    lot_number: Optional[str] = None
    remaining_quantity: Optional[int] = None

class LotCreateRequest(BaseModel):
    material_id: int = Field(..., description="材料ID")
    lot_number: str = Field(..., max_length=100, description="ロット番号")
    length_mm: int = Field(..., gt=0, description="長さ（mm）")
    initial_quantity: int = Field(..., gt=0, description="初期本数")
    supplier: Optional[str] = Field(None, max_length=200, description="仕入先")
    received_date: Optional[datetime] = Field(None, description="入荷日")
    notes: Optional[str] = Field(None, description="備考")

class ItemCreateRequest(BaseModel):
    lot_id: int = Field(..., description="ロットID")
    location_id: Optional[int] = Field(None, description="置き場ID")
    initial_quantity: int = Field(..., gt=0, description="初期本数")

# API エンドポイント
@router.get("/", response_model=List[MovementResponse])
async def get_movements(
    skip: int = 0,
    limit: int = 100,
    movement_type: Optional[MovementType] = None,
    item_id: Optional[int] = None,
    instruction_number: Optional[str] = None,
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

    if instruction_number is not None:
        query = query.filter(Movement.instruction_number.ilike(f"%{instruction_number}%"))

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
            "instruction_number": movement.instruction_number,
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
        instruction_number=movement_data.instruction_number,
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
        instruction_number=movement_data.instruction_number,
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
        new_values=f"数量: {item.current_quantity}, 出庫本数: {resolved_quantity}, 出庫重量: {calculated_weight}kg, 指示書: {movement_data.instruction_number}",
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
        "instruction_number": movement_data.instruction_number,
        "calculated_weight_kg": calculated_weight,
        "input_weight_kg": normalized_input_weight,
        "weight_difference_kg": weight_difference
    }

@router.get("/by-instruction/{instruction_number}")
async def get_movements_by_instruction(
    instruction_number: str,
    db: Session = Depends(get_db)
):
    """指示書番号別の入出庫履歴取得"""
    movements = db.query(Movement).options(
        joinedload(Movement.item).joinedload(Item.lot).joinedload(Lot.material)
    ).filter(
        Movement.instruction_number == instruction_number
    ).order_by(desc(Movement.processed_at)).all()

    if not movements:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="指定された指示書番号の履歴が見つかりません"
        )

    result = []
    for movement in movements:
        material = movement.item.lot.material
        weight_per_piece_kg = _calculate_weight_per_piece_kg(movement.item)
        total_weight_kg = round(weight_per_piece_kg * movement.quantity, 3)

        result.append({
            "movement_id": movement.id,
            "movement_type": movement.movement_type.value,
            "quantity": movement.quantity,
            "weight_kg": total_weight_kg,
            "processed_at": movement.processed_at,
            "item": {
                "management_code": movement.item.management_code,
                "current_quantity": movement.item.current_quantity
            },
            "material": {
                "name": material.name,
                "shape": material.shape.value,
                "diameter_mm": material.diameter_mm
            },
            "lot": {
                "lot_number": movement.item.lot.lot_number,
                "length_mm": movement.item.lot.length_mm
            },
            "notes": movement.notes
        })

    return {
        "instruction_number": instruction_number,
        "movements": result,
        "total_movements": len(result)
    }

@router.post("/lots", status_code=status.HTTP_201_CREATED)
async def create_lot(lot_data: LotCreateRequest, db: Session = Depends(get_db)):
    """新しいロット作成"""
    # 材料存在確認
    material = db.query(Material).filter(Material.id == lot_data.material_id).first()
    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="指定された材料が見つかりません"
        )

    # 同じロット番号の存在確認
    existing_lot = db.query(Lot).filter(Lot.lot_number == lot_data.lot_number).first()
    if existing_lot:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="同じロット番号が既に存在します"
        )

    # ロット作成
    new_lot = Lot(
        lot_number=lot_data.lot_number,
        material_id=lot_data.material_id,
        length_mm=lot_data.length_mm,
        initial_quantity=lot_data.initial_quantity,
        supplier=lot_data.supplier,
        received_date=lot_data.received_date or datetime.now(),
        notes=lot_data.notes
    )

    db.add(new_lot)
    db.commit()
    db.refresh(new_lot)

    return {
        "message": "ロットが作成されました",
        "lot_id": new_lot.id,
        "lot_number": new_lot.lot_number
    }

@router.post("/items", status_code=status.HTTP_201_CREATED)
async def create_item(item_data: ItemCreateRequest, db: Session = Depends(get_db)):
    """新しいアイテム作成"""
    # ロット存在確認
    lot = db.query(Lot).filter(Lot.id == item_data.lot_id).first()
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="指定されたロットが見つかりません"
        )

    # 置き場存在確認（指定された場合）
    if item_data.location_id is not None:
        location = db.query(Location).filter(Location.id == item_data.location_id).first()
        if not location:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="指定された置き場が見つかりません"
            )

    # アイテム作成
    new_item = Item(
        lot_id=item_data.lot_id,
        location_id=item_data.location_id,
        current_quantity=item_data.initial_quantity
    )

    db.add(new_item)
    db.commit()
    db.refresh(new_item)

    return {
        "message": "アイテムが作成されました",
        "item_id": new_item.id,
        "management_code": new_item.management_code,
        "initial_quantity": new_item.current_quantity
    }

@router.get("/lots", response_model=List[dict])
async def get_lots(
    skip: int = 0,
    limit: int = 100,
    material_id: Optional[int] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """ロット一覧取得"""
    query = db.query(Lot).options(
        joinedload(Lot.material)
    )

    # 材料フィルタ
    if material_id is not None:
        query = query.filter(Lot.material_id == material_id)

    # 検索フィルタ（ロット番号、仕入先）
    if search:
        query = query.filter(
            (Lot.lot_number.ilike(f"%{search}%")) |
            (Lot.supplier.ilike(f"%{search}%"))
        )

    lots = query.order_by(desc(Lot.created_at)).offset(skip).limit(limit).all()

    # レスポンス用に関連情報を追加
    result = []
    for lot in lots:
        material = lot.material

        # 重量計算（1本あたり）
        if material.shape.value == "round":
            radius_cm = (material.diameter_mm / 2) / 10
            length_cm = lot.length_mm / 10
            volume_cm3 = 3.14159 * (radius_cm ** 2) * length_cm
        elif material.shape.value == "hexagon":
            side_cm = (material.diameter_mm / 2) / 10
            length_cm = lot.length_mm / 10
            volume_cm3 = (3 * (3 ** 0.5) / 2) * (side_cm ** 2) * length_cm
        elif material.shape.value == "square":
            side_cm = material.diameter_mm / 10
            length_cm = lot.length_mm / 10
            volume_cm3 = (side_cm ** 2) * length_cm
        else:
            volume_cm3 = 0

        weight_per_piece_kg = (volume_cm3 * material.current_density) / 1000

        # このロットに属するアイテム数と総在庫数を計算
        items = db.query(Item).options(
            joinedload(Item.location)
        ).filter(Item.lot_id == lot.id, Item.is_active == True).all()
        total_items = len(items)
        total_quantity = sum(item.current_quantity for item in items)

        # アイテム詳細情報（管理コード含む）
        items_detail = []
        for item in items:
            items_detail.append({
                "id": item.id,
                "management_code": item.management_code,
                "current_quantity": item.current_quantity,
                "location_id": item.location_id,
                "location_name": item.location.name if item.location else None
            })

        result.append({
            "id": lot.id,
            "lot_number": lot.lot_number,
            "length_mm": lot.length_mm,
            "initial_quantity": lot.initial_quantity,
            "supplier": lot.supplier,
            "received_date": lot.received_date,
            "notes": lot.notes,
            "created_at": lot.created_at,
            "material": {
                "id": material.id,
                "name": material.name,
                "shape": material.shape.value,
                "shape_name": get_shape_name(material.shape.value),
                "diameter_mm": material.diameter_mm,
                "density": material.current_density
            },
            "calculated": {
                "weight_per_piece_kg": round(weight_per_piece_kg, 3),
                "volume_per_piece_cm3": round(volume_cm3, 3)
            },
            "items_summary": {
                "total_items": total_items,
                "total_quantity": total_quantity,
                "remaining_rate": round((total_quantity / lot.initial_quantity) * 100, 1) if lot.initial_quantity > 0 else 0
            },
            "items": items_detail
        })

    return result

@router.get("/search-items", response_model=List[dict])
async def search_items(
    material_name: Optional[str] = None,
    diameter_mm: Optional[int] = None,
    lot_number: Optional[str] = None,
    location_id: Optional[int] = None,
    min_quantity: Optional[int] = None,
    max_quantity: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """アイテム検索（材料名、径、ロット番号など複数条件）"""
    query = db.query(Item).options(
        joinedload(Item.lot).joinedload(Lot.material),
        joinedload(Item.location)
    ).filter(Item.is_active == True)

    # フィルタ条件に応じたJOINを追加
    if any([material_name, diameter_mm, lot_number]):
        query = query.join(Lot, Item.lot)

    if material_name or diameter_mm:
        query = query.join(Material, Lot.material)

    # 各種フィルタ適用
    if material_name:
        query = query.filter(Material.name.ilike(f"%{material_name}%"))

    if diameter_mm:
        query = query.filter(Material.diameter_mm == diameter_mm)

    if lot_number:
        query = query.filter(Lot.lot_number.ilike(f"%{lot_number}%"))

    if location_id:
        query = query.filter(Item.location_id == location_id)

    if min_quantity is not None:
        query = query.filter(Item.current_quantity >= min_quantity)
    if max_quantity is not None:
        query = query.filter(Item.current_quantity <= max_quantity)
    items = query.order_by(desc(Item.updated_at)).limit(50).all()

    result = []
    for item in items:
        material = item.lot.material

        # 重量計算
        if material.shape.value == "round":
            radius_cm = (material.diameter_mm / 2) / 10
            length_cm = item.lot.length_mm / 10
            volume_cm3 = 3.14159 * (radius_cm ** 2) * length_cm
        elif material.shape.value == "hexagon":
            side_cm = (material.diameter_mm / 2) / 10
            length_cm = item.lot.length_mm / 10
            volume_cm3 = (3 * (3 ** 0.5) / 2) * (side_cm ** 2) * length_cm
        elif material.shape.value == "square":
            side_cm = material.diameter_mm / 10
            length_cm = item.lot.length_mm / 10
            volume_cm3 = (side_cm ** 2) * length_cm
        else:
            volume_cm3 = 0

        weight_per_piece_kg = (volume_cm3 * material.current_density) / 1000
        total_weight_kg = weight_per_piece_kg * item.current_quantity

        result.append({
            "id": item.id,
            "management_code": item.management_code,
            "current_quantity": item.current_quantity,
            "is_active": item.is_active,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "material": {
                "id": material.id,
                "name": material.name,
                "shape": material.shape.value,
                "shape_name": get_shape_name(material.shape.value),
                "diameter_mm": material.diameter_mm,
                "density": material.current_density
            },
            "lot": {
                "id": item.lot.id,
                "lot_number": item.lot.lot_number,
                "length_mm": item.lot.length_mm,
                "supplier": item.lot.supplier,
                "received_date": item.lot.received_date
            },
            "location": {
                "id": item.location.id if item.location else None,
                "name": item.location.name if item.location else None
            },
            "calculated": {
                "weight_per_piece_kg": round(weight_per_piece_kg, 3),
                "total_weight_kg": round(total_weight_kg, 3),
                "volume_per_piece_cm3": round(volume_cm3, 3)
            }
        })

    return result

def get_shape_name(shape_value: str) -> str:
    """形状値を日本語名に変換"""
    shape_map = {
        "round": "丸棒",
        "hexagon": "六角棒",
        "square": "角棒"
    }
    return shape_map.get(shape_value, shape_value)
