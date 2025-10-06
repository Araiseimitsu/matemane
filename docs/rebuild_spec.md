## 再構築仕様書

## セクション1. アプリ全体構成と実行フロー

### 1-1. プロジェクト概要
- **目的**: 旋盤用棒材の在庫・発注・入出庫・検品を統合管理する新システムを構築する。
- **技術スタック**: FastAPI / SQLAlchemy / MySQL / Jinja2 / Tailwind CSS / Vanilla JS + Alpine.js（必要に応じて）。
- **依存管理**: `requirements.txt` に主要ライブラリを固定。`.env` で DB や CORS 設定を管理。
- **環境差分**: `.env` のみで開発・本番を切り替え、追加の設定ファイルは作成しない。

### 1-2. ディレクトリ構成案
```
project_root/
├─ app/
│  ├─ core/        # 設定・起動処理
│  ├─ db/          # セッション・モデル定義
│  ├─ api/         # FastAPI ルータ（機能別）
│  ├─ services/    # ビジネスロジック
│  ├─ schemas/     # Pydantic モデル
│  ├─ templates/   # Jinja2 テンプレート
│  └─ static/      # JS / CSS / 画像
├─ scripts/        # CSV 変換など補助ツール
├─ docs/           # 仕様・運用ドキュメント
├─ run.py
└─ requirements.txt
```

### 1-3. 起動フロー
1. `.env` から設定を読み込み、SQLAlchemy エンジンを生成。
2. `Base.metadata.create_all()` を実行して必要テーブルを自動生成。
3. FastAPI アプリを初期化し、CORS・TrustedHost・静的ファイル・テンプレートを設定。
4. `app/api/v1` から各機能のルータを登録。
5. `python run.py` で Uvicorn を起動（開発時はリロード有効）。

### 1-4. ミドルウェアとログ
- CORS と TrustedHost は `.env` の値で制御。
- 404/500 用のテンプレート・JSON レスポンスを共通化。
- ログは Python 標準 `logging` を INFO レベルで構成し、詳細ログは後続フェーズで検討。

### 1-5. データフロー
1. Excel のフルネームを基準に材料を登録。
2. 発注時に UUID を含む発注アイテムを生成。
3. 入庫処理でロット・在庫アイテムを作成し、置き場に割り当て。
4. 入出庫操作で数量変動を記録し、履歴テーブルへ保存。
5. 検品結果をロットに紐づく履歴テーブルへ保存。
6. ダッシュボードで在庫サマリ・不足アラートを表示。


## セクション2. データベース設計

### 2-1. 設計方針
- MySQL 8.x（InnoDB）を使用。
- ログイン機能は実装しないため認証系テーブルは不要。
- 起動時の自動テーブル生成を継続（マイグレーションツールは未導入）。
- 材料名は Excel のフルネームをユニークに保持し、ユーザーが分離した項目を補助カラムに格納。
- 置き場はユーザーが任意管理し、自動作成を行わない。

### 2-2. 主要テーブル一覧
- `materials`: `full_name`（ユニーク）を中心とした材料マスタ。`name`、`diameter_label`、`detail_info`、`usage_type` などを保持。
- `material_aliases`: 別名管理。
- `material_groups` / `material_group_members`: 同等品グループの定義と所属関係。
- `locations`: ユーザー管理の置き場マスタ。
- `purchase_orders` / `purchase_order_items`: 発注ヘッダとアイテム。`reservation_code` で UUID を保持。
- `lots`: 入庫ロット情報（発注アイテムとの関連を保持）。
- `items`: 在庫単位（管理コード UUID、置き場、現数量など）。
- `movements`: 入出庫履歴（IN/OUT、数量、指示書番号、作業者）。
- `lot_inspections`: 検品履歴（ステータス・測定値・検査メモ）。
- `density_presets`: 材料ごとの標準比重。

### 2-3. 主要制約
- `materials.full_name` にユニークインデックス。
- `material_group_members` は `(group_id, material_id)` のユニーク制約。
- `lots.lot_number`・`items.management_code`・`purchase_order_items.reservation_code` はそれぞれユニーク。
- 外部キーは基本的に `ON DELETE RESTRICT` を採用。

### 2-4. 初期化と運用
- 起動時に `create_all()` を実行、初期データは投入しない。
- 開発時にデータを入れ替える場合は `scripts/reset_db.py` を利用。


## セクション3. API 仕様

### 3-1. 設計原則
- RESTful な設計で `/api/v1/` プレフィックスを採用。
- 認証・認可は実装しない（ローカル環境前提）。
- Pydantic スキーマでリクエストとレスポンスを型付け。
- 入出庫や入庫処理はビジネスルール（在庫不足など）に応じて 400 エラーを返却。

