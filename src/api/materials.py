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
    part_number: Optional[str] = Field(None, max_length=100, description="品番")
    name: str = Field(..., max_length=100, description="材質名（例：S45C）")
    description: Optional[str] = Field(None, description="説明")
    shape: MaterialShape = Field(..., description="断面形状")
    diameter_mm: float = Field(..., gt=0, description="直径または一辺の長さ（mm）")
    current_density: float = Field(..., gt=0, description="現在の比重（g/cm³）")

class MaterialCreate(MaterialBase):
    pass

class MaterialUpdate(BaseModel):
    part_number: Optional[str] = Field(None, max_length=100, description="品番")
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
        query = query.filter(Material.part_number.contains(part_number))

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
        query = query.filter(Material.part_number.contains(part_number))

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

    db_material = Material(**material.model_dump())
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

def parse_material_text(material_text: str) -> Dict:
    """
    材料名テキストから形状、寸法、材質名を解析する

    解析パターン:
    - SUS303 ∅10.0CM → 材質: SUS303, 形状: round, 直径: 10.0mm
    - C3602Lcd ∅12.0 → 材質: C3602Lcd, 形状: round, 直径: 12.0mm
    - S45C □15 → 材質: S45C, 形状: square, 一辺: 15mm
    - SUS304 六角 10 → 材質: SUS304, 形状: hexagon, 対辺距離: 10mm
    """
    result = {
        'material_name': '',
        'shape': 'round',  # デフォルト
        'diameter_mm': None,
        'parsed_successfully': False
    }

    # テキストをクリーニング
    text = material_text.strip().upper()

    # 材質名の抽出（英数字と一部記号のみ）
    material_name_match = re.match(r'^([A-Z0-9\-]+(?:FS|CF|LCD|T)?)', text)
    if material_name_match:
        result['material_name'] = material_name_match.group(1)
    else:
        result['material_name'] = text[:20]  # 最初の20文字を材質名とする

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
        r'(\d+\.?\d*)\s*[Mm][Mm]',  # 10.0mm, 12MM 等
        r'(\d+\.?\d*)\s*CM',      # 10.0CM 等（mmとして扱う）
        r'[^\d](\d+\.?\d*)[^\d]',  # 数字のみ（前後に数字以外）
        r'^(\d+\.?\d*)',          # 先頭の数字
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

def parse_materials_csv(file_path: str) -> List[Dict]:
    """
    材料マスターCSVファイルを解析し、形状・寸法・比重を自動抽出する
    解析できない項目はデフォルト値（NULL or ユーザー設定可能な値）を設定
    """
    try:
        # エンコーディングを試行しながらCSVを読み込み
        encodings = ['utf-8', 'cp932', 'shift_jis', 'utf-8-sig']
        df = None

        for encoding in encodings:
            try:
                df = pd.read_csv(file_path, encoding=encoding)
                break
            except UnicodeDecodeError:
                continue

        if df is None:
            # 最後の手段でヘッダーなしで読み込み
            df = pd.read_csv(file_path, header=None, encoding='utf-8', errors='ignore')

        materials = []

        # データフレームの列数を確認
        num_columns = len(df.columns)

        # ヘッダーが存在する場合の判定
        has_header = False
        part_number_col = None
        material_col = None

        if num_columns >= 2:
            # ヘッダー行をチェック
            if any('品番' in str(col).lower() or 'part' in str(col).lower() for col in df.columns):
                has_header = True
                # 品番列と材料列を特定
                for i, col in enumerate(df.columns):
                    col_str = str(col).lower()
                    if '品番' in col_str or 'part' in col_str:
                        part_number_col = i
                    elif '材質' in col_str or '材料' in col_str:
                        material_col = i

            # ヘッダーがない場合のデフォルト設定
            if not has_header:
                material_col = 0  # 1列目を材料とする
                if num_columns >= 2:
                    part_number_col = 1  # 2列目を品番とする

        start_row = 1 if has_header else 0

        for index in range(start_row, len(df)):
            row = df.iloc[index]

            # 材料名を取得
            if material_col is not None and material_col < len(row):
                material_text = str(row.iloc[material_col]).strip() if pd.notna(row.iloc[material_col]) else ''
            else:
                material_text = str(row.iloc[0]).strip() if len(row) > 0 and pd.notna(row.iloc[0]) else ''

            # 品番を取得
            part_number = ''
            if part_number_col is not None and part_number_col < len(row):
                part_number = str(row.iloc[part_number_col]).strip() if pd.notna(row.iloc[part_number_col]) else ''

            # 空行やヘッダー行をスキップ
            if not material_text or material_text in ['材質＆材料径', '材料名', '材質&材料径']:
                continue

            # 材料名から形状・寸法を解析
            parsed = parse_material_text(material_text)

            # 解析できなかった場合のデフォルト値
            # diameter_mm が None の場合は 1.0 をデフォルト値として設定（ユーザーが後で修正可能）
            diameter = parsed['diameter_mm'] if parsed['diameter_mm'] is not None else 1.0

            parsed_material = {
                'original_text': material_text,
                'part_number': part_number if part_number else None,
                'material_name': material_text,  # 元の表記をそのまま使用
                'shape': parsed['shape'],
                'diameter_mm': diameter,
                'parsed_successfully': parsed['parsed_successfully'],
                'additional_info': '' if parsed['parsed_successfully'] else '要確認：寸法未解析',
                'row_number': index + 1
            }

            materials.append(parsed_material)

            status = "✓ 解析成功" if parsed['parsed_successfully'] else "⚠ 要確認"
            print(f"{status}: 品番='{part_number}', 材料名='{material_text}', 形状={parsed['shape']}, 寸法={diameter}mm")

        return materials

    except Exception as e:
        print(f"CSV解析エラー: {e}")
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
            print(f"解析された材料数: {len(raw_materials)}")

            unique_materials = get_unique_materials(raw_materials)
            print(f"重複除去後の材料数: {len(unique_materials)}")

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

            for material_data in unique_materials:
                try:
                    # 比重を自動判定（材質名から検索）
                    density = None  # まず None で初期化
                    material_text = material_data['material_name'].upper()

                    # 各材質名がCSVテキストに含まれているかチェック（前方一致優先）
                    for material_key, material_density in default_densities.items():
                        if material_key.upper() in material_text:
                            density = material_density
                            break

                    # 比重が見つからない場合のデフォルト値
                    if density is None:
                        density = 7.85  # 炭素鋼のデフォルト値
                        parse_warnings.append(f"行 {material_data['row_number']}: 比重不明（デフォルト 7.85 を設定） - {material_text}")

                    # 寸法が解析できなかった場合の警告
                    if not material_data['parsed_successfully']:
                        parse_warnings.append(f"行 {material_data['row_number']}: 寸法未解析（デフォルト 1.0mm を設定） - {material_data['original_text']}")

                    # 重複チェックを無効化 - すべての材料を登録

                    # 新しい材料を作成
                    db_material = Material(
                        part_number=material_data.get('part_number') if material_data.get('part_number') else None,
                        name=material_data['material_name'],
                        shape=MaterialShape(material_data['shape']),
                        diameter_mm=material_data['diameter_mm'],
                        current_density=density,
                        description=f"CSVからインポート: {material_data['original_text']}",
                        is_active=True
                    )

                    db.add(db_material)
                    db.flush()  # IDを取得するためにflush

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

                except Exception as e:
                    errors.append(f"行 {material_data['row_number']}: {str(e)}")

            db.commit()

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
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CSVインポートエラー: {str(e)}"
        )
