#!/usr/bin/env python3
"""
データベースリセットスクリプト

開発環境でデータベースを完全にリセットし、初期データを投入します。
"""

import sys
import os
from datetime import datetime

# プロジェクトルートをPythonパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from src.config import settings
from src.db.models import Base, User, Material, Location, Lot, Item, MaterialShape, UserRole
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

        # サンプル材料を作成
        sample_materials = [
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
                description="ステンレス鋼",
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
        sus304 = db.query(Material).filter(Material.name == "SUS304").first()
        a5056 = db.query(Material).filter(Material.name == "A5056").first()
        c1020 = db.query(Material).filter(Material.name == "C1020").first()

        print(f"材料データ確認: S45C={s45c.id if s45c else None}, SUS304={sus304.id if sus304 else None}, A5056={a5056.id if a5056 else None}, C1020={c1020.id if c1020 else None}")

        if not s45c or not sus304 or not a5056 or not c1020:
            print("エラー: 材料データが見つかりません")
            return False

        sample_lots = [
            # S45C用ロット（SS400をS45Cに変更）
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
                lot_number="S45C-240915-002",
                material_id=s45c.id,
                length_mm=4000,
                initial_quantity=30,
                supplier="関西スチール",
                received_date=datetime.now() - timedelta(days=8),
                notes="特注長さ"
            ),
            # S45C用ロット
            Lot(
                lot_number="S45C-240905-001",
                material_id=s45c.id,
                length_mm=2500,
                initial_quantity=40,
                supplier="大阪金属",
                received_date=datetime.now() - timedelta(days=12),
                notes="機械加工用"
            ),
            Lot(
                lot_number="S45C-240920-002",
                material_id=s45c.id,
                length_mm=3500,
                initial_quantity=25,
                supplier="東京鋼材",
                received_date=datetime.now() - timedelta(days=5),
                notes="高精度品"
            ),
            # SUS304用ロット
            Lot(
                lot_number="SUS304-240910-001",
                material_id=sus304.id,
                length_mm=3000,
                initial_quantity=20,
                supplier="ステンレス工業",
                received_date=datetime.now() - timedelta(days=10),
                notes="耐食性重視"
            ),
            Lot(
                lot_number="SUS304-240922-002",
                material_id=sus304.id,
                length_mm=2000,
                initial_quantity=35,
                supplier="関西ステンレス",
                received_date=datetime.now() - timedelta(days=3),
                notes="短尺品"
            ),
            # A5056用ロット
            Lot(
                lot_number="A5056-240912-001",
                material_id=a5056.id,
                length_mm=4000,
                initial_quantity=15,
                supplier="アルミ工業",
                received_date=datetime.now() - timedelta(days=8),
                notes="軽量化用途"
            ),
            Lot(
                lot_number="A5056-240925-002",
                material_id=a5056.id,
                length_mm=3000,
                initial_quantity=28,
                supplier="東京アルミ",
                received_date=datetime.now() - timedelta(days=1),
                notes="新規入荷"
            ),
            # C1020用ロット
            Lot(
                lot_number="C1020-240918-001",
                material_id=c1020.id,
                length_mm=2000,
                initial_quantity=20,
                supplier="銅材商事",
                received_date=datetime.now() - timedelta(days=6),
                notes="電気用途"
            ),
            Lot(
                lot_number="C1020-240923-002",
                material_id=c1020.id,
                length_mm=2500,
                initial_quantity=18,
                supplier="関東銅業",
                received_date=datetime.now() - timedelta(days=2),
                notes="高純度品"
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

    end_time = datetime.now()
    duration = end_time - start_time

    print("=" * 50)
    print("データベースリセットが正常に完了しました！")
    print(f"処理時間: {duration.total_seconds():.2f}秒")
    print("=" * 50)

if __name__ == "__main__":
    main()