#!/usr/bin/env python3
"""
データベースリセットスクリプト

開発環境でデータベースを完全にリセットし、初期データを投入します。
"""

import sys
import os
from datetime import datetime, timedelta

# プロジェクトルートをPythonパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from src.config import settings
from src.db.models import (
    Base, User, Material, Location, Lot, Item, MaterialShape, UserRole, DensityPreset,
    PurchaseOrder, PurchaseOrderItem, PurchaseOrderStatus, PurchaseOrderItemStatus,
    MaterialStandard, MaterialGrade, MaterialProduct, MaterialAlias, UsageType
)
from src.utils.auth import get_password_hash
from src.db import SessionLocal

def drop_database():
    """データベースを削除"""
    print("データベースを削除中...")

    # データベース名を除いたURL
    db_url_without_db = f"mysql+pymysql://{settings.db_user}:{settings.db_password}@{settings.db_host}:{settings.db_port}"

    try:
        engine = create_engine(db_url_without_db)
        with engine.connect() as conn:
            # 既存の接続を強制終了
            conn.execute(text(f"DROP DATABASE IF EXISTS {settings.db_name}"))
            print(f"データベース '{settings.db_name}' を削除しました")
        engine.dispose()
    except SQLAlchemyError as e:
        print(f"データベース削除エラー: {e}")
        return False

    return True

