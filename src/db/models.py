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

class UsageType(enum.Enum):
    GENERAL = "general"      # 汎用品
    DEDICATED = "dedicated"  # 専用品



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

class MaterialStandard(Base):
    """材料標準規格マスタ（第1層: JIS標準材質）"""
    __tablename__ = "material_standards"

    id = Column(Integer, primary_key=True, index=True)
    jis_code = Column(String(50), unique=True, nullable=False, index=True, comment="JIS規格コード（例: SUS303, C3604）")
    jis_name = Column(String(100), nullable=False, comment="JIS規格名称")
    category = Column(String(50), comment="カテゴリ（ステンレス/黄銅/炭素鋼等）")
    description = Column(Text, comment="説明")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # リレーション
    grades = relationship("MaterialGrade", back_populates="standard")

class MaterialGrade(Base):
    """材料グレード/特性マスタ（第2層）"""
    __tablename__ = "material_grades"

    id = Column(Integer, primary_key=True, index=True)
    standard_id = Column(Integer, ForeignKey("material_standards.id"), nullable=False)
    grade_code = Column(String(50), nullable=False, index=True, comment="グレードコード（例: LCD, 標準）")
    characteristics = Column(String(200), comment="特性（快削性、耐食性等）")
    description = Column(Text, comment="説明")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # リレーション
    standard = relationship("MaterialStandard", back_populates="grades")
    products = relationship("MaterialProduct", back_populates="grade")

class MaterialProduct(Base):
    """材料実製品/ブランドマスタ（第3層）"""
    __tablename__ = "material_products"

    id = Column(Integer, primary_key=True, index=True)
    grade_id = Column(Integer, ForeignKey("material_grades.id"), nullable=False)
    product_code = Column(String(100), nullable=False, index=True, comment="製品コード（例: ASK3000, C3604LCD）")
    manufacturer = Column(String(200), comment="メーカー名")
    is_equivalent = Column(Boolean, default=False, comment="同等品フラグ")
    description = Column(Text, comment="説明")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # リレーション
    grade = relationship("MaterialGrade", back_populates="products")
    materials = relationship("Material", back_populates="product")

class MaterialAlias(Base):
    """材料別名管理テーブル（表記揺れ対応）"""
    __tablename__ = "material_aliases"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    alias_name = Column(String(200), nullable=False, index=True, comment="別名（例: SUS303 φ10.0D, ASK3000 ∅10）")
    description = Column(Text, comment="説明")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # リレーション
    material = relationship("Material", back_populates="aliases")

class Material(Base):
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("material_products.id"), nullable=True, comment="製品ID（第3層との紐付け）")
    part_number = Column(String(100), nullable=True, comment="品番")
    name = Column(String(100), nullable=False, comment="材質名（例：S45C）")
    display_name = Column(String(200), nullable=True, comment="表示名（表記揺れ対応: φ10.0D等）")
    description = Column(Text, comment="説明")
    shape = Column(Enum(MaterialShape), nullable=False, comment="断面形状")
    diameter_mm = Column(Float, nullable=False, comment="直径または一辺の長さ（mm）")
    current_density = Column(Float, nullable=False, comment="現在の比重（g/cm³）")
    usage_type = Column(Enum(UsageType), nullable=True, default=UsageType.GENERAL, comment="用途区分（汎用/専用）")
    dedicated_part_number = Column(String(100), nullable=True, comment="専用品番")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # リレーション
    product = relationship("MaterialProduct", back_populates="materials")
    density_history = relationship("Density", back_populates="material")
    lots = relationship("Lot", back_populates="material")
    aliases = relationship("MaterialAlias", back_populates="material")

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
    received_unit_price = Column(Float, comment="入庫時単価")
    received_amount = Column(Float, comment="入庫時金額")
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
    item_name = Column(String(200), nullable=False, comment="発注品名")
    order_type = Column(Enum(OrderType), nullable=False, default=OrderType.QUANTITY, comment="発注方式")
    ordered_quantity = Column(Integer, comment="発注数量（本数指定時）")
    received_quantity = Column(Integer, default=0, comment="入庫数量（本数）")
    ordered_weight_kg = Column(Float, comment="発注重量（重量指定時、kg）")
    received_weight_kg = Column(Float, comment="入庫重量（kg）")
    unit_price = Column(Float, comment="単価")
    amount = Column(Float, comment="金額（単価 × 数量）")
    management_code = Column(CHAR(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), comment="事前生成UUID管理コード")
    status = Column(Enum(PurchaseOrderItemStatus), nullable=False, default=PurchaseOrderItemStatus.PENDING, comment="アイテム状態")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # リレーション
    purchase_order = relationship("PurchaseOrder", back_populates="items")
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


