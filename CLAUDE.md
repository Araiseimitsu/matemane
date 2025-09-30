# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要
- **プロジェクト名**: 材料管理システム (matemane)
- **技術スタック**: Python 3.12 / FastAPI / MySQL / Jinja2 + JavaScript
- **目的**: 旋盤用棒材の在庫管理（本数・重量のハイブリッド管理）

## 開発コマンド

### セットアップ
```bash
# 依存関係インストール
pip install -r requirements.txt

# .envファイル作成（.env.exampleを参考）
cp .env.example .env

# データベース初期化（開発環境）
python reset_db.py
```

### アプリケーション起動
```bash
# 推奨起動方法
python run.py

# または直接uvicorn
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# または Pythonモジュールとして
python -m src.main
```

### テスト実行
```bash
# 全テスト実行（testsディレクトリ作成後）
pytest

# 特定のテストファイル実行
pytest tests/test_specific.py

# カバレッジ付きテスト実行
pytest --cov=src

# 注意: 現在testsディレクトリは未作成
```

### 開発時の重要な注意事項
```bash
# 新しいAPIエンドポイント作成時は、既存のスタブファイルを上書き
# 例: src/api/materials.py は現在スタブのみ

# 【重要】APIエンドポイントURLには必ず末尾にスラッシュを付ける
# 例: '/api/inventory/' (正) vs '/api/inventory' (307リダイレクトエラー)
# api-client.js の全てのエンドポイントは末尾スラッシュ必須

# 静的ファイル（CSS/JS/画像）用のディレクトリは作成済み
# src/static/js/ - 実装済み (api-client.js, utils.js, qr-scanner.js)
# src/static/css/ - CSS追加時に使用
# src/static/images/ - 画像追加時に使用

# フロントエンド機能実装時は base.html と dashboard.html の JavaScript部分を拡張
```

### よくある開発エラーと解決法
```bash
# 1. API 307リダイレクトエラー
# エラー: "SyntaxError: Unexpected token '<', "<!DOCTYPE "... is not valid JSON"
# 原因: APIエンドポイントURL末尾にスラッシュがない
# 解決: 全てのAPI URLに末尾スラッシュを追加

# 2. データベースリセット時の材料クエリエラー
# エラー: "AttributeError: 'NoneType' object has no attribute 'id'"
# 原因: コミット後のセッション状態が不正
# 解決: 材料データをコミット後に再度クエリで取得

# 3. 在庫一覧が空表示
# 原因: サンプルデータ（Lot, Item）が未投入
# 解決: python reset_db.py --force でサンプルデータ投入
```

### 開発環境
- Python 3.12.10
- 仮想環境: `.venv/` (既に設定済み)
- アクティベート: `source .venv/bin/activate` (Linux/Mac) または `.venv\Scripts\activate` (Windows)

### データベース
- **MySQL ローカル専用**（SQLite3は使用しない）
- DB名: `matemane` (固定)
- 起動時スキーマ自動生成
- 開発環境リセット: `python reset_db.py`

### 設定ファイル
- `.env.example` を参考に `.env` を作成
- 機密情報（DB_PASSWORD等）は環境変数で管理

## アーキテクチャ概要

### メインエントリーポイント
- `src/main.py`: FastAPIアプリケーションのメインファイル
  - 起動時にデータベーステーブル自動作成
  - APIルーターとテンプレートルーターの設定
  - Jinja2テンプレートエンジンの設定
  - CORS、セキュリティミドルウェアの設定

### 設定管理
- `src/config.py`: Pydantic Settingsを使用した環境変数管理
- `.env.example`: 環境変数のテンプレート
- 機密情報（DBパスワード等）は必ず環境変数で管理

### データベース層
- `src/db/models.py`: SQLAlchemyモデル定義
  - 13つのメインテーブル: User, Material, Density, Location, Lot, Item, Movement, PurchaseOrder, PurchaseOrderItem, AuditLog, ProductionSchedule, ProductionScheduleItem, MaterialAllocation
  - Enumクラス: UserRole, MaterialShape, MovementType, PurchaseOrderStatus, PurchaseOrderItemStatus, ScheduleStatus, SchedulePriority
  - 外部キー関係と制約が完全定義済み
