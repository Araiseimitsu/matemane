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
    MaterialGroup, MaterialGroupMember
)
from src.api.order_utils import generate_order_number
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

# Pydantic スキーマ
class PurchaseOrderItemCreate(BaseModel):
    item_name: str = Field(..., max_length=200, description="発注品名")
    order_type: OrderType = Field(OrderType.QUANTITY, description="発注方式")
    ordered_quantity: Optional[int] = Field(None, gt=0, description="発注数量（本数指定時）")
    ordered_weight_kg: Optional[float] = Field(None, gt=0, description="発注重量（重量指定時、kg）")
    unit_price: Optional[float] = Field(None, ge=0, description="単価")

    def validate_order_data(self):
        """発注データのバリデーション"""
        if self.order_type == OrderType.QUANTITY:
            if not self.ordered_quantity:
                raise ValueError("本数指定の場合は発注数量が必要です")
        elif self.order_type == OrderType.WEIGHT:
            if not self.ordered_weight_kg:
                raise ValueError("重量指定の場合は発注重量が必要です")
        else:
            raise ValueError("無効な発注方式です")

class PurchaseOrderCreate(BaseModel):
    order_number: Optional[str] = Field(None, max_length=50, description="発注番号（未指定時は自動生成）")
    supplier: str = Field(..., max_length=200, description="仕入先")
    order_date: datetime = Field(..., description="発注日")
    expected_delivery_date: Optional[datetime] = Field(None, description="納期予定日")
    purpose: Optional[str] = Field(None, description="用途・製品名")
    notes: Optional[str] = Field(None, description="備考")
    items: List[PurchaseOrderItemCreate] = Field(..., min_items=1, description="発注アイテム")

    @field_validator("order_date", "expected_delivery_date", mode="before")
    @classmethod
    def _coerce_date_only_to_datetime(cls, v):
        """フロントから日付文字列(YYYY-MM-DD)が来た場合は0時のdatetimeへ補完する"""
        if v is None:
            return v
        if isinstance(v, datetime):
            return v
        if isinstance(v, date):
            return datetime(v.year, v.month, v.day)
        if isinstance(v, str):
            try:
                # 'YYYY-MM-DD' 形式を優先的に処理
                if len(v) == 10 and v[4] == '-' and v[7] == '-':
                    y, m, d = v.split("-")
                    return datetime(int(y), int(m), int(d))
                # それ以外は標準のfromisoformatに委ねる
                return datetime.fromisoformat(v)
            except Exception:
                raise ValueError("日付の形式が不正です")
        return v

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
    management_code: str
    status: PurchaseOrderItemStatus
    purchase_order_id: int
    created_at: datetime
    updated_at: datetime

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
    total_amount: Optional[float]
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
    # 材料情報（入庫確認時に入力）
    material_name: str = Field(..., max_length=100, description="材質名")
    detail_info: Optional[str] = Field(None, max_length=200, description="詳細情報")
    diameter_mm: float = Field(..., gt=0, description="直径または一辺の長さ（mm）")
    shape: MaterialShape = Field(..., description="断面形状")
    # 区分（汎用/専用）は廃止。グループ運用で統一するため削除。
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

