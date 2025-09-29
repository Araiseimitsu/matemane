from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
import pandas as pd
import re
import os
import tempfile
import json

from src.db import get_db
from src.db.models import Material, MaterialShape, Density

router = APIRouter()

# Pydantic スキーマ
class MaterialBase(BaseModel):
    name: str = Field(..., max_length=100, description="材質名（例：S45C）")
    description: Optional[str] = Field(None, description="説明")
    shape: MaterialShape = Field(..., description="断面形状")
    diameter_mm: float = Field(..., gt=0, description="直径または一辺の長さ（mm）")
    current_density: float = Field(..., gt=0, description="現在の比重（g/cm³）")

class MaterialCreate(MaterialBase):
    pass

class MaterialUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100, description="材質名")
    description: Optional[str] = Field(None, description="説明")
    shape: Optional[MaterialShape] = Field(None, description="断面形状")
    diameter_mm: Optional[float] = Field(None, gt=0, description="直径または一辺の長さ（mm）")
    current_density: Optional[float] = Field(None, gt=0, description="現在の比重（g/cm³）")
    is_active: Optional[bool] = Field(None, description="有効フラグ")

class MaterialResponse(MaterialBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

# API エンドポイント
@router.get("/", response_model=List[MaterialResponse])
async def get_materials(
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = None,
    shape: Optional[MaterialShape] = None,
    name: Optional[str] = None,
    diameter_mm: Optional[float] = None,
    db: Session = Depends(get_db)
):
    """材料一覧取得"""
    query = db.query(Material)

    if is_active is not None:
        query = query.filter(Material.is_active == is_active)

    if shape is not None:
        query = query.filter(Material.shape == shape)

    if name is not None:
        query = query.filter(Material.name.contains(name))

    if diameter_mm is not None:
        query = query.filter(Material.diameter_mm == diameter_mm)

    materials = query.offset(skip).limit(limit).all()
    return materials

@router.get("/{material_id}", response_model=MaterialResponse)
async def get_material(material_id: int, db: Session = Depends(get_db)):
    """材料詳細取得"""
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="材料が見つかりません"
        )
    return material

@router.post("/", response_model=MaterialResponse, status_code=status.HTTP_201_CREATED)
async def create_material(material: MaterialCreate, db: Session = Depends(get_db)):
    """材料作成"""
    # 同じ名前と形状・寸法の材料が既に存在するかチェック
    existing = db.query(Material).filter(
        Material.name == material.name,
        Material.shape == material.shape,
        Material.diameter_mm == material.diameter_mm,
        Material.is_active == True
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="同じ材質・形状・寸法の材料が既に存在します"
        )

    db_material = Material(**material.model_dump())
    db.add(db_material)
    db.commit()
    db.refresh(db_material)

    # 比重履歴にも記録
    density_record = Density(
        material_id=db_material.id,
        density=material.current_density,
        effective_from=datetime.now(),
        created_by=1  # TODO: 認証実装後にユーザーIDを設定
    )
    db.add(density_record)
    db.commit()

    return db_material

@router.put("/{material_id}", response_model=MaterialResponse)
async def update_material(
    material_id: int,
    material_update: MaterialUpdate,
    db: Session = Depends(get_db)
):
    """材料更新"""
    db_material = db.query(Material).filter(Material.id == material_id).first()
    if not db_material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="材料が見つかりません"
        )

    # 比重が更新される場合、比重履歴にも記録
    old_density = db_material.current_density

    update_data = material_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_material, field, value)

    db.commit()
    db.refresh(db_material)

    # 比重が変更された場合は履歴に記録
    if 'current_density' in update_data and update_data['current_density'] != old_density:
        density_record = Density(
            material_id=material_id,
            density=update_data['current_density'],
            effective_from=datetime.now(),
            created_by=1  # TODO: 認証実装後にユーザーIDを設定
        )
        db.add(density_record)
        db.commit()

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
        "material_name": material.name,
        "shape": material.shape.value,
        "diameter_mm": material.diameter_mm,
        "length_mm": length_mm,
        "quantity": quantity,
        "density": material.current_density,
        "volume_per_piece_cm3": round(volume_cm3, 3),
        "weight_per_piece_kg": round(weight_per_piece_kg, 3),
        "total_weight_kg": round(total_weight_kg, 3)
    }

