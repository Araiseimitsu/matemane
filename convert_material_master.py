#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
材料マスター.csv を新形式に変換するスクリプト

入力形式:
  製品番号,材質＆材料径
  00101A00200-0,SUS303 φ8.0CM

出力形式:
  材質名,形状・寸法,品番,用途区分,専用品番
  SUS303,φ8.0,,汎用,CM
"""

import pandas as pd
import re
from typing import Dict, Optional

def parse_material_specification(spec_text: str) -> Dict[str, Optional[str]]:
    """
    材質＆材料径テキストを解析

    例:
    - SUS303 φ8.0CM → 材質名: SUS303, 寸法: φ8.0, 追加情報: CM
    - C3604Lcd φ6.0 平目 22山 → 材質名: C3604LCD, 寸法: φ6.0, 追加情報: 平目 22山
    - ASK2600S φ8.0CM → 材質名: ASK2600S, 寸法: φ8.0, 追加情報: CM
    - SUS440C φ6.0G  2m → 材質名: SUS440C, 寸法: φ6.0, 追加情報: G 2m
    - C3604Lcd Hex4.0 → 材質名: C3604LCD, 寸法: Hex4.0, 追加情報: なし
    """
    if not spec_text or pd.isna(spec_text):
        return {
            'material_name': None,
            'dimension': None,
            'additional_info': None
        }

    text = str(spec_text).strip()

    # 材質名の抽出（先頭の英数字部分）
    material_match = re.match(r'^([A-Z0-9\-]+(?:FS|CF|LCD|Lcd|T)?)', text, re.IGNORECASE)
    material_name = material_match.group(1).upper().replace('Lcd', 'LCD') if material_match else None

    if not material_name:
        # 材質名が抽出できない場合は全体を材質名として扱う
        return {
            'material_name': text[:50],  # 最大50文字
            'dimension': None,
            'additional_info': None
        }

    # 材質名以降の部分
    remaining = text[len(material_match.group(1)):].strip()

    # 寸法の抽出（複数パターン）
    dimension = None
    dimension_patterns = [
        r'([∅Φφ]\s*\d+\.?\d*)',           # ∅10.0, φ8.0
        r'(Hex\s*\d+\.?\d*)',              # Hex4.0
        r'([□]\s*\d+\.?\d*)',              # □15
        r'(\d+\.?\d*\s*[Mm][Mm])',        # 10.0mm
    ]

    dimension_match = None
    for pattern in dimension_patterns:
        match = re.search(pattern, remaining, re.IGNORECASE)
        if match:
            dimension_match = match
            dimension = match.group(1).strip()
            break

    # 追加情報の抽出（寸法以外の部分）
    additional_info = None
    if dimension_match:
        # 寸法の前と後ろの部分を結合
        before = remaining[:dimension_match.start()].strip()
        after = remaining[dimension_match.end():].strip()

        parts = []
        if before:
            parts.append(before)
        if after:
            parts.append(after)

        if parts:
            additional_info = ' '.join(parts)
    else:
        # 寸法が見つからない場合、残り全体を追加情報として扱う
        if remaining:
            additional_info = remaining

    return {
        'material_name': material_name,
        'dimension': dimension,
        'additional_info': additional_info if additional_info else None
    }

def convert_material_master(input_file: str, output_file: str):
    """
    材料マスター.csv を新形式に変換
    """
    print(f"入力ファイル: {input_file}")
    print(f"出力ファイル: {output_file}")
    print()

    # CSVファイルを読み込み（複数エンコーディング対応）
    encodings = ['utf-8-sig', 'cp932', 'shift_jis', 'utf-8']
    df = None

    for encoding in encodings:
        try:
            df = pd.read_csv(input_file, encoding=encoding)
            print(f"エンコーディング: {encoding} で読み込み成功")
            break
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue

    if df is None:
        raise ValueError("CSVファイルの読み込みに失敗しました")

    print(f"総行数: {len(df)}")
    print()

    # 新形式のデータを格納するリスト
    converted_data = []

    success_count = 0
    warning_count = 0
    error_count = 0

    for index, row in df.iterrows():
        try:
            # 1列目（製品番号）を取得
            product_number = None
            if len(row) >= 1 and not pd.isna(row.iloc[0]):
                product_number = str(row.iloc[0]).strip()

            # 2列目（材質＆材料径）を取得
            if len(row) < 2:
                error_count += 1
                print(f"[WARN] 行 {index + 2}: 列数不足 - スキップ")
                continue

            spec_text = row.iloc[1]

            if pd.isna(spec_text) or str(spec_text).strip() == '':
                error_count += 1
                print(f"[WARN] 行 {index + 2}: 材質＆材料径が空 - スキップ")
                continue

            # 材質＆材料径を解析
            parsed = parse_material_specification(spec_text)

            # 材質名がない場合はスキップ
            if not parsed['material_name']:
                error_count += 1
                print(f"[WARN] 行 {index + 2}: 材質名を抽出できませんでした - '{spec_text}'")
                continue

            # 新形式のデータを作成
            converted_row = {
                '材質名': parsed['material_name'],
                '形状・寸法': parsed['dimension'] if parsed['dimension'] else '',
                '品番': product_number if product_number else '',  # 1列目の製品番号を品番として使用
                '用途区分': '汎用',
                '専用品番': parsed['additional_info'] if parsed['additional_info'] else ''
            }

            converted_data.append(converted_row)

            # 進捗表示
            if parsed['dimension']:
                success_count += 1
                if success_count % 100 == 0:
                    print(f"[OK] {success_count} 件処理完了")
            else:
                warning_count += 1
                if warning_count <= 10:  # 最初の10件のみ表示
                    print(f"[WARN] 行 {index + 2}: 寸法なし - 材質名='{parsed['material_name']}', 元データ='{spec_text}'")

        except Exception as e:
            error_count += 1
            print(f"[ERROR] 行 {index + 2}: エラー - {e}")

    # 新形式のCSVファイルに書き出し
    if converted_data:
        output_df = pd.DataFrame(converted_data)
        output_df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print()
        print("=" * 60)
        print(f"変換完了!")
        print(f"  成功: {success_count} 件（寸法あり）")
        print(f"  警告: {warning_count} 件（寸法なし、材質名のみ登録）")
        print(f"  エラー: {error_count} 件（スキップ）")
        print(f"  合計登録: {len(converted_data)} 件")
        print(f"  出力先: {output_file}")
        print("=" * 60)
    else:
        print()
        print("変換可能なデータがありませんでした")

if __name__ == '__main__':
    input_file = '材料マスター.csv'
    output_file = '材料マスター_新形式.csv'

    try:
        convert_material_master(input_file, output_file)
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()