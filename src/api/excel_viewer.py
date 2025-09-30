"""
Excel直接ビューア API

Excelファイルを直接読み込み、在庫との照合結果を返すシンプルなAPI
"""

import pandas as pd
import tempfile
import os
import re
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel

from src.db import get_db
from src.db.models import Material, Item, Lot, MaterialShape, UsageType

router = APIRouter(prefix="/api/excel-viewer", tags=["excel-viewer"])

class ExcelRowResponse(BaseModel):
    row_number: int
    schedule_date: Optional[str]
    item_code: Optional[str]
    material_spec: Optional[str]
    required_quantity: Optional[float]
    current_stock: int
    shortage: int
    stock_status: str  # "sufficient", "shortage", "unknown"

def parse_material_info(material_spec: str) -> Dict[str, Any]:
    """
    材料仕様文字列を解析

    例:
    - SUS303 ∅10.0CM → {material_name: 'SUS303', diameter: 10.0, shape: round}
    - C3602Lcd ∅12.0 (NB5N) → {material_name: 'C3602LCD', diameter: 12.0, shape: round, dedicated_part_number: 'NB5N'}
    """
    if not material_spec or pd.isna(material_spec):
        return None

    material_spec = str(material_spec).strip()

    # 専用品番の抽出（カッコ内）
    dedicated_part_number = None
    dedicated_match = re.search(r'\(([^)]+)\)', material_spec)
    if dedicated_match:
        dedicated_part_number = dedicated_match.group(1).strip()

    # パターンマッチング（実際のExcelデータに合わせて調整）
    patterns = [
        # SUS303 ∅10.0CM の形式
        r'^(SUS\d+[A-Za-z]*)\s*[∅φΦ]?(\d+(?:\.\d+)?)(?:CM|cm)?',
        # C3602Lcd ∅12.0 の形式
        r'^(C\d+[A-Za-z]*)\s*[∅φΦ]?(\d+(?:\.\d+)?)',
        # その他の材質
        r'^([A-Z]+\d+[A-Za-z]*)\s*[∅φΦ]?(\d+(?:\.\d+)?)',
    ]

    for pattern in patterns:
        match = re.search(pattern, material_spec, re.IGNORECASE)
        if match:
            material_name = match.group(1).upper()
            diameter = float(match.group(2))

            # 材料名の正規化
            material_name = material_name.replace('Lcd', 'LCD')
            if material_name.startswith('C3602LCD') or material_name.startswith('C3602Lcd'):
                material_name = 'C3602LCD'

            return {
                'material_name': material_name,
                'diameter': diameter,
                'shape': MaterialShape.ROUND,  # 基本的に丸棒と仮定
                'dedicated_part_number': dedicated_part_number
            }

    return None

def get_current_stock(db: Session, material_info: Dict[str, Any]) -> int:
    """
    指定された材料の現在在庫数を取得

    汎用材料: 材質名・形状・寸法が一致すれば在庫を集計
    専用材料: 上記に加えて専用品番も一致する場合のみ在庫を集計
    """
    if not material_info:
        return 0

    try:
        dedicated_part_number = material_info.get('dedicated_part_number')

        # 基本条件で材料を検索
        query = db.query(Material).filter(
            Material.name == material_info['material_name'],
            Material.diameter_mm == material_info['diameter'],
            Material.shape == material_info['shape'],
            Material.is_active == True
        )

        # 専用品番が指定されている場合
        if dedicated_part_number:
            # 専用材料で専用品番が一致するもの、または汎用材料
            query = query.filter(
                (Material.usage_type == UsageType.DEDICATED) & (Material.dedicated_part_number == dedicated_part_number) |
                (Material.usage_type == UsageType.GENERAL)
            )
        else:
            # 汎用材料のみ
            query = query.filter(Material.usage_type == UsageType.GENERAL)

        materials = query.all()

        if not materials:
            return 0

        # すべてのマッチした材料の在庫を合計
        total_stock = 0
        for material in materials:
            stock = db.query(func.sum(Item.current_quantity)).join(
                Lot, Item.lot_id == Lot.id
            ).filter(
                Lot.material_id == material.id,
                Item.is_active == True
            ).scalar()

            total_stock += (stock or 0)

        return total_stock

    except Exception as e:
        print(f"在庫取得エラー: {e}")
        import traceback
        traceback.print_exc()
        return 0

@router.post("/analyze")
async def analyze_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
) -> List[ExcelRowResponse]:
    """
    Excelファイルを解析して在庫照合結果を返す
    """

    if not file.filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="Excelファイル(.xlsx)をアップロードしてください")

    try:
        # 一時ファイルに保存
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as temp_file:
            temp_file.write(await file.read())
            temp_path = temp_file.name

        # Excelファイルを読み込み
        df = pd.read_excel(temp_path, sheet_name='セット予定')

        results = []

        for index, row in df.iterrows():
            # 重要な列を取得
            schedule_date = row.iloc[3] if len(row) > 3 else None  # D列
            item_code = row.iloc[8] if len(row) > 8 else None      # I列
            material_spec = row.iloc[11] if len(row) > 11 else None # L列
            required_qty = row.iloc[27] if len(row) > 27 else None  # AB列

            # 空行をスキップ
            if pd.isna(item_code) and pd.isna(material_spec):
                continue

            # 材料情報を解析
            material_info = parse_material_info(material_spec)

            # 在庫数を取得
            current_stock = get_current_stock(db, material_info)

            # 必要数量の処理
            if pd.isna(required_qty):
                required_quantity = None
                shortage = 0
                stock_status = "unknown"
            else:
                required_quantity = float(required_qty)
                shortage = max(0, int(required_quantity) - current_stock)
                if current_stock >= required_quantity:
                    stock_status = "sufficient"
                elif current_stock > 0:
                    stock_status = "partial"
                else:
                    stock_status = "shortage"

            # 日付の処理
            if pd.isna(schedule_date):
                formatted_date = None
            else:
                try:
                    if hasattr(schedule_date, 'strftime'):
                        formatted_date = schedule_date.strftime('%Y-%m-%d')
                    else:
                        formatted_date = str(schedule_date)
                except:
                    formatted_date = str(schedule_date)

            results.append(ExcelRowResponse(
                row_number=index + 1,
                schedule_date=formatted_date,
                item_code=str(item_code) if not pd.isna(item_code) else None,
                material_spec=str(material_spec) if not pd.isna(material_spec) else None,
                required_quantity=required_quantity,
                current_stock=current_stock,
                shortage=shortage,
                stock_status=stock_status
            ))

        # 一時ファイルを削除
        os.unlink(temp_path)

        return results

    except Exception as e:
        # 一時ファイルを削除
        if 'temp_path' in locals():
            try:
                os.unlink(temp_path)
            except:
                pass

        raise HTTPException(status_code=500, detail=f"Excel解析エラー: {str(e)}")