@router.post("/", response_model=PurchaseOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_purchase_order(order: PurchaseOrderCreate, db: Session = Depends(get_db)):
    """発注作成"""
    # 発注番号の重複チェック
    provided_order_number = (order.order_number or "").strip()

    if provided_order_number:
        existing = db.query(PurchaseOrder).filter(
            PurchaseOrder.order_number == provided_order_number
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="同じ発注番号が既に存在します"
            )
        order_number_value = provided_order_number
    else:
        order_number_value = generate_order_number(db)

    # アイテム数の制約: 1件のみ許可
    if len(order.items) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="発注アイテムは1件のみ許可されます"
        )

    # 発注作成
    db_order = PurchaseOrder(
        order_number=order_number_value,
        supplier=order.supplier,
        order_date=order.order_date,
        expected_delivery_date=order.expected_delivery_date,
        purpose=order.purpose,
        notes=order.notes,
        created_by=ensure_default_user(db)  # デフォルトユーザーを使用
    )

    db.add(db_order)
    db.flush()  # IDを取得するためにflush

    # 発注アイテム作成
    total_amount = 0
    for item_data in order.items:
        # 発注データバリデーション
        try:
            item_data.validate_order_data()
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

        # 数量ベースで金額計算
        item_amount = None
        if item_data.unit_price and item_data.ordered_quantity:
            item_amount = item_data.unit_price * item_data.ordered_quantity

        # 発注アイテム作成
        db_item = PurchaseOrderItem(
            purchase_order_id=db_order.id,
            item_name=item_data.item_name,
            order_type=item_data.order_type,
            ordered_quantity=item_data.ordered_quantity,
            ordered_weight_kg=item_data.ordered_weight_kg,
            unit_price=item_data.unit_price,
            amount=item_amount
        )

        db.add(db_item)

        # 合計金額計算
        if item_amount:
            total_amount += item_amount

    # 合計金額を設定
    db_order.total_amount = total_amount if total_amount > 0 else None

    db.commit()

    # 作成された発注を返す
    db.refresh(db_order)
    return db.query(PurchaseOrder).options(joinedload(PurchaseOrder.items)).filter(
        PurchaseOrder.id == db_order.id
    ).first()

@router.put("/{order_id}", response_model=PurchaseOrderResponse)
async def update_purchase_order(order_id: int, order: PurchaseOrderCreate, db: Session = Depends(get_db)):
    """発注更新"""
    db_order = db.query(PurchaseOrder).options(joinedload(PurchaseOrder.items)).filter(
        PurchaseOrder.id == order_id
    ).first()

    if not db_order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="発注が見つかりません"
        )

    # 入庫済みアイテムが含まれている場合は編集不可
    if any(i.status == PurchaseOrderItemStatus.RECEIVED for i in db_order.items):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="入庫済みアイテムが含まれるため編集できません"
        )

    # 発注番号の重複チェック（変更時のみ）
    provided_order_number = (order.order_number or "").strip()
    if provided_order_number and provided_order_number != db_order.order_number:
        existing = db.query(PurchaseOrder).filter(
            PurchaseOrder.order_number == provided_order_number
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="同じ発注番号が既に存在します"
            )
        db_order.order_number = provided_order_number

    # 基本情報更新
    db_order.supplier = order.supplier
    db_order.order_date = order.order_date
    db_order.expected_delivery_date = order.expected_delivery_date
    db_order.purpose = order.purpose
    db_order.notes = order.notes

    # アイテム数の制約: 1件のみ許可
    if len(order.items) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="発注アイテムは1件のみ許可されます"
        )

    # 既存アイテムを削除して再作成
    for existing_item in list(db_order.items):
        db.delete(existing_item)
    db.flush()

    total_amount = 0
    for item_data in order.items:
        # 発注データバリデーション
        try:
            item_data.validate_order_data()
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

        # 数量ベースで金額計算
        item_amount = None
        if item_data.unit_price and item_data.ordered_quantity:
            item_amount = item_data.unit_price * item_data.ordered_quantity

        # 発注アイテム作成
        db_item = PurchaseOrderItem(
            purchase_order_id=db_order.id,
            item_name=item_data.item_name,
            order_type=item_data.order_type,
            ordered_quantity=item_data.ordered_quantity,
            ordered_weight_kg=item_data.ordered_weight_kg,
            unit_price=item_data.unit_price,
            amount=item_amount
        )

        db.add(db_item)

        # 合計金額計算
        if item_amount:
            total_amount += item_amount

    # 合計金額を設定
    db_order.total_amount = total_amount if total_amount > 0 else None

    db.commit()

    db.refresh(db_order)
    return db.query(PurchaseOrder).options(joinedload(PurchaseOrder.items)).filter(
        PurchaseOrder.id == db_order.id
    ).first()

