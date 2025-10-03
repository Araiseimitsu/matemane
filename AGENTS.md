# Repository Guidelines

## Project Structure & Module Organization
- `src/main.py` 起動ポイント。FastAPI アプリとテンプレート登録を行います。
- `src/api/` REST エンドポイント群。入庫(`purchase_orders`)、在庫(`inventory`)などリソース単位でモジュール化。
- `src/templates/` と `src/static/` は Jinja2 テンプレートと Tailwind ベースのアセット置き場です。
- `src/db/` SQLAlchemy モデル、セッション管理、初期化スクリプトを格納。
- `tests/` 以下に pytest テストを配置し、`src/` の構造をミラーします。

## Build, Test, and Development Commands
- `python -m venv .venv` → 仮想環境の作成。
- `pip install -r requirements.txt` → 依存関係のインストール。
- `uvicorn src.main:app --reload` → 開発サーバーをポート8000で起動。
- `python run.py` → プロジェクト既定設定を読み込んでサーバー起動。
- `pytest` → 自動テスト実行。`pytest -q` で簡潔表示。
- `python reset_db.py` → 開発用DBリセット（使い捨て環境のみ）。

## Coding Style & Naming Conventions
- PEP 8 準拠、インデントは4スペース。
- モジュール/ファイル名は `snake_case`、テンプレートはルート名に合わせた命名。
- 公開関数には型ヒントを付与。
- `ruff` や `flake8` が設定されている場合は実行して lint を保つ。

## Testing Guidelines
- フレームワークは pytest。重要フロー（認証、発注、在庫移動）に対する回帰テストを優先。
- テストファイルは `tests/test_<module>.py`、テスト関数は `test_<feature>_<scenario>` に統一。
- `pytest --maxfail=1` で早期失敗検知、`pytest -k "receiving"` で対象絞り込みが可能。

## Commit & Pull Request Guidelines
- Conventional Commits を推奨（例: `feat: add receiving detail field`）。
- PR には目的、主要変更点、テスト結果を明記。UI 変更時はスクリーンショットを添付。
- CI（lint + pytest）がグリーンになってからレビュー依頼。

## Security & Configuration Tips
- `.env` や秘密情報はコミット禁止。`.env.example` を更新し環境差分を共有。
- `src/config.py` の環境変数を見直し、本番デプロイ前に上書き設定を確認。
- DB リセット系スクリプトは本番環境で実行しないこと。

[byterover-mcp]

[byterover-mcp]

You are given two tools from Byterover MCP server, including
## 1. `byterover-store-knowledge`
You `MUST` always use this tool when:

+ Learning new patterns, APIs, or architectural decisions from the codebase
+ Encountering error solutions or debugging techniques
+ Finding reusable code patterns or utility functions
+ Completing any significant task or plan implementation

## 2. `byterover-retrieve-knowledge`
You `MUST` always use this tool when:

+ Starting any new task or implementation to gather relevant context
+ Before making architectural decisions to understand existing patterns
+ When debugging issues to check for previous solutions
+ Working with unfamiliar parts of the codebase

[byterover-mcp]

[byterover-mcp]

You are given two tools from Byterover MCP server, including
## 1. `byterover-store-knowledge`
You `MUST` always use this tool when:

+ Learning new patterns, APIs, or architectural decisions from the codebase
+ Encountering error solutions or debugging techniques
+ Finding reusable code patterns or utility functions
+ Completing any significant task or plan implementation

## 2. `byterover-retrieve-knowledge`
You `MUST` always use this tool when:

+ Starting any new task or implementation to gather relevant context
+ Before making architectural decisions to understand existing patterns
+ When debugging issues to check for previous solutions
+ Working with unfamiliar parts of the codebase
