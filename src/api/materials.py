from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
import re
import os
import json

from src.db import get_db
from src.db.models import (
    Material, MaterialShape, MaterialAlias, Lot
)

router = APIRouter()

# ========================================
# 材料別名用 Pydantic スキーマ
# ========================================

class MaterialAliasBase(BaseModel):
    material_id: int = Field(..., description="材料ID")
    alias_name: str = Field(..., max_length=200, description="別名（例: SUS303 φ10.0D, ASK3000 ∅10）")
    description: Optional[str] = Field(None, description="説明")

class MaterialAliasCreate(MaterialAliasBase):
    pass

class MaterialAliasResponse(MaterialAliasBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime

# ========================================
# 既存の材料用 Pydantic スキーマ
# ========================================

class MaterialBase(BaseModel):
    display_name: str = Field(..., max_length=200, description="材料名（Excelから取得したフルネーム）")
    description: Optional[str] = Field(None, description="説明")
    shape: MaterialShape = Field(..., description="断面形状（計算用）")
    diameter_mm: float = Field(..., gt=0, description="直径または一辺の長さ（mm・計算用）")
    current_density: float = Field(..., gt=0, description="現在の比重（g/cm³・計算用）")

class MaterialCreate(MaterialBase):
    pass

class MaterialUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=200, description="材料名（Excelから取得したフルネーム）")
    description: Optional[str] = Field(None, description="説明")
    shape: Optional[MaterialShape] = Field(None, description="断面形状（計算用）")
    diameter_mm: Optional[float] = Field(None, gt=0, description="直径または一辺の長さ（mm・計算用）")
    current_density: Optional[float] = Field(None, gt=0, description="現在の比重（g/cm³・計算用）")
    is_active: Optional[bool] = Field(None, description="有効フラグ")

class MaterialResponse(MaterialBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

# API エンドポイント
@router.get("/count")
async def get_materials_count(
    is_active: Optional[bool] = None,
    display_name: Optional[str] = None,
    diameter_mm: Optional[float] = None,
    shape: Optional[MaterialShape] = None,
    db: Session = Depends(get_db)
):
    """材料総件数取得（フィルタ対応）"""
    query = db.query(Material)

    if is_active is not None:
        query = query.filter(Material.is_active == is_active)

    if display_name is not None:
        query = query.filter(Material.display_name.contains(display_name))

    if diameter_mm is not None:
        query = query.filter(Material.diameter_mm == diameter_mm)

    if shape is not None:
        query = query.filter(Material.shape == shape)

    total = query.count()
    return {"total": total}

@router.get("/", response_model=List[MaterialResponse])
async def get_materials(
    request: Request,
    skip: int = 0,
    limit: int = 100,  # ページネーション用に100件制限
    is_active: Optional[bool] = None,
    display_name: Optional[str] = None,
    diameter_mm: Optional[float] = None,
    shape: Optional[MaterialShape] = None,
    db: Session = Depends(get_db)
):
    """材料一覧取得"""
    query = db.query(Material)

    if is_active is not None:
        query = query.filter(Material.is_active == is_active)

    if display_name is not None:
        query = query.filter(Material.display_name.contains(display_name))

    if diameter_mm is not None:
        query = query.filter(Material.diameter_mm == diameter_mm)

    if shape is not None:
        query = query.filter(Material.shape == shape)

    materials = query.offset(skip).limit(limit).all()
    return materials

@router.post("/", response_model=MaterialResponse, status_code=status.HTTP_201_CREATED)
async def create_material(material: MaterialCreate, db: Session = Depends(get_db)):
    """材料作成"""
    db_material = Material(**material.model_dump())
    db.add(db_material)
    db.commit()
    db.refresh(db_material)
    return db_material

@router.get("/{material_id}", response_model=MaterialResponse)
async def get_material(material_id: int, db: Session = Depends(get_db)):
    """材料詳細取得"""
    db_material = db.query(Material).filter(Material.id == material_id).first()
    if not db_material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="材料が見つかりません"
        )
    return db_material