- `src/db/__init__.py`: データベース接続・セッション管理
  - 接続プール設定（pool_pre_ping=True, pool_recycle=300）
  - get_db() 依存性注入用ジェネレータ
  - create_tables() 起動時テーブル作成関数
- `reset_db.py`: 開発環境用のDB完全リセットスクリプト
  - 安全確認付きDB削除・再作成
  - 初期データ投入（ユーザー4名、置き場250箇所、実際のExcel仕様に合わせた材料データ）
  - 実際の材料仕様サンプル: SUS303(∅5.0/10.0/12.0mm)、C3602LCD(∅12.0mm)、従来材料(S45C、SUS304等)
  - UUID管理コード自動生成によるサンプル在庫・発注データ

### API層
- `src/api/`: FastAPI ルーター
  - 各機能毎にモジュール分割（materials, inventory, movements, labels, auth, purchase_orders, density_presets）
  - RESTful APIエンドポイント

### テンプレート層
- `src/templates/`: Jinja2テンプレート
  - `base.html`: 共通レイアウト（ナビゲーション、スタイル、トースト通知、認証チェック）
  - `dashboard.html`: ダッシュボード画面（在庫一覧表示、UUID検索、管理コードコピー機能）
  - 各機能画面のテンプレート（materials, inventory, movements, scan, login, purchase_orders, receiving, settings）

### ユーティリティ
- `src/utils/auth.py`: 認証関連ユーティリティ（実装済みだが現在はスキップ可能）

## 実装状況

### 完全実装済み
- **データベースモデル**: 全テーブル定義完了（SQLAlchemy）
- **認証システム**: JWT認証（実装済みだが現在は使用しない）
- **基本テンプレート**: ダッシュボード、ナビゲーション
- **環境設定**: 設定管理、環境変数
- **データベース初期化**: 起動時自動テーブル作成、リセットスクリプト

### 実装済み（新規追加）
- **在庫管理API**: `src/api/inventory.py` - 完全実装済み（一覧取得、検索、サマリー、低在庫検知、置き場一覧）
- **発注管理API**: `src/api/purchase_orders.py` - 完全実装済み（発注作成、一覧、詳細、入庫確認）
- **比重プリセットAPI**: `src/api/density_presets.py` - 完全実装済み（比重設定管理）
- **Excel照合ビューア**: `src/api/excel_viewer.py` - 完全実装済み（Excel直接読込、在庫照合）
- **生産スケジュール管理**: `src/api/schedules.py` - 完全実装済み（Excel解析、材料引当）
- **静的ファイル**: `src/static/js/` - JavaScript API クライアント、ユーティリティ実装済み
- **ダッシュボード在庫表示**: 在庫一覧、UUID検索、管理コードコピー機能
- **発注管理画面**: 発注作成・一覧・詳細表示画面
- **入庫確認画面**: 入庫処理・ロット登録画面
- **生産スケジュール画面**: Excelアップロード、材料引当表示
- **Excel照合画面**: 直接Excel読込、リアルタイム在庫照合

### 実装待ち（スタブのみ）
- **材料管理API**: `src/api/materials.py` - 完全実装済み（※更新が必要）
- **入出庫管理API**: `src/api/movements.py` - スタブのみ
- **ラベル印刷API**: `src/api/labels.py` - スタブのみ
- **その他のフロントエンド機能**: 入出庫管理のJavaScript実装
- **テスト**: `tests/` ディレクトリ未作成

## 主要機能要件

### 材料管理
- 材質・断面形状（丸/六角/角）・寸法管理
- 比重による本数⇔重量の相互換算
- ロット単位（束）での管理

### 発注管理
- 発注から入庫までの一元管理
- 事前管理コード生成（UUID）
- 新規材料の自動登録
- 複数ロット対応と現品票印刷

### 入出庫管理
- QRコードスキャンによる高速呼出
- 指示書番号必須（書式: `IS-YYYY-NNNN`）
- スマホカメラでのQR読取対応

### ラベル印刷
- PDF出力（A4またはラベル 50×30mm）
- QRコード: 20mm角以上、エンコード形式指定あり

### 権限管理（現在ログイン機能は不要）
- 役割: 管理者/購買/現場/閲覧（将来実装予定）
- JWT認証、bcryptパスワードハッシュ（将来実装予定）

