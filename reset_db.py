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
from src.db.models import Base, User, Material, Location, MaterialShape, UserRole
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

        # データをコミット
        db.commit()
        print("初期データの投入が完了しました")

        # 作成されたデータの確認
        print(f"\n作成されたデータ:")
        print(f"- ユーザー: {db.query(User).count()}件")
        print(f"- 置き場: {db.query(Location).count()}件")
        print(f"- 材料: {db.query(Material).count()}件")

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
    print("=" * 50)
    print("材料管理システム データベースリセット")
    print("=" * 50)
    print(f"対象データベース: {settings.db_name}")
    print(f"ホスト: {settings.db_host}:{settings.db_port}")
    print(f"ユーザー: {settings.db_user}")
    print("=" * 50)

    # 確認
    if input("データベースを完全にリセットしますか？ (y/N): ").lower() != 'y':
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