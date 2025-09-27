from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict, validator
from datetime import datetime
import re

from src.db import get_db
from src.db.models import Movement, Item, Lot, Material, Location, MovementType, AuditLog

router = APIRouter()

# Pydantic スキーマ
class MovementBase(BaseModel):
    quantity: int = Field(..., gt=0, description="移動本数")
    instruction_number: Optional[str] = Field(None, description="指示書番号（IS-YYYY-NNNN）")
    notes: Optional[str] = Field(None, description="備考")

    @validator('instruction_number')
    def validate_instruction_number(cls, v):
        if v is not None:
            # IS-YYYY-NNNN形式をチェック
            if not re.match(r'^IS-\d{4}-\d{4}$', v):
                raise ValueError('指示書番号はIS-YYYY-NNNN形式で入力してください')
        return v

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
        movement_dict = {
            "id": movement.id,
            "item_id": movement.item_id,
            "movement_type": movement.movement_type,
            "quantity": movement.quantity,
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

    # 入庫前の数量を記録
    old_quantity = item.current_quantity

    # アイテムの数量を増加
    item.current_quantity += movement_data.quantity

    # 入庫履歴を作成
    movement = Movement(
        item_id=item_id,
        movement_type=MovementType.IN,
        quantity=movement_data.quantity,
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
        new_values=f"数量: {item.current_quantity}, 入庫数: {movement_data.quantity}",
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
        "in_quantity": movement_data.quantity
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

    # 在庫不足チェック
    if item.current_quantity < movement_data.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"在庫が不足しています。現在庫: {item.current_quantity}本, 出庫要求: {movement_data.quantity}本"
        )

    # 出庫前の数量を記録
    old_quantity = item.current_quantity

    # アイテムの数量を減少
    item.current_quantity -= movement_data.quantity

    # 出庫履歴を作成
    movement = Movement(
        item_id=item_id,
        movement_type=MovementType.OUT,
        quantity=movement_data.quantity,
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
        new_values=f"数量: {item.current_quantity}, 出庫数: {movement_data.quantity}, 指示書: {movement_data.instruction_number}",
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
        "out_quantity": movement_data.quantity,
        "instruction_number": movement_data.instruction_number
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

        # 重量計算
        if material.shape.value == "round":
            radius_cm = (material.diameter_mm / 2) / 10
            length_cm = movement.item.lot.length_mm / 10
            volume_cm3 = 3.14159 * (radius_cm ** 2) * length_cm
        elif material.shape.value == "hexagon":
            side_cm = (material.diameter_mm / 2) / 10
            length_cm = movement.item.lot.length_mm / 10
            volume_cm3 = (3 * (3 ** 0.5) / 2) * (side_cm ** 2) * length_cm
        elif material.shape.value == "square":
            side_cm = material.diameter_mm / 10
            length_cm = movement.item.lot.length_mm / 10
            volume_cm3 = (side_cm ** 2) * length_cm
        else:
            volume_cm3 = 0

        weight_per_piece_kg = (volume_cm3 * material.current_density) / 1000
        total_weight_kg = weight_per_piece_kg * movement.quantity

        result.append({
            "movement_id": movement.id,
            "movement_type": movement.movement_type.value,
            "quantity": movement.quantity,
            "weight_kg": round(total_weight_kg, 3),
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
        items = db.query(Item).filter(Item.lot_id == lot.id, Item.is_active == True).all()
        total_items = len(items)
        total_quantity = sum(item.current_quantity for item in items)

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
