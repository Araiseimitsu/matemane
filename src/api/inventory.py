from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

from src.db import get_db
from src.db.models import Item, Lot, Material, Location, MaterialShape

router = APIRouter()

# Pydantic スキーマ
class LocationInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None

class MaterialInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    shape: MaterialShape
    diameter_mm: float
    current_density: float

class LotInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lot_number: str
    length_mm: int
    initial_quantity: int
    supplier: Optional[str] = None
    received_date: Optional[datetime] = None

class InventoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    management_code: str
    current_quantity: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # 関連情報
    lot: LotInfo
    material: MaterialInfo
    location: Optional[LocationInfo] = None

    # 計算項目
    total_weight_kg: Optional[float] = None
    weight_per_piece_kg: Optional[float] = None

class InventorySummary(BaseModel):
    material_id: int
    material_name: str
    material_shape: MaterialShape
    diameter_mm: float
    length_mm: int
    total_quantity: int
    total_weight_kg: float
    lot_count: int
    location_count: int

# API エンドポイント
@router.get("/", response_model=List[InventoryItem])
async def get_inventory(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    material_id: Optional[int] = Query(None, description="材料IDでフィルタ"),
    location_id: Optional[int] = Query(None, description="置き場IDでフィルタ"),
    lot_number: Optional[str] = Query(None, description="ロット番号で検索"),
    is_active: Optional[bool] = Query(True, description="有効フラグでフィルタ"),
    has_stock: Optional[bool] = Query(None, description="在庫有無でフィルタ"),
    db: Session = Depends(get_db)
):
    """在庫一覧取得"""
    query = db.query(Item).options(
        joinedload(Item.lot).joinedload(Lot.material),
        joinedload(Item.location)
    )

    if is_active is not None:
        query = query.filter(Item.is_active == is_active)

    if has_stock is not None:
        if has_stock:
            query = query.filter(Item.current_quantity > 0)
        else:
            query = query.filter(Item.current_quantity == 0)

    if material_id is not None:
        query = query.join(Lot).filter(Lot.material_id == material_id)

    if location_id is not None:
        query = query.filter(Item.location_id == location_id)

    if lot_number is not None:
        query = query.join(Lot).filter(Lot.lot_number.ilike(f"%{lot_number}%"))

    items = query.offset(skip).limit(limit).all()

    # 重量計算を追加
    result = []
    for item in items:
        material = item.lot.material

        # 体積計算（cm³）
        if material.shape == MaterialShape.ROUND:
            radius_cm = (material.diameter_mm / 2) / 10
            length_cm = item.lot.length_mm / 10
            volume_cm3 = 3.14159 * (radius_cm ** 2) * length_cm
        elif material.shape == MaterialShape.HEXAGON:
            side_cm = (material.diameter_mm / 2) / 10
            length_cm = item.lot.length_mm / 10
            volume_cm3 = (3 * (3 ** 0.5) / 2) * (side_cm ** 2) * length_cm
        elif material.shape == MaterialShape.SQUARE:
            side_cm = material.diameter_mm / 10
            length_cm = item.lot.length_mm / 10
            volume_cm3 = (side_cm ** 2) * length_cm
        else:
            volume_cm3 = 0

        weight_per_piece_kg = (volume_cm3 * material.current_density) / 1000
        total_weight_kg = weight_per_piece_kg * item.current_quantity

        # アイテムを辞書に変換して重量情報を追加
        item_dict = {
            "id": item.id,
            "management_code": item.management_code,
            "current_quantity": item.current_quantity,
            "is_active": item.is_active,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "lot": {
                "id": item.lot.id,
                "lot_number": item.lot.lot_number,
                "length_mm": item.lot.length_mm,
                "initial_quantity": item.lot.initial_quantity,
                "supplier": item.lot.supplier,
                "received_date": item.lot.received_date
            },
            "material": {
                "id": material.id,
                "name": material.name,
                "shape": material.shape,
                "diameter_mm": material.diameter_mm,
                "current_density": material.current_density
            },
            "location": {
                "id": item.location.id,
                "name": item.location.name,
                "description": item.location.description
            } if item.location else None,
            "weight_per_piece_kg": round(weight_per_piece_kg, 3),
            "total_weight_kg": round(total_weight_kg, 3)
        }

        result.append(InventoryItem(**item_dict))

    return result

@router.get("/summary", response_model=List[InventorySummary])
async def get_inventory_summary(
    material_id: Optional[int] = Query(None, description="材料IDでフィルタ"),
    db: Session = Depends(get_db)
):
    """在庫サマリー取得（材料・長さ別の集計）"""
    query = db.query(
        Material.id.label("material_id"),
        Material.name.label("material_name"),
        Material.shape.label("material_shape"),
        Material.diameter_mm.label("diameter_mm"),
        Lot.length_mm.label("length_mm"),
        func.sum(Item.current_quantity).label("total_quantity"),
        func.count(func.distinct(Lot.id)).label("lot_count"),
        func.count(func.distinct(Item.location_id)).label("location_count")
    ).select_from(Item).join(Lot).join(Material).filter(
        Item.is_active == True,
        Item.current_quantity > 0
    ).group_by(
        Material.id,
        Material.name,
        Material.shape,
        Material.diameter_mm,
        Lot.length_mm
    )

    if material_id is not None:
        query = query.filter(Material.id == material_id)

    results = query.all()

    summary_list = []
    for result in results:
        # 重量計算
        if result.material_shape == MaterialShape.ROUND:
            radius_cm = (result.diameter_mm / 2) / 10
            length_cm = result.length_mm / 10
            volume_cm3 = 3.14159 * (radius_cm ** 2) * length_cm
        elif result.material_shape == MaterialShape.HEXAGON:
            side_cm = (result.diameter_mm / 2) / 10
            length_cm = result.length_mm / 10
            volume_cm3 = (3 * (3 ** 0.5) / 2) * (side_cm ** 2) * length_cm
        elif result.material_shape == MaterialShape.SQUARE:
            side_cm = result.diameter_mm / 10
            length_cm = result.length_mm / 10
            volume_cm3 = (side_cm ** 2) * length_cm
        else:
            volume_cm3 = 0

        # 材料の比重を取得
        material = db.query(Material).filter(Material.id == result.material_id).first()
        weight_per_piece_kg = (volume_cm3 * material.current_density) / 1000
        total_weight_kg = weight_per_piece_kg * result.total_quantity

        summary_list.append(InventorySummary(
            material_id=result.material_id,
            material_name=result.material_name,
            material_shape=result.material_shape,
            diameter_mm=result.diameter_mm,
            length_mm=result.length_mm,
            total_quantity=result.total_quantity,
            total_weight_kg=round(total_weight_kg, 3),
            lot_count=result.lot_count,
            location_count=result.location_count
        ))

    return summary_list

