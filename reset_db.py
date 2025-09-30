#!/usr/bin/env python3
"""
データベースリセットスクリプト

開発環境でデータベースを完全にリセットし、テーブルを作成します。
"""

import sys
import os

# プロジェクトルートをPythonパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from src.config import settings
from src.db.models import Base
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

    print("=" * 50)
    print("データベースリセットが正常に完了しました！")
    print("=" * 50)

if __name__ == "__main__":
    main()