def create_database():
    """データベースを作成"""
    print("データベースを作成中...")

    # データベース名を除いたURL
    db_url_without_db = f"mysql+pymysql://{settings.db_user}:{settings.db_password}@{settings.db_host}:{settings.db_port}"

    try:
        engine = create_engine(db_url_without_db)
        with engine.connect() as conn:
            conn.execute(text(f"CREATE DATABASE {settings.db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
            print(f"データベース '{settings.db_name}' を作成しました")
        engine.dispose()
    except SQLAlchemyError as e:
        print(f"データベース作成エラー: {e}")
        return False

    return True

def create_tables():
    """テーブルを作成"""
    print("テーブルを作成中...")

    try:
        engine = create_engine(settings.database_url)
        Base.metadata.create_all(bind=engine)
        print("テーブルの作成が完了しました")
        engine.dispose()
    except SQLAlchemyError as e:
        print(f"テーブル作成エラー: {e}")
        return False

    return True

def insert_initial_data():
    """初期データを投入"""
    print("初期データを投入中...")

    db = SessionLocal()
    try:
        # 管理者ユーザーを作成
        admin_user = User(
            username="admin",
            email="admin@example.com",
            hashed_password=get_password_hash("admin123"),
            full_name="システム管理者",
            role=UserRole.ADMIN,
            is_active=True
        )
        db.add(admin_user)

        # テストユーザーを作成
        test_users = [
            User(
                username="purchase",
                email="purchase@example.com",
                hashed_password=get_password_hash("purchase123"),
                full_name="購買担当者",
                role=UserRole.PURCHASE,
                is_active=True
            ),
            User(
                username="operator",
                email="operator@example.com",
                hashed_password=get_password_hash("operator123"),
                full_name="現場作業者",
                role=UserRole.OPERATOR,
                is_active=True
            ),
            User(
                username="viewer",
                email="viewer@example.com",
                hashed_password=get_password_hash("viewer123"),
                full_name="閲覧者",
                role=UserRole.VIEWER,
                is_active=True
            )
        ]

        for user in test_users:
            db.add(user)

        # 置き場を初期化（1〜250）
        locations = []
        for i in range(1, 251):
            location = Location(
                name=str(i),
                description=f"置き場{i}",
                is_active=True
            )
            locations.append(location)

        db.add_all(locations)

        # 比重プリセットを作成
        density_presets = [
            DensityPreset(
                name="S45C",
                density=7.85,
                description="機械構造用炭素鋼",
                is_active=True
            ),
            DensityPreset(
                name="SUS303",
                density=7.93,
                description="ステンレス鋼（快削性）",
                is_active=True
            ),
            DensityPreset(
                name="SUS304",
                density=7.93,
                description="ステンレス鋼",
                is_active=True
            ),
            DensityPreset(
                name="SUS316",
                density=8.00,
                description="ステンレス鋼（耐食性向上）",
                is_active=True
            ),
            DensityPreset(
                name="A5056",
                density=2.64,
                description="アルミニウム合金",
                is_active=True
            ),
            DensityPreset(
                name="A6061",
                density=2.70,
                description="アルミニウム合金（構造用）",
                is_active=True
            ),
            DensityPreset(
                name="C1020",
                density=8.96,
                description="銅",
                is_active=True
            ),
            DensityPreset(
                name="C3602LCD",
                density=8.50,
                description="快削黄銅（C3602Lcd）",
                is_active=True
            ),
            DensityPreset(
                name="C3604",
                density=8.50,
                description="快削黄銅",
                is_active=True
            ),
            DensityPreset(
                name="SCM440",
                density=7.85,
                description="クロムモリブデン鋼",
                is_active=True
            ),
            DensityPreset(
                name="SK3",
                density=7.84,
                description="炭素工具鋼",
                is_active=True
            ),
            DensityPreset(
                name="FC200",
                density=7.20,
                description="ねずみ鋳鉄",
                is_active=True
            )
        ]

        db.add_all(density_presets)

        # サンプル材料を作成（実際のExcelファイルに合わせた仕様）
        sample_materials = [
            # SUS303系（Excelで実際に使用されている材料）
            Material(
                name="SUS303",
                description="ステンレス鋼（SUS303）",
                shape=MaterialShape.ROUND,
                diameter_mm=5.0,
                current_density=7.93,
                is_active=True
            ),
            Material(
                name="SUS303",
                description="ステンレス鋼（SUS303）",
                shape=MaterialShape.ROUND,
                diameter_mm=10.0,
                current_density=7.93,
                is_active=True
            ),
            Material(
                name="SUS303",
                description="ステンレス鋼（SUS303）",
                shape=MaterialShape.ROUND,
                diameter_mm=12.0,
                current_density=7.93,
                is_active=True
            ),
            # C3602系（真鍮系快削材）
            Material(
                name="C3602LCD",
                description="快削黄銅（C3602Lcd）",
                shape=MaterialShape.ROUND,
                diameter_mm=12.0,
                current_density=8.5,
                is_active=True
            ),
            # その他のよく使用される材料
            Material(
                name="S45C",
                description="機械構造用炭素鋼",
                shape=MaterialShape.ROUND,
                diameter_mm=20.0,
                current_density=7.85,
                is_active=True
            ),
            Material(
                name="SUS304",
                description="ステンレス鋼（SUS304）",
                shape=MaterialShape.ROUND,
                diameter_mm=25.0,
                current_density=7.93,
                is_active=True
            ),
            Material(
                name="A5056",
                description="アルミニウム合金",
                shape=MaterialShape.HEXAGON,
                diameter_mm=30.0,
                current_density=2.64,
                is_active=True
            ),
            Material(
                name="C1020",
                description="銅",
                shape=MaterialShape.SQUARE,
                diameter_mm=15.0,
                current_density=8.96,
                is_active=True
            )
        ]

        db.add_all(sample_materials)
        db.commit()  # 材料IDを取得するために一度コミット

        # ロットサンプルデータ
        print("ロットサンプルデータを作成中...")
        from datetime import datetime, timedelta
        import random

        # 材料IDを取得（データベースから再度読み込み）
        s45c = db.query(Material).filter(Material.name == "S45C").first()
        sus303_5 = db.query(Material).filter(Material.name == "SUS303", Material.diameter_mm == 5.0).first()
        sus303_10 = db.query(Material).filter(Material.name == "SUS303", Material.diameter_mm == 10.0).first()
        sus303_12 = db.query(Material).filter(Material.name == "SUS303", Material.diameter_mm == 12.0).first()
        c3602_12 = db.query(Material).filter(Material.name == "C3602LCD", Material.diameter_mm == 12.0).first()
        sus304 = db.query(Material).filter(Material.name == "SUS304").first()
        a5056 = db.query(Material).filter(Material.name == "A5056").first()
        c1020 = db.query(Material).filter(Material.name == "C1020").first()

        print(f"材料データ確認:")
        print(f"  S45C={s45c.id if s45c else None}")
        print(f"  SUS303(5mm)={sus303_5.id if sus303_5 else None}")
        print(f"  SUS303(10mm)={sus303_10.id if sus303_10 else None}")
        print(f"  SUS303(12mm)={sus303_12.id if sus303_12 else None}")
        print(f"  C3602LCD(12mm)={c3602_12.id if c3602_12 else None}")
        print(f"  SUS304={sus304.id if sus304 else None}")

        if not all([s45c, sus303_5, sus303_10, sus303_12, c3602_12, sus304]):
            print("エラー: 必要な材料データが見つかりません")
            return False

        sample_lots = [
            # SUS303系（Excelでよく使用される材料）
            Lot(
                lot_number="SUS303-5-241001-001",
                material_id=sus303_5.id,
                length_mm=3000,
                initial_quantity=100,
                supplier="ステンレス工業",
                received_date=datetime.now() - timedelta(days=10),
                notes="SUS303 ∅5.0 標準品"
            ),
            Lot(
                lot_number="SUS303-10-241001-001",
                material_id=sus303_10.id,
                length_mm=3000,
                initial_quantity=200,
                supplier="ステンレス工業",
                received_date=datetime.now() - timedelta(days=10),
                notes="SUS303 ∅10.0 標準品"
            ),
            Lot(
                lot_number="SUS303-12-241001-001",
                material_id=sus303_12.id,
                length_mm=3000,
                initial_quantity=150,
                supplier="ステンレス工業",
                received_date=datetime.now() - timedelta(days=10),
                notes="SUS303 ∅12.0 標準品"
            ),
            # C3602LCD（真鍮快削材）
            Lot(
                lot_number="C3602-12-241001-001",
                material_id=c3602_12.id,
                length_mm=3000,
                initial_quantity=120,
                supplier="黄銅商事",
                received_date=datetime.now() - timedelta(days=8),
                notes="C3602Lcd ∅12.0 快削品"
            ),
            # 追加の在庫（バリエーション用）
            Lot(
                lot_number="SUS303-5-241015-002",
                material_id=sus303_5.id,
                length_mm=4000,
                initial_quantity=50,
                supplier="関西ステンレス",
                received_date=datetime.now() - timedelta(days=5),
                notes="SUS303 ∅5.0 長尺品"
            ),
            Lot(
                lot_number="SUS303-10-241015-002",
                material_id=sus303_10.id,
                length_mm=4000,
                initial_quantity=80,
                supplier="関西ステンレス",
                received_date=datetime.now() - timedelta(days=5),
                notes="SUS303 ∅10.0 長尺品"
            ),
            # S45C・その他（従来の材料も維持）
            Lot(
                lot_number="S45C-240901-001",
                material_id=s45c.id,
                length_mm=3000,
                initial_quantity=50,
                supplier="東京鋼材",
                received_date=datetime.now() - timedelta(days=15),
                notes="定期入荷分"
            ),
            Lot(
                lot_number="SUS304-240910-001",
                material_id=sus304.id,
                length_mm=3000,
                initial_quantity=20,
                supplier="ステンレス工業",
                received_date=datetime.now() - timedelta(days=10),
                notes="耐食性重視"
            )
        ]

        db.add_all(sample_lots)
        db.commit()  # ロットIDを取得するために一度コミット

        # 在庫アイテムサンプルデータ
        print("在庫アイテムサンプルデータを作成中...")

        # 作成したロットを取得
        lots = db.query(Lot).all()

        sample_items = []
        for lot in lots:
            # 各ロットに対して1-3個のアイテムを作成
            item_count = random.randint(1, 3)
            remaining_quantity = lot.initial_quantity

            for i in range(item_count):
                if remaining_quantity <= 0:
                    break

                # 在庫数をランダムに分配（最後のアイテムは残り全部）
                if i == item_count - 1:
                    current_quantity = remaining_quantity
                else:
                    max_quantity = min(remaining_quantity, remaining_quantity // (item_count - i) + 10)
                    current_quantity = random.randint(0, max_quantity)

                remaining_quantity -= current_quantity

                # ランダムな置き場を選択（1-20）
                location_id = random.randint(1, 20)

                item = Item(
                    lot_id=lot.id,
                    location_id=location_id,
                    current_quantity=current_quantity,
                    # management_codeは自動生成される（UUID）
                    is_active=True
                )
                sample_items.append(item)

        db.add_all(sample_items)
        db.commit()

        # データをコミット
        print("初期データの投入が完了しました")

        # 作成されたデータの確認
        print(f"\n作成されたデータ:")
        print(f"- ユーザー: {db.query(User).count()}件")
        print(f"- 置き場: {db.query(Location).count()}件")
        print(f"- 材料: {db.query(Material).count()}件")
        print(f"- ロット: {db.query(Lot).count()}件")
        print(f"- 在庫アイテム: {db.query(Item).count()}件")

        print(f"\nデフォルトユーザー:")
        print(f"- admin / admin123 (管理者)")
        print(f"- purchase / purchase123 (購買)")
        print(f"- operator / operator123 (現場)")
        print(f"- viewer / viewer123 (閲覧)")

    except SQLAlchemyError as e:
        print(f"初期データ投入エラー: {e}")
        db.rollback()
        return False
    finally:
        db.close()

    return True

def insert_hierarchy_data():
    """階層データ（標準材質・グレード・製品・別名）を投入"""
    print("階層データを投入中...")

    db = SessionLocal()
    try:
        # ========================================
        # 第1層: 標準材質（MaterialStandard）
        # ========================================
        standards_data = [
            # ステンレス系
            {"jis_code": "SUS303", "jis_name": "ステンレス鋼（快削性）", "category": "ステンレス", "description": "快削性に優れたステンレス鋼"},
            {"jis_code": "SUS304", "jis_name": "ステンレス鋼", "category": "ステンレス", "description": "最も一般的なステンレス鋼"},
            {"jis_code": "SUS316", "jis_name": "ステンレス鋼（耐食性向上）", "category": "ステンレス", "description": "耐食性に優れたステンレス鋼"},
            # 炭素鋼系
            {"jis_code": "S45C", "jis_name": "機械構造用炭素鋼", "category": "炭素鋼", "description": "一般的な機械構造用鋼材"},
            {"jis_code": "S50C", "jis_name": "機械構造用炭素鋼", "category": "炭素鋼", "description": "炭素含有量0.50%前後の鋼材"},
            {"jis_code": "SK", "jis_name": "炭素工具鋼", "category": "炭素鋼", "description": "工具用途の炭素鋼"},
            # 黄銅系
            {"jis_code": "C3604", "jis_name": "快削黄銅", "category": "黄銅", "description": "快削性に優れた黄銅"},
            {"jis_code": "C3602", "jis_name": "快削黄銅", "category": "黄銅", "description": "快削黄銅の一種"},
            # アルミニウム系
            {"jis_code": "A5056", "jis_name": "アルミニウム合金", "category": "アルミニウム", "description": "耐食性に優れたアルミニウム合金"},
            {"jis_code": "A6061", "jis_name": "アルミニウム合金（構造用）", "category": "アルミニウム", "description": "構造材として広く使用されるアルミニウム合金"},
        ]

        standards = []
        for data in standards_data:
            standard = MaterialStandard(**data)
            db.add(standard)
            standards.append(standard)

        db.commit()  # 標準規格IDを取得するために一度コミット

        # 作成した標準規格を辞書で管理
        standards_dict = {s.jis_code: s for s in db.query(MaterialStandard).all()}

        # ========================================
        # 第2層: グレード（MaterialGrade）
        # ========================================
        grades_data = [
            # SUS303系
            {"standard_code": "SUS303", "grade_code": "標準", "characteristics": "標準品", "description": "一般的なSUS303"},
            # SUS304系
            {"standard_code": "SUS304", "grade_code": "標準", "characteristics": "標準品", "description": "一般的なSUS304"},
            # C3604系
            {"standard_code": "C3604", "grade_code": "LCD", "characteristics": "快削性向上", "description": "快削性を向上させたグレード"},
            {"standard_code": "C3604", "grade_code": "標準", "characteristics": "標準品", "description": "一般的なC3604"},
            # C3602系
            {"standard_code": "C3602", "grade_code": "LCD", "characteristics": "快削性向上", "description": "快削性を向上させたグレード"},
            # S45C系
            {"standard_code": "S45C", "grade_code": "標準", "characteristics": "標準品", "description": "一般的なS45C"},
            {"standard_code": "S45C", "grade_code": "FS", "characteristics": "快削性向上", "description": "快削鋼（Free Steel）"},
            # A5056系
            {"standard_code": "A5056", "grade_code": "標準", "characteristics": "標準品", "description": "一般的なA5056"},
            # A6061系
            {"standard_code": "A6061", "grade_code": "標準", "characteristics": "標準品", "description": "一般的なA6061"},
        ]

        grades = []
        for data in grades_data:
            standard_code = data.pop("standard_code")
            if standard_code in standards_dict:
                grade = MaterialGrade(
                    standard_id=standards_dict[standard_code].id,
                    **data
                )
                db.add(grade)
                grades.append(grade)

        db.commit()  # グレードIDを取得するために一度コミット

        # ========================================
        # 第3層: 製品（MaterialProduct）
        # ========================================
        # グレードを辞書で管理
        grades_list = db.query(MaterialGrade).all()
        grades_dict = {}
        for grade in grades_list:
            standard = db.query(MaterialStandard).filter(MaterialStandard.id == grade.standard_id).first()
            key = f"{standard.jis_code}-{grade.grade_code}"
            grades_dict[key] = grade

        products_data = [
            # SUS303系製品
            {"grade_key": "SUS303-標準", "product_code": "SUS303", "manufacturer": None, "is_equivalent": False, "description": "標準SUS303製品"},
            # S45C系製品
            {"grade_key": "S45C-標準", "product_code": "S45C", "manufacturer": None, "is_equivalent": False, "description": "標準S45C製品"},
            {"grade_key": "S45C-FS", "product_code": "S45CFS", "manufacturer": None, "is_equivalent": False, "description": "快削S45C製品"},
            {"grade_key": "S45C-標準", "product_code": "ASK3000", "manufacturer": "愛知製鋼", "is_equivalent": True, "description": "S45C同等品（メーカーブランド）"},
            # C3604系製品
            {"grade_key": "C3604-LCD", "product_code": "C3604LCD", "manufacturer": None, "is_equivalent": False, "description": "快削黄銅LCD品"},
            {"grade_key": "C3604-標準", "product_code": "C3604", "manufacturer": None, "is_equivalent": False, "description": "標準C3604製品"},
            # C3602系製品
            {"grade_key": "C3602-LCD", "product_code": "C3602LCD", "manufacturer": None, "is_equivalent": False, "description": "C3602快削品"},
            # SUS304系製品
            {"grade_key": "SUS304-標準", "product_code": "SUS304", "manufacturer": None, "is_equivalent": False, "description": "標準SUS304製品"},
            # アルミニウム系製品
            {"grade_key": "A5056-標準", "product_code": "A5056", "manufacturer": None, "is_equivalent": False, "description": "標準A5056製品"},
            {"grade_key": "A6061-標準", "product_code": "A6061", "manufacturer": None, "is_equivalent": False, "description": "標準A6061製品"},
        ]

        products = []
        for data in products_data:
            grade_key = data.pop("grade_key")
            if grade_key in grades_dict:
                product = MaterialProduct(
                    grade_id=grades_dict[grade_key].id,
                    **data
                )
                db.add(product)
                products.append(product)

        db.commit()

        print("階層データの投入が完了しました")
        print(f"- 標準材質: {db.query(MaterialStandard).count()}件")
        print(f"- グレード: {db.query(MaterialGrade).count()}件")
        print(f"- 製品: {db.query(MaterialProduct).count()}件")

    except SQLAlchemyError as e:
        print(f"階層データ投入エラー: {e}")
        db.rollback()
        return False
    finally:
        db.close()

    return True

def map_existing_materials_to_hierarchy():
    """既存材料データを階層構造にマッピング"""
    print("既存材料データの階層マッピング中...")

    db = SessionLocal()
    try:
        # 製品を辞書で管理
        products = db.query(MaterialProduct).all()
        products_dict = {}
        for product in products:
            products_dict[product.product_code] = product

        # 既存の材料データを取得
        materials = db.query(Material).all()

        mapped_count = 0
        for material in materials:
            # 材料名から製品コードを推測してマッピング
            material_name = material.name.upper()

            # 製品コードとのマッチング
            for product_code, product in products_dict.items():
                if product_code in material_name:
                    material.product_id = product.id
                    mapped_count += 1
                    break

        db.commit()

        print(f"階層マッピングが完了しました: {mapped_count}/{len(materials)} 件マッピング")

    except SQLAlchemyError as e:
        print(f"階層マッピングエラー: {e}")
        db.rollback()
        return False
    finally:
        db.close()

    return True

def insert_sample_aliases():
    """サンプル別名データを投入（表記揺れ対応）"""
    print("サンプル別名データを投入中...")

    db = SessionLocal()
    try:
        # 材料を取得
        sus303_5 = db.query(Material).filter(Material.name == "SUS303", Material.diameter_mm == 5.0).first()
        sus303_10 = db.query(Material).filter(Material.name == "SUS303", Material.diameter_mm == 10.0).first()
        sus303_12 = db.query(Material).filter(Material.name == "SUS303", Material.diameter_mm == 12.0).first()
        c3602_12 = db.query(Material).filter(Material.name == "C3602LCD", Material.diameter_mm == 12.0).first()

        aliases_data = []

        # SUS303 ∅5.0 の別名
        if sus303_5:
            aliases_data.extend([
                MaterialAlias(material_id=sus303_5.id, alias_name="SUS303 φ5.0D", description="表記揺れ（φとD）"),
                MaterialAlias(material_id=sus303_5.id, alias_name="SUS303 ∅5.0CM", description="表記揺れ（∅とCM）"),
                MaterialAlias(material_id=sus303_5.id, alias_name="SUS303 Φ5", description="表記揺れ（Φ）"),
            ])

        # SUS303 ∅10.0 の別名
        if sus303_10:
            aliases_data.extend([
                MaterialAlias(material_id=sus303_10.id, alias_name="SUS303 φ10.0D", description="表記揺れ（φとD）"),
                MaterialAlias(material_id=sus303_10.id, alias_name="SUS303 ∅10.0CM", description="表記揺れ（∅とCM）"),
                MaterialAlias(material_id=sus303_10.id, alias_name="SUS303 Φ10", description="表記揺れ（Φ）"),
            ])

        # SUS303 ∅12.0 の別名
        if sus303_12:
            aliases_data.extend([
                MaterialAlias(material_id=sus303_12.id, alias_name="SUS303 φ12.0D", description="表記揺れ（φとD）"),
                MaterialAlias(material_id=sus303_12.id, alias_name="SUS303 ∅12.0CM", description="表記揺れ（∅とCM）"),
            ])

        # C3602LCD ∅12.0 の別名
        if c3602_12:
            aliases_data.extend([
                MaterialAlias(material_id=c3602_12.id, alias_name="C3602Lcd ∅12.0 (NB5N)", description="表記揺れ（括弧付き品番）"),
                MaterialAlias(material_id=c3602_12.id, alias_name="C3602LCD φ12", description="表記揺れ（φ表記）"),
            ])

        db.add_all(aliases_data)
        db.commit()

        print(f"サンプル別名データの投入が完了しました: {len(aliases_data)}件")

    except SQLAlchemyError as e:
        print(f"サンプル別名データ投入エラー: {e}")
        db.rollback()
        return False
    finally:
        db.close()

    return True

def insert_sample_purchase_orders():
    """サンプル発注データを投入"""
    print("サンプル発注データを投入中...")

    try:
        db = SessionLocal()

        # ユーザー取得（発注者として使用）
        admin_user = db.query(User).filter(User.username == "admin").first()
        purchase_user = db.query(User).filter(User.username == "purchase").first()

        if not admin_user or not purchase_user:
            print("エラー: ユーザーデータが見つかりません")
            return False

        # 材料データ取得
        s45c = db.query(Material).filter(Material.name == "S45C").first()
        sus304 = db.query(Material).filter(Material.name == "SUS304").first()

        if not s45c or not sus304:
            print("エラー: 材料データが見つかりません")
            return False

        # サンプル発注作成
        sample_orders = [
            {
                "order": PurchaseOrder(
                    order_number="PO-2025-001",
                    supplier="東京鋼材株式会社",
                    order_date=datetime.now() - timedelta(days=10),
                    expected_delivery_date=datetime.now() + timedelta(days=5),
                    status=PurchaseOrderStatus.PENDING,
                    notes="定期発注分",
                    total_amount=150000.0,
                    created_by=purchase_user.id
                ),
                "items": [
                    PurchaseOrderItem(
                        material_id=s45c.id,
                        material_name="S45C",
                        shape=MaterialShape.ROUND,
                        diameter_mm=20.0,
                        length_mm=3000,
                        density=7.85,
                        ordered_quantity=50,
                        unit_price=2500.0,
                        is_new_material=False,
                        status=PurchaseOrderItemStatus.PENDING
                    ),
                    PurchaseOrderItem(
                        material_id=s45c.id,
                        material_name="S45C",
                        shape=MaterialShape.ROUND,
                        diameter_mm=25.0,
                        length_mm=4000,
                        density=7.85,
                        ordered_quantity=30,
                        unit_price=3500.0,
                        is_new_material=False,
                        status=PurchaseOrderItemStatus.PENDING
                    )
                ]
            },
            {
                "order": PurchaseOrder(
                    order_number="PO-2025-002",
                    supplier="関西スチール工業",
                    order_date=datetime.now() - timedelta(days=7),
                    expected_delivery_date=datetime.now() + timedelta(days=3),
                    status=PurchaseOrderStatus.PENDING,
                    notes="SUS304材料の緊急発注",
                    total_amount=200000.0,
                    created_by=admin_user.id
                ),
                "items": [
                    PurchaseOrderItem(
                        material_id=sus304.id,
                        material_name="SUS304",
                        shape=MaterialShape.ROUND,
                        diameter_mm=15.0,
                        length_mm=2000,
                        density=8.03,
                        ordered_quantity=40,
                        unit_price=4000.0,
                        is_new_material=False,
                        status=PurchaseOrderItemStatus.PENDING
                    ),
                    PurchaseOrderItem(
                        material_id=sus304.id,
                        material_name="SUS304",
                        shape=MaterialShape.HEXAGON,
                        diameter_mm=12.0,
                        length_mm=3000,
                        density=8.03,
                        ordered_quantity=25,
                        unit_price=4800.0,
                        is_new_material=False,
                        status=PurchaseOrderItemStatus.PENDING
                    )
                ]
            },
            {
                "order": PurchaseOrder(
                    order_number="PO-2025-003",
                    supplier="大阪金属商事",
                    order_date=datetime.now() - timedelta(days=3),
                    expected_delivery_date=datetime.now() + timedelta(days=7),
                    status=PurchaseOrderStatus.PENDING,
                    notes="新規材料A6061の試験発注",
                    total_amount=80000.0,
                    created_by=purchase_user.id
                ),
                "items": [
                    PurchaseOrderItem(
                        material_id=None,  # 新規材料
                        material_name="A6061",
                        shape=MaterialShape.SQUARE,
                        diameter_mm=30.0,
                        length_mm=2500,
                        density=2.70,
                        ordered_quantity=20,
                        unit_price=4000.0,
                        is_new_material=True,
                        status=PurchaseOrderItemStatus.PENDING
                    )
                ]
            }
        ]

        # 発注データを投入
        for order_data in sample_orders:
            # 発注を追加
            db.add(order_data["order"])
            db.flush()  # IDを取得

            # 発注アイテムを追加
            for item in order_data["items"]:
                item.purchase_order_id = order_data["order"].id
                db.add(item)

        db.commit()

        print("サンプル発注データの投入が完了しました")
        print(f"- 発注: {db.query(PurchaseOrder).count()}件")
        print(f"- 発注アイテム: {db.query(PurchaseOrderItem).count()}件")

    except SQLAlchemyError as e:
        print(f"サンプル発注データ投入エラー: {e}")
        db.rollback()
        return False
    finally:
        db.close()

    return True

def main():
    """メイン処理"""
    import sys

    print("=" * 50)
    print("材料管理システム データベースリセット")
    print("=" * 50)
    print(f"対象データベース: {settings.db_name}")
    print(f"ホスト: {settings.db_host}:{settings.db_port}")
    print(f"ユーザー: {settings.db_user}")
    print("=" * 50)

    # 確認（--forceオプションで省略可能）
    if "--force" not in sys.argv:
        try:
            if input("データベースを完全にリセットしますか？ (y/N): ").lower() != 'y':
                print("処理を中止しました")
                return
        except EOFError:
            print("処理を中止しました")
            return

    start_time = datetime.now()

    # 1. データベース削除
    if not drop_database():
        print("データベース削除に失敗しました")
        return

    # 2. データベース作成
    if not create_database():
        print("データベース作成に失敗しました")
        return

    # 3. テーブル作成
    if not create_tables():
        print("テーブル作成に失敗しました")
        return

    # 4. 初期データ投入
    if not insert_initial_data():
        print("初期データ投入に失敗しました")
        return

    # 5. 階層データ投入
    if not insert_hierarchy_data():
        print("階層データ投入に失敗しました")
        return

    # 6. 既存材料データの階層マッピング
    if not map_existing_materials_to_hierarchy():
        print("階層マッピングに失敗しました")
        return

    # 7. サンプル別名データ投入
    if not insert_sample_aliases():
        print("サンプル別名データ投入に失敗しました")
        return

    # 8. サンプル発注データ投入
    if not insert_sample_purchase_orders():
        print("サンプル発注データ投入に失敗しました")
        return

    end_time = datetime.now()
    duration = end_time - start_time

    print("=" * 50)
    print("データベースリセットが正常に完了しました！")
    print(f"処理時間: {duration.total_seconds():.2f}秒")
    print("=" * 50)

if __name__ == "__main__":
    main()