@router.get("/search/{management_code}")
async def search_by_management_code(management_code: str, db: Session = Depends(get_db)):
    """管理コード（UUID）による検索"""
    item = db.query(Item).options(
        joinedload(Item.lot).joinedload(Lot.material),
        joinedload(Item.location)
    ).filter(Item.management_code == management_code).first()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="指定された管理コードのアイテムが見つかりません"
        )

    # 重量計算
    material = item.lot.material

    if material.shape == MaterialShape.ROUND:
        radius_cm = (material.diameter_mm / 2) / 10
        length_cm = item.lot.length_mm / 10
        volume_cm3 = 3.14159 * (radius_cm ** 2) * length_cm
    elif material.shape == MaterialShape.HEXAGON:
        side_cm = (material.diameter_mm / 2) / 10
        length_cm = item.lot.length_mm / 10
        volume_cm3 = (3 * (3 ** 0.5) / 2) * (side_cm ** 2) * length_cm
    elif material.shape == MaterialShape.SQUARE:
        side_cm = material.diameter_mm / 10
        length_cm = item.lot.length_mm / 10
        volume_cm3 = (side_cm ** 2) * length_cm
    else:
        volume_cm3 = 0

    weight_per_piece_kg = (volume_cm3 * material.current_density) / 1000
    total_weight_kg = weight_per_piece_kg * item.current_quantity

    return {
        "item": {
            "id": item.id,
            "management_code": item.management_code,
            "current_quantity": item.current_quantity,
            "is_active": item.is_active,
            "created_at": item.created_at,
            "updated_at": item.updated_at
        },
        "lot": {
            "id": item.lot.id,
            "lot_number": item.lot.lot_number,
            "length_mm": item.lot.length_mm,
            "initial_quantity": item.lot.initial_quantity,
            "supplier": item.lot.supplier,
            "received_date": item.lot.received_date
        },
        "material": {
            "id": material.id,
            "name": material.name,
            "shape": material.shape.value,
            "diameter_mm": material.diameter_mm,
            "current_density": material.current_density
        },
        "location": {
            "id": item.location.id,
            "name": item.location.name,
            "description": item.location.description
        } if item.location else None,
        "weight_per_piece_kg": round(weight_per_piece_kg, 3),
        "total_weight_kg": round(total_weight_kg, 3)
    }

@router.get("/low-stock")
async def get_low_stock_items(
    threshold: int = Query(5, ge=0, description="在庫下限値"),
    db: Session = Depends(get_db)
):
    """在庫下限アラート"""
    items = db.query(Item).options(
        joinedload(Item.lot).joinedload(Lot.material),
        joinedload(Item.location)
    ).filter(
        Item.is_active == True,
        Item.current_quantity <= threshold
    ).all()

    result = []
    for item in items:
        material = item.lot.material

        # 重量計算
        if material.shape == MaterialShape.ROUND:
            radius_cm = (material.diameter_mm / 2) / 10
            length_cm = item.lot.length_mm / 10
            volume_cm3 = 3.14159 * (radius_cm ** 2) * length_cm
        elif material.shape == MaterialShape.HEXAGON:
            side_cm = (material.diameter_mm / 2) / 10
            length_cm = item.lot.length_mm / 10
            volume_cm3 = (3 * (3 ** 0.5) / 2) * (side_cm ** 2) * length_cm
        elif material.shape == MaterialShape.SQUARE:
            side_cm = material.diameter_mm / 10
            length_cm = item.lot.length_mm / 10
            volume_cm3 = (side_cm ** 2) * length_cm
        else:
            volume_cm3 = 0

        weight_per_piece_kg = (volume_cm3 * material.current_density) / 1000

        result.append({
            "management_code": item.management_code,
            "material_name": material.name,
            "lot_number": item.lot.lot_number,
            "length_mm": item.lot.length_mm,
            "current_quantity": item.current_quantity,
            "location_name": item.location.name if item.location else "未配置",
            "weight_per_piece_kg": round(weight_per_piece_kg, 3),
            "alert_level": "危険" if item.current_quantity == 0 else "注意" if item.current_quantity <= threshold / 2 else "警告"
        })

    return {"threshold": threshold, "items": result}

@router.get("/locations/", response_model=List[LocationInfo])
async def get_locations(
    is_active: Optional[bool] = Query(True, description="有効な置き場のみ取得"),
    db: Session = Depends(get_db)
):
    """置き場一覧取得"""
    query = db.query(Location)

    if is_active is not None:
        query = query.filter(Location.is_active == is_active)

    locations = query.order_by(Location.name).all()
    return locations
