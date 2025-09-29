import pandas as pd
import re
import json
from typing import Dict, List, Tuple, Optional

def analyze_materials_csv(file_path: str) -> List[Dict]:
    """
    材料マスターCSVファイルを解析し、材料データを抽出する
    """
    try:
        # UTF-8でCSVを読み込み
        df = pd.read_csv(file_path, encoding='utf-8', header=None)

        materials = []
        material_patterns = [
            # 基本パターン：材質 + φ + サイズ + 追加情報
            r'^(.+?)\s*[φΦ]\s*(\d+(?:\.\d+)?)\s*(.*)$',
            # 六角棒パターン：材質 + Hex + サイズ
            r'^(.+?)\s+Hex\s*(\d+(?:\.\d+)?)\s*(.*)$',
            # 角棒パターン：材質 + サイズ（材質名に形状情報が含まれる場合）
            r'^(.+?)\s+(\d+(?:\.\d+)?)\s*(.*)$'
        ]

        for index, row in df.iterrows():
            if pd.isna(row[0]) or str(row[0]).strip() == '' or str(row[0]).strip() == '材質＆材料径':
                continue

            material_text = str(row[0]).strip()
            print(f"解析中: {material_text}")

            parsed_material = None

            # パターン1：標準的なφ記法
            match = re.match(r'^(.+?)\s*[φΦ]\s*(\d+(?:\.\d+)?)\s*(.*)$', material_text)
            if match:
                material_name = match.group(1).strip()
                size = float(match.group(2))
                additional_info = match.group(3).strip()

                # 形状判定
                shape = "round"  # デフォルトで丸棒

                # 追加情報から形状を判定
                if "hex" in additional_info.lower() or "六角" in additional_info:
                    shape = "hexagon"
                elif "square" in additional_info.lower() or "角" in additional_info:
                    shape = "square"

                parsed_material = {
                    'original_text': material_text,
                    'material_name': material_name,
                    'shape': shape,
                    'diameter_mm': size,
                    'additional_info': additional_info,
                    'row_number': index + 1
                }

            # パターン2：Hex記法
            if not parsed_material:
                match = re.match(r'^(.+?)\s+Hex\s*(\d+(?:\.\d+)?)\s*(.*)$', material_text)
                if match:
                    material_name = match.group(1).strip()
                    size = float(match.group(2))

                    parsed_material = {
                        'original_text': material_text,
                        'material_name': material_name,
                        'shape': 'hexagon',
                        'diameter_mm': size,
                        'additional_info': match.group(3).strip(),
                        'row_number': index + 1
                    }

            # パターン3：その他の記法
            if not parsed_material:
                # サイズを抽出（数字部分）
                size_match = re.search(r'(\d+(?:\.\d+)?)', material_text)
                if size_match:
                    size = float(size_match.group(1))

                    # 材質名を抽出（最初の単語）
                    words = material_text.split()
                    material_name = words[0] if words else material_text

                    # 形状判定のヒント
                    shape_hints = {
                        'hex': 'hexagon',
                        '六角': 'hexagon',
                        'square': 'square',
                        '角': 'square',
                        'round': 'round',
                        '丸': 'round'
                    }

                    shape = 'round'  # デフォルト
                    for hint, shape_value in shape_hints.items():
                        if hint.lower() in material_text.lower():
                            shape = shape_value
                            break

                    parsed_material = {
                        'original_text': material_text,
                        'material_name': material_name,
                        'shape': shape,
                        'diameter_mm': size,
                        'additional_info': material_text.replace(material_name, '').replace(str(size), '').strip(),
                        'row_number': index + 1
                    }

            if parsed_material:
                materials.append(parsed_material)
                print(f"  → 材質: {parsed_material['material_name']}, 形状: {parsed_material['shape']}, サイズ: {parsed_material['diameter_mm']}mm")

        return materials

    except Exception as e:
        print(f"CSV解析エラー: {e}")
        return []

def get_unique_materials(materials: List[Dict]) -> List[Dict]:
    """
    重複を除去してユニークな材料のみを返す
    """
    unique_materials = []
    seen = set()

    for material in materials:
        # 材質名、形状、サイズの組み合わせで重複チェック
        key = (material['material_name'], material['shape'], material['diameter_mm'])

        if key not in seen:
            seen.add(key)
            unique_materials.append(material)

    return unique_materials

def create_import_data(materials: List[Dict]) -> List[Dict]:
    """
    DBインポート用のデータ形式に変換
    """
    import_data = []

    # 材質ごとのデフォルト比重を設定
    default_densities = {
        'ASK2600S': 7.85,  # 炭素鋼
        'C3604Lcd': 8.49,  # 黄銅
        'C3604': 8.49,     # 黄銅
        'C3602Lcd': 8.49,  # 黄銅
        'SUS303': 7.93,    # ステンレス
        'SUS304': 7.93,    # ステンレス
        'SUS440C': 7.70,   # ステンレス
        'S45CFS': 7.85,    # 炭素鋼
        'S45CF': 7.85,     # 炭素鋼
        'C5191': 8.80,     # リン青銅
        'SF-20T': 7.85,    # 炭素鋼
        '1144': 7.85,      # 炭素鋼
        'TLS': 7.85,       # 炭素鋼
        'G23-T8': 7.85,    # 炭素鋼
        'ASK2200R': 7.85   # 炭素鋼
    }

    for material in materials:
        # デフォルト比重を設定
        base_name = material['material_name'].split()[0] if material['material_name'] else ''
        density = default_densities.get(base_name, 7.85)  # デフォルトは炭素鋼の比重

        import_item = {
            'name': material['material_name'],
            'shape': material['shape'],
            'diameter_mm': material['diameter_mm'],
            'current_density': density,
            'description': f"CSVからインポート: {material['original_text']}",
            'is_active': True
        }

        import_data.append(import_item)

    return import_data

def test_csv_import():
    """CSVインポート機能をテスト"""
    csv_file = "材料マスター.csv"

    print("材料マスターCSVを解析中...")
    materials = analyze_materials_csv(csv_file)

    print(f"\n解析結果: {len(materials)} 件の材料データを抽出")

    # 重複を除去
    unique_materials = get_unique_materials(materials)
    print(f"重複除去後: {len(unique_materials)} 件のユニークな材料")

    # インポート用データに変換
    import_data = create_import_data(unique_materials)

    # 結果をJSONファイルに保存
    with open('materials_import.json', 'w', encoding='utf-8') as f:
        json.dump(import_data, f, ensure_ascii=False, indent=2)

    print("インポート用JSONファイルを作成しました: materials_import.json")

    # 解析結果を表示
    print("\n=== 解析結果プレビュー ===")
    for i, material in enumerate(unique_materials[:10], 1):
        print(f"{i}. {material['material_name']} - {material['shape']} - {material['diameter_mm']}mm")

    print("...")

    return import_data

if __name__ == "__main__":
    test_csv_import()
