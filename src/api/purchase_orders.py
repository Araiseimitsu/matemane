from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from src.db.models import MaterialAlias
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime, date
import re

from src.db import get_db
from src.db.models import (
    PurchaseOrder, PurchaseOrderItem, PurchaseOrderStatus, PurchaseOrderItemStatus,
    Material, MaterialShape, Lot, Item, Location, OrderType, User,
    MaterialGroup, MaterialGroupMember, InspectionStatus, AuditLog, Movement
)
from src.utils.auth import get_password_hash

router = APIRouter()

def ensure_default_user(db: Session) -> int:
    """デフォルトユーザーが存在しない場合は作成し、IDを返す"""
    # デフォルトユーザーをチェック
    default_user = db.query(User).filter(User.username == "system").first()

    if not default_user:
        # デフォルトユーザーを作成
        default_user = User(
            username="system",
            email="system@example.com",
            hashed_password=get_password_hash("system123"),
            full_name="システムユーザー"
        )
        db.add(default_user)
        db.commit()
        db.refresh(default_user)

    return default_user.id

# ユーティリティ関数
def calculate_weight_from_quantity(quantity: int, shape: MaterialShape, diameter_mm: float, length_mm: int, density: float) -> float:
    """本数から重量を計算"""
    if shape == MaterialShape.ROUND:
        # 丸棒: π × (直径/2)² × 長さ
        radius_cm = diameter_mm / 20  # mm → cm, /2 for radius
        volume_cm3 = 3.14159 * (radius_cm ** 2) * (length_mm / 10)
    elif shape == MaterialShape.HEXAGON:
        # 六角棒: (3√3/2) × (一辺)² × 長さ
        # 仕様: 径(diameter_mm)は「対辺距離」。一辺 = 対辺距離 / 2
        side_cm = (diameter_mm / 2) / 10  # mm → cm
        volume_cm3 = (3 * (3 ** 0.5) / 2) * (side_cm ** 2) * (length_mm / 10)
    elif shape == MaterialShape.SQUARE:
        # 角棒: 一辺² × 長さ（径は一辺の長さ）
        side_cm = diameter_mm / 10  # mm → cm
        volume_cm3 = (side_cm ** 2) * (length_mm / 10)
    else:
        raise ValueError(f"未対応の形状: {shape}")

    weight_kg = volume_cm3 * density / 1000  # g → kg
    return weight_kg * quantity

def calculate_quantity_from_weight(weight_kg: float, shape: MaterialShape, diameter_mm: float, length_mm: int, density: float) -> int:
    """重量から本数を計算（切り捨てで整数）"""
    single_piece_weight = calculate_weight_from_quantity(1, shape, diameter_mm, length_mm, density)
    if single_piece_weight <= 0:
        return 0
    quantity = weight_kg / single_piece_weight
    from math import floor
    return max(0, floor(quantity))

# Pydantic スキーマ（Excel取込専用 - 手動作成は廃止）

class PurchaseOrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_name: str
    order_type: OrderType
    ordered_quantity: Optional[int]
    received_quantity: int
    ordered_weight_kg: Optional[float]
    received_weight_kg: Optional[float]
    unit_price: Optional[float]
    amount: Optional[float]
    status: PurchaseOrderItemStatus
    purchase_order_id: int
    created_at: datetime
    updated_at: datetime

    # 検品ステータス（フロントエンドのN+1問題解消用）
    inspection_status: Optional[str] = None

class PurchaseOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_number: str
    supplier: str
    order_date: datetime
    expected_delivery_date: Optional[datetime]
    status: PurchaseOrderStatus
    notes: Optional[str]
    created_by: int
    created_at: datetime
    updated_at: datetime
    items: List[PurchaseOrderItemResponse]

