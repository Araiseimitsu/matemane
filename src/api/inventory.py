from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict, field_serializer
from datetime import datetime

from src.db import get_db
from src.db.models import Item, Lot, Material, Location, MaterialShape, MaterialGroup, MaterialGroupMember, InspectionStatus

router = APIRouter()

# ========================================
# 材料マッチング用ヘルパー関数
# ========================================

def match_material_for_allocation(
    db: Session,
    material_name: str,
    diameter_mm: float,
    shape: MaterialShape,
    dedicated_part_number: Optional[str] = None,
    length_mm: Optional[int] = None
) -> List[Material]:
    """
    在庫引当用の材料マッチング

    仕様変更により、形状・専用品番は同一性判定に用いません。
    材質名と径が一致する材料を返します。

    Args:
        db: データベースセッション
        material_name: 材質名（例: SUS303, C3604LCD）
        diameter_mm: 直径（mm）
        shape: 形状（round/hexagon/square）
        dedicated_part_number: 専用品番（専用材料の場合）
        length_mm: 長さ（mm）※オプション

    Returns:
        マッチした材料のリスト
    """
    # 材質名を正規化
    normalized_name = material_name.strip().upper()
    normalized_name = normalized_name.replace('Lcd', 'LCD')

    # 基本条件（材質名・径）※形状・専用品番は非使用
    query = db.query(Material).filter(
        Material.name == normalized_name,
        Material.diameter_mm == diameter_mm,
        Material.is_active == True
    )

    return query.all()

def get_available_stock_for_material(
    db: Session,
    material_id: int,
    required_quantity: int,
    dedicated_part_number: Optional[str] = None
) -> int:
    """
    指定材料の利用可能在庫数を取得

    Args:
        db: データベースセッション
        material_id: 材料ID
        required_quantity: 必要数量
        dedicated_part_number: 専用品番（専用材料の場合）

    Returns:
        利用可能な在庫数
    """
    # 材料情報を取得
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        return 0

    # 仕様変更: 専用品番のチェックは行わない

    # 在庫数を合計
    total_stock = db.query(func.sum(Item.current_quantity)).join(
        Lot, Item.lot_id == Lot.id
    ).filter(
        Lot.material_id == material.id,
        Item.is_active == True,
        Item.current_quantity > 0
    ).scalar()

    return total_stock or 0

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
    display_name: Optional[str] = None
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
    inspection_status: Optional[InspectionStatus] = None
    inspected_at: Optional[datetime] = None
    
    @field_serializer('inspection_status')
    def serialize_inspection_status(self, value: Optional[InspectionStatus], _info):
        if value is None:
            return None
        if isinstance(value, InspectionStatus):
            return value.value
        return value

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

class InventorySummaryByName(BaseModel):
    material_name: str
    total_quantity: int
    total_weight_kg: float
    lot_count: int
    location_count: int
    diameter_variations: int
    length_variations: int

