from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, case
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict, field_serializer
from datetime import datetime

from src.db import get_db
from src.db.models import Item, Lot, Material, Location, MaterialShape, MaterialGroup, MaterialGroupMember, InspectionStatus, InspectionJudgement, PurchaseOrderItem, PurchaseOrder

router = APIRouter()

# ========================================
# 材料マッチング用ヘルパー関数
# ========================================

def match_material_for_allocation(
    db: Session,
    material_name: str,
    diameter_mm: float,
    shape: MaterialShape,
    length_mm: Optional[int] = None
) -> List[Material]:
    """
    在庫引当用の材料マッチング

    材質名と径が一致する材料を返します。

    Args:
        db: データベースセッション
        material_name: 材質名（例: SUS303, C3604LCD）
        diameter_mm: 直径（mm）
        shape: 形状（round/hexagon/square）
        length_mm: 長さ（mm）※オプション

    Returns:
        マッチした材料のリスト
    """
    # 材質名を正規化
    normalized_name = material_name.strip().upper()
    normalized_name = normalized_name.replace('Lcd', 'LCD')

    # 基本条件（材質名・径）
    query = db.query(Material).filter(
        Material.display_name == normalized_name,
        Material.diameter_mm == diameter_mm,
        Material.is_active == True
    )

    return query.all()

def get_available_stock_for_material(
    db: Session,
    material_id: int,
    required_quantity: int
) -> int:
    """
    指定材料の利用可能在庫数を取得

    Args:
        db: データベースセッション
        material_id: 材料ID
        required_quantity: 必要数量

    Returns:
        利用可能な在庫数
    """
    # 材料情報を取得
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        return 0

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
    display_name: str
    shape: MaterialShape
    diameter_mm: float
    current_density: float

class LotInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lot_number: str
    length_mm: int
    initial_quantity: int
    initial_weight_kg: Optional[float] = None
    supplier: Optional[str] = None
    received_date: Optional[datetime] = None
    inspection_status: Optional[InspectionStatus] = None
    inspected_at: Optional[datetime] = None
    purchase_month: Optional[str] = None
    notes: Optional[str] = None
    purchase_order_item_id: Optional[int] = None
    order_number: Optional[str] = None
    
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
    lot_id: int
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

        # 単重決定（初期入力重量があれば優先）
        if item.lot.initial_weight_kg and item.lot.initial_quantity and item.lot.initial_quantity > 0:
            weight_per_piece_kg = item.lot.initial_weight_kg / item.lot.initial_quantity
        else:
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
        # 発注番号の取得（存在する場合）
        po_item = item.lot.purchase_order_item if hasattr(item.lot, "purchase_order_item") else None
        order_number = None
        if po_item and getattr(po_item, "purchase_order", None):
            order_number = po_item.purchase_order.order_number

        item_dict = {
            "id": item.id,
            "lot_id": item.lot_id,
            "current_quantity": item.current_quantity,
            "is_active": item.is_active,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "lot": {
                "id": item.lot.id,
                "lot_number": item.lot.lot_number,
                "length_mm": item.lot.length_mm,
                "initial_quantity": item.lot.initial_quantity,
                "initial_weight_kg": item.lot.initial_weight_kg,
                "supplier": item.lot.supplier,
                "received_date": item.lot.received_date,
                "inspection_status": item.lot.inspection_status,
                "inspected_at": item.lot.inspected_at,
                "purchase_month": item.lot.purchase_month,
                "notes": item.lot.notes,
                "purchase_order_item_id": item.lot.purchase_order_item_id,
                "order_number": order_number
            },
            "material": {
                "id": material.id,
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
        Material.display_name.label("material_name"),
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
        Material.display_name,
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
    name: Optional[str] = Query(None, description="材料表示名（フルネーム）でフィルタ（完全一致）"),
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
        Material.display_name.label("material_name"),
        func.sum(Item.current_quantity).label("total_quantity"),
        func.count(func.distinct(Lot.id)).label("lot_count"),
        func.count(func.distinct(Item.location_id)).label("location_count"),
        func.count(func.distinct(Material.diameter_mm)).label("diameter_variations"),
        func.count(func.distinct(Lot.length_mm)).label("length_variations")
    ).select_from(Item).join(Lot).join(Material).filter(*base_filter)

    if name is not None:
        group_query = group_query.filter(Material.display_name == name)

    group_query = group_query.group_by(Material.display_name)
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
            .filter(Material.display_name == g.material_name)
            .all()
        )

        total_weight_kg = 0.0
        for item in items:
            material = item.lot.material
            # 重量計算（初期入力重量があれば優先して単重を決定）
            if lot.initial_weight_kg and lot.initial_quantity and lot.initial_quantity > 0:
                weight_per_piece_kg = lot.initial_weight_kg / lot.initial_quantity
                # 体積計算の代わりに入力値ベースの単重を利用
            else:
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