class PaginatedPurchaseOrderResponse(BaseModel):
    """ページネーション対応の発注一覧レスポンス"""
    items: List[PurchaseOrderResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

class PurchaseOrderUpdate(BaseModel):
    """発注ヘッダー更新用スキーマ"""
    supplier: Optional[str] = Field(None, max_length=200, description="仕入先")
    expected_delivery_date: Optional[datetime] = Field(None, description="納期")
    notes: Optional[str] = Field(None, description="備考")

class PurchaseOrderItemUpdate(BaseModel):
    """発注アイテム更新用スキーマ"""
    ordered_quantity: Optional[int] = Field(None, gt=0, description="発注数量")
    ordered_weight_kg: Optional[float] = Field(None, gt=0, description="発注重量（kg）")
    unit_price: Optional[float] = Field(None, ge=0, description="単価")
    amount: Optional[float] = Field(None, ge=0, description="金額")

class ReceivingConfirmation(BaseModel):
    lot_number: str = Field(..., max_length=100, description="ロット番号")
    # 計算用パラメータ（必須）
    diameter_mm: float = Field(..., gt=0, description="直径または一辺の長さ（mm・計算用）")
    shape: MaterialShape = Field(..., description="断面形状（計算用）")
    density: float = Field(..., gt=0, description="比重（g/cm³・計算用）")
    # 入庫情報
    length_mm: int = Field(..., gt=0, description="長さ（mm）")
    received_date: datetime = Field(..., description="入荷日")
    received_quantity: Optional[int] = Field(None, gt=0, description="入庫数量（本数指定時）")
    received_weight_kg: Optional[float] = Field(None, gt=0, description="入庫重量（重量指定時、kg）")
    unit_price: Optional[float] = Field(None, ge=0, description="単価")
    amount: Optional[float] = Field(None, ge=0, description="金額")
    purchase_month: Optional[str] = Field(None, max_length=4, description="購入月（YYMM形式）")
    # 置き場
    location_id: Optional[int] = Field(None, description="置き場ID")
    location_ids: Optional[List[int]] = Field(None, description="置き場IDの配列（複数指定時）")
    notes: Optional[str] = Field(None, description="備考")
    group_id: Optional[int] = Field(None, description="材料グループID（任意）")

    def validate_receiving_data(self):
        """入庫データのバリデーション"""
        # 数量・重量のいずれかは必須。両方の同時入力も許可
        if self.received_quantity is None and self.received_weight_kg is None:
            raise ValueError("数量または重量のいずれかを入力してください")
        return

class MaterialSuggestionResponse(BaseModel):
    material_id: int
    display_name: str
    shape: MaterialShape
    diameter_mm: float
    density: float

# API エンドポイント
@router.get("/", response_model=PaginatedPurchaseOrderResponse)
async def get_purchase_orders(
    page: int = 1,
    page_size: int = 50,
    status: Optional[PurchaseOrderStatus] = None,
    supplier: Optional[str] = None,
    purpose: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """発注一覧取得（ページネーション対応）"""
    # ページネーションパラメータのバリデーション
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 50

    # クエリ構築
    query = db.query(PurchaseOrder).options(joinedload(PurchaseOrder.items))

    if status is not None:
        query = query.filter(PurchaseOrder.status == status)

    if supplier is not None:
        query = query.filter(PurchaseOrder.supplier.contains(supplier))

    if purpose is not None:
        query = query.filter(PurchaseOrder.purpose.contains(purpose))

    # 総件数取得
    total = query.count()

    # ページネーション計算
    skip = (page - 1) * page_size
    total_pages = (total + page_size - 1) // page_size  # 切り上げ

    # データ取得
    orders = query.order_by(PurchaseOrder.created_at.desc()).offset(skip).limit(page_size).all()

    return {
        "items": orders,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }

@router.get("/{order_id}", response_model=PurchaseOrderResponse)
async def get_purchase_order(order_id: int, db: Session = Depends(get_db)):
    """発注詳細取得"""
    order = db.query(PurchaseOrder).options(joinedload(PurchaseOrder.items)).filter(
        PurchaseOrder.id == order_id
    ).first()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="発注が見つかりません"
        )
    return order

# 手動発注作成・編集・削除APIは廃止（Excel取込のみ使用）

@router.get("/pending/items/", response_model=List[PurchaseOrderItemResponse])
async def get_pending_items(db: Session = Depends(get_db)):
    """入庫待ちアイテム一覧取得"""
    items = db.query(PurchaseOrderItem).options(
        joinedload(PurchaseOrderItem.purchase_order)
    ).filter(
        PurchaseOrderItem.status == PurchaseOrderItemStatus.PENDING
    ).all()

    return items

@router.get("/pending-or-inspection/items/", response_model=List[PurchaseOrderItemResponse])
async def get_pending_or_inspection_items(
    include_inspected: bool = False,
    db: Session = Depends(get_db)
):
    """入庫待ち、または検品未完了アイテム一覧取得（オプションで検品完了も含める）

    - 発注アイテムが未入庫（PENDING）のもの
    - 入庫済み（RECEIVED）だが、紐づく最新ロットの検品が未完了（PENDING/FAILED）のもの
    - include_inspected=true の場合、検品完了（PASSED）のものも含める
    """
    from sqlalchemy.sql import exists
    from src.db.models import Lot

    lot_has_unpassed_inspection = exists().where(
        (Lot.purchase_order_item_id == PurchaseOrderItem.id) &
        (Lot.inspection_status != InspectionStatus.PASSED)
    )

    # 検品完了も含める条件
    lot_has_passed_inspection = exists().where(
        (Lot.purchase_order_item_id == PurchaseOrderItem.id) &
        (Lot.inspection_status == InspectionStatus.PASSED)
    )

    conditions = [
        (PurchaseOrderItem.status == PurchaseOrderItemStatus.PENDING),
        lot_has_unpassed_inspection
    ]

    if include_inspected:
        conditions.append(lot_has_passed_inspection)

    items = db.query(PurchaseOrderItem).options(
        joinedload(PurchaseOrderItem.purchase_order),
        joinedload(PurchaseOrderItem.lots)
    ).filter(
        or_(*conditions)
    ).all()

    # 検品ステータスを各アイテムに付与（N+1問題解消）
    result = []
    for item in items:
        item_dict = PurchaseOrderItemResponse.model_validate(item).model_dump()

        # 最新ロットの検品ステータスを取得
        if item.lots:
            latest_lot = max(item.lots, key=lambda l: (l.received_date or datetime.min, l.id))
            item_dict['inspection_status'] = latest_lot.inspection_status.value if latest_lot.inspection_status else 'PENDING'
        else:
            item_dict['inspection_status'] = None

        result.append(item_dict)

    return result

@router.get("/items/{item_id}/suggest-material", response_model=Optional[MaterialSuggestionResponse])
async def suggest_material_for_item(item_id: int, db: Session = Depends(get_db)):
    """発注アイテムの全文（item_name）に一致する材料マスター候補を返す"""
    item = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="発注アイテムが見つかりません")

    # 1) display_name = item_name
    material = db.query(Material).filter(
        Material.display_name == item.item_name,
        Material.is_active == True
    ).first()

    # 2) alias = item_name
    if not material:
        alias = db.query(MaterialAlias).filter(MaterialAlias.alias_name == item.item_name).first()
        if alias:
            material = db.query(Material).filter(Material.id == alias.material_id, Material.is_active == True).first()

    if not material:
        return None

    return MaterialSuggestionResponse(
        material_id=material.id,
        display_name=material.display_name,
        shape=material.shape,
        diameter_mm=material.diameter_mm,
        density=material.current_density,
    )