def parse_materials_csv(file_path: str) -> List[Dict]:
    """
    材料マスターCSVファイルを解析し、材料データを抽出する
    """
    try:
        # UTF-8でCSVを読み込み
        df = pd.read_csv(file_path, encoding='utf-8', header=None)

        materials = []

        for index, row in df.iterrows():
            if pd.isna(row[0]) or str(row[0]).strip() == '' or str(row[0]).strip() == '材質＆材料径':
                continue

            material_text = str(row[0]).strip()

            parsed_material = None

            # パターン1：標準的なφ記法
            match = re.match(r'^(.+?)\s*[φΦ]\s*(\d+(?:\.\d+)?)\s*(.*)$', material_text)
            if match:
                material_name = match.group(1).strip()
                size = float(match.group(2))
                additional_info = match.group(3).strip()

                # 形状判定
                shape = "round"  # デフォルトで丸棒

                # 追加情報から形状を判定
                if "hex" in additional_info.lower() or "六角" in additional_info:
                    shape = "hexagon"
                elif "square" in additional_info.lower() or "角" in additional_info:
                    shape = "square"

                parsed_material = {
                    'original_text': material_text,
                    'material_name': material_name,
                    'shape': shape,
                    'diameter_mm': size,
                    'additional_info': additional_info,
                    'row_number': index + 1
                }

            # パターン2：Hex記法
            if not parsed_material:
                match = re.match(r'^(.+?)\s+Hex\s*(\d+(?:\.\d+)?)\s*(.*)$', material_text)
                if match:
                    material_name = match.group(1).strip()
                    size = float(match.group(2))

                    parsed_material = {
                        'original_text': material_text,
                        'material_name': material_name,
                        'shape': 'hexagon',
                        'diameter_mm': size,
                        'additional_info': match.group(3).strip(),
                        'row_number': index + 1
                    }

            # パターン3：その他の記法
            if not parsed_material:
                # サイズを抽出（数字部分）
                size_match = re.search(r'(\d+(?:\.\d+)?)', material_text)
                if size_match:
                    size = float(size_match.group(1))

                    # 材質名を抽出（最初の単語）
                    words = material_text.split()
                    material_name = words[0] if words else material_text

                    # 形状判定のヒント
                    shape_hints = {
                        'hex': 'hexagon',
                        '六角': 'hexagon',
                        'square': 'square',
                        '角': 'square',
                        'round': 'round',
                        '丸': 'round'
                    }

                    shape = 'round'  # デフォルト
                    for hint, shape_value in shape_hints.items():
                        if hint.lower() in material_text.lower():
                            shape = shape_value
                            break

                    parsed_material = {
                        'original_text': material_text,
                        'material_name': material_name,
                        'shape': shape,
                        'diameter_mm': size,
                        'additional_info': material_text.replace(material_name, '').replace(str(size), '').strip(),
                        'row_number': index + 1
                    }

            if parsed_material:
                materials.append(parsed_material)

        return materials

    except Exception as e:
        print(f"CSV解析エラー: {e}")
        return []

def get_unique_materials(materials: List[Dict]) -> List[Dict]:
    """
    重複を除去してユニークな材料のみを返す
    """
    unique_materials = []
    seen = set()

    for material in materials:
        # 材質名、形状、サイズの組み合わせで重複チェック
        key = (material['material_name'], material['shape'], material['diameter_mm'])

        if key not in seen:
            seen.add(key)
            unique_materials.append(material)

    return unique_materials

@router.post("/import-csv")
async def import_materials_from_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    CSVファイルから材料を一括インポート
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSVファイルのみ対応しています"
        )

    try:
        # 一時ファイルに保存
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.csv', delete=False) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name

        try:
            # CSVを解析
            raw_materials = parse_materials_csv(tmp_file_path)
            unique_materials = get_unique_materials(raw_materials)

            # デフォルト比重を設定
            default_densities = {
                'ASK2600S': 7.85,  # 炭素鋼
                'C3604Lcd': 8.49,  # 黄銅
                'C3604': 8.49,     # 黄銅
                'C3602Lcd': 8.49,  # 黄銅
                'SUS303': 7.93,    # ステンレス
                'SUS304': 7.93,    # ステンレス
                'SUS440C': 7.70,   # ステンレス
                'S45CFS': 7.85,    # 炭素鋼
                'S45CF': 7.85,     # 炭素鋼
                'C5191': 8.80,     # リン青銅
                'SF-20T': 7.85,    # 炭素鋼
                '1144': 7.85,      # 炭素鋼
                'TLS': 7.85,       # 炭素鋼
                'G23-T8': 7.85,    # 炭素鋼
                'ASK2200R': 7.85   # 炭素鋼
            }

            imported_count = 0
            skipped_count = 0
            errors = []

            for material_data in unique_materials:
                try:
                    # デフォルト比重を設定
                    base_name = material_data['material_name'].split()[0] if material_data['material_name'] else ''
                    density = default_densities.get(base_name, 7.85)

                    # 同じ材質・形状・寸法の材料が既に存在するかチェック
                    existing = db.query(Material).filter(
                        Material.name == material_data['material_name'],
                        Material.shape == MaterialShape(material_data['shape']),
                        Material.diameter_mm == material_data['diameter_mm'],
                        Material.is_active == True
                    ).first()

                    if existing:
                        skipped_count += 1
                        continue

                    # 新しい材料を作成
                    db_material = Material(
                        name=material_data['material_name'],
                        shape=MaterialShape(material_data['shape']),
                        diameter_mm=material_data['diameter_mm'],
                        current_density=density,
                        description=f"CSVからインポート: {material_data['original_text']}",
                        is_active=True
                    )

                    db.add(db_material)
                    db.flush()  # IDを取得するためにflush

                    # 比重履歴にも記録
                    density_record = Density(
                        material_id=db_material.id,
                        density=density,
                        effective_from=datetime.now(),
                        created_by=1  # TODO: 認証実装後にユーザーIDを設定
                    )
                    db.add(density_record)

                    imported_count += 1

                except Exception as e:
                    errors.append(f"行 {material_data['row_number']}: {str(e)}")

            db.commit()

            return {
                "message": f"インポート完了: {imported_count} 件インポート、{skipped_count} 件スキップ",
                "imported_count": imported_count,
                "skipped_count": skipped_count,
                "total_processed": len(unique_materials),
                "errors": errors
            }

        finally:
            # 一時ファイルを削除
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CSVインポートエラー: {str(e)}"
        )