@router.get("/search/{lot_number}", response_model=InventoryItem)
async def search_by_lot_number(lot_number: str, db: Session = Depends(get_db)):
    """LOT番号による検索"""
    item = db.query(Item).join(Item.lot).options(
        joinedload(Item.lot).joinedload(Lot.material),
        joinedload(Item.location)
    ).filter(Lot.lot_number == lot_number).first()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="指定されたLOT番号のアイテムが見つかりません"
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
        "lot_id": item.lot_id,
        "current_quantity": item.current_quantity,
        "is_active": item.is_active,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "lot": {
            "id": item.lot.id,
            "lot_number": item.lot.lot_number,
            "length_mm": item.lot.length_mm,
            "initial_quantity": item.lot.initial_quantity,
            "initial_weight_kg": item.lot.initial_weight_kg,
            "supplier": item.lot.supplier,
            "received_date": item.lot.received_date,
            "inspection_status": item.lot.inspection_status,
            "inspected_at": item.lot.inspected_at,
            "purchase_month": item.lot.purchase_month,
            "notes": item.lot.notes,
            "purchase_order_item_id": item.lot.purchase_order_item_id,
            "order_number": None
        },
        "material": {
            "id": material.id,
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
    # display_name と lot_number のみに限定
    search_filter = (
        Lot.lot_number.ilike(f"%{query}%") |
        Material.display_name.ilike(f"%{query}%")
    )

    query_obj = query_obj.join(Lot).join(Material).filter(search_filter)

    items = query_obj.limit(limit).all()

    # 重量計算を追加
    result = []
    for item in items:
        material = item.lot.material

        # 単重決定（初期入力重量があれば優先）
        if item.lot.initial_weight_kg and item.lot.initial_quantity and item.lot.initial_quantity > 0:
            weight_per_piece_kg = item.lot.initial_weight_kg / item.lot.initial_quantity
        else:
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
        # 発注番号の取得（存在する場合）
        po_item = item.lot.purchase_order_item if hasattr(item.lot, "purchase_order_item") else None
        order_number = None
        if po_item and getattr(po_item, "purchase_order", None):
            order_number = po_item.purchase_order.order_number

        item_dict = {
            "id": item.id,
            "lot_id": item.lot_id,
            "current_quantity": item.current_quantity,
            "is_active": item.is_active,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "lot": {
                "id": item.lot.id,
                "lot_number": item.lot.lot_number,
                "length_mm": item.lot.length_mm,
                "initial_quantity": item.lot.initial_quantity,
                "initial_weight_kg": item.lot.initial_weight_kg,
                "supplier": item.lot.supplier,
                "received_date": item.lot.received_date,
                "inspection_status": item.lot.inspection_status,
                "inspected_at": item.lot.inspected_at,
                "notes": item.lot.notes,
                "purchase_order_item_id": item.lot.purchase_order_item_id,
                "order_number": order_number,
                "purchase_month": item.lot.purchase_month
            },
            "material": {
                "id": material.id,
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
            "lot_number": item.lot.lot_number,
            "material_name": material.display_name,
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
            materials=[GroupMaterialBrief(id=m.id, name=m.display_name, diameter_mm=m.diameter_mm) for m in member_materials]
        ))

    return summaries


# ========================================
# 検品用エンドポイント
# ========================================

class InspectionLotResponse(BaseModel):
    """検品用ロット情報レスポンス"""
    model_config = ConfigDict(from_attributes=True)

    lot_id: int
    lot_number: str
    material_name: str
    shape: MaterialShape
    diameter_mm: float
    length_mm: int
    total_quantity: int
    total_weight_kg: float
    inspection_status: InspectionStatus
    inspected_at: Optional[datetime] = None
    received_date: datetime
    order_number: Optional[str] = None

    @field_serializer('inspection_status')
    def serialize_inspection_status(self, value: InspectionStatus, _info):
        return value.value if value else None

    @field_serializer('shape')
    def serialize_shape(self, value: MaterialShape, _info):
        return value.value if value else None


@router.get("/lots/for-inspection/", response_model=List[InspectionLotResponse])
def get_lots_for_inspection(
    include_completed: bool = Query(False, description="検品完了済みも含める"),
    db: Session = Depends(get_db)
):
    """
    検品対象のロット一覧を取得

    - デフォルトでは検品待ち（PENDING）のロットのみ返す
    - include_completed=trueで全ロットを返す
    """
    # ロットごとの集計クエリ
    query = db.query(
        Lot.id.label("lot_id"),
        Lot.lot_number,
        Lot.length_mm,
        Lot.inspection_status,
        Lot.inspected_at,
        Lot.received_date,
        Material.display_name.label("material_name"),
        Material.shape,
        Material.diameter_mm,
        func.sum(Item.current_quantity).label("total_quantity"),
        Material.current_density.label("current_density"),
        PurchaseOrder.order_number.label("order_number"),
        Lot.initial_weight_kg
    ).select_from(Lot).join(
        Item, Item.lot_id == Lot.id
    ).join(
        Material, Lot.material_id == Material.id
    ).outerjoin(
        PurchaseOrderItem, PurchaseOrderItem.id == Lot.purchase_order_item_id
    ).outerjoin(
        PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.purchase_order_id
    ).filter(
        Item.is_active == True
    ).group_by(
        Lot.id,
        Lot.lot_number,
        Lot.length_mm,
        Lot.inspection_status,
        Lot.inspected_at,
        Lot.received_date,
        Material.display_name,
        Material.shape,
        Material.diameter_mm,
        Lot.initial_weight_kg
    )

    # 検品完了済みを含めるかどうか
    if not include_completed:
        query = query.filter(Lot.inspection_status == InspectionStatus.PENDING)

    # 受領日降順でソート
    query = query.order_by(Lot.received_date.desc())

    results = query.all()

    inspected_list: List[InspectionLotResponse] = []
    for row in results:
        # 重量計算（材質密度 × 体積）
        if row.shape == MaterialShape.ROUND:
            radius_cm = (row.diameter_mm / 2) / 10
            length_cm = row.length_mm / 10
            volume_cm3 = 3.14159 * (radius_cm ** 2) * length_cm
        elif row.shape == MaterialShape.HEXAGON:
            side_cm = (row.diameter_mm / 2) / 10
            length_cm = row.length_mm / 10
            volume_cm3 = (3 * (3 ** 0.5) / 2) * (side_cm ** 2) * length_cm
        elif row.shape == MaterialShape.SQUARE:
            side_cm = row.diameter_mm / 10
            length_cm = row.length_mm / 10
            volume_cm3 = (side_cm ** 2) * length_cm
        else:
            volume_cm3 = 0

        density = float(row.current_density or 0.0)
        qty = int(row.total_quantity or 0)
        weight_per_piece_kg = (volume_cm3 * density) / 1000
        total_weight_kg = row.initial_weight_kg if row.initial_weight_kg is not None else (weight_per_piece_kg * qty)

        inspected_list.append(InspectionLotResponse(
            lot_id=row.lot_id,
            lot_number=row.lot_number,
            material_name=row.material_name,
            shape=row.shape,
            diameter_mm=row.diameter_mm,
            length_mm=row.length_mm,
            total_quantity=row.total_quantity or 0,
            total_weight_kg=round(total_weight_kg, 3),
            inspection_status=row.inspection_status,
            inspected_at=row.inspected_at,
            received_date=row.received_date,
            order_number=None
        ))

    return inspected_list


class UpdateInspectionRequest(BaseModel):
    """検品情報更新リクエスト"""
    inspection_status: InspectionStatus
    inspected_at: datetime
    bending_ok: Optional[bool] = None
    inspected_by_name: Optional[str] = None
    inspection_notes: Optional[str] = None
    scratch_ok: Optional[bool] = None
    dirt_ok: Optional[bool] = None
    inspection_judgement: Optional[InspectionJudgement] = None

    # 寸法1/寸法2 最大・最小（左端/中央/右端）
    dim1_left_max: Optional[float] = None
    dim1_left_min: Optional[float] = None
    dim1_center_max: Optional[float] = None
    dim1_center_min: Optional[float] = None
    dim1_right_max: Optional[float] = None
    dim1_right_min: Optional[float] = None
    dim2_left_max: Optional[float] = None
    dim2_left_min: Optional[float] = None
    dim2_center_max: Optional[float] = None
    dim2_center_min: Optional[float] = None
    dim2_right_max: Optional[float] = None
    dim2_right_min: Optional[float] = None


class InspectionDetailResponse(BaseModel):
    """検品詳細（再編集用）レスポンス"""
    model_config = ConfigDict(from_attributes=True)

    lot_id: int
    lot_number: str
    inspection_status: Optional[InspectionStatus] = None
    inspected_at: Optional[datetime] = None
    bending_ok: Optional[bool] = None
    scratch_ok: Optional[bool] = None
    dirt_ok: Optional[bool] = None
    inspected_by_name: Optional[str] = None
    inspection_notes: Optional[str] = None
    inspection_judgement: Optional[InspectionJudgement] = None

    # 寸法1/寸法2 最大・最小（左端/中央/右端）
    dim1_left_max: Optional[float] = None
    dim1_left_min: Optional[float] = None
    dim1_center_max: Optional[float] = None
    dim1_center_min: Optional[float] = None
    dim1_right_max: Optional[float] = None
    dim1_right_min: Optional[float] = None
    dim2_left_max: Optional[float] = None
    dim2_left_min: Optional[float] = None
    dim2_center_max: Optional[float] = None
    dim2_center_min: Optional[float] = None
    dim2_right_max: Optional[float] = None
    dim2_right_min: Optional[float] = None

    @field_serializer('inspection_status')
    def serialize_inspection_status(self, value: Optional[InspectionStatus], _info):
        return value.value if value else None

    @field_serializer('inspection_judgement')
    def serialize_inspection_judgement(self, value: Optional[InspectionJudgement], _info):
        return value.value if value else None

@router.put("/lots/{lot_id}/inspection/")
def update_lot_inspection(
    lot_id: int,
    request: UpdateInspectionRequest,
    db: Session = Depends(get_db)
):
    """
    ロットの検品情報を更新
    """
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(status_code=404, detail="ロットが見つかりません")

    # 検品情報を更新
    lot.inspection_status = request.inspection_status
    lot.inspected_at = request.inspected_at
    lot.bending_ok = request.bending_ok
    lot.scratch_ok = request.scratch_ok
    lot.dirt_ok = request.dirt_ok
    lot.inspected_by_name = request.inspected_by_name
    lot.inspection_notes = request.inspection_notes
    lot.inspection_judgement = request.inspection_judgement

    # 寸法の保存
    lot.dim1_left_max = request.dim1_left_max
    lot.dim1_left_min = request.dim1_left_min
    lot.dim1_center_max = request.dim1_center_max
    lot.dim1_center_min = request.dim1_center_min
    lot.dim1_right_max = request.dim1_right_max
    lot.dim1_right_min = request.dim1_right_min
    lot.dim2_left_max = request.dim2_left_max
    lot.dim2_left_min = request.dim2_left_min
    lot.dim2_center_max = request.dim2_center_max
    lot.dim2_center_min = request.dim2_center_min
    lot.dim2_right_max = request.dim2_right_max
    lot.dim2_right_min = request.dim2_right_min

    db.commit()
    db.refresh(lot)

    return {
        "message": "検品情報を更新しました",
        "lot_id": lot.id,
        "lot_number": lot.lot_number,
        "inspection_status": lot.inspection_status.value
    }


@router.get("/lots/{lot_id}/inspection/", response_model=InspectionDetailResponse)
def get_lot_inspection_detail(
    lot_id: int,
    db: Session = Depends(get_db)
):
    """再編集用に、ロットの検品詳細を取得"""
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(status_code=404, detail="ロットが見つかりません")

    return InspectionDetailResponse(
        lot_id=lot.id,
        lot_number=lot.lot_number,
        inspection_status=lot.inspection_status,
        inspected_at=lot.inspected_at,
        bending_ok=lot.bending_ok,
        scratch_ok=lot.scratch_ok,
        dirt_ok=lot.dirt_ok,
        inspected_by_name=lot.inspected_by_name,
        inspection_notes=lot.inspection_notes,
        inspection_judgement=lot.inspection_judgement,
        dim1_left_max=lot.dim1_left_max,
        dim1_left_min=lot.dim1_left_min,
        dim1_center_max=lot.dim1_center_max,
        dim1_center_min=lot.dim1_center_min,
        dim1_right_max=lot.dim1_right_max,
        dim1_right_min=lot.dim1_right_min,
        dim2_left_max=lot.dim2_left_max,
        dim2_left_min=lot.dim2_left_min,
        dim2_center_max=lot.dim2_center_max,
        dim2_center_min=lot.dim2_center_min,
        dim2_right_max=lot.dim2_right_max,
        dim2_right_min=lot.dim2_right_min,
    )

# ========================================
# 検品済みロット一覧（検索フィルタ付き）
# ========================================

class InspectedLotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    lot_id: int
    lot_number: str
    material_name: str
    shape: MaterialShape
    diameter_mm: float
    length_mm: int
    total_quantity: int
    total_weight_kg: float
    inspection_status: InspectionStatus
    inspected_at: Optional[datetime] = None
    received_date: datetime
    order_number: Optional[str] = None

    @field_serializer('inspection_status')
    def serialize_inspection_status(self, value: InspectionStatus, _info):
        return value.value if value else None

    @field_serializer('shape')
    def serialize_shape(self, value: MaterialShape, _info):
        return value.value if value else None


@router.get("/lots/inspected/", response_model=List[InspectedLotResponse])
def get_inspected_lots(
    material_spec: Optional[str] = Query(None, description="材料仕様（display_nameに部分一致）"),
    lot_number: Optional[str] = Query(None, description="ロット番号に部分一致"),
    order_number: Optional[str] = Query(None, description="発注番号に部分一致"),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """検品済みロット一覧（検索フィルタ付き）"""

    # 基本集計クエリ（ロット単位）
    query = db.query(
        Lot.id.label("lot_id"),
        Lot.lot_number,
        Lot.length_mm,
        Lot.inspection_status,
        Lot.inspected_at,
        Lot.received_date,
        Material.display_name.label("material_name"),
        Material.shape,
        Material.diameter_mm,
        func.sum(Item.current_quantity).label("total_quantity"),
        Material.current_density.label("current_density"),
        PurchaseOrder.order_number.label("order_number"),
        Lot.initial_weight_kg
    ).select_from(Lot).join(
        Item, Item.lot_id == Lot.id
    ).join(
        Material, Lot.material_id == Material.id
    ).outerjoin(
        PurchaseOrderItem, PurchaseOrderItem.id == Lot.purchase_order_item_id
    ).outerjoin(
        PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.purchase_order_id
    ).filter(
        Item.is_active == True,
        Lot.inspection_status != InspectionStatus.PENDING
    ).group_by(
        Lot.id,
        Lot.lot_number,
        Lot.length_mm,
        Lot.inspection_status,
        Lot.inspected_at,
        Lot.received_date,
        Material.display_name,
        Material.shape,
        Material.diameter_mm,
        PurchaseOrder.order_number,
        Lot.initial_weight_kg
    ).order_by(
        case((Lot.inspected_at.is_(None), 1), else_=0),
        Lot.inspected_at.desc()
    )

    # フィルタ
    if material_spec:
        query = query.filter(Material.display_name.ilike(f"%{material_spec}%"))
    if lot_number:
        query = query.filter(Lot.lot_number.ilike(f"%{lot_number}%"))
    if order_number:
        query = query.filter(PurchaseOrder.order_number.ilike(f"%{order_number}%"))

    rows = query.offset(skip).limit(limit).all()

    responses: List[InspectedLotResponse] = []
    for row in rows:
        # 重量計算（材質密度 × 体積）
        if row.shape == MaterialShape.ROUND:
            radius_cm = (row.diameter_mm / 2) / 10
            length_cm = row.length_mm / 10
            volume_cm3 = 3.14159 * (radius_cm ** 2) * length_cm
        elif row.shape == MaterialShape.HEXAGON:
            side_cm = (row.diameter_mm / 2) / 10
            length_cm = row.length_mm / 10
            volume_cm3 = (3 * (3 ** 0.5) / 2) * (side_cm ** 2) * length_cm
        elif row.shape == MaterialShape.SQUARE:
            side_cm = row.diameter_mm / 10
            length_cm = row.length_mm / 10
            volume_cm3 = (side_cm ** 2) * length_cm
        else:
            volume_cm3 = 0

        density = float(row.current_density or 0.0)
        qty = int(row.total_quantity or 0)
        weight_per_piece_kg = (volume_cm3 * density) / 1000
        total_weight_kg = row.initial_weight_kg if row.initial_weight_kg is not None else (weight_per_piece_kg * qty)

        responses.append(InspectedLotResponse(
            lot_id=row.lot_id,
            lot_number=row.lot_number,
            material_name=row.material_name,
            shape=row.shape,
            diameter_mm=row.diameter_mm,
            length_mm=row.length_mm,
            total_quantity=row.total_quantity or 0,
            total_weight_kg=round(total_weight_kg, 3),
            inspection_status=row.inspection_status,
            inspected_at=row.inspected_at,
            received_date=row.received_date,
            order_number=row.order_number
        ))

    return responses
