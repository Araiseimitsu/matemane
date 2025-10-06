from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from src.db.models import MaterialAlias
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime, date

from src.db import get_db
from src.db.models import (
    PurchaseOrder, PurchaseOrderItem, PurchaseOrderStatus, PurchaseOrderItemStatus,
    Material, MaterialShape, Lot, Item, Location, OrderType, User,
    MaterialGroup, MaterialGroupMember, InspectionStatus
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
        side_cm = diameter_mm / 10  # mm → cm
        volume_cm3 = (3 * (3 ** 0.5) / 2) * (side_cm ** 2) * (length_mm / 10)
    elif shape == MaterialShape.SQUARE:
        # 角棒: 一辺² × 長さ
        side_cm = diameter_mm / 10  # mm → cm
        volume_cm3 = (side_cm ** 2) * (length_mm / 10)
    else:
        raise ValueError(f"未対応の形状: {shape}")

    weight_kg = volume_cm3 * density / 1000  # g → kg
    return round(weight_kg * quantity, 3)

def calculate_quantity_from_weight(weight_kg: float, shape: MaterialShape, diameter_mm: float, length_mm: int, density: float) -> int:
    """重量から本数を計算"""
    single_piece_weight = calculate_weight_from_quantity(1, shape, diameter_mm, length_mm, density)
    quantity = weight_kg / single_piece_weight
    return max(1, round(quantity))  # 最低1本

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
    purpose: Optional[str]
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

class ReceivingConfirmation(BaseModel):
    lot_number: str = Field(..., max_length=100, description="ロット番号")
    material_name: str = Field(..., max_length=100, description="材質名")
    detail_info: Optional[str] = Field(None, max_length=200, description="詳細情報")
    diameter_mm: float = Field(..., gt=0, description="直径または一辺の長さ（mm）")
    shape: MaterialShape = Field(..., description="断面形状")
    density: float = Field(..., gt=0, description="比重（g/cm³）")
    # 入庫情報
    length_mm: int = Field(..., gt=0, description="長さ（mm）")
    received_date: datetime = Field(..., description="入荷日")
    received_quantity: Optional[int] = Field(None, gt=0, description="入庫数量（本数指定時）")
    received_weight_kg: Optional[float] = Field(None, gt=0, description="入庫重量（重量指定時、kg）")
    unit_price: Optional[float] = Field(None, ge=0, description="単価")
    amount: Optional[float] = Field(None, ge=0, description="金額")
    # 置き場
    location_id: Optional[int] = Field(None, description="置き場ID")
    location_ids: Optional[List[int]] = Field(None, description="置き場IDの配列（複数指定時）")
    notes: Optional[str] = Field(None, description="備考")
    group_id: Optional[int] = Field(None, description="材料グループID（任意）")

    def validate_receiving_data(self):
        """入庫データのバリデーション"""
        if not self.received_quantity and not self.received_weight_kg:
            raise ValueError("入庫数量または入庫重量のいずれかが必要です")
        if self.received_quantity and self.received_weight_kg:
            raise ValueError("入庫数量と入庫重量は同時に指定できません")

class MaterialSuggestionResponse(BaseModel):
    material_id: int
    display_name: str
    name: Optional[str]
    shape: Optional[MaterialShape]
    diameter_mm: Optional[float]
    detail_info: Optional[str]
    density: Optional[float]

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
        name=material.name,
        shape=material.shape,
        diameter_mm=material.diameter_mm,
        detail_info=material.detail_info,
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

        # 材料候補の特定（発注品名の全文で一致を優先。径・詳細は判定に使わない）
        detail_info = receiving.detail_info.strip() if receiving.detail_info else None

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

        # 3) 上記で見つからない場合は、ユーザー入力の材質名でもマッチを試みる（後方互換）
        if not existing_material:
            existing_material = db.query(Material).filter(
                or_(
                    Material.display_name == receiving.material_name,
                    Material.name == receiving.material_name
                ),
                Material.is_active == True
            ).first()
            if not existing_material:
                alias2 = db.query(MaterialAlias).filter(
                    MaterialAlias.alias_name == receiving.material_name
                ).first()
                if alias2:
                    existing_material = db.query(Material).filter(
                        Material.id == alias2.material_id,
                        Material.is_active == True
                    ).first()

        # 計算用属性（既存があればマスター値を優先）
        effective_shape = existing_material.shape if existing_material else receiving.shape
        effective_diameter = existing_material.diameter_mm if existing_material else receiving.diameter_mm
        effective_density = existing_material.current_density if existing_material else receiving.density

        # ユーザーの入力に応じて最終的な入庫数量と重量を計算
        if receiving.received_weight_kg:
            # 重量入力：重量から本数を計算
            final_received_quantity = calculate_quantity_from_weight(
                receiving.received_weight_kg, effective_shape, effective_diameter,
                receiving.length_mm, effective_density
            )
            final_received_weight = receiving.received_weight_kg
        else:
            # 本数入力：本数から重量を計算
            final_received_quantity = receiving.received_quantity
            final_received_weight = calculate_weight_from_quantity(
                receiving.received_quantity, effective_shape, effective_diameter,
                receiving.length_mm, effective_density
            )

        if existing_material:
            material_id = existing_material.id
        else:
            # 新規材料として登録（マスターは発注品名の全文を基準にdisplay_nameへ保存）
            new_material = Material(
                name=receiving.material_name,
                display_name=item.item_name,  # 発注品名の全文
                detail_info=detail_info,
                shape=receiving.shape,
                diameter_mm=receiving.diameter_mm,
                current_density=receiving.density,
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
            supplier=item.purchase_order.supplier,
            received_date=receiving.received_date,
            received_unit_price=receiving.unit_price,
            received_amount=receiving.amount,
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

        created_item_ids: List[int] = []
        primary_management_code: Optional[str] = None

        # 第一置き場へまとめて登録（数量を分けない）
        primary_location = target_locations[0] if len(target_locations) > 0 else None
        inventory_item = Item(
            lot_id=lot.id,
            location_id=primary_location,
            current_quantity=final_received_quantity
        )
        db.add(inventory_item)
        db.flush()
        created_item_ids.append(inventory_item.id)
        primary_management_code = inventory_item.management_code

        # 追加の置き場情報は備考へ追記（構造化テーブルなしのため）
        if len(target_locations) > 1:
            others = ", ".join(str(loc) for loc in target_locations[1:] if loc is not None)
            if others:
                if lot.notes:
                    lot.notes = f"{lot.notes}\n追加置き場: {others}"
                else:
                    lot.notes = f"追加置き場: {others}"

        # 発注アイテムの状態更新（複数ロット対応：累積計算）
        item.received_quantity = (item.received_quantity or 0) + final_received_quantity
        item.received_weight_kg = round((item.received_weight_kg or 0) + final_received_weight, 3)
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

        # 後方互換：item_id は先頭のIDを返し、複数時は item_ids も返す
        return {
            "message": "入庫処理が完了しました",
            "lot_id": lot.id,
            "item_id": created_item_ids[0],
            "item_ids": created_item_ids,
            "management_code": primary_management_code,
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
    """入庫内容の再編集（入庫済みアイテムの受入情報を更新）"""
    # 発注アイテム取得
    item = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="発注アイテムが見つかりません")

    if item.status != PurchaseOrderItemStatus.RECEIVED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未入庫アイテムは更新ではなく入庫処理を行ってください")

    # 紐づく最新ロット取得
    lot = db.query(Lot).filter(Lot.purchase_order_item_id == item.id).order_by(Lot.received_date.desc(), Lot.id.desc()).first()
    if not lot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="紐づくロットが見つかりません")

    # 入庫データのバリデーション
    try:
        receiving.validate_receiving_data()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # 材料を取得（ロットの材料）
    material = db.query(Material).filter(Material.id == lot.material_id, Material.is_active == True).first()
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ロットに紐づく材料が見つかりません")

    # 材料属性の更新（display_nameは維持。name/detail/shape/径/密度を更新）
    material.name = receiving.material_name
    material.detail_info = (receiving.detail_info or None)
    material.shape = receiving.shape
    material.diameter_mm = receiving.diameter_mm
    material.current_density = receiving.density
    db.flush()

    # 計算用属性（更新後の材料値を使用）
    effective_shape = material.shape
    effective_diameter = material.diameter_mm
    effective_density = material.current_density

    # ユーザー入力に応じて数量・重量を再計算
    if receiving.received_weight_kg:
        final_received_quantity = calculate_quantity_from_weight(
            receiving.received_weight_kg, effective_shape, effective_diameter,
            receiving.length_mm, effective_density
        )
        final_received_weight = receiving.received_weight_kg
    else:
        final_received_quantity = receiving.received_quantity
        final_received_weight = calculate_weight_from_quantity(
            receiving.received_quantity, effective_shape, effective_diameter,
            receiving.length_mm, effective_density
        )

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
    lot.received_date = receiving.received_date
    lot.received_unit_price = receiving.unit_price
    lot.received_amount = receiving.amount
    lot.notes = receiving.notes
    db.flush()

    # 在庫アイテム（第一置き場）の更新
    inv_item = db.query(Item).filter(Item.lot_id == lot.id).order_by(Item.id.asc()).first()
    if not inv_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ロットに紐づく在庫アイテムが見つかりません")

    primary_location = None
    if receiving.location_ids and len(receiving.location_ids) > 0:
        primary_location = receiving.location_ids[0]
    elif receiving.location_id is not None:
        primary_location = receiving.location_id
    inv_item.location_id = primary_location
    inv_item.current_quantity = final_received_quantity
    db.flush()

    # 追加置き場の表記（備考へ追記）
    if receiving.location_ids and len(receiving.location_ids) > 1:
        others = ", ".join(str(loc) for loc in receiving.location_ids[1:] if loc is not None)
        if others:
            if lot.notes:
                lot.notes = f"{lot.notes}\n追加置き場: {others}"
            else:
                lot.notes = f"追加置き場: {others}"

    # 発注アイテムの数量・重量更新
    item.received_quantity = final_received_quantity
    item.received_weight_kg = final_received_weight

    db.commit()

    return {
        "message": "入庫内容を更新しました",
        "lot_id": lot.id,
        "item_id": inv_item.id,
        "management_code": inv_item.management_code,
        "material_id": material.id
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