# ==== TEMP: 外部Excel取込テストエンドポイント（後で削除しやすいよう最小限） ====
@router.post("/external-import-test", response_model=dict)
async def external_import_test(dry_run: bool = True, excel: Optional[str] = None, sheet: Optional[str] = None):
    """Excelからの発注作成処理をDRY-RUN/本実行を切替で起動（テスト用・一時的）

    クエリパラメータ:
      - dry_run: true なら検証のみ、false ならDB書き込みを実行
      - excel: 対象Excelファイル（省略時は デフォルト）
      - sheet: シート名（省略時は デフォルト）
    """
    try:
        # import を関数内に限定し、削除しやすい形にする
        from src.scripts.excel_po_import import import_excel_to_purchase_orders
        excel_path = excel or "材料管理.xlsx"
        sheet_name = sheet or "材料管理表"
        result = await run_in_threadpool(import_excel_to_purchase_orders, excel_path, sheet_name, dry_run)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/items/{item_id}/receive/", response_model=dict)
async def receive_item(
    item_id: int,
    receiving: ReceivingConfirmation,
    db: Session = Depends(get_db)
):
    """入庫確認（材料情報入力対応）- 複数ロット対応"""
    try:
        # 発注アイテム取得
        item = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == item_id).first()
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="発注アイテムが見つかりません"
            )

        # 複数ロット対応：既に入庫済みでも追加ロットを作成可能
        # ステータスチェックを削除

        # 入庫データのバリデーション
        try:
            receiving.validate_receiving_data()
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

        # 材料候補の特定（発注品名の全文 item_name で一致を確認）
        # 1) 発注アイテムの全文（item_name）で材料マスターに一致するか
        existing_material = db.query(Material).filter(
            Material.display_name == item.item_name,
            Material.is_active == True
        ).first()

        # 2) 別名でも一致させる（表示揺れ対応）
        if not existing_material:
            alias = db.query(MaterialAlias).filter(
                MaterialAlias.alias_name == item.item_name
            ).first()
            if alias:
                existing_material = db.query(Material).filter(
                    Material.id == alias.material_id,
                    Material.is_active == True
                ).first()

        # 計算用属性（既存があればマスター値を優先、新規なら入力値を使用）
        effective_shape = existing_material.shape if existing_material else receiving.shape
        effective_diameter = existing_material.diameter_mm if existing_material else receiving.diameter_mm
        effective_density = existing_material.current_density if existing_material else receiving.density

        # ユーザー入力をそのまま採用（換算なし）
        final_received_quantity = receiving.received_quantity or 0
        final_received_weight = receiving.received_weight_kg or 0.0

        if existing_material:
            material_id = existing_material.id
        else:
            # 新規材料として登録（display_name = 発注品名の全文、計算用パラメータも保存）
            new_material = Material(
                display_name=item.item_name,  # 発注品名の全文（表示用）
                shape=receiving.shape,        # 計算用
                diameter_mm=receiving.diameter_mm,  # 計算用
                current_density=receiving.density,  # 計算用
            )
            db.add(new_material)
            db.flush()
            material_id = new_material.id

        # 材料グループ指定がある場合は所属を登録（重複はスキップ）
        if receiving.group_id is not None:
            group = db.query(MaterialGroup).filter(
                MaterialGroup.id == receiving.group_id,
                MaterialGroup.is_active == True
            ).first()
            if not group:
                raise HTTPException(status_code=404, detail="指定された材料グループが見つかりません")
            exists_member = db.query(MaterialGroupMember).filter(
                MaterialGroupMember.group_id == receiving.group_id,
                MaterialGroupMember.material_id == material_id
            ).first()
            if not exists_member:
                db.add(MaterialGroupMember(group_id=receiving.group_id, material_id=material_id))
                db.flush()

        # 置き場の存在チェック（不正なIDによる外部キー制約違反を防ぐ）
        invalid_locations: List[int] = []
        if receiving.location_ids and len(receiving.location_ids) > 0:
            for loc_id in receiving.location_ids:
                loc = db.query(Location).filter(Location.id == loc_id, Location.is_active == True).first()
                if not loc:
                    invalid_locations.append(loc_id)
        elif receiving.location_id is not None:
            loc = db.query(Location).filter(Location.id == receiving.location_id, Location.is_active == True).first()
            if not loc:
                invalid_locations.append(receiving.location_id)

        if invalid_locations:
            raise HTTPException(status_code=404, detail=f"指定された置き場が見つかりません: {', '.join(str(x) for x in invalid_locations)}")

        # ロット作成
        lot = Lot(
            lot_number=receiving.lot_number,
            material_id=material_id,
            purchase_order_item_id=item.id,
            length_mm=receiving.length_mm,
            initial_quantity=final_received_quantity,
            initial_weight_kg=final_received_weight,
            supplier=item.purchase_order.supplier,
            received_date=receiving.received_date,
            received_unit_price=receiving.unit_price,
            received_amount=receiving.amount,
            purchase_month=receiving.purchase_month,
            notes=receiving.notes
        )
        db.add(lot)
        db.flush()

        # 置き場の決定（複数指定でも数量は分けない）
        target_locations: List[Optional[int]] = []
        if receiving.location_ids and len(receiving.location_ids) > 0:
            target_locations = list(receiving.location_ids)
        elif receiving.location_id is not None:
            target_locations = [receiving.location_id]
        else:
            target_locations = [None]

        # 在庫アイテムは検品完了時に登録するため、ここでは作成しない
        # 検品完了まで在庫管理には表示されない
        created_item_ids: List[int] = []
        primary_lot_number: Optional[str] = None

        # 置き場情報をロットの備考に保存（検品完了時に在庫登録で使用）
        location_info = ", ".join(str(loc) for loc in target_locations if loc is not None)
        if location_info:
            if lot.notes:
                lot.notes = f"{lot.notes}\n登録予定置き場: {location_info}"
            else:
                lot.notes = f"登録予定置き場: {location_info}"
        
        primary_lot_number = lot.lot_number

        # 発注アイテムの状態更新（複数ロット対応：累積計算）
        item.received_quantity = (item.received_quantity or 0) + final_received_quantity
        item.received_weight_kg = round((item.received_weight_kg or 0) + final_received_weight, 3)
        
        # 単価・金額を更新（入力された場合のみ）
        if receiving.unit_price is not None:
            item.unit_price = receiving.unit_price
        if receiving.amount is not None:
            item.amount = receiving.amount
        
        if item.status == PurchaseOrderItemStatus.PENDING:
            item.status = PurchaseOrderItemStatus.RECEIVED

        # 発注全体の状態更新
        order = item.purchase_order
        all_items_received = all(
            i.status == PurchaseOrderItemStatus.RECEIVED
            for i in order.items
        )

        if all_items_received:
            order.status = PurchaseOrderStatus.COMPLETED
        else:
            order.status = PurchaseOrderStatus.PARTIAL

        db.commit()

        # 検品完了時に在庫登録するため、item_idはNoneを返す
        return {
            "message": "入庫処理が完了しました（検品待ち）",
            "lot_id": lot.id,
            "item_id": None,
            "item_ids": [],
            "lot_number": primary_lot_number,
            "material_id": material_id
        }
    except HTTPException:
        # HTTPExceptionはそのまま再送出
        db.rollback()
        raise
    except Exception as e:
        # その他のエラーはログ出力して500エラーを返す
        db.rollback()
        import traceback
        error_trace = traceback.format_exc()
        print(f"入庫確認エラー: {error_trace}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"入庫処理中にエラーが発生しました: {str(e)}"
        )

