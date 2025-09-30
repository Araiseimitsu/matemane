#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
APIの直接テストスクリプト
"""

import requests
import os

def test_api():
    csv_path = '材料マスター.csv'

    if not os.path.exists(csv_path):
        print(f'File not found: {csv_path}')
        return False

    print(f'File exists: {csv_path}')
    print(f'Size: {os.path.getsize(csv_path)} bytes')

    with open(csv_path, 'rb') as f:
        files = {'file': ('材料マスター.csv', f, 'text/csv')}

        try:
            print('Sending request to /api/materials/import-csv...')
            r = requests.post('http://127.0.0.1:8000/api/materials/import-csv', files=files, timeout=30)
            print(f'Status: {r.status_code}')

            if r.status_code == 200:
                result = r.json()
                print('SUCCESS!')
                print(f'Imported: {result.get("imported_count", 0)}')
                print(f'Skipped: {result.get("skipped_count", 0)}')
                print(f'Total: {result.get("total_processed", 0)}')

                if result.get('errors'):
                    print('Errors:')
                    for error in result['errors'][:3]:
                        print(f'  - {error}')
                    if len(result['errors']) > 3:
                        print(f'  ... and {len(result["errors"]) - 3} more errors')

                if result.get('warnings'):
                    print('Warnings:')
                    for warning in result['warnings'][:3]:
                        print(f'  - {warning}')
                    if len(result['warnings']) > 3:
                        print(f'  ... and {len(result["warnings"]) - 3} more warnings')

                return True
            else:
                print(f'FAILED: {r.status_code}')
                try:
                    error_detail = r.json()
                    print(f'Error detail: {error_detail}')
                except:
                    print(f'Response: {r.text}')
                return False

        except Exception as e:
            print(f'Exception: {e}')
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    test_api()
