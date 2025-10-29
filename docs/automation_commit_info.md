# Automationコミット情報取得機能

## 概要

このドキュメントは「Automationの最新のコミットは？」という質問に対する回答として実装された機能について説明します。

## 実装内容

### 1. ユーティリティモジュール (`src/utils/automation_info.py`)

Gitリポジトリの最新コミット情報を取得する機能を提供します。

**主要機能:**
- `get_latest_commit_info()`: 最新コミットの詳細情報を取得
- `get_automation_commit_summary()`: フォーマットされたコミット情報を表示

### 2. コマンドラインツール (`get_automation_commit.py`)

プロジェクトルートから簡単に実行できるCLIツールです。

## 使用方法

### 基本的な使用方法

```bash
# コマンドラインツールとして実行
python get_automation_commit.py
```

### Pythonモジュールとして実行

```bash
# モジュールとして直接実行
python -m src.utils.automation_info
```

### Pythonコードから使用

```python
from src.utils.automation_info import get_latest_commit_info

# コミット情報を取得
info = get_latest_commit_info()
print(f"最新コミット: {info['hash']}")
print(f"作成者: {info['author']}")
print(f"日時: {info['date']}")
print(f"メッセージ: {info['message']}")
```

## 出力例

```
╔═══════════════════════════════════════════════════════════╗
║           Automationの最新コミット情報                     ║
╠═══════════════════════════════════════════════════════════╣
║ コミットハッシュ: 52ef1ad...                    
║ 作成者          : copilot-swe-agent[bot]
║ 日時            : 2025-10-29 14:00:42 +0000
║ メッセージ      : Add automation commit info utility
╚═══════════════════════════════════════════════════════════╝
```

## 技術詳細

- **使用技術**: Python 3.12
- **依存関係**: 標準ライブラリのみ（subprocess）
- **Git操作**: `git rev-parse`, `git log` コマンドを使用

## 更新履歴

- 2025-10-29: 初版作成