# API エンドポイント
@router.get("/", response_model=List[InventoryItem])
async def get_inventory(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    material_id: Optional[int] = Query(None, description="材料IDでフィルタ"),
    location_id: Optional[int] = Query(None, description="置き場IDでフィルタ"),
    lot_number: Optional[str] = Query(None, description="ロット番号で検索"),
    is_active: Optional[bool] = Query(True, description="有効フラグでフィルタ"),
    has_stock: Optional[bool] = Query(True, description="在庫有無でフィルタ（デフォルト: 在庫ありのみ）"),
    include_zero_stock: Optional[bool] = Query(False, description="在庫数=0のアイテムも含める"),
    db: Session = Depends(get_db)
):
    """在庫一覧取得"""
    query = db.query(Item).options(
        joinedload(Item.lot).joinedload(Lot.material),
        joinedload(Item.location)
    )

    if is_active is not None:
        query = query.filter(Item.is_active == is_active)

    # 在庫フィルタリングロジックを更新
    if has_stock is not None and not include_zero_stock:
        if has_stock:
            query = query.filter(Item.current_quantity > 0)
        else:
            query = query.filter(Item.current_quantity == 0)
    elif include_zero_stock:
        # 在庫数=0のアイテムも含める場合、has_stockフィルタを無視
        pass

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
                "received_date": item.lot.received_date,
                "inspection_status": item.lot.inspection_status,
                "inspected_at": item.lot.inspected_at
            },
            "material": {
                "id": material.id,
                "name": material.name,
                "display_name": material.display_name,
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


@router.get("/summary-by-name", response_model=List[InventorySummaryByName])
async def get_inventory_summary_by_name(
    name: Optional[str] = Query(None, description="材料名でフィルタ（完全一致）"),
    include_zero_stock: Optional[bool] = Query(False, description="在庫数=0のアイテムも含める"),
    db: Session = Depends(get_db)
):
    """在庫サマリー取得（材料名のみで集計、長さや寸法は無視）

    Excelの材料名（全文）が一致するものを同一として扱う要件に対応します。
    総重量はロットごとの寸法・長さに基づいて各アイテム重量を合計して算出します。
    """
    base_filter = [Item.is_active == True]
    if not include_zero_stock:
        base_filter.append(Item.current_quantity > 0)

    group_query = db.query(
        Material.name.label("material_name"),
        func.sum(Item.current_quantity).label("total_quantity"),
        func.count(func.distinct(Lot.id)).label("lot_count"),
        func.count(func.distinct(Item.location_id)).label("location_count"),
        func.count(func.distinct(Material.diameter_mm)).label("diameter_variations"),
        func.count(func.distinct(Lot.length_mm)).label("length_variations")
    ).select_from(Item).join(Lot).join(Material).filter(*base_filter)

    if name is not None:
        group_query = group_query.filter(Material.name == name)

    group_query = group_query.group_by(Material.name)
    grouped = group_query.all()

    summaries: List[InventorySummaryByName] = []

    # 総重量はPython側で各アイテムの重量を合算
    for g in grouped:
        items = (
            db.query(Item)
            .options(joinedload(Item.lot).joinedload(Lot.material))
            .join(Lot)
            .join(Material)
            .filter(*base_filter)
            .filter(Material.name == g.material_name)
            .all()
        )

        total_weight_kg = 0.0
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
            total_weight_kg += weight_per_piece_kg * (item.current_quantity or 0)

        summaries.append(InventorySummaryByName(
            material_name=g.material_name,
            total_quantity=int(g.total_quantity or 0),
            total_weight_kg=round(total_weight_kg, 3),
            lot_count=int(g.lot_count or 0),
            location_count=int(g.location_count or 0),
            diameter_variations=int(g.diameter_variations or 0),
            length_variations=int(g.length_variations or 0)
        ))

    return summaries

@router.get("/search/{management_code}", response_model=InventoryItem)
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

    # InventoryItem形式で返却（在庫一覧APIと同じ構造）
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
            "display_name": material.display_name,
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

    return InventoryItem(**item_dict)

@router.get("/search", response_model=List[InventoryItem])
async def search_inventory_items(
    query: str = Query(..., description="検索クエリ（管理コード、材料名、ロット番号等）"),
    include_zero_stock: Optional[bool] = Query(False, description="在庫数=0のアイテムも含める"),
    limit: int = Query(50, ge=1, le=200, description="検索結果の上限数"),
    db: Session = Depends(get_db)
):
    """在庫アイテム検索（管理コード、材料名、ロット番号等で検索）"""
    # 基本クエリ
    query_obj = db.query(Item).options(
        joinedload(Item.lot).joinedload(Lot.material),
        joinedload(Item.location)
    ).filter(Item.is_active == True)

    # 在庫数=0のアイテムを含めるかどうか
    if not include_zero_stock:
        query_obj = query_obj.filter(Item.current_quantity > 0)

    # 検索条件（複数のフィールドで検索）
    search_filter = (
        Item.management_code.ilike(f"%{query}%") |
        Lot.lot_number.ilike(f"%{query}%") |
        Material.name.ilike(f"%{query}%") |
        Material.display_name.ilike(f"%{query}%") |
        Material.part_number.ilike(f"%{query}%")
    )

    query_obj = query_obj.join(Lot).join(Material).filter(search_filter)

    items = query_obj.limit(limit).all()

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
                "received_date": item.lot.received_date,
                "inspection_status": item.lot.inspection_status,
                "inspected_at": item.lot.inspected_at
            },
            "material": {
                "id": material.id,
                "name": material.name,
                "display_name": material.display_name,
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

# ========================================
# グループ集計（ユーザー定義の同等品グループ単位）
# ========================================

class GroupMaterialBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    diameter_mm: float


class InventoryGroupSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    group_id: int
    group_name: str
    is_active: bool
    total_stock: int
    lot_count: int
    materials: List[GroupMaterialBrief]


@router.get("/groups", response_model=List[InventoryGroupSummary])
async def get_inventory_groups(
    include_inactive_groups: Optional[bool] = Query(False, description="無効グループも含める"),
    db: Session = Depends(get_db)
):
    """材料グループ単位の在庫集計（本数合計とロット数）"""

    group_query = db.query(MaterialGroup)
    if not include_inactive_groups:
        group_query = group_query.filter(MaterialGroup.is_active == True)
    groups = group_query.all()

    summaries: List[InventoryGroupSummary] = []

    for group in groups:
        member_materials = (
            db.query(Material)
            .join(MaterialGroupMember, MaterialGroupMember.material_id == Material.id)
            .filter(MaterialGroupMember.group_id == group.id)
            .all()
        )

        if member_materials:
            material_ids = [m.id for m in member_materials]
            total_stock = (
                db.query(func.coalesce(func.sum(Item.current_quantity), 0))
                .join(Lot, Item.lot_id == Lot.id)
                .filter(Item.is_active == True)
                .filter(Item.current_quantity > 0)
                .filter(Lot.material_id.in_(material_ids))
                .scalar()
            )

            lot_count = (
                db.query(func.count(func.distinct(Lot.id)))
                .join(Item, Item.lot_id == Lot.id)
                .filter(Item.is_active == True)
                .filter(Item.current_quantity > 0)
                .filter(Lot.material_id.in_(material_ids))
                .scalar()
            )
        else:
            total_stock = 0
            lot_count = 0

        summaries.append(InventoryGroupSummary(
            group_id=group.id,
            group_name=group.group_name,
            is_active=group.is_active,
            total_stock=int(total_stock or 0),
            lot_count=int(lot_count or 0),
            materials=[GroupMaterialBrief(id=m.id, name=m.name, diameter_mm=m.diameter_mm) for m in member_materials]
        ))

    return summaries