@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_purchase_order(order_id: int, db: Session = Depends(get_db)):
    """発注削除"""
    db_order = db.query(PurchaseOrder).options(joinedload(PurchaseOrder.items)).filter(
        PurchaseOrder.id == order_id
    ).first()

    if not db_order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="発注が見つかりません"
        )

    # 入庫済みアイテムが含まれている場合は削除不可
    if any(i.status == PurchaseOrderItemStatus.RECEIVED for i in db_order.items):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="入庫済みアイテムが含まれるため削除できません"
        )

    # 子アイテム→親の順で削除
    for existing_item in list(db_order.items):
        db.delete(existing_item)
    db.delete(db_order)
    db.commit()
    return None

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
async def get_pending_or_inspection_items(db: Session = Depends(get_db)):
    """入庫待ち、または検品未完了アイテム一覧取得

    - 発注アイテムが未入庫（PENDING）のもの
    - 入庫済み（RECEIVED）だが、紐づくロットの検品が未完了（PENDING/FAILED）のもの
    """
    from sqlalchemy.sql import exists
    from src.db.models import Lot, InspectionStatus

    lot_has_unpassed_inspection = exists().where(
        (Lot.purchase_order_item_id == PurchaseOrderItem.id) &
        (Lot.inspection_status != InspectionStatus.PASSED)
    )

    items = db.query(PurchaseOrderItem).options(
        joinedload(PurchaseOrderItem.purchase_order)
    ).filter(
        or_(
            PurchaseOrderItem.status == PurchaseOrderItemStatus.PENDING,
            lot_has_unpassed_inspection
        )
    ).all()

    return items

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
    """入庫確認（材料情報入力対応）"""
    # 発注アイテム取得
    item = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="発注アイテムが見つかりません"
        )

    if item.status != PurchaseOrderItemStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="このアイテムは既に入庫済みです"
        )

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

    # 発注アイテムの状態更新
    item.received_quantity = final_received_quantity
    item.received_weight_kg = final_received_weight
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

@router.get("/items/{item_id}/management-code/", response_model=dict)
async def get_management_code(item_id: int, db: Session = Depends(get_db)):
    """管理コード取得"""
    item = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="発注アイテムが見つかりません"
        )

    return {
        "item_id": item.id,
        "management_code": item.management_code,
        "item_name": item.item_name,
        "ordered_quantity": item.ordered_quantity
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
        "management_code": inv_item.management_code
    }

class ConversionRequest(BaseModel):
    shape: MaterialShape
    diameter_mm: float = Field(..., gt=0)
    length_mm: int = Field(..., gt=0)
    density: float = Field(..., gt=0)
    quantity: Optional[int] = Field(None, gt=0)
    weight_kg: Optional[float] = Field(None, gt=0)

@router.post("/calculate-conversion/", response_model=dict)
async def calculate_conversion(request: ConversionRequest):
    """重量⇔本数換算計算"""
    if request.quantity is not None and request.weight_kg is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="数量と重量は同時に指定できません"
        )

    if request.quantity is None and request.weight_kg is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="数量または重量のいずれかを指定してください"
        )

    try:
        if request.quantity is not None:
            # 本数から重量を計算
            calculated_weight = calculate_weight_from_quantity(
                request.quantity, request.shape, request.diameter_mm, request.length_mm, request.density
            )
            return {
                "input_quantity": request.quantity,
                "calculated_weight_kg": calculated_weight,
                "conversion_type": "quantity_to_weight"
            }
        else:
            # 重量から本数を計算
            calculated_quantity = calculate_quantity_from_weight(
                request.weight_kg, request.shape, request.diameter_mm, request.length_mm, request.density
            )
            return {
                "input_weight_kg": request.weight_kg,
                "calculated_quantity": calculated_quantity,
                "conversion_type": "weight_to_quantity"
            }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"換算計算エラー: {str(e)}"
        )