@router.put("/items/{item_id}/receive/", response_model=dict)
async def update_received_item(
    item_id: int,
    receiving: ReceivingConfirmation,
    db: Session = Depends(get_db)
):
    """入庫内容の再編集（入庫済みアイテムの特定ロットを更新）"""
    # 発注アイテム取得
    item = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="発注アイテムが見つかりません")

    if item.status != PurchaseOrderItemStatus.RECEIVED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未入庫アイテムは更新ではなく入庫処理を行ってください")

    # リクエストのロット番号で該当ロットを検索
    lot = db.query(Lot).filter(
        Lot.purchase_order_item_id == item.id,
        Lot.lot_number == receiving.lot_number
    ).first()
    
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"ロット番号 '{receiving.lot_number}' が見つかりません。新規ロットの場合はPOSTメソッドを使用してください。"
        )

    # 入庫データのバリデーション
    try:
        receiving.validate_receiving_data()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # 材料を取得（ロットの材料）
    material = db.query(Material).filter(Material.id == lot.material_id, Material.is_active == True).first()
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ロットに紐づく材料が見つかりません")

    # 計算用パラメータの更新（display_nameは維持）
    material.shape = receiving.shape
    material.diameter_mm = receiving.diameter_mm
    material.current_density = receiving.density
    db.flush()

    # 計算用属性（更新後の材料値を使用）
    effective_shape = material.shape
    effective_diameter = material.diameter_mm
    effective_density = material.current_density

    # ユーザー入力をそのまま採用（換算なし）
    final_received_quantity = receiving.received_quantity or 0
    final_received_weight = receiving.received_weight_kg or 0.0

    # 置き場の存在チェック
    invalid_locations: List[int] = []
    if receiving.location_ids and len(receiving.location_ids) > 0:
        for loc_id in receiving.location_ids:
            loc = db.query(Location).filter(Location.id == loc_id, Location.is_active == True).first()
            if not loc:
                invalid_locations.append(loc_id)
    elif receiving.location_id is not None:
        loc = db.query(Location).filter(Location.id == receiving.location_id, Location.is_active == True).first()
        if not loc:
            invalid_locations.append(receiving.location_id)

    if invalid_locations:
        raise HTTPException(status_code=404, detail=f"指定された置き場が見つかりません: {', '.join(str(x) for x in invalid_locations)}")

    # ロット情報更新
    lot.lot_number = receiving.lot_number
    lot.length_mm = receiving.length_mm
    lot.initial_quantity = final_received_quantity
    lot.initial_weight_kg = final_received_weight
    lot.received_date = receiving.received_date
    lot.received_unit_price = receiving.unit_price
    lot.received_amount = receiving.amount
    lot.purchase_month = receiving.purchase_month
    lot.notes = receiving.notes
    db.flush()

    # 発注アイテムの単価・金額も更新（入力された場合のみ）
    if receiving.unit_price is not None:
        item.unit_price = receiving.unit_price
    if receiving.amount is not None:
        item.amount = receiving.amount

    # 在庫アイテム（第一置き場）の更新
    inv_item = db.query(Item).filter(Item.lot_id == lot.id).order_by(Item.id.asc()).first()
    
    primary_location = None
    if receiving.location_ids and len(receiving.location_ids) > 0:
        primary_location = receiving.location_ids[0]
    elif receiving.location_id is not None:
        primary_location = receiving.location_id
    
    # 在庫アイテムが存在する場合のみ更新（検品済みの場合）
    if inv_item:
        inv_item.location_id = primary_location
        inv_item.current_quantity = final_received_quantity
        db.flush()
    else:
        # 検品前の場合、置き場情報をロットの備考に保存
        location_info = ", ".join(str(loc) for loc in (receiving.location_ids or [receiving.location_id]) if loc is not None)
        if location_info:
            if lot.notes and "登録予定置き場:" in lot.notes:
                # 既存の登録予定置き場を更新
                lot.notes = re.sub(r"登録予定置き場:[^\n]*", f"登録予定置き場: {location_info}", lot.notes)
            else:
                # 新規に登録予定置き場を追加
                if lot.notes:
                    lot.notes = f"{lot.notes}\n登録予定置き場: {location_info}"
                else:
                    lot.notes = f"登録予定置き場: {location_info}"

    # 追加置き場の表記（備考へ追記）
    if receiving.location_ids and len(receiving.location_ids) > 1:
        others = ", ".join(str(loc) for loc in receiving.location_ids[1:] if loc is not None)
        if others:
            if lot.notes:
                lot.notes = f"{lot.notes}\n追加置き場: {others}"
            else:
                lot.notes = f"追加置き場: {others}"

    # 発注アイテムの数量・重量更新
    # 既存ロットも含めた合計を再計算して反映
    remaining_lots = db.query(Lot).options(joinedload(Lot.material)).filter(
        Lot.purchase_order_item_id == item.id
    ).all()

    total_quantity = 0
    total_weight_kg = 0.0

    for remaining_lot in remaining_lots:
        total_quantity += remaining_lot.initial_quantity or 0
        lot_weight = remaining_lot.initial_weight_kg or 0.0
        if not lot_weight:
            material_for_lot = remaining_lot.material
            if material_for_lot and remaining_lot.initial_quantity:
                try:
                    lot_weight = calculate_weight_from_quantity(
                        remaining_lot.initial_quantity,
                        material_for_lot.shape,
                        material_for_lot.diameter_mm,
                        remaining_lot.length_mm,
                        material_for_lot.current_density
                    )
                except Exception:
                    lot_weight = 0.0
        total_weight_kg += lot_weight

    item.received_quantity = total_quantity if total_quantity > 0 else 0
    item.received_weight_kg = total_weight_kg if total_weight_kg > 0 else None

    db.commit()

    return {
        "message": "入庫内容を更新しました",
        "lot_id": lot.id,
        "item_id": inv_item.id if inv_item else None,
        "material_id": material.id
    }


