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