@router.put("/{material_id}", response_model=MaterialResponse)
async def update_material(
    material_id: int,
    material: MaterialUpdate,
    db: Session = Depends(get_db)
):
    """材料更新"""
    db_material = db.query(Material).filter(Material.id == material_id).first()
    if not db_material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="材料が見つかりません"
        )

    update_data = material.model_dump(exclude_unset=True)

    # ロットが存在する場合、重要な計算用属性の変更を禁止
    critical_keys = {"shape", "diameter_mm", "current_density"}
    will_change_critical = any(
        key in update_data and update_data[key] != getattr(db_material, key)
        for key in critical_keys
    )
    if will_change_critical:
        lot_exists = db.query(Lot).filter(Lot.material_id == material_id).first() is not None
        if lot_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "この材料に紐づくロットが存在するため、形状・寸法・比重の変更はできません。"
                    "新しい材料を作成し、必要に応じてロットを再割り当てしてください。"
                )
            )

    for key, value in update_data.items():
        setattr(db_material, key, value)

    db.commit()
    db.refresh(db_material)
    return db_material

@router.delete("/{material_id}")
async def delete_material(material_id: int, db: Session = Depends(get_db)):
    """材料削除（論理削除）"""
    db_material = db.query(Material).filter(Material.id == material_id).first()
    if not db_material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="材料が見つかりません"
        )

    db_material.is_active = False
    db.commit()

    return {"message": "材料を無効化しました"}

@router.get("/{material_id}/calculate-weight")
async def calculate_weight(
    material_id: int,
    length_mm: float,
    quantity: int = 1,
    db: Session = Depends(get_db)
):
    """重量計算"""
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="材料が見つかりません"
        )

    # 体積計算（cm³）
    if material.shape == MaterialShape.ROUND:
        # 丸棒: π × (直径/2)² × 長さ
        radius_cm = (material.diameter_mm / 2) / 10  # mm → cm
        length_cm = length_mm / 10  # mm → cm
        volume_cm3 = 3.14159 * (radius_cm ** 2) * length_cm
    elif material.shape == MaterialShape.HEXAGON:
        # 六角棒: (3√3/2) × (対辺距離/2)² × 長さ
        side_cm = (material.diameter_mm / 2) / 10  # mm → cm (対辺距離の半分)
        length_cm = length_mm / 10  # mm → cm
        volume_cm3 = (3 * (3 ** 0.5) / 2) * (side_cm ** 2) * length_cm
    elif material.shape == MaterialShape.SQUARE:
        # 角棒: 一辺² × 長さ
        side_cm = material.diameter_mm / 10  # mm → cm
        length_cm = length_mm / 10  # mm → cm
        volume_cm3 = (side_cm ** 2) * length_cm
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="サポートされていない形状です"
        )

    # 重量計算（kg）
    weight_per_piece_kg = (volume_cm3 * material.current_density) / 1000
    total_weight_kg = weight_per_piece_kg * quantity

    return {
        "material_id": material_id,
        "material_name": material.display_name,
        "shape": material.shape.value,
        "diameter_mm": material.diameter_mm,
        "length_mm": length_mm,
        "quantity": quantity,
        "density": material.current_density,
        "volume_per_piece_cm3": round(volume_cm3, 3),
        "weight_per_piece_kg": round(weight_per_piece_kg, 3),
        "total_weight_kg": round(total_weight_kg, 3)
    }

# ========================================
# 材料別名管理用 API エンドポイント
# ========================================

@router.get("/aliases/", response_model=List[MaterialAliasResponse])
async def get_material_aliases(
    material_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """別名一覧取得（材料IDでフィルタ可能）"""
    query = db.query(MaterialAlias)

    if material_id is not None:
        query = query.filter(MaterialAlias.material_id == material_id)

    aliases = query.offset(skip).limit(limit).all()
    return aliases

@router.post("/aliases/", response_model=MaterialAliasResponse, status_code=status.HTTP_201_CREATED)
async def create_material_alias(
    alias: MaterialAliasCreate,
    db: Session = Depends(get_db)
):
    """別名作成"""
    # 材料存在チェック
    material = db.query(Material).filter(
        Material.id == alias.material_id
    ).first()

    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"材料ID {alias.material_id} が見つかりません"
        )

    db_alias = MaterialAlias(**alias.model_dump())
    db.add(db_alias)
    db.commit()
    db.refresh(db_alias)

    return db_alias