@router.delete("/items/{item_id}/receive/{lot_number}/", response_model=dict)
async def delete_received_lot(
    item_id: int,
    lot_number: str,
    db: Session = Depends(get_db)
):
    """入庫済みロットの削除

    - 指定した発注アイテムに紐づくロットを物理削除
    - 削除前に入出庫履歴の有無を確認（存在する場合は削除不可）
    - ロット削除後に入庫数量・重量、発注ステータスを再計算
    """

    if not lot_number:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ロット番号を指定してください")

    item = db.query(PurchaseOrderItem).options(joinedload(PurchaseOrderItem.lots)).filter(
        PurchaseOrderItem.id == item_id
    ).first()

    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="発注アイテムが見つかりません")

    lot = db.query(Lot).options(joinedload(Lot.material), joinedload(Lot.items)).filter(
        Lot.lot_number == lot_number
    ).first()

    if not lot or lot.purchase_order_item_id != item.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="指定されたロットが見つかりません")

    # ひも付く在庫アイテムを取得
    inventory_item = db.query(Item).options(joinedload(Item.movements)).filter(Item.lot_id == lot.id).first()

    if inventory_item:
        # 入出庫履歴が存在する場合は削除を禁止
        movement_exists = db.query(Movement).filter(Movement.item_id == inventory_item.id).first() is not None
        if movement_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="このロットには入出庫履歴が存在するため削除できません"
            )

    # ロットと在庫アイテムを削除
    if inventory_item:
        db.delete(inventory_item)
    db.delete(lot)
    db.flush()

    # 残存ロットから入庫数量と重量を再計算
    remaining_lots = db.query(Lot).options(joinedload(Lot.material)).filter(
        Lot.purchase_order_item_id == item.id
    ).all()

    total_quantity = 0
    total_weight_kg = 0.0

    for remaining_lot in remaining_lots:
        total_quantity += remaining_lot.initial_quantity or 0

        # 重量は保存済みの初期重量を優先、なければ数量から計算
        lot_weight = remaining_lot.initial_weight_kg or 0.0
        if not lot_weight:
            material_for_lot = remaining_lot.material
            if material_for_lot and remaining_lot.initial_quantity:
                try:
                    lot_weight = calculate_weight_from_quantity(
                        remaining_lot.initial_quantity,
                        material_for_lot.shape,
                        material_for_lot.diameter_mm,
                        remaining_lot.length_mm,
                        material_for_lot.current_density
                    )
                except Exception:
                    lot_weight = 0.0
        total_weight_kg += lot_weight

    item.received_quantity = total_quantity if total_quantity > 0 else 0
    item.received_weight_kg = total_weight_kg if total_weight_kg > 0 else None

    if total_quantity > 0:
        item.status = PurchaseOrderItemStatus.RECEIVED
    else:
        item.status = PurchaseOrderItemStatus.PENDING

    # 発注ステータスを再計算
    order = item.purchase_order
    if order:
        received_items = [i for i in order.items if i.status == PurchaseOrderItemStatus.RECEIVED]
        if len(received_items) == len(order.items) and len(order.items) > 0:
            order.status = PurchaseOrderStatus.COMPLETED
        elif len(received_items) > 0:
            order.status = PurchaseOrderStatus.PARTIAL
        else:
            order.status = PurchaseOrderStatus.PENDING

    db.commit()

    return {
        "message": "ロットを削除しました",
        "deleted_lot_number": lot_number,
        "remaining_lot_count": len(remaining_lots)
    }


