#!/usr/bin/env python
"""
Automationの最新コミット情報を表示するコマンドラインツール

使用方法:
    python get_automation_commit.py
"""

from src.utils.automation_info import get_automation_commit_summary

if __name__ == '__main__':
    print(get_automation_commit_summary())
