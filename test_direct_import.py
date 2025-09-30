#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
直接インポート機能をテストするスクリプト
"""

import requests
import os
import sys

def test_direct_import():
    """材料マスター.csvを直接インポートするテスト"""

    # サーバーURL
    base_url = "http://127.0.0.1:8000"

    # 材料マスターCSVファイルのパス
    csv_file_path = "材料マスター.csv"

    if not os.path.exists(csv_file_path):
        print(f"Error: {csv_file_path} not found")
        return False

    try:
        # CSVファイルを読み込み
        with open(csv_file_path, 'rb') as f:
            files = {'file': (os.path.basename(csv_file_path), f, 'text/csv')}

            print("Testing direct import...")
            print(f"File: {csv_file_path}")
            print(f"Size: {os.path.getsize(csv_file_path)} bytes")

            # まずサーバーが動作しているか確認
            try:
                health_response = requests.get(f"{base_url}/", timeout=5)
                print(f"Server health check: {health_response.status_code}")
            except:
                print("Server health check failed")

            # APIリクエストを送信
            response = requests.post(
                f"{base_url}/api/materials/import-csv",
                files=files,
                timeout=30
            )

        print(f"Response status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print("SUCCESS: Import completed!")
            print(f"  Imported count: {result.get('imported_count', 0)}")
            print(f"  Skipped count: {result.get('skipped_count', 0)}")
            print(f"  Total processed: {result.get('total_processed', 0)}")

            if result.get('errors'):
                print("Errors:")
                for error in result['errors'][:5]:  # Show first 5 errors only
                    print(f"  - {error}")
                if len(result['errors']) > 5:
                    print(f"  ... and {len(result['errors']) - 5} more errors")

            if result.get('warnings'):
                print("Warnings:")
                for warning in result['warnings'][:5]:  # Show first 5 warnings only
                    print(f"  - {warning}")
                if len(result['warnings']) > 5:
                    print(f"  ... and {len(result['warnings']) - 5} more warnings")

            return True
        else:
            print(f"FAILED: Import failed with status {response.status_code}")
            try:
                error_msg = response.json()
                print(f"Error message: {error_msg}")
            except:
                print(f"Error response: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        print("FAILED: Cannot connect to server. Please check if server is running.")
        return False
    except Exception as e:
        print(f"FAILED: Error during test execution: {e}")
        return False

if __name__ == "__main__":
    success = test_direct_import()
    sys.exit(0 if success else 1)