@router.get("/items/{item_id}/receive/previous/", response_model=dict)
async def get_previous_receiving_values(
    item_id: int,
    db: Session = Depends(get_db)
):
    """再編集用に、ユーザーが登録した受入値（全ロット）を返す

    - 指定の発注アイテムに紐づく全ロットを取得
    - 各ロットの材料属性・入庫属性・金額情報・置き場をまとめて返す
    - 重量は保存していないため、数量から計算し補完
    - 共通の材料パラメータ（径・形状・比重・長さ）も返す
    """
    # 発注アイテム確認
    po_item = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == item_id).first()
    if not po_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="発注アイテムが見つかりません")

    # 紐づく全ロット（受入日昇順→ID昇順）
    lots = db.query(Lot).filter(Lot.purchase_order_item_id == item_id).order_by(Lot.received_date.asc(), Lot.id.asc()).all()
    if not lots:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="紐づくロットが見つかりません")

    # 最初のロットから材料を取得（全ロットで共通）
    first_lot = lots[0]
    material = db.query(Material).filter(Material.id == first_lot.material_id, Material.is_active == True).first()
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ロットに紐づく材料が見つかりません")

    # 各ロットの情報を構築
    lots_data = []
    for lot in lots:
        # 重量は保存された初期重量を使用。なければ数量から計算
        received_quantity = lot.initial_quantity
        received_weight_kg = lot.initial_weight_kg
        if (received_weight_kg is None or received_weight_kg == 0) and received_quantity and received_quantity > 0:
            try:
                received_weight_kg = calculate_weight_from_quantity(
                    received_quantity, material.shape, material.diameter_mm, lot.length_mm, material.current_density
                )
            except Exception:
                received_weight_kg = None

        # 置き場
        items_for_lot = db.query(Item).filter(Item.lot_id == lot.id).all()
        location_id = items_for_lot[0].location_id if items_for_lot and items_for_lot[0].location_id else None

        lots_data.append({
            'lot_number': lot.lot_number,
            'received_quantity': received_quantity,
            'received_weight_kg': received_weight_kg,
            'location_id': location_id,
            'purchase_month': lot.purchase_month,
            'notes': lot.notes
        })

    # レスポンス
    return {
        'diameter_mm': material.diameter_mm,
        'shape': material.shape.value if material.shape else 'round',
        'density': material.current_density,
        'length_mm': first_lot.length_mm,
        'received_date': first_lot.received_date.isoformat() if first_lot.received_date else None,
        'purchase_month': first_lot.purchase_month,
        'lots': lots_data
    }


