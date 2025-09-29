import requests

def test_csv_import_fix():
    """修正後のCSVインポート機能をテスト"""
    print("=== CSVインポート機能修正テスト ===")

    # 1. 既存のCSVインポートデータを削除
    print("1. 既存のCSVインポートデータを削除中...")
    response = requests.get('http://localhost:8000/api/materials')
    if response.status_code == 200:
        materials = response.json()
        deleted_count = 0
        for material in materials:
            if material['description'].startswith('CSVからインポート'):
                delete_response = requests.delete(f"http://localhost:8000/api/materials/{material['id']}")
                if delete_response.status_code == 200:
                    deleted_count += 1
        print(f"   {deleted_count}件のデータを削除しました")
    else:
        print(f"   エラー: {response.status_code}")

    # 2. 再度CSVインポートを実行
    print("\n2. CSVインポートを再実行中...")
    csv_file_path = "test_materials.csv"

    try:
        with open(csv_file_path, 'rb') as f:
            files = {'file': ('test_materials.csv', f, 'text/csv')}
            response = requests.post('http://localhost:8000/api/materials/import-csv', files=files)

        print(f"   ステータスコード: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print("   インポート成功:")
            print(f"     インポート件数: {result['imported_count']}")
            print(f"     スキップ件数: {result['skipped_count']}")
            print(f"     処理済み件数: {result['total_processed']}")

            # 3. 結果を確認
            print("\n3. インポート結果を確認...")
            response = requests.get('http://localhost:8000/api/materials')
            if response.status_code == 200:
                materials = response.json()
                csv_materials = [m for m in materials if m['description'].startswith('CSVからインポート')]
                print(f"   CSVインポート材料数: {len(csv_materials)}")

                for material in csv_materials:
                    print(f"     材料名: {material['name']}")
                    print(f"     形状: {material['shape']}")
                    print(f"     直径: {material['diameter_mm']}mm")
                    print(f"     説明: {material['description']}")
                    print("     ---")
        else:
            try:
                error_data = response.json()
                print(f"   エラー: {error_data.get('detail', '不明なエラー')}")
            except:
                print(f"   HTTPエラー: {response.status_code}")

    except Exception as e:
        print(f"   リクエストエラー: {e}")

if __name__ == "__main__":
    test_csv_import_fix()
