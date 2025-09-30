#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
材料CSVインポートのテストスクリプト
dedicated_part_number フィールドに正しく保存されているか確認
"""

import sys
sys.path.append('.')

from src.db.models import Material, UsageType
from src.db import SessionLocal

def check_imported_materials():
    """インポートされた材料のdedicated_part_numberを確認"""
    db = SessionLocal()
    try:
        # 最初の20件の材料を取得
        materials = db.query(Material).limit(20).all()

        print("=" * 80)
        print("材料データ確認（最初の20件）")
        print("=" * 80)

        for i, material in enumerate(materials, 1):
            print(f"\n{i}. 材質名: {material.name}")
            print(f"   品番: {material.part_number or '(なし)'}")
            print(f"   形状: {material.shape.value}")
            print(f"   寸法: {material.diameter_mm}mm")
            print(f"   用途: {material.usage_type.value}")
            print(f"   専用品番・追加情報: {material.dedicated_part_number or '(なし)'}")
            print(f"   説明: {material.description or '(なし)'}")

        print("\n" + "=" * 80)

        # dedicated_part_numberが設定されている材料をカウント
        with_dedicated = db.query(Material).filter(Material.dedicated_part_number.isnot(None)).count()
        total = db.query(Material).count()

        print(f"\n統計:")
        print(f"  総材料数: {total}")
        print(f"  専用品番・追加情報あり: {with_dedicated}")
        print(f"  専用品番・追加情報なし: {total - with_dedicated}")
        print("=" * 80)

    finally:
        db.close()

if __name__ == '__main__':
    check_imported_materials()
