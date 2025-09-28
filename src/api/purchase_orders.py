from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

from src.db import get_db
from src.db.models import (
    PurchaseOrder, PurchaseOrderItem, PurchaseOrderStatus, PurchaseOrderItemStatus,
    Material, MaterialShape, Lot, Item, Location, OrderType
)

router = APIRouter()

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
    material_id: Optional[int] = Field(None, description="既存材料ID（新規材料の場合はNULL）")
    material_name: str = Field(..., max_length=100, description="材料名")
    shape: MaterialShape = Field(..., description="断面形状")
    diameter_mm: float = Field(..., gt=0, description="直径または一辺の長さ（mm）")
    length_mm: int = Field(..., gt=0, description="長さ（mm）")
    density: float = Field(..., gt=0, description="比重（g/cm³）")
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

    def get_final_quantity_and_weight(self):
        """最終的な発注数量と重量を計算"""
        if self.order_type == OrderType.QUANTITY:
            # 本数指定：重量を計算
            weight = calculate_weight_from_quantity(
                self.ordered_quantity, self.shape, self.diameter_mm,
                self.length_mm, self.density
            )
            return self.ordered_quantity, weight
        else:
            # 重量指定：本数を計算
            quantity = calculate_quantity_from_weight(
                self.ordered_weight_kg, self.shape, self.diameter_mm,
                self.length_mm, self.density
            )
            return quantity, self.ordered_weight_kg

class PurchaseOrderCreate(BaseModel):
    order_number: str = Field(..., max_length=50, description="発注番号")
    supplier: str = Field(..., max_length=200, description="仕入先")
    order_date: datetime = Field(..., description="発注日")
    expected_delivery_date: Optional[datetime] = Field(None, description="納期予定日")
    purpose: Optional[str] = Field(None, description="用途・製品名")
    notes: Optional[str] = Field(None, description="備考")
    items: List[PurchaseOrderItemCreate] = Field(..., min_items=1, description="発注アイテム")

class PurchaseOrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    material_id: Optional[int]
    material_name: str
    shape: MaterialShape
    diameter_mm: float
    length_mm: int
    density: float
    order_type: OrderType
    ordered_quantity: Optional[int]
    received_quantity: int
    ordered_weight_kg: Optional[float]
    received_weight_kg: Optional[float]
    unit_price: Optional[float]
    management_code: str
    is_new_material: bool
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

class ReceivingConfirmation(BaseModel):
    lot_number: str = Field(..., max_length=100, description="ロット番号")
    received_quantity: Optional[int] = Field(None, gt=0, description="入庫数量（本数指定時）")
    received_weight_kg: Optional[float] = Field(None, gt=0, description="入庫重量（重量指定時、kg）")
    location_id: Optional[int] = Field(None, description="置き場ID")
    notes: Optional[str] = Field(None, description="備考")

    def validate_receiving_data(self):
        """入庫データのバリデーション"""
        if not self.received_quantity and not self.received_weight_kg:
            raise ValueError("入庫数量または入庫重量のいずれかが必要です")
        if self.received_quantity and self.received_weight_kg:
            raise ValueError("入庫数量と入庫重量は同時に指定できません")

