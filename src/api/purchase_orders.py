from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

from src.db import get_db
from src.db.models import (
    PurchaseOrder, PurchaseOrderItem, PurchaseOrderStatus, PurchaseOrderItemStatus,
    Material, MaterialShape, Lot, Item, Location
)

router = APIRouter()

# Pydantic スキーマ
class PurchaseOrderItemCreate(BaseModel):
    material_id: Optional[int] = Field(None, description="既存材料ID（新規材料の場合はNULL）")
    material_name: str = Field(..., max_length=100, description="材料名")
    shape: MaterialShape = Field(..., description="断面形状")
    diameter_mm: float = Field(..., gt=0, description="直径または一辺の長さ（mm）")
    length_mm: int = Field(..., gt=0, description="長さ（mm）")
    density: float = Field(..., gt=0, description="比重（g/cm³）")
    ordered_quantity: int = Field(..., gt=0, description="発注数量")
    unit_price: Optional[float] = Field(None, ge=0, description="単価")

class PurchaseOrderCreate(BaseModel):
    order_number: str = Field(..., max_length=50, description="発注番号")
    supplier: str = Field(..., max_length=200, description="仕入先")
    order_date: datetime = Field(..., description="発注日")
    expected_delivery_date: Optional[datetime] = Field(None, description="納期予定日")
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
    ordered_quantity: int
    received_quantity: int
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
    notes: Optional[str]
    total_amount: Optional[float]
    created_by: int
    created_at: datetime
    updated_at: datetime
    items: List[PurchaseOrderItemResponse]

class ReceivingConfirmation(BaseModel):
    lot_number: str = Field(..., max_length=100, description="ロット番号")
    received_quantity: int = Field(..., gt=0, description="入庫数量")
    location_id: Optional[int] = Field(None, description="置き場ID")
    notes: Optional[str] = Field(None, description="備考")

# API エンドポイント
@router.get("/", response_model=List[PurchaseOrderResponse])
async def get_purchase_orders(
    skip: int = 0,
    limit: int = 100,
    status: Optional[PurchaseOrderStatus] = None,
    supplier: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """発注一覧取得"""
    query = db.query(PurchaseOrder).options(joinedload(PurchaseOrder.items))

    if status is not None:
        query = query.filter(PurchaseOrder.status == status)

    if supplier is not None:
        query = query.filter(PurchaseOrder.supplier.contains(supplier))

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
        notes=order.notes,
        created_by=1  # TODO: 認証実装後にユーザーIDを設定
    )

    db.add(db_order)
    db.flush()  # IDを取得するためにflush

    # 発注アイテム作成
    total_amount = 0
    for item_data in order.items:
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
            ordered_quantity=item_data.ordered_quantity,
            unit_price=item_data.unit_price,
            is_new_material=is_new_material
        )

        db.add(db_item)

        # 合計金額計算
        if item_data.unit_price:
            total_amount += item_data.unit_price * item_data.ordered_quantity

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
        initial_quantity=receiving.received_quantity,
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
        current_quantity=receiving.received_quantity,
        management_code=item.management_code  # 発注時に生成された管理コードを使用
    )
    db.add(inventory_item)

    # 発注アイテムの状態更新
    item.received_quantity = receiving.received_quantity
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