@router.get("/items/{item_id}/inspection-target/", response_model=dict)
async def get_inspection_target(item_id: int, db: Session = Depends(get_db)):
    """検品対象取得（ロットIDと在庫管理コード）

    - 指定の発注アイテムに紐づく最新ロットを特定
    - ロットに紐づく在庫アイテムから管理コードを返す
    """
    # 発注アイテム確認
    po_item = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == item_id).first()
    if not po_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="発注アイテムが見つかりません")

    # 紐づくロットを取得（受入日降順→ID降順）
    lot = db.query(Lot).filter(Lot.purchase_order_item_id == item_id).order_by(Lot.received_date.desc(), Lot.id.desc()).first()
    if not lot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="検品対象ロットが見つかりません")

    # ロットに紐づく在庫アイテムを取得（最初の1件）
    inv_item = db.query(Item).filter(Item.lot_id == lot.id).order_by(Item.id.asc()).first()
    if not inv_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ロットに紐づく在庫アイテムが見つかりません")

    return {
        "lot_id": lot.id,
        "inventory_item_id": inv_item.id,
        "management_code": inv_item.management_code,
        "inspection_status": lot.inspection_status.value if lot.inspection_status else None
    }

# 重量⇔本数換算APIは廃止（フロントエンド未使用）

@router.put("/{order_id}", response_model=PurchaseOrderResponse)
async def update_purchase_order(
    order_id: int,
    order_data: PurchaseOrderUpdate,
    db: Session = Depends(get_db)
):
    """発注ヘッダーの編集（仕入先・納期・備考を更新）"""
    # 発注取得
    order = db.query(PurchaseOrder).options(joinedload(PurchaseOrder.items)).filter(
        PurchaseOrder.id == order_id
    ).first()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="発注が見つかりません"
        )

    # 入庫済み（COMPLETED/PARTIAL）の場合は警告（編集は許可するが推奨しない）
    if order.status in [PurchaseOrderStatus.COMPLETED, PurchaseOrderStatus.PARTIAL]:
        # 警告をログに出力（実運用ではフロントエンドで確認ダイアログを表示推奨）
        print(f"警告: 入庫済み発注（ID: {order_id}）を編集しています")

    # 旧値を記録
    old_values = f"仕入先: {order.supplier}, 納期: {order.expected_delivery_date}, 備考: {order.notes or 'なし'}"

    # 更新
    if order_data.supplier is not None:
        order.supplier = order_data.supplier
    if order_data.expected_delivery_date is not None:
        order.expected_delivery_date = order_data.expected_delivery_date
    if order_data.notes is not None:
        order.notes = order_data.notes

    order.updated_at = datetime.now()

    # 監査ログ記録
    audit_log = AuditLog(
        user_id=1,  # TODO: 認証実装後にユーザーIDを設定
        action="発注ヘッダー編集",
        target_table="purchase_orders",
        target_id=order_id,
        old_values=old_values,
        new_values=f"仕入先: {order.supplier}, 納期: {order.expected_delivery_date}, 備考: {order.notes or 'なし'}",
        created_at=datetime.now()
    )

    db.add(audit_log)
    db.commit()
    db.refresh(order)

    return order