# API エンドポイント
@router.get("/", response_model=List[PurchaseOrderResponse])
async def get_purchase_orders(
    skip: int = 0,
    limit: int = 100,
    status: Optional[PurchaseOrderStatus] = None,
    supplier: Optional[str] = None,
    purpose: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """発注一覧取得"""
    query = db.query(PurchaseOrder).options(joinedload(PurchaseOrder.items))

    if status is not None:
        query = query.filter(PurchaseOrder.status == status)

    if supplier is not None:
        query = query.filter(PurchaseOrder.supplier.contains(supplier))

    if purpose is not None:
        query = query.filter(PurchaseOrder.purpose.contains(purpose))

    orders = query.order_by(PurchaseOrder.created_at.desc()).offset(skip).limit(limit).all()
    return orders

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
    existing = db.query(PurchaseOrder).filter(
        PurchaseOrder.order_number == order.order_number
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="同じ発注番号が既に存在します"
        )

    # 発注作成
    db_order = PurchaseOrder(
        order_number=order.order_number,
        supplier=order.supplier,
        order_date=order.order_date,
        expected_delivery_date=order.expected_delivery_date,
        purpose=order.purpose,
        notes=order.notes,
        created_by=1  # TODO: 認証実装後にユーザーIDを設定
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

        # 最終的な数量と重量を計算
        final_quantity, final_weight = item_data.get_final_quantity_and_weight()

        # 既存材料かチェック
        is_new_material = False
        if item_data.material_id:
            # 既存材料IDが指定された場合、材料が存在するかチェック
            material = db.query(Material).filter(Material.id == item_data.material_id).first()
            if not material:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"材料ID {item_data.material_id} が見つかりません"
                )
        else:
            # 新規材料の場合、同じ仕様の材料が既に存在するかチェック
            existing_material = db.query(Material).filter(
                Material.name == item_data.material_name,
                Material.shape == item_data.shape,
                Material.diameter_mm == item_data.diameter_mm,
                Material.is_active == True
            ).first()

            if existing_material:
                # 既存材料が見つかった場合は使用
                item_data.material_id = existing_material.id
            else:
                # 新規材料フラグを設定
                is_new_material = True

        # 発注アイテム作成
        db_item = PurchaseOrderItem(
            purchase_order_id=db_order.id,
            material_id=item_data.material_id,
            material_name=item_data.material_name,
            shape=item_data.shape,
            diameter_mm=item_data.diameter_mm,
            length_mm=item_data.length_mm,
            density=item_data.density,
            order_type=item_data.order_type,
            ordered_quantity=final_quantity,
            ordered_weight_kg=final_weight,
            unit_price=item_data.unit_price,
            is_new_material=is_new_material
        )

        db.add(db_item)

        # 合計金額計算（本数ベース）
        if item_data.unit_price:
            total_amount += item_data.unit_price * final_quantity

    # 合計金額を設定
    db_order.total_amount = total_amount if total_amount > 0 else None

    db.commit()

    # 作成された発注を返す
    db.refresh(db_order)
    return db.query(PurchaseOrder).options(joinedload(PurchaseOrder.items)).filter(
        PurchaseOrder.id == db_order.id
    ).first()

@router.get("/pending/items/", response_model=List[PurchaseOrderItemResponse])
async def get_pending_items(db: Session = Depends(get_db)):
    """入庫待ちアイテム一覧取得"""
    items = db.query(PurchaseOrderItem).options(
        joinedload(PurchaseOrderItem.purchase_order)
    ).filter(
        PurchaseOrderItem.status == PurchaseOrderItemStatus.PENDING
    ).all()

    return items

@router.post("/items/{item_id}/receive/", response_model=dict)
async def receive_item(
    item_id: int,
    receiving: ReceivingConfirmation,
    db: Session = Depends(get_db)
):
    """入庫確認"""
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

    # ユーザーの入力に応じて最終的な入庫数量と重量を計算
    if receiving.received_weight_kg:
        # 重量入力：重量から本数を計算
        final_received_quantity = calculate_quantity_from_weight(
            receiving.received_weight_kg, item.shape, item.diameter_mm,
            item.length_mm, item.density
        )
        final_received_weight = receiving.received_weight_kg
    else:
        # 本数入力：本数から重量を計算
        final_received_quantity = receiving.received_quantity
        final_received_weight = calculate_weight_from_quantity(
            receiving.received_quantity, item.shape, item.diameter_mm,
            item.length_mm, item.density
        )

    # 材料の自動登録（新規材料の場合）
    material_id = item.material_id
    if item.is_new_material and not material_id:
        # 新規材料として登録
        new_material = Material(
            name=item.material_name,
            shape=item.shape,
            diameter_mm=item.diameter_mm,
            current_density=item.density
        )
        db.add(new_material)
        db.flush()
        material_id = new_material.id

        # 発注アイテムの材料IDを更新
        item.material_id = material_id
        item.is_new_material = False

    # ロット作成
    lot = Lot(
        lot_number=receiving.lot_number,
        material_id=material_id,
        purchase_order_item_id=item.id,
        length_mm=item.length_mm,
        initial_quantity=final_received_quantity,
        supplier=item.purchase_order.supplier,
        received_date=datetime.now(),
        notes=receiving.notes
    )
    db.add(lot)
    db.flush()

    # アイテム作成（束管理）
    inventory_item = Item(
        lot_id=lot.id,
        location_id=receiving.location_id,
        current_quantity=final_received_quantity,
        management_code=item.management_code  # 発注時に生成された管理コードを使用
    )
    db.add(inventory_item)

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

    return {
        "message": "入庫処理が完了しました",
        "lot_id": lot.id,
        "item_id": inventory_item.id,
        "management_code": item.management_code
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
        "material_name": item.material_name,
        "shape": item.shape.value,
        "diameter_mm": item.diameter_mm,
        "length_mm": item.length_mm,
        "ordered_quantity": item.ordered_quantity
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