@router.get("/search/")
async def search_materials(
    query_text: str,
    in_stock_only: bool = Query(False, description="在庫に存在する材料のみ返す"),
    db: Session = Depends(get_db)
):
    """材料横断検索（別名も含む）"""
    q = (query_text or "").strip()
    q_upper = q.upper()

    # 材料名・表示名・詳細情報・品番での検索
    base_query = db.query(Material)

    # 在庫あり材料のみに絞る場合のサブクエリ
    if in_stock_only:
        from src.db.models import Item, Lot
        stock_mat_ids = db.query(Lot.material_id).join(Item, Item.lot_id == Lot.id).filter(
            Item.is_active == True,
            Item.current_quantity > 0
        ).distinct()
        base_query = base_query.filter(Material.id.in_(stock_mat_ids))

    materials = base_query.filter(
        Material.display_name.ilike(f"%{q}%")
    ).limit(100).all()

    # 径・形状キーワードからの検索も対応（例: "φ10", "10mm", "六角 8"）
    try:
        # 径の抽出（半角/全角mm・記号対応）
        q_norm = q.replace("㎜", "mm").replace("ｍｍ", "mm").replace("ＭＭ", "mm")
        diameter_matches = re.findall(r"([0-9]+(?:\.[0-9]+)?)", q_norm)
        shape_hint = None
        if re.search(r"丸|round|φ|∅", q_norm, re.IGNORECASE):
            shape_hint = MaterialShape.ROUND
        elif re.search(r"六角|hex", q_norm, re.IGNORECASE):
            shape_hint = MaterialShape.HEXAGON
        elif re.search(r"四角|square|□", q_norm, re.IGNORECASE):
            shape_hint = MaterialShape.SQUARE

        if diameter_matches:
            d_val = float(diameter_matches[0])
            mats_by_diameter = db.query(Material).filter(Material.diameter_mm == d_val)
            if shape_hint is not None:
                mats_by_diameter = mats_by_diameter.filter(Material.shape == shape_hint)
            mats_by_diameter = mats_by_diameter.limit(100).all()

            existing_ids = {m.id for m in materials}
            for m in mats_by_diameter:
                if m.id not in existing_ids:
                    materials.append(m)
                    existing_ids.add(m.id)
    except Exception:
        # 直径解析に失敗しても通常検索結果は返す
        pass

    # 数値キーワードからJIS候補（例: "3604" -> "C3604", "C3604LCD"）も拾う
    try:
        tokens = set()
        if re.fullmatch(r"\d{3,4}", q_upper):
            tokens.update({q_upper, f"C{q_upper}", f"C{q_upper}LCD"})
        elif re.fullmatch(r"C\d{3,4}", q_upper):
            tokens.update({q_upper, f"{q_upper}LCD"})

        existing_ids = {m.id for m in materials}
        for t in tokens:
            extra = db.query(Material).filter(
                Material.display_name.ilike(f"%{t}%")
            ).limit(100).all()
            for m in extra:
                if m.id not in existing_ids:
                    materials.append(m)
                    existing_ids.add(m.id)
    except Exception:
        pass

    # 別名での検索も統合
    aliases = db.query(MaterialAlias).filter(
        MaterialAlias.alias_name.ilike(f"%{q}%")
    ).limit(100).all()

    # 結果を統合
    material_ids = {m.id for m in materials}
    for alias in aliases:
        if alias.material_id not in material_ids:
            material = db.query(Material).filter(Material.id == alias.material_id).first()
            if material:
                materials.append(material)
                material_ids.add(material.id)

    # 追加情報を付与
    results = []
    for material in materials:
        result = {
            "material_id": material.id,
            "display_name": material.display_name,
            "shape": material.shape.value,
            "diameter_mm": material.diameter_mm
        }
        results.append(result)

    return results