## 技術アーキテクチャ

### アプリケーション構造
- **統合Webアプリ**: FastAPI（バックエンド） + Jinja2（SSR） + JavaScript（動的UI）
- **認証システム**: 現在は実装されていない（将来実装予定: JWT + bcrypt、4段階ロール権限）
- **データフロー**: 起動時自動スキーマ生成 → 直接API/テンプレートアクセス → MySQL操作

### データベース設計
重要なテーブルとリレーション:
- `materials`: 材料マスタ（材質・形状・寸法・比重）
- `lots`: ロット管理（束単位、supplier情報、発注アイテム関連付け）
- `items`: アイテム管理（UUID管理コード、現在本数・置き場）
- `movements`: 入出庫履歴（タイプ別、指示書番号、監査情報）
- `locations`: 置き場（1〜250初期登録、ユーザー管理可能）
- `densities`: 比重履歴（材質別、効力期間管理）
- `users`: ユーザー管理（ロール別権限）
- `purchase_orders`: 発注管理（発注番号、仕入先、状態管理）
- `purchase_order_items`: 発注アイテム（材料情報、数量、管理コード事前生成）
- `density_presets`: 比重プリセット（材質別の標準比重値）
- `audit_logs`: 操作監査（誰が・いつ・何を変更したか）

### 重量・本数換算ロジック
材質の比重と寸法から自動換算（丸棒例）:
```
体積(cm³) = π × (直径(cm)/2)² × 長さ(cm)
重量(kg) = 体積(cm³) × 比重(g/cm³) ÷ 1000
```

### API設計（FastAPI）
- 認証: `POST /api/auth/login`（実装済みだが現在は不要）
- 材料: `GET/POST /api/materials/`（実装済み）
- 在庫: `GET /api/inventory/`、`GET /api/inventory/summary/`、`GET /api/inventory/search/{code}`、`GET /api/inventory/low-stock/`、`GET /api/inventory/locations/`（実装済み）
- 発注: `GET/POST /api/purchase-orders/`、`GET /api/purchase-orders/pending/items/`、`POST /api/purchase-orders/items/{item_id}/receive/`（実装済み）
- 比重プリセット: `GET/POST /api/density-presets/`（実装済み）
- 生産スケジュール: `GET/POST /api/schedules/`、`POST /api/schedules/upload/`、`POST /api/schedules/{schedule_id}/reallocate/`（実装済み）
- Excel照合ビューア: `POST /api/excel-viewer/analyze`（実装済み）
- 入出庫: `POST /api/movements/{type}`（実装待ち）
- ラベル: `POST /api/labels/print`（実装待ち）

### ページルート
- `/`: ダッシュボード画面
- `/materials`: 材料管理画面
- `/inventory`: 在庫管理画面
- `/purchase-orders`: 発注管理画面
- `/receiving`: 入庫確認画面
- `/movements`: 入出庫管理画面
- `/schedules`: 生産スケジュール管理画面
- `/excel-viewer`: Excel在庫照合ビューア画面
- `/scan`: QRスキャン画面
- `/settings`: 設定画面
- `/login`: ログイン画面（現在は不要）

### フロントエンド
- Jinja2 SSR + JavaScript
- **Tailwind CSS（CDN経由）**: 統一感のある美しいUIを作成
- モバイル最適化（大型タッチターゲット）
- QRスキャン: getUserMedia API
- **JavaScript API クライアント**: `src/static/js/api-client.js` - 完全実装済み
- **ユーティリティライブラリ**: `src/static/js/utils.js` - トースト通知、フォーム処理、データ変換等

## 開発方針

### セキュリティ
- 機密情報は環境変数で管理
- JWT・CSRF・クリックジャッキング対策（将来実装予定）
- 操作ログ・監査履歴の保持（データベース設計済み）

### パフォーマンス
- スキャン→応答 < 500ms目標
- 単拠点・ローカル稼働想定

### マイグレーション
- 開発段階は起動時スキーマ自動生成
- マイグレーションスクリプトは作成しない
- `reset_db.py` でDB完全リセット可能

