from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Enum
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.db import Base
import enum
import uuid

class UserRole(enum.Enum):
    ADMIN = "admin"
    PURCHASE = "purchase"
    OPERATOR = "operator"
    VIEWER = "viewer"

class MaterialShape(enum.Enum):
    ROUND = "round"
    HEXAGON = "hexagon"
    SQUARE = "square"

class MovementType(enum.Enum):
    IN = "in"
    OUT = "out"

class PurchaseOrderStatus(enum.Enum):
    PENDING = "pending"      # 発注済み（入庫待ち）
    PARTIAL = "partial"      # 一部入庫
    COMPLETED = "completed"  # 完了
    CANCELLED = "cancelled"  # キャンセル

class PurchaseOrderItemStatus(enum.Enum):
    PENDING = "pending"      # 入庫待ち
    RECEIVED = "received"    # 入庫済み

class OrderType(enum.Enum):
    QUANTITY = "quantity"    # 本数指定
    WEIGHT = "weight"        # 重量指定



class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.VIEWER)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Material(Base):
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="材質名（例：S45C）")
    description = Column(Text, comment="説明")
    shape = Column(Enum(MaterialShape), nullable=False, comment="断面形状")
    diameter_mm = Column(Float, nullable=False, comment="直径または一辺の長さ（mm）")
    current_density = Column(Float, nullable=False, comment="現在の比重（g/cm³）")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # リレーション
    density_history = relationship("Density", back_populates="material")
    lots = relationship("Lot", back_populates="material")

class Density(Base):
    __tablename__ = "densities"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    density = Column(Float, nullable=False, comment="比重（g/cm³）")
    effective_from = Column(DateTime(timezone=True), nullable=False, comment="適用開始日")
    notes = Column(Text, comment="変更理由など")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # リレーション
    material = relationship("Material", back_populates="density_history")
    creator = relationship("User")

class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, comment="置き場名（1〜250）")
    description = Column(Text, comment="説明")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # リレーション
    items = relationship("Item", back_populates="location")

class Lot(Base):
    __tablename__ = "lots"

    id = Column(Integer, primary_key=True, index=True)
    lot_number = Column(String(100), unique=True, nullable=False, comment="ロット番号")
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    purchase_order_item_id = Column(Integer, ForeignKey("purchase_order_items.id"), nullable=True, comment="発注アイテムID")
    length_mm = Column(Integer, nullable=False, comment="長さ（mm）")
    initial_quantity = Column(Integer, nullable=False, comment="初期本数")
    supplier = Column(String(200), comment="仕入先")
    received_date = Column(DateTime(timezone=True), comment="入荷日")
    notes = Column(Text, comment="備考")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # リレーション
    material = relationship("Material", back_populates="lots")
    purchase_order_item = relationship("PurchaseOrderItem", back_populates="lots")
    items = relationship("Item", back_populates="lot")

class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    management_code = Column(CHAR(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), comment="UUID管理コード")
    lot_id = Column(Integer, ForeignKey("lots.id"), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    current_quantity = Column(Integer, nullable=False, comment="現在本数")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # リレーション
    lot = relationship("Lot", back_populates="items")
    location = relationship("Location", back_populates="items")
    movements = relationship("Movement", back_populates="item")

class Movement(Base):
    __tablename__ = "movements"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    movement_type = Column(Enum(MovementType), nullable=False)
    quantity = Column(Integer, nullable=False, comment="移動本数")
    instruction_number = Column(String(50), comment="指示書番号（IS-YYYY-NNNN）")
    notes = Column(Text, comment="備考")
    processed_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    processed_at = Column(DateTime(timezone=True), server_default=func.now())

    # リレーション
    item = relationship("Item", back_populates="movements")
    processor = relationship("User")

class DensityPreset(Base):
    __tablename__ = "density_presets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="材質名（例：S45C、SUS304）")
    density = Column(Float, nullable=False, comment="比重（g/cm³）")
    description = Column(Text, comment="説明")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(50), unique=True, nullable=False, comment="発注番号")
    supplier = Column(String(200), nullable=False, comment="仕入先")
    order_date = Column(DateTime(timezone=True), nullable=False, comment="発注日")
    expected_delivery_date = Column(DateTime(timezone=True), comment="納期予定日")
    status = Column(Enum(PurchaseOrderStatus), nullable=False, default=PurchaseOrderStatus.PENDING, comment="発注状態")
    purpose = Column(Text, comment="用途・製品名（例：○○製品用材料）")
    notes = Column(Text, comment="備考")
    total_amount = Column(Float, comment="合計金額")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # リレーション
    creator = relationship("User")
    items = relationship("PurchaseOrderItem", back_populates="purchase_order")

class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    id = Column(Integer, primary_key=True, index=True)
    purchase_order_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=True, comment="材料ID（新規材料の場合はNULL）")
    material_name = Column(String(100), nullable=False, comment="材料名")
    shape = Column(Enum(MaterialShape), nullable=False, comment="断面形状")
    diameter_mm = Column(Float, nullable=False, comment="直径または一辺の長さ（mm）")
    length_mm = Column(Integer, nullable=False, comment="長さ（mm）")
    density = Column(Float, nullable=False, comment="比重（g/cm³）")
    order_type = Column(Enum(OrderType), nullable=False, default=OrderType.QUANTITY, comment="発注方式")
    ordered_quantity = Column(Integer, comment="発注数量（本数指定時）")
    received_quantity = Column(Integer, default=0, comment="入庫数量（本数）")
    ordered_weight_kg = Column(Float, comment="発注重量（重量指定時、kg）")
    received_weight_kg = Column(Float, comment="入庫重量（kg）")
    unit_price = Column(Float, comment="単価")
    management_code = Column(CHAR(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), comment="事前生成UUID管理コード")
    is_new_material = Column(Boolean, default=False, comment="新規材料フラグ")
    status = Column(Enum(PurchaseOrderItemStatus), nullable=False, default=PurchaseOrderItemStatus.PENDING, comment="アイテム状態")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # リレーション
    purchase_order = relationship("PurchaseOrder", back_populates="items")
    material = relationship("Material")
    lots = relationship("Lot", back_populates="purchase_order_item")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False, comment="操作内容")
    target_table = Column(String(50), comment="対象テーブル")
    target_id = Column(Integer, comment="対象レコードID")
    old_values = Column(Text, comment="変更前の値（JSON）")
    new_values = Column(Text, comment="変更後の値（JSON）")
    ip_address = Column(String(45), comment="IPアドレス")
    user_agent = Column(Text, comment="ユーザーエージェント")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # リレーション
    user = relationship("User")