### 3-2. エンドポイント概要
- **材料** `/api/v1/materials/`: CRUD、別名管理、Excel 解析。
- **材料グループ** `/api/v1/material-groups/`: グループの作成・メンバー管理。
- **比重プリセット** `/api/v1/density-presets/`: 比重マスタの CRUD。
- **置き場** `/api/v1/locations/`: 置き場 CRUD。
- **発注** `/api/v1/purchase-orders/`: 発注の登録・更新・アイテム追加。
- **入庫** `/api/v1/receiving/`: 発注アイテムを元にロット・在庫を生成。
- **在庫** `/api/v1/items/`・`/api/v1/lots/`: 在庫一覧・ロット管理。
- **入出庫** `/api/v1/movements/`: 入庫補正・出庫・履歴検索。
- **検品** `/api/v1/inspections/`: ロット検品履歴の登録と一覧。
- **ダッシュボード** `/api/v1/inventory/summary/` など在庫サマリ用エンドポイント。
- **Excel ツール** `/api/v1/excel/analyze/`: Excel と在庫の照合結果を返す。

### 3-3. エラーハンドリング
- 422: バリデーションエラー。
- 404: リソース未検出。
- 400: ビジネスルール違反（在庫不足など）。
- 500: サーバエラー（詳細はログで確認）。


## セクション4. フロントエンド（Jinja2 + Tailwind）

### 4-1. デザイン方針
- Tailwind CSS を用いたモダンで洗練された UI。既存デザインに縛られず再設計。
- ダーク/ライトテーマに対応できるよう配色を調整。
- モバイルファーストで設計し、主要ボタンは 44px 以上。
- Alpine.js を必要に応じて採用し、モーダルやフォームの反応性を簡潔に実装。

### 4-2. テンプレート構成
```
templates/
├─ base.html
├─ dashboard.html
├─ materials.html
├─ purchase_orders.html
├─ receiving.html
├─ inventory.html
├─ movements.html
├─ inspections.html
├─ excel_tools.html
└─ settings.html
```
- `base.html` でヘッダー・サイドナビ・トーストを共有。
- 各ページは `title` / `hero` / `content` / `modals` ブロックを定義。

### 4-3. Tailwind 運用
- 開発時は CDN、リリース時は `npx tailwindcss` で `static/css/app.css` をビルド。
- カスタムテーマを `tailwind.config.js` で定義し、アクセントカラーを統一。

### 4-4. JavaScript モジュール構成
```
static/js/
├─ apiClient.js
├─ utils.js
├─ dashboard.js
├─ materials.js
├─ purchaseOrders.js
├─ receiving.js
├─ inventory.js
├─ movements.js
├─ inspections.js
└─ excelTools.js
```
- `apiClient.js` で fetch ラッパーとエラー処理を共通化。
- DOM 更新は `data-*` 属性やテンプレート埋め込み JSON を活用し、軽量な相互作用に留める。


## セクション5. ユーティリティ & サポートツール

### 5-1. CSV/Excel 解析
- `scripts/materials_excel_parser.py` を用意し、材料フルネームと候補データを JSON/CSV に出力。
- 解析ロジックは正規表現ベースで、最終確定は UI で編集する前提。

### 5-2. データベース管理
- `scripts/reset_db.py`: 開発環境で DB を再作成するスクリプト。
- `scripts/seed_demo_data.py`: デモ用データ投入（本番では使用しない）。

### 5-3. ラベル生成テスト
- `scripts/label_preview.py`: `reportlab` と `qrcode` を使ってラベル PDF を生成（検証用）。

### 5-4. Tailwind ビルド
- `scripts/build_tailwind.py`: `npx tailwindcss` を呼び出すビルド補助。

### 5-5. ドキュメント
- `docs/operation/` へ補助ツールの使用手順を Markdown で整備。


## セクション6. レガシー整理ガイドライン

### 6-1. 持ち込み禁止事項
- 旧認証機構（`users` テーブル等）は新プロジェクトにコピーしない。
- 旧巨大テンプレートや JS ファイルは参考に留め、再実装する。
- 不要な Excel / CSV / バイナリはリポジトリに含めない。

### 6-2. 再利用条件
- アルゴリズム・正規表現など概念的な要素のみ参照。
- コードを移植する場合でも命名・構造を新プロジェクト規約に合わせて再実装。

### 6-3. クリーンアップルール
- `tmp/`・`old/` 等の一時ディレクトリは作成しない。
- PR チェックリストに不要ファイル混入確認を追加。
- 新規スクリプトを追加する際は関連ドキュメントを同時に更新。

### 6-4. 継続的整理プロセス
1. 参考にした旧コードは `legacy_notes/` に記録。
2. 新実装が完了したら記録を削除。
3. 定期的に自動レポートで未使用ファイルを検出し整理。


## セクション7. 次のアクション
- この仕様を基に新リポジトリ（またはブランチ）を作成し、ディレクトリと初期ファイルを整備。
- DB モデル・API スキーマ・フロントテンプレートを順次実装。
- 実装進捗に合わせて本ドキュメントを更新し、変更履歴を管理。