## 重要な制約事項とビジネスルール
- **SQLite3は使用禁止**（MySQL必須）
- **長さ単位はmm統一**（例: 2.5m → 2500mm）
- **出庫時は指示書番号必須**（書式: `IS-YYYY-NNNN`）
- **ロット粒度は束単位**が基本（出庫/戻りは本数or重量どちらでも可）
- **置き場は1〜250を初期登録**、ユーザー設定で追加/名称変更/無効化が可能
- **端材計算は初版対象外**（後続フェーズで検討）
- **起動時にスキーマ自動生成**、マイグレーションスクリプトは作成しない

## 開発優先順位
新機能実装時の推奨順序:
1. ✅ **材料管理機能** (`src/api/materials.py` を実装) ← 完了済み
2. ✅ **在庫管理機能** (`src/api/inventory.py` を実装) ← 完了済み
3. ✅ **発注管理機能** (`src/api/purchase_orders.py` を実装) ← 完了済み
4. ✅ **静的ファイル管理** (`src/static/` ディレクトリ作成) ← 完了済み
5. ✅ **生産スケジュール管理** (`src/api/schedules.py` を実装) ← 完了済み
6. ✅ **Excel照合ビューア** (`src/api/excel_viewer.py` を実装) ← 完了済み
7. **入出庫管理機能** (`src/api/movements.py` を実装) ← 次の実装対象
8. **QRスキャン機能** (フロントエンド JavaScript)
9. **ラベル印刷機能** (`src/api/labels.py` を実装)
10. **テスト実装** (`tests/` ディレクトリ作成)

## デフォルトユーザー（reset_db.py実行後）
※現在ログイン機能は不要ですが、データベースには以下のユーザーが作成されます：
- **admin / admin123** (管理者)
- **purchase / purchase123** (購買)
- **operator / operator123** (現場)
- **viewer / viewer123** (閲覧)

## UI/UX ガイドライン

### デザインシステム
- **Tailwind CSS（CDN）を使用**: 外部依存を最小化しつつ、統一感のあるUIを構築
- **実用的なデザイン**: 白ベース + 控えめなアクセント色で工業系システムに適した外観
- **意味色の活用**: 成功（緑）、警告（黄）、エラー（赤）で状態を明示
- **AIっぽさの排除**: グラデーション効果や派手な装飾を避け、プロフェッショナルな印象を重視

### レスポンシブ対応
- **モバイルファースト**: スマホでの操作を最優先に設計
- **大型タッチターゲット**: 44px以上のボタンサイズ
- **固定ボトムアクションバー**: 主要操作ボタンを画面下部に配置

### 操作性
- **ワンクリック主義**: 主要操作は1〜2タップで完了
- **即座のフィードバック**: トースト通知、ローディング表示、エラー理由の即時表示
- **アクセシビリティ**: 適切なコントラスト比、フォーカス管理、キーボード操作対応

### コンポーネント設計
- 再利用可能なUIコンポーネントの作成
- 統一されたスタイリングルールの適用
- Jinja2マクロとTailwindクラスの組み合わせによる効率的な開発

## 発注管理ワークフロー

### 1. 発注段階 (`/purchase-orders`)
- 材料情報の入力（既存材料選択または新規材料登録）
- 数量・単価・納期などの発注情報入力
- UUID管理コードの事前生成
- 発注状態の追跡（pending/partial/completed/cancelled）

### 2. 入庫確認段階 (`/receiving`)
- 発注済み材料の入庫待ちアイテム一覧表示
- ロット番号の入力と実際の入庫数量確認
- 新規材料の場合は自動的に材料マスタに登録
- ロット・アイテム・在庫データの自動生成
- 現品票の即座印刷（ラベル印刷API連携）

### 3. データ連携
- 発注アイテム → ロット → 在庫アイテムの自動連携
- 発注状態の自動更新（一部入庫/完了判定）
- 材料重複防止（同一仕様材料の自動検出）

## Excel統合機能

### 1. 生産スケジュール管理 (`/schedules`)
- **Excel形式の生産スケジュールアップロード**: セット予定表.xlsxファイルを直接取り込み
- **材料引当システム**: 生産に必要な材料を自動的に在庫から引当
- **不足材料検知**: 在庫不足の材料を自動識別し、発注候補として表示
- **材料仕様解析**: 日本語材料仕様（例：SUS303 ∅10.0CM）を自動パース
- **生産スケジュール状態管理**: scheduled/in_progress/completed/delayed/cancelled