@router.put("/items/{item_id}", response_model=PurchaseOrderItemResponse)
async def update_purchase_order_item(
    item_id: int,
    item_data: PurchaseOrderItemUpdate,
    db: Session = Depends(get_db)
):
    """発注アイテムの編集（数量・単価・金額を更新）"""
    # アイテム取得
    item = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == item_id).first()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="発注アイテムが見つかりません"
        )

    # 入庫済み（RECEIVED）の場合は編集不可
    if item.status == PurchaseOrderItemStatus.RECEIVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="入庫済みアイテムは編集できません。入庫内容の修正は PUT /items/{item_id}/receive/ を使用してください"
        )

    # 旧値を記録
    old_values = f"数量: {item.ordered_quantity}, 重量: {item.ordered_weight_kg}, 単価: {item.unit_price}, 金額: {item.amount}"

    # 更新
    if item_data.ordered_quantity is not None:
        item.ordered_quantity = item_data.ordered_quantity
    if item_data.ordered_weight_kg is not None:
        item.ordered_weight_kg = item_data.ordered_weight_kg
    if item_data.unit_price is not None:
        item.unit_price = item_data.unit_price
    if item_data.amount is not None:
        item.amount = item_data.amount

    item.updated_at = datetime.now()

    # 監査ログ記録
    audit_log = AuditLog(
        user_id=1,  # TODO: 認証実装後にユーザーIDを設定
        action="発注アイテム編集",
        target_table="purchase_order_items",
        target_id=item_id,
        old_values=old_values,
        new_values=f"数量: {item.ordered_quantity}, 重量: {item.ordered_weight_kg}, 単価: {item.unit_price}, 金額: {item.amount}",
        created_at=datetime.now()
    )

    db.add(audit_log)
    db.commit()
    db.refresh(item)

    return item

@router.delete("/{order_id}")
async def delete_purchase_order(
    order_id: int,
    db: Session = Depends(get_db)
):
    """発注の削除（未入庫のみ）"""
    # 発注取得
    order = db.query(PurchaseOrder).options(joinedload(PurchaseOrder.items)).filter(
        PurchaseOrder.id == order_id
    ).first()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="発注が見つかりません"
        )

    # 入庫済みアイテムがある場合は削除不可
    has_received_items = any(
        item.status == PurchaseOrderItemStatus.RECEIVED
        for item in order.items
    )

    if has_received_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="入庫済みアイテムがあるため削除できません"
        )

    # 監査ログ記録
    audit_log = AuditLog(
        user_id=1,  # TODO: 認証実装後にユーザーIDを設定
        action="発注削除",
        target_table="purchase_orders",
        target_id=order_id,
        old_values=f"発注番号: {order.order_number}, 仕入先: {order.supplier}, アイテム数: {len(order.items)}",
        new_values="削除",
        created_at=datetime.now()
    )

    db.add(audit_log)

    # 発注アイテムを先に削除（外部キー制約対応）
    for item in order.items:
        db.delete(item)

    # 発注本体を削除
    db.delete(order)
    db.commit()

    return {
        "message": "発注を削除しました",
        "order_id": order_id,
        "order_number": order.order_number
    }
