from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request, Query
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
from src.db.models import (
    Material, MaterialShape, Density,
    MaterialStandard, MaterialGrade, MaterialProduct, MaterialAlias
)

router = APIRouter()

# ========================================
# 標準規格管理用 Pydantic スキーマ（簡素化）
# ========================================

class MaterialStandardBase(BaseModel):
    jis_code: str = Field(..., max_length=50, description="JIS規格コード（例: SUS303, C3604）")
    jis_name: str = Field(..., max_length=100, description="JIS規格名称")
    category: Optional[str] = Field(None, max_length=50, description="カテゴリ（ステンレス/黄銅/炭素鋼等）")
    description: Optional[str] = Field(None, description="説明")

class MaterialStandardCreate(MaterialStandardBase):
    pass

class MaterialStandardResponse(MaterialStandardBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

class MaterialGradeBase(BaseModel):
    standard_id: int = Field(..., description="標準規格ID")
    grade_code: str = Field(..., max_length=50, description="グレードコード（例: LCD, 標準）")
    characteristics: Optional[str] = Field(None, max_length=200, description="特性（快削性、耐食性等）")
    description: Optional[str] = Field(None, description="説明")

class MaterialGradeCreate(MaterialGradeBase):
    pass

class MaterialGradeResponse(MaterialGradeBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

class MaterialProductBase(BaseModel):
    grade_id: int = Field(..., description="グレードID")
    product_code: str = Field(..., max_length=100, description="製品コード（例: ASK3000, C3604LCD）")
    manufacturer: Optional[str] = Field(None, max_length=200, description="メーカー名")
    is_equivalent: bool = Field(False, description="同等品フラグ")
    description: Optional[str] = Field(None, description="説明")

class MaterialProductCreate(MaterialProductBase):
    pass

class MaterialProductResponse(MaterialProductBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

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
    product_id: Optional[int] = Field(None, description="製品ID（第3層との紐付け）")
    part_number: Optional[str] = Field(None, max_length=100, description="品番")
    name: str = Field(..., max_length=100, description="材質名（例：S45C）")
    display_name: Optional[str] = Field(None, max_length=200, description="表示名（表記揺れ対応: φ10.0D等）")
    detail_info: Optional[str] = Field(None, max_length=200, description="詳細情報（寸法以降の補足）")
    description: Optional[str] = Field(None, description="説明")
    shape: MaterialShape = Field(..., description="断面形状")
    diameter_mm: float = Field(..., gt=0, description="直径または一辺の長さ（mm）")
    current_density: float = Field(..., gt=0, description="現在の比重（g/cm³）")
    dedicated_part_number: Optional[str] = Field(None, max_length=100, description="専用品番")

class MaterialCreate(MaterialBase):
    pass

class MaterialUpdate(BaseModel):
    product_id: Optional[int] = Field(None, description="製品ID（第3層との紐付け）")
    part_number: Optional[str] = Field(None, max_length=100, description="品番")
    name: Optional[str] = Field(None, max_length=100, description="材質名")
    display_name: Optional[str] = Field(None, max_length=200, description="表示名（表記揺れ対応）")
    detail_info: Optional[str] = Field(None, max_length=200, description="詳細情報（寸法以降の補足）")
    description: Optional[str] = Field(None, description="説明")
    shape: Optional[MaterialShape] = Field(None, description="断面形状")
    diameter_mm: Optional[float] = Field(None, gt=0, description="直径または一辺の長さ（mm）")
    current_density: Optional[float] = Field(None, gt=0, description="現在の比重（g/cm³）")
    dedicated_part_number: Optional[str] = Field(None, max_length=100, description="専用品番")
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
    request: Request,
    skip: int = 0,
    limit: int = 100,  # ページネーション用に100件制限
    is_active: Optional[bool] = None,
    shape: Optional[MaterialShape] = None,
    name: Optional[str] = None,
    part_number: Optional[str] = None,
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

    if part_number is not None:
        query = query.filter(Material.part_number == part_number)

    # 部分一致検索用パラメータ（フロントエンド予測入力用）
    part_number_contains = request.query_params.get("part_number_contains")
    if part_number_contains is not None:
        query = query.filter(Material.part_number.contains(part_number_contains))

    if diameter_mm is not None:
        query = query.filter(Material.diameter_mm == diameter_mm)

    materials = query.offset(skip).limit(limit).all()
    return materials

@router.get("/count")
async def get_materials_count(
    is_active: Optional[bool] = None,
    shape: Optional[MaterialShape] = None,
    name: Optional[str] = None,
    part_number: Optional[str] = None,
    diameter_mm: Optional[float] = None,
    db: Session = Depends(get_db)
):
    """材料総件数取得"""
    query = db.query(Material)

    if is_active is not None:
        query = query.filter(Material.is_active == is_active)

    if shape is not None:
        query = query.filter(Material.shape == shape)

    if name is not None:
        query = query.filter(Material.name.contains(name))

    if part_number is not None:
        query = query.filter(Material.part_number == part_number)

    if diameter_mm is not None:
        query = query.filter(Material.diameter_mm == diameter_mm)

    count = query.count()
    return {"total": count}

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
    # 重複チェックを無効化 - すべての材料登録を許可

    # 説明フィールドが空文字列の場合はNoneに設定
    material_data = material.model_dump()
    if material_data.get('description') == "":
        material_data['description'] = None
    if material_data.get('detail_info') == "":
        material_data['detail_info'] = None

    db_material = Material(**material_data)
    db.add(db_material)
    db.commit()
    db.refresh(db_material)

    # 比重履歴の記録は一旦スキップ（created_by制約のため）
    # TODO: 認証実装後に比重履歴機能を有効化
    # density_record = Density(
    #     material_id=db_material.id,
    #     density=material.current_density,
    #     effective_from=datetime.now(),
    #     created_by=1
    # )
    # db.add(density_record)
    # db.commit()

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

    # 説明フィールドが空文字列の場合は適切に処理
    if 'description' in update_data and update_data['description'] == "":
        update_data['description'] = None
    if 'detail_info' in update_data and update_data['detail_info'] == "":
        update_data['detail_info'] = None

    for field, value in update_data.items():
        setattr(db_material, field, value)

    db.commit()
    db.refresh(db_material)

    # 比重履歴の記録は一旦スキップ（created_by制約のため）
    # TODO: 認証実装後に比重履歴機能を有効化
    # if 'current_density' in update_data and update_data['current_density'] != old_density:
    #     density_record = Density(
    #         material_id=material_id,
    #         density=update_data['current_density'],
    #         effective_from=datetime.now(),
    #         created_by=1
    #     )
    #     db.add(density_record)
    #     db.commit()

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

def parse_material_name(material_name: str) -> str:
    """
    材質名を正規化する

    例: C3604Lcd → C3604LCD, SUS303 → SUS303
    """
    if not material_name or pd.isna(material_name):
        return ''

    name = str(material_name).strip().upper()

    # LCDの正規化
    name = name.replace('Lcd', 'LCD')

    return name

def parse_dimension_text(dimension_text: str) -> Dict:
    """
    寸法・形状テキストから形状と寸法を解析する

    解析パターン:
    - ∅10.0CM → 形状: round, 直径: 10.0mm
    - ∅12.0 → 形状: round, 直径: 12.0mm
    - Hex4.0 → 形状: hexagon, 対辺距離: 4.0mm
    - □15 → 形状: square, 一辺: 15mm
    """
    result = {
        'shape': 'round',  # デフォルト
        'diameter_mm': None,
        'parsed_successfully': False
    }

    if not dimension_text or pd.isna(dimension_text):
        return result

    # テキストをクリーニング
    text = str(dimension_text).strip().upper()

    # 形状の判定
    if '□' in text or 'SQUARE' in text or '角' in text:
        result['shape'] = 'square'
    elif '六角' in text or 'HEX' in text or 'HEXAGON' in text:
        result['shape'] = 'hexagon'
    else:
        result['shape'] = 'round'  # デフォルトは丸棒

    # 寸法の抽出（複数パターン対応）
    diameter_patterns = [
        r'[∅Φφ]\s*(\d+\.?\d*)',  # ∅10.0, Φ12 等
        r'[□]\s*(\d+\.?\d*)',     # □15 等
        r'HEX\s*(\d+\.?\d*)',     # Hex4.0 等
        r'(\d+\.?\d*)\s*[Mm][Mm]',  # 10.0mm, 12MM 等
        r'(\d+\.?\d*)\s*CM',      # 10.0CM 等（mmとして扱う）
        r'(\d+\.?\d*)',           # 数字のみ
    ]

    for pattern in diameter_patterns:
        match = re.search(pattern, text)
        if match:
            try:
                diameter = float(match.group(1))
                if 0.1 <= diameter <= 500:  # 妥当な範囲の寸法のみ
                    result['diameter_mm'] = diameter
                    result['parsed_successfully'] = True
                    break
            except (ValueError, IndexError):
                continue

    return result

def parse_material_specification(spec_text: str) -> Dict[str, Optional[str]]:
    """
    材質＆材料径テキストを解析（convert_material_master.pyから移植）

    例:
    - SUS303 φ8.0CM → 材質名: SUS303, 寸法: φ8.0, 追加情報: CM
    - C3604Lcd φ6.0 平目 22山 → 材質名: C3604LCD, 寸法: φ6.0, 追加情報: 平目 22山
    - ASK2600S φ8.0CM → 材質名: ASK2600S, 寸法: φ8.0, 追加情報: CM
    - SUS440C φ6.0G  2m → 材質名: SUS440C, 寸法: φ6.0, 追加情報: G 2m
    - C3604Lcd Hex4.0 → 材質名: C3604LCD, 寸法: Hex4.0, 追加情報: なし
    """
    if not spec_text or pd.isna(spec_text):
        return {
            'material_name': None,
            'dimension': None,
            'additional_info': None
        }

    text = str(spec_text).strip()

    # 材質名の抽出（先頭の英数字部分）
    material_match = re.match(r'^([A-Z0-9\-]+(?:FS|CF|LCD|Lcd|T)?)', text, re.IGNORECASE)
    material_name = material_match.group(1).upper().replace('Lcd', 'LCD') if material_match else None

    if not material_name:
        # 材質名が抽出できない場合は全体を材質名として扱う
        return {
            'material_name': text[:50],  # 最大50文字
            'dimension': None,
            'additional_info': None
        }

    # 材質名以降の部分
    remaining = text[len(material_match.group(1)):].strip()

    # 寸法の抽出（複数パターン）
    dimension = None
    dimension_patterns = [
        r'([∅Φφ]\s*\d+\.?\d*)',           # ∅10.0, φ8.0
        r'(Hex\s*\d+\.?\d*)',              # Hex4.0
        r'([□]\s*\d+\.?\d*)',              # □15
        r'(\d+\.?\d*\s*[Mm][Mm])',        # 10.0mm
    ]

    dimension_match = None
    for pattern in dimension_patterns:
        match = re.search(pattern, remaining, re.IGNORECASE)
        if match:
            dimension_match = match
            dimension = match.group(1).strip()
            break

    # 追加情報の抽出（寸法以外の部分）
    additional_info = None
    if dimension_match:
        # 寸法の前と後ろの部分を結合
        before = remaining[:dimension_match.start()].strip()
        after = remaining[dimension_match.end():].strip()

        parts = []
        if before:
            parts.append(before)
        if after:
            parts.append(after)

        if parts:
            additional_info = ' '.join(parts)
    else:
        # 寸法が見つからない場合、残り全体を追加情報として扱う
        if remaining:
            additional_info = remaining

    return {
        'material_name': material_name,
        'dimension': dimension,
        'additional_info': additional_info if additional_info else None
    }

def parse_materials_csv(file_path: str) -> List[Dict]:
    """
    材料マスターCSVファイルを解析し、形状・寸法・比重を自動抽出する

    対応CSV形式:
    1. 新形式（標準）:
       - 1列目: 材質名（例: C3604, SUS303）
       - 2列目: 形状・寸法（例: ∅6.0, ∅8.0CM, Hex4.0）
       - 3列目: 品番（管理用）
       - 4列目: 用途区分（汎用 or 専用）
       - 5列目: 専用品番（専用材料の場合のみ）

    2. 原始形式（製品番号,材質＆材料径）:
       - 1列目: 製品番号
       - 2列目: 材質＆材料径（例: SUS303 φ8.0CM）
    """
    print(f"[DEBUG] parse_materials_csv開始: {file_path}")

    try:
        # エンコーディングを試行しながらCSVを読み込み
        encodings = ['utf-8', 'cp932', 'shift_jis', 'utf-8-sig']
        df = None

        print(f"[DEBUG] CSV読み込み試行開始")
        for encoding in encodings:
            try:
                print(f"[DEBUG] エンコーディング試行: {encoding}")
                df = pd.read_csv(file_path, encoding=encoding, header=0)
                print(f"[DEBUG] エンコーディング成功: {encoding}")
                break
            except UnicodeDecodeError as e:
                print(f"[DEBUG] エンコーディング失敗 {encoding}: {e}")
                continue
            except Exception as e:
                print(f"[DEBUG] その他のエラー {encoding}: {e}")
                continue

        if df is None:
            error_msg = "CSVファイルの読み込みに失敗しました"
            print(f"[ERROR] {error_msg}")
            raise ValueError(error_msg)

        print(f"[DEBUG] CSV読み込み成功: 行数={len(df)}, 列数={len(df.columns)}")
        materials = []

        # CSV形式を判定（列名で判断）
        columns = list(df.columns)
        print(f"CSV列名: {columns}")

        # 原始形式の判定（製品番号,材質＆材料径）
        is_original_format = False
        if len(columns) >= 2:
            first_col = str(columns[0]).strip().lower()
            second_col = str(columns[1]).strip().lower()
            if ('製品番号' in first_col or '製品' in first_col) and ('材質' in second_col and '材料径' in second_col):
                is_original_format = True
                print("原始形式（製品番号,材質＆材料径）を検出しました")
            else:
                print("新形式（材質名,形状・寸法）を検出しました")

        print(f"[DEBUG] CSV形式判定開始: 列数={len(df.columns)}, 列名={list(df.columns)}")

        # CSV形式を判定（列名で判断）
        columns = list(df.columns)
        print(f"[DEBUG] CSV列名: {columns}")

        # 原始形式の判定（製品番号,材質＆材料径）
        is_original_format = False
        if len(columns) >= 2:
            first_col = str(columns[0]).strip().lower()
            second_col = str(columns[1]).strip().lower()
            print(f"[DEBUG] 列名チェック: 1列目='{first_col}', 2列目='{second_col}'")
            if ('製品番号' in first_col or '製品' in first_col) and ('材質' in second_col and '材料径' in second_col):
                is_original_format = True
                print("[DEBUG] 原始形式（製品番号,材質＆材料径）を検出しました")
            else:
                print("[DEBUG] 新形式（材質名,形状・寸法）を検出しました")

        if is_original_format:
            # 原始形式の処理
            print(f"[DEBUG] 原始形式で処理開始、総行数: {len(df)}")

            for index, row in df.iterrows():
                try:
                    print(f"[DEBUG] 処理中: 行 {index + 2}")

                    # 製品番号を取得（1列目）
                    product_number = None
                    if len(row) >= 1 and not pd.isna(row.iloc[0]):
                        product_number = str(row.iloc[0]).strip()
                        print(f"[DEBUG] 製品番号: '{product_number}'")

                    # 材質＆材料径を取得（2列目）
                    if len(row) < 2:
                        print(f"[WARN] 行 {index + 2}: 列数不足")
                        continue

                    spec_text = row.iloc[1]
                    print(f"[DEBUG] 材質＆材料径: '{spec_text}'")

                    if pd.isna(spec_text) or str(spec_text).strip() == '':
                        print(f"[WARN] 行 {index + 2}: 材質＆材料径が空")
                        continue

                    # 材質＆材料径を解析
                    parsed = parse_material_specification(spec_text)
                    print(f"[DEBUG] パース結果: {parsed}")

                    if not parsed['material_name']:
                        print(f"[WARN] 行 {index + 2}: 材質名を抽出できませんでした - '{spec_text}'")
                        continue

                    # 寸法テキストを解析
                    dimension_text = parsed['dimension'] if parsed['dimension'] else None
                    print(f"[DEBUG] 寸法テキスト: '{dimension_text}'")
                    parsed_dim = parse_dimension_text(dimension_text)
                    print(f"[DEBUG] 寸法パース結果: {parsed_dim}")

                    # 解析できなかった場合のデフォルト値
                    diameter = parsed_dim['diameter_mm'] if parsed_dim['diameter_mm'] is not None else 1.0

                    parsed_material = {
                        'material_name': parsed['material_name'],
                        'shape': parsed_dim['shape'],
                        'diameter_mm': diameter,
                        'part_number': product_number,  # 製品番号を品番として使用
                        'usage_type': UsageType.GENERAL,  # デフォルトは汎用
                        'dedicated_part_number': parsed['additional_info'] if parsed['additional_info'] else None,
                        'parsed_successfully': parsed_dim['parsed_successfully'],
                        'additional_info': '' if parsed_dim['parsed_successfully'] else '要確認：寸法未解析',
                        'row_number': int(index) + 2  # ヘッダー行を考慮
                    }

                    materials.append(parsed_material)
                    print(f"[DEBUG] 材料データ追加: {parsed_material['material_name']} - {parsed_material['shape']} - {parsed_material['diameter_mm']}mm")

                    status = "✓ 解析成功" if parsed_dim['parsed_successfully'] else "⚠ 要確認"
                    usage_str = "専用" if parsed_material['dedicated_part_number'] else "汎用"
                    dedicated_info = f", 専用品番={parsed_material['dedicated_part_number']}" if parsed_material['dedicated_part_number'] else ""
                    print(f"{status}: 材質名='{parsed['material_name']}', 形状={parsed_dim['shape']}, 寸法={diameter}mm, 用途={usage_str}{dedicated_info}")

                except Exception as e:
                    print(f"[ERROR] 行 {index + 2} 処理エラー: {e}")
                    import traceback
                    traceback.print_exc()
        else:
            print("[DEBUG] 新形式処理に進みます")
            # 新形式の処理（既存の処理）
            # 列名マッピング（柔軟に対応）
            col_map = {}
            for i, col_name in enumerate(df.columns):
                col_str = str(col_name).strip().lower()
                if '材質' in col_str and '材料径' not in col_str and '寸法' not in col_str:
                    col_map['material_name'] = i
                    print(f"  材質名列: {i} ({col_name})")
                elif '寸法' in col_str or '材料径' in col_str or '形状' in col_str:
                    col_map['dimension'] = i
                    print(f"  寸法列: {i} ({col_name})")
                elif '品番' in col_str and '専用' not in col_str:
                    col_map['part_number'] = i
                    print(f"  品番列: {i} ({col_name})")
                elif '用途' in col_str or '区分' in col_str:
                    col_map['usage_type'] = i
                    print(f"  用途区分列: {i} ({col_name})")
                elif '専用品番' in col_str or ('専用' in col_str and '品番' in col_str) or '追加情報' in col_str:
                    col_map['dedicated_part_number'] = i
                    print(f"  専用品番列: {i} ({col_name})")

            # 列インデックスが見つからない場合はデフォルト設定
            if 'material_name' not in col_map:
                col_map['material_name'] = 0
                print(f"  デフォルト材質名列: 0")
            if 'dimension' not in col_map and len(df.columns) > 1:
                col_map['dimension'] = 1
                print(f"  デフォルト寸法列: 1")
            if 'part_number' not in col_map and len(df.columns) > 2:
                col_map['part_number'] = 2
                print(f"  デフォルト品番列: 2")
            if 'usage_type' not in col_map and len(df.columns) > 3:
                col_map['usage_type'] = 3
                print(f"  デフォルト用途区分列: 3")
            if 'dedicated_part_number' not in col_map and len(df.columns) > 4:
                col_map['dedicated_part_number'] = 4
                print(f"  デフォルト専用品番列: 4")

            print(f"最終的な列マッピング: {col_map}")

            for index, row in df.iterrows():
                # 材質名を取得
                material_name_raw = row.iloc[col_map['material_name']] if 'material_name' in col_map else None
                if pd.isna(material_name_raw) or str(material_name_raw).strip() == '':
                    continue  # 材質名が空の行はスキップ

                material_name = parse_material_name(material_name_raw)

                # 寸法を取得
                dimension_text = row.iloc[col_map['dimension']] if 'dimension' in col_map else None

                # 寸法が空の場合、形状・寸法列自体が空の可能性がある
                if pd.isna(dimension_text) or str(dimension_text).strip() == '':
                    dimension_text = None

                parsed_dim = parse_dimension_text(dimension_text)

                # 品番を取得
                part_number = None
                if 'part_number' in col_map:
                    part_number_raw = row.iloc[col_map['part_number']]
                    if not pd.isna(part_number_raw) and str(part_number_raw).strip() != '':
                        part_number = str(part_number_raw).strip()

                # 用途区分を取得
                usage_type = UsageType.GENERAL  # デフォルトは汎用
                if 'usage_type' in col_map:
                    usage_type_raw = row.iloc[col_map['usage_type']]
                    if not pd.isna(usage_type_raw):
                        usage_str = str(usage_type_raw).strip()
                        if '専用' in usage_str or 'dedicated' in usage_str.lower():
                            usage_type = UsageType.DEDICATED

                # 専用品番を取得
                dedicated_part_number = None
                if 'dedicated_part_number' in col_map:
                    dedicated_pn_raw = row.iloc[col_map['dedicated_part_number']]
                    if not pd.isna(dedicated_pn_raw) and str(dedicated_pn_raw).strip() != '':
                        dedicated_part_number = str(dedicated_pn_raw).strip()

                # 解析できなかった場合のデフォルト値
                diameter = parsed_dim['diameter_mm'] if parsed_dim['diameter_mm'] is not None else 1.0

                parsed_material = {
                    'material_name': material_name,
                    'shape': parsed_dim['shape'],
                    'diameter_mm': diameter,
                    'part_number': part_number,
                    'usage_type': usage_type,
                    'dedicated_part_number': dedicated_part_number,
                    'parsed_successfully': parsed_dim['parsed_successfully'],
                    'additional_info': '' if parsed_dim['parsed_successfully'] else '要確認：寸法未解析',
                    'row_number': int(index) + 2  # ヘッダー行を考慮
                }

                materials.append(parsed_material)

                status = "✓ 解析成功" if parsed_dim['parsed_successfully'] else "⚠ 要確認"
                usage_str = "専用" if usage_type == UsageType.DEDICATED else "汎用"
                dedicated_info = f", 専用品番={dedicated_part_number}" if dedicated_part_number else ""
                print(f"{status}: 材質名='{material_name}', 形状={parsed_dim['shape']}, 寸法={diameter}mm, 用途={usage_str}{dedicated_info}")

        return materials

    except Exception as e:
        print(f"CSV解析エラー: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_unique_materials(materials: List[Dict]) -> List[Dict]:
    """
    すべての材料をそのまま返す（重複除去なし）
    """
    return materials

@router.post("/import-csv")
async def import_materials_from_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    CSVファイルから材料を一括インポート

    対応するCSV形式:
    1. 新形式（標準）:
       - 1列目: 材質名（例: C3604, SUS303）
       - 2列目: 形状・寸法（例: ∅6.0, ∅8.0CM, Hex4.0）
       - 3列目: 品番（管理用）
       - 4列目: 用途区分（汎用 or 専用）
       - 5列目: 専用品番（専用材料の場合のみ）

    2. 原始形式（製品番号,材質＆材料径）:
       - 1列目: 製品番号
       - 2列目: 材質＆材料径（例: SUS303 φ8.0CM）
       ※ convert_material_master.pyによる変換をスキップして直接インポート可能
    """
    print(f"[DEBUG] import_materials_from_csv開始: {file.filename}")
    import sys
    sys.stdout.flush()  # ログを強制出力

    if not file.filename.endswith('.csv'):
        error_msg = "CSVファイルのみ対応しています"
        print(f"[ERROR] {error_msg}")
        sys.stdout.flush()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    try:
        # 一時ファイルに保存
        print(f"[DEBUG] 一時ファイル保存開始")
        sys.stdout.flush()
        try:
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.csv', delete=False) as tmp_file:
                content = await file.read()
                tmp_file.write(content)
                tmp_file_path = tmp_file.name
            print(f"[DEBUG] 一時ファイル保存完了: {tmp_file_path}")
            sys.stdout.flush()
        except Exception as e:
            print(f"[ERROR] 一時ファイル保存エラー: {e}")
            sys.stdout.flush()
            raise

        try:
            # CSVを解析
            print(f"[DEBUG] CSV解析開始: {tmp_file_path}")
            sys.stdout.flush()
            raw_materials = parse_materials_csv(tmp_file_path)
            print(f"[DEBUG] 解析完了: {len(raw_materials)} 件の材料データ")
            sys.stdout.flush()

            unique_materials = get_unique_materials(raw_materials)
            print(f"[DEBUG] 重複除去完了: {len(unique_materials)} 件の材料データ")
            sys.stdout.flush()

            # 詳細な比重データベース（材質名から自動判定）
            default_densities = {
                # ステンレス系
                'SUS303': 7.93,
                'SUS304': 7.93,
                'SUS316': 7.98,
                'SUS430': 7.70,
                'SUS440C': 7.70,
                'SUS440': 7.70,
                # 炭素鋼系
                'S45C': 7.85,
                'S45CFS': 7.85,
                'S45CF': 7.85,
                'S50C': 7.85,
                'S55C': 7.85,
                'SK': 7.85,
                'ASK2600S': 7.85,
                'ASK2200R': 7.85,
                'SF-20T': 7.85,
                '1144': 7.85,
                'TLS': 7.85,
                'G23-T8': 7.85,
                # 黄銅系
                'C3604': 8.49,
                'C3604LCD': 8.49,
                'C3602': 8.49,
                'C3602LCD': 8.49,
                'C3601': 8.49,
                # リン青銅系
                'C5191': 8.80,
                'C5212': 8.80,
                # アルミニウム系
                'A2024': 2.78,
                'A2017': 2.79,
                'A5056': 2.64,
                'A6061': 2.70,
                'A7075': 2.80,
                # チタン系
                'TI': 4.51,
                'TC4': 4.43,
            }

            imported_count = 0
            skipped_count = 0
            errors = []
            parse_warnings = []

            print(f"[DEBUG] インポート処理開始: {len(unique_materials)} 件の材料データ")

            for i, material_data in enumerate(unique_materials):
                try:
                    print(f"[DEBUG] 材料 {i+1}/{len(unique_materials)} を処理中: {material_data['material_name']}")

                    # 比重を自動判定（材質名から検索）
                    density = None  # まず None で初期化
                    material_text = material_data['material_name'].upper()
                    print(f"[DEBUG] 材質テキスト: '{material_text}'")

                    # 各材質名がCSVテキストに含まれているかチェック（前方一致優先）
                    for material_key, material_density in default_densities.items():
                        if material_key.upper() in material_text:
                            density = material_density
                            print(f"[DEBUG] 比重マッチ: {material_key} -> {material_density}")
                            break

                    # 比重が見つからない場合のデフォルト値
                    if density is None:
                        density = 7.85  # 炭素鋼のデフォルト値
                        parse_warnings.append(f"行 {material_data['row_number']}: 比重不明（デフォルト 7.85 を設定） - {material_text}")
                        print(f"[DEBUG] 比重デフォルト値設定: 7.85")

                    # 寸法が解析できなかった場合の警告
                    if not material_data['parsed_successfully']:
                        parse_warnings.append(f"行 {material_data['row_number']}: 寸法未解析（デフォルト 1.0mm を設定）")

                    # 重複チェックを無効化 - すべての材料を登録

                    # 説明フィールドはNoneに設定（CSVインポート時は説明を空に）
                    description = None

                    print(f"[DEBUG] データベースに材料を登録: {material_data['material_name']} - {material_data['shape']} - {material_data['diameter_mm']}mm")

                    # 新しい材料を作成
                    db_material = Material(
                        part_number=material_data.get('part_number') if material_data.get('part_number') else None,
                        name=material_data['material_name'],
                        shape=MaterialShape(material_data['shape']),
                        diameter_mm=material_data['diameter_mm'],
                        current_density=density,
                        usage_type=material_data['usage_type'],
                        dedicated_part_number=material_data.get('dedicated_part_number'),
                        description=description,
                        is_active=True
                    )

                    db.add(db_material)
                    db.flush()  # IDを取得するためにflush
                    print(f"[DEBUG] データベース登録成功: ID={db_material.id}")

                    # 比重履歴にも記録（created_byは一旦Noneで登録）
                    # TODO: 認証実装後に適切なユーザーIDを設定
                    # density_record = Density(
                    #     material_id=db_material.id,
                    #     density=density,
                    #     effective_from=datetime.now(),
                    #     created_by=1
                    # )
                    # db.add(density_record)

                    imported_count += 1
                    print(f"[DEBUG] インポート成功: {imported_count} 件目")

                except Exception as e:
                    print(f"[ERROR] 材料処理エラー: {e}")
                    errors.append(f"行 {material_data['row_number']}: {str(e)}")

            print(f"[DEBUG] データベースコミット開始")
            db.commit()
            print(f"[DEBUG] データベースコミット完了")

            return {
                "message": f"インポート完了: {imported_count} 件インポート、{skipped_count} 件スキップ",
                "imported_count": imported_count,
                "skipped_count": skipped_count,
                "total_processed": len(unique_materials),
                "errors": errors,
                "warnings": parse_warnings  # 解析警告を追加
            }

        finally:
            # 一時ファイルを削除
            try:
                if os.path.exists(tmp_file_path):
                    os.unlink(tmp_file_path)
                    print(f"[DEBUG] 一時ファイル削除完了: {tmp_file_path}")
                    sys.stdout.flush()
            except Exception as e:
                print(f"[WARN] 一時ファイル削除エラー: {e}")
                sys.stdout.flush()

    except Exception as e:
        print(f"[ERROR] CSVインポート処理エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CSVインポートエラー: {str(e)}"
        )

# ========================================
# 標準規格管理用 API エンドポイント（簡素化）
# ========================================

@router.get("/standards/", response_model=List[MaterialStandardResponse])
async def get_material_standards(
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """標準材質一覧取得"""
    query = db.query(MaterialStandard)

    if is_active is not None:
        query = query.filter(MaterialStandard.is_active == is_active)

    if category is not None:
        query = query.filter(MaterialStandard.category == category)

    standards = query.offset(skip).limit(limit).all()
    return standards

@router.post("/standards/", response_model=MaterialStandardResponse, status_code=status.HTTP_201_CREATED)
async def create_material_standard(
    standard: MaterialStandardCreate,
    db: Session = Depends(get_db)
):
    """標準材質作成"""
    # 重複チェック
    existing = db.query(MaterialStandard).filter(
        MaterialStandard.jis_code == standard.jis_code
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"JIS規格コード '{standard.jis_code}' は既に登録されています"
        )

    db_standard = MaterialStandard(**standard.model_dump())
    db.add(db_standard)
    db.commit()
    db.refresh(db_standard)

    return db_standard

@router.get("/grades/", response_model=List[MaterialGradeResponse])
async def get_material_grades(
    standard_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """グレード一覧取得（標準規格IDでフィルタ可能）"""
    query = db.query(MaterialGrade)

    if standard_id is not None:
        query = query.filter(MaterialGrade.standard_id == standard_id)

    if is_active is not None:
        query = query.filter(MaterialGrade.is_active == is_active)

    grades = query.offset(skip).limit(limit).all()
    return grades

@router.post("/grades/", response_model=MaterialGradeResponse, status_code=status.HTTP_201_CREATED)
async def create_material_grade(
    grade: MaterialGradeCreate,
    db: Session = Depends(get_db)
):
    """グレード作成"""
    # 標準規格存在チェック
    standard = db.query(MaterialStandard).filter(
        MaterialStandard.id == grade.standard_id
    ).first()

    if not standard:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"標準規格ID {grade.standard_id} が見つかりません"
        )

    db_grade = MaterialGrade(**grade.model_dump())
    db.add(db_grade)
    db.commit()
    db.refresh(db_grade)

    return db_grade

@router.get("/products/", response_model=List[MaterialProductResponse])
async def get_material_products(
    grade_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = None,
    is_equivalent: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """製品一覧取得（グレードIDでフィルタ可能）"""
    query = db.query(MaterialProduct)

    if grade_id is not None:
        query = query.filter(MaterialProduct.grade_id == grade_id)

    if is_active is not None:
        query = query.filter(MaterialProduct.is_active == is_active)

    if is_equivalent is not None:
        query = query.filter(MaterialProduct.is_equivalent == is_equivalent)

    products = query.offset(skip).limit(limit).all()
    return products

@router.post("/products/", response_model=MaterialProductResponse, status_code=status.HTTP_201_CREATED)
async def create_material_product(
    product: MaterialProductCreate,
    db: Session = Depends(get_db)
):
    """製品作成"""
    # グレード存在チェック
    grade = db.query(MaterialGrade).filter(
        MaterialGrade.id == product.grade_id
    ).first()

    if not grade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"グレードID {product.grade_id} が見つかりません"
        )

    db_product = MaterialProduct(**product.model_dump())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)

    return db_product

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
        (Material.name.ilike(f"%{q_upper}%")) |
        (Material.display_name.ilike(f"%{q}%")) |
        (Material.detail_info.ilike(f"%{q}%")) |
        (Material.part_number.ilike(f"%{q}%"))
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
                (Material.name.ilike(f"%{t}%")) |
                (Material.display_name.ilike(f"%{t}%")) |
                (Material.part_number.ilike(f"%{t}%"))
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
            "name": material.name,
            "display_name": material.display_name,
            "part_number": material.part_number,
            "shape": material.shape.value,
            "diameter_mm": material.diameter_mm,
            # usage_typeは廃止。グループ運用へ統一
            "hierarchy": None
        }

        # 標準規格情報の取得
        if material.product_id:
            product = db.query(MaterialProduct).filter(MaterialProduct.id == material.product_id).first()
            if product:
                grade = db.query(MaterialGrade).filter(MaterialGrade.id == product.grade_id).first()
                if grade:
                    standard = db.query(MaterialStandard).filter(MaterialStandard.id == grade.standard_id).first()
                    if standard:
                        result["hierarchy"] = {
                            "standard": {
                                "id": standard.id,
                                "jis_code": standard.jis_code,
                                "jis_name": standard.jis_name,
                                "category": standard.category
                            },
                            "grade": {
                                "id": grade.id,
                                "grade_code": grade.grade_code,
                                "characteristics": grade.characteristics
                            },
                            "product": {
                                "id": product.id,
                                "product_code": product.product_code,
                                "manufacturer": product.manufacturer,
                                "is_equivalent": product.is_equivalent
                            }
                        }

        results.append(result)

    # 既存フロントエンドは配列レスポンスを期待しているため、
    # 結果配列のみを返却（total等は不要）
    return results