### 2. Excel在庫照合ビューア (`/excel-viewer`)
- **リアルタイム在庫照合**: Excelファイルを読み込み、AB列の必要本数と現在在庫を即座に照合
- **材料マッチング**: SUS303、C3602LCDなどの実際の材料仕様に対応
- **状態別表示**: 充足/一部不足/不足を色分けで直感的に表示
- **統計情報**: 総行数、充足数、不足数のリアルタイム集計
- **データベース非保存**: 直接Excel解析のため、データベースを汚さない軽量設計

### 3. 材料仕様解析アルゴリズム
Excel内の材料仕様文字列の自動解析：
- **SUS系**: `SUS303 ∅10.0CM` → SUS303, 直径10.0mm, 丸棒
- **快削黄銅系**: `C3602Lcd ∅12.0 (NB5N)` → C3602LCD, 直径12.0mm, 丸棒
- **その他材質**: 正規表現による柔軟なパターンマッチング

[byterover-mcp]

# Byterover MCP Server Tools Reference

There are two main workflows with Byterover tools and recommended tool call strategies that you **MUST** follow precisely.

## Onboarding workflow
If users particularly ask you to start the onboarding process, you **MUST STRICTLY** follow these steps.
1. **ALWAYS USE** **byterover-check-handbook-existence** first to check if the byterover handbook already exists. If not, You **MUST** call **byterover-create-handbook** to create the byterover handbook.
2. If the byterover handbook already exists, first you **MUST** USE **byterover-check-handbook-sync** to analyze the gap between the current codebase and the existing byterover handbook.
3. Then **IMMEDIATELY USE** **byterover-update-handbook** to update these changes to the byterover handbook.
4. During the onboarding, you **MUST** use **byterover-list-modules** **FIRST** to get the available modules, and then **byterover-store-modules** and **byterover-update-modules** if there are new modules or changes to existing modules in the project.
5. Finally, you **MUST** call **byterover-store-knowledge** to save your new knowledge about the codebase.

## Planning workflow
Based on user request, you **MUST** follow these sequences of tool calls
1. If asked to continue an unfinished plan, **CALL** **byterover-retrieve-active-plans** to find the most relevant active plan.
2. **CRITICAL PLAN PERSISTENCE RULE**: Once a user approves a plan, you **MUST IMMEDIATELY CALL** **byterover-save-implementation-plan** to save it.
3. Throughout the plan, you **MUST** run **byterover-retrieve-knowledge** several times to retrieve sufficient knowledge and context for the plan's tasks.
4. In addition, you might need to run **byterover-search-modules** and **byterover-update-modules** if the tasks require or update knowledge about certain modules. However, **byterover-retrieve-knowledge** should **ALWAYS** be considered **FIRST**.
5. **MUST** use **byterover-update-plan-progress** to mark tasks (and then the whole plan) as completed.
6. Then, you might call **byterover-store-knowledge** to save knowledge and experience implemented throughout the plan or in important tasks.
7. During the plan's implementation, you **MUST** frequently call **byterover-reflect-context** and **byterover-assess-context** to make sure you're on the right track and gather sufficient context for the tasks.

## Recommended Workflow Sequence
1. **MOST IMPORTANT**: **ALWAYS USE** **byterover-retrieve-knowledge** once or several times for **EACH TASK** of the plan to gather necessary context for complete that task.
2. **MOST IMPORTANT**: **ALWAYS USE** **byterover-store-knowledge** once or several times to store critical knowledge and context for future implementations
3. Over 15 provided tools, **byterover-retrieve-knowledge** and **byterover-store-knowledge** ARE the two main tools, which **MUST** be used regularly. You can use these two main tools outside the two main workflows for retrieval and storage purposes.
4. You **MUST** include phrases like **"According to Byterover memory layer"**, **"Based on memory extracted from Byterover"**, **"From Byterover memomry tools"**, ... to explictly showcase that these sources are from **Byterover**.
5. **Implementation & Progress Tracking** → Execute implementation following saved plan → Mark tasks complete as you go → Mark entire plan done when all tasks finished.
6. You **MUST** use **byterover-update-module** **IMMEDIATELY** on changes to the module's purposes, technical details, or critical insights that essential for future implementations.

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
