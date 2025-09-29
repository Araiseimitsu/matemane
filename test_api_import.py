import requests
import os

def test_csv_import():
    """CSVインポートAPIをテスト"""
    # テスト用CSVファイルのパス
    csv_file_path = "test_materials.csv"

    if not os.path.exists(csv_file_path):
        print(f"テストファイルが見つかりません: {csv_file_path}")
        return

    try:
        # ファイルを開いてアップロード
        with open(csv_file_path, 'rb') as f:
            files = {'file': ('test_materials.csv', f, 'text/csv')}
            response = requests.post('http://localhost:8000/api/materials/import-csv', files=files)

        print(f"ステータスコード: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print("インポート成功:")
            print(f"  インポート件数: {result['imported_count']}")
            print(f"  スキップ件数: {result['skipped_count']}")
            print(f"  処理済み件数: {result['total_processed']}")
            if result['errors']:
                print("エラー:")
                for error in result['errors']:
                    print(f"  - {error}")
        else:
            try:
                error_data = response.json()
                print(f"エラー: {error_data.get('detail', '不明なエラー')}")
            except:
                print(f"HTTPエラー: {response.status_code}")

    except Exception as e:
        print(f"リクエストエラー: {e}")

if __name__ == "__main__":
    test_csv_import()
