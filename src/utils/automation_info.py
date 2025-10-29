"""
Automation情報取得ユーティリティ

このモジュールはGitリポジトリの最新コミット情報を取得します。
"""

import subprocess
from datetime import datetime
from typing import Dict, Optional


def get_latest_commit_info() -> Dict[str, str]:
    """
    最新のコミット情報を取得する
    
    Returns:
        Dict[str, str]: コミット情報を含む辞書
            - hash: コミットハッシュ
            - author: 作成者名
            - date: コミット日時
            - message: コミットメッセージ
    """
    try:
        # コミットハッシュを取得
        commit_hash = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'],
            text=True
        ).strip()
        
        # 作成者を取得
        author = subprocess.check_output(
            ['git', 'log', '-1', '--pretty=%an'],
            text=True
        ).strip()
        
        # コミット日時を取得
        date = subprocess.check_output(
            ['git', 'log', '-1', '--pretty=%ci'],
            text=True
        ).strip()
        
        # コミットメッセージを取得
        message = subprocess.check_output(
            ['git', 'log', '-1', '--pretty=%s'],
            text=True
        ).strip()
        
        return {
            'hash': commit_hash,
            'author': author,
            'date': date,
            'message': message
        }
    except subprocess.CalledProcessError as e:
        return {
            'hash': 'N/A',
            'author': 'N/A',
            'date': 'N/A',
            'message': f'Error: {str(e)}'
        }


def get_automation_commit_summary() -> str:
    """
    Automation関連の最新コミット情報のサマリーを取得する
    
    Returns:
        str: フォーマットされたコミット情報
    """
    info = get_latest_commit_info()
    
    summary = f"""
╔═══════════════════════════════════════════════════════════╗
║           Automationの最新コミット情報                     ║
╠═══════════════════════════════════════════════════════════╣
║ コミットハッシュ: {info['hash'][:7]}...                    
║ 作成者          : {info['author']}
║ 日時            : {info['date']}
║ メッセージ      : {info['message']}
╚═══════════════════════════════════════════════════════════╝
    """.strip()
    
    return summary


if __name__ == '__main__':
    print(get_automation_commit_summary())
