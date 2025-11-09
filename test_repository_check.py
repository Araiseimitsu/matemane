"""
リポジトリアクセス確認機能のテスト

このスクリプトは、repository_check APIの動作を検証します。
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from src.api.repository_check import check_path_accessibility, RepositoryStatus


def test_check_path_accessibility():
    """check_path_accessibility関数のテスト"""
    print("=" * 60)
    print("リポジトリアクセス確認機能のテスト")
    print("=" * 60)
    
    # テスト1: 存在するパス（カレントディレクトリ）
    print("\n[テスト1] カレントディレクトリのチェック")
    result = check_path_accessibility(".")
    print(f"  パス: .")
    print(f"  存在: {result['exists']}")
    print(f"  読取可: {result['readable']}")
    print(f"  書込可: {result['writable']}")
    print(f"  アクセス可: {result['accessible']}")
    print(f"  エラー: {result['error_message'] or 'なし'}")
    
    assert result['exists'] == True, "カレントディレクトリは存在するはず"
    assert result['accessible'] == True, "カレントディレクトリはアクセス可能なはず"
    print("  ✓ テスト1: 成功")
    
    # テスト2: 存在しないパス
    print("\n[テスト2] 存在しないパスのチェック")
    result = check_path_accessibility("/nonexistent/path/to/file.txt")
    print(f"  パス: /nonexistent/path/to/file.txt")
    print(f"  存在: {result['exists']}")
    print(f"  読取可: {result['readable']}")
    print(f"  書込可: {result['writable']}")
    print(f"  アクセス可: {result['accessible']}")
    print(f"  エラー: {result['error_message'] or 'なし'}")
    
    assert result['exists'] == False, "存在しないパスは存在しないはず"
    assert result['accessible'] == False, "存在しないパスはアクセス不可のはず"
    assert result['error_message'] is not None, "エラーメッセージが設定されるはず"
    print("  ✓ テスト2: 成功")
    
    # テスト3: ファイルのチェック（README.md）
    print("\n[テスト3] README.mdファイルのチェック")
    result = check_path_accessibility("README.md")
    print(f"  パス: README.md")
    print(f"  存在: {result['exists']}")
    print(f"  読取可: {result['readable']}")
    print(f"  書込可: {result['writable']}")
    print(f"  アクセス可: {result['accessible']}")
    print(f"  エラー: {result['error_message'] or 'なし'}")
    
    if result['exists']:
        assert result['readable'] == True, "README.mdは読み取り可能なはず"
        print("  ✓ テスト3: 成功")
    else:
        print("  ⚠ テスト3: README.mdが見つかりませんでした")
    
    # テスト4: RepositoryStatusモデルのテスト
    print("\n[テスト4] RepositoryStatusモデルのテスト")
    status = RepositoryStatus(
        name="テストリポジトリ",
        path="/test/path",
        accessible=True,
        exists=True,
        readable=True,
        writable=False,
        error_message=None
    )
    print(f"  リポジトリ名: {status.name}")
    print(f"  パス: {status.path}")
    print(f"  アクセス可: {status.accessible}")
    print("  ✓ テスト4: 成功")
    
    print("\n" + "=" * 60)
    print("すべてのテストが成功しました！")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_check_path_accessibility()
        print("\n✓ テスト完了")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n✗ テスト失敗: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ エラー発生: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
