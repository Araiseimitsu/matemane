import requests
import json

def check_materials():
    """材料データを確認"""
    try:
        response = requests.get('http://localhost:8000/api/materials')
        if response.status_code == 200:
            materials = response.json()
            print(f"登録材料数: {len(materials)}")
            print("\n=== 材料一覧 ===")
            for material in materials:
                print(f"ID: {material['id']}")
                print(f"材料名: {material['name']}")
                print(f"形状: {material['shape']}")
                print(f"直径: {material['diameter_mm']}mm")
                print(f"説明: {material['description']}")
                print("---")
        else:
            print(f"エラー: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"エラー: {e}")

if __name__ == "__main__":
    check_materials()
