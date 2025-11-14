# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要
- **プロジェクト名**: 材料管理システム (matemane)
- **技術スタック**: Python 3.12 / FastAPI / MySQL / Jinja2 + JavaScript
- **目的**: 旋盤用棒材の在庫管理（本数・重量のハイブリッド管理）
- **運用フロー**: Excel取込 → 発注管理 → 入庫確認 → 検品 → 在庫管理

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
```

### データベース管理
```bash
# データベース完全リセット（全データ削除）
python reset_db.py

# 強制実行（確認スキップ）
python reset_db.py --force
```

### Excel取込スクリプト
```bash
# DRY-RUN（検証のみ）
python -m src.scripts.excel_po_import --excel "材料管理.xlsx" --sheet "材料管理表" --dry-run

# 本実行（DB書き込み）
python -m src.scripts.excel_po_import --excel "材料管理.xlsx" --sheet "材料管理表"
```

### 重要な注意事項
- **APIエンドポイントURLには必ず末尾にスラッシュを付ける**（例: `/api/inventory/`）
- **データベーススキーマ変更後は必ず `python reset_db.py` で完全リセット**
- **Pydanticスキーマとモデル定義の整合性を必ず確認**（削除したカラムがレスポンススキーマに残っていないか注意）

### テストコマンド
```bash
# ユニットテスト実行
pytest

# 特定のテストファイル実行
pytest tests/test_materials.py

# カバレッジ付きテスト
pytest --cov=src --cov-report=html
```

### 開発環境
- Python 3.12.10
- 仮想環境: `.venv/` (既に設定済み)
- アクティベート: `.venv\Scripts\activate` (Windows)

### データベース
- **MySQL ローカル専用**（SQLite3は使用しない）
- DB名: `matemane` (固定)
- 起動時スキーマ自動生成
- 開発環境リセット: `python reset_db.py`

## アーキテクチャ概要

### メインエントリーポイント
- `src/main.py`: FastAPIアプリケーションのメインファイル
  - 起動時にデータベーステーブル自動作成
  - APIルーターとテンプレートルーターの設定
  - Jinja2テンプレートエンジンの設定

### 【重要】材料名の取り扱い方針（2025-01-07更新）
- **材料名はExcel表記のフルネームのみで管理**
- **ユーザーによる材料名の解析・分解は不要**
- **`display_name` カラムのみを使用し、`name`・`detail_info` カラムは完全に廃止**
- 入庫確認モーダルでは、Excelから取得した材料名（フルネーム）を表示
- ユーザーは計算用パラメータ（径・形状・比重）のみを入力
- 径はExcel材料名から自動抽出（例: "SUS303 φ10.0" → 10.0）
- 形状はExcel材料名から自動判定（φ→丸棒、H→六角棒、□→角棒）
- 全画面で材料名は`display_name`のみを表示

### データベース層（2025-01 リファクタリング済み）
- `src/db/models.py`: SQLAlchemyモデル定義
  - **削除済み**: `MaterialStandard`, `MaterialGrade`, `MaterialProduct` テーブル（未実装の3層構造）
  - **削除済み**: `UsageType` Enum（グループ運用へ移行）
  - **削除済みカラム**:
    - `materials.name`（材質名）、`materials.detail_info`（詳細情報） → `display_name`に統合
    - `materials.product_id`, `materials.usage_type`, `materials.dedicated_part_number`
    - `purchase_orders.purpose`（用途・製品名） → `notes`に記録
    - `purchase_order_items.management_code`（入庫時にItem側でUUID生成）
    - `movements.instruction_number`（未実装の指示書機能）

  - 主要テーブル: User, Material, MaterialAlias, MaterialGroup, MaterialGroupMember, Density, Location, Lot, Item, Movement, PurchaseOrder, PurchaseOrderItem, DensityPreset, AuditLog
  - Enumクラス: UserRole, MaterialShape, MovementType, PurchaseOrderStatus, PurchaseOrderItemStatus, OrderType, InspectionStatus

### API層（2025-01 リファクタリング済み）
- `src/api/purchase_orders.py`: 発注管理
  - **実装済み**: Excel取込、一覧取得、詳細取得、入庫確認API
  - **追加済み（2025-10-09）**: 発注ヘッダー編集 (`PUT /api/purchase-orders/{order_id}`)
  - **追加済み（2025-10-09）**: 発注アイテム編集 (`PUT /api/purchase-orders/items/{item_id}`)
  - **追加済み（2025-10-09）**: 発注削除 (`DELETE /api/purchase-orders/{order_id}`)

- `src/api/materials.py`: 材料マスタ管理（2025-01-06 完全リファクタリング）
  - **修正済み**: 欠落していたCRUD実装（POST/GET/PUT）
  - **削除済み**: 標準規格/グレード/製品関連のエンドポイント
  - **削除済み**: 未使用ユーティリティ関数（parse_material_specification等）
  - **保持**: 材料CRUD、別名管理、材料検索、総件数取得（`/count`）

- `src/api/movements.py`: 入出庫管理（2025-01完全実装、2025-10-09編集機能追加）
  - **削除済み**: 指示書番号関連のエンドポイント
  - **実装済み**: 入庫（戻し）処理、出庫処理、履歴取得
  - **追加済み（2025-10-09）**: 履歴編集 (`PUT /api/movements/{movement_id}`)
  - **追加済み（2025-10-09）**: 履歴削除 (`DELETE /api/movements/{movement_id}`)
  - **重要**: 編集・削除時は在庫数を自動再計算、監査ログに記録

- `src/api/analytics.py`: 集計・分析（2025-01実装）
  - 材料別・日付別の在庫数、入出庫数、金額を集計
  - Chart.js用のグラフデータ生成（時系列、材料別構成比、仕入先別金額）
  - CSV/Excel出力（openpyxl使用）
  - **重要**: SQLAlchemyのJOIN条件は明示的に指定（`Material.id == Lot.material_id`）

- `src/scripts/excel_po_import.py`: Excel取込スクリプト
  - 材料管理.xlsxから発注データを自動作成
  - **取込条件**: I列(品番)非空、L列(材料)非空、Z列(指定納期)入力あり、AC列(入荷日)が空
  - **列マッピング**:
    - I列: 品番 → `item_name`
    - L列: 材料 → `item_name` に統合
    - T列: 数量 → `ordered_quantity`
    - Z列: 指定納期 → `expected_delivery_date`
    - AC列: 入荷日 → 空の場合のみ取込対象

### テンプレート層（2025-01 リファクタリング済み）
- `src/templates/base.html`: 共通レイアウト
  - Tailwind CSS v3.4（CDN）
  - Font Awesome 6.4（アイコン）
  - 共通ナビゲーション

- `src/templates/order_flow.html`: 発注フロー統合画面
  - Excel取込タブ
  - 入庫確認タブ（発注待ち一覧）
  - 検品タブ（検品ステータス管理）
  - ラベル印刷タブ

- `src/templates/inventory.html`: 在庫管理画面
  - 同等品グループ別表示
  - JavaScriptクラス設計: `InventoryManager`, `InventoryFilterManager`
  - 材料グループ名の集約ロジック
  - QRコード連携

- `src/templates/movements.html`: 入出庫管理画面（統合フォーム、2025-10-09編集機能追加）
  - **削除済み**: 重複した入庫/出庫フォーム（約200行）
  - **削除済み**: 重複したJavaScript関数（約300行）
  - **保持**: 統合フォーム（出庫/戻し切替）、在庫一覧、履歴表示、QRスキャン
  - **追加済み（2025-10-09）**: 履歴編集モーダル、削除ボタン
  - 数量⇔重量の自動相互換算

- `src/templates/analytics.html`: 集計・分析画面
  - 検索フォーム（日付範囲、材料名、購入月、仕入先、入出庫種別）
  - 集計サマリーカード（在庫数、入出庫数、金額）
  - Chart.js v4によるグラフ表示（時系列、円グラフ、棒グラフ）
  - CSV/Excel出力ボタン

## 実装状況（2025-10更新）

### 完全実装済み
- ✅ **Excel取込による発注管理**: 自動発注作成、一覧表示、詳細確認
- ✅ **発注編集・削除機能**: 発注ヘッダー・アイテム編集、未入庫発注の削除（2025-10-09追加）
- ✅ **入庫確認機能**: ロット登録、材料マスタ自動登録、在庫生成
- ✅ **検品機能**: 検品ステータス管理、再編集機能
- ✅ **在庫管理API**: 一覧取得、検索、サマリー、低在庫検知
- ✅ **材料管理**: 材料CRUD、別名管理、グループ管理
- ✅ **生産スケジュール管理**: Excel解析、材料引当
- ✅ **Excel照合ビューア**: 直接Excel読込、在庫照合
- ✅ **入出庫管理**: 統合フォーム（出庫/戻し）、在庫一覧表示、履歴管理、QRスキャン、数量⇔重量換算
- ✅ **入出庫履歴編集・削除**: 履歴の編集・削除機能、在庫数の自動再計算（2025-10-09追加）
- ✅ **集計・分析機能**: 材料別集計、時系列グラフ、CSV/Excel出力

### 実装待ち
- ⏳ **ラベル印刷機能**: `src/api/labels.py` - スタブのみ
- ⏳ **テスト**: `tests/` ディレクトリ未作成

## 主要画面とルーティング

| URL | 画面名 | 機能 |
|-----|--------|------|
| `/` | ダッシュボード | KPI表示、クイックアクション、在庫アラート、最近の入出庫 |
| `/order-flow` | 発注フロー統合 | Excel取込→入庫確認→検品→ラベル印刷の一連の流れ |
| `/materials` | 材料マスタ管理 | 材料CRUD、別名管理、CSV一括インポート |
| `/inventory` | 在庫管理 | グループ別在庫表示、検索、フィルタ |
| `/movements` | 入出庫管理 | 統合フォーム（出庫/戻し）、履歴表示・編集・削除、QRスキャン |
| `/production-schedule` | 生産中一覧 | Excel解析、材料引当、在庫切れ予測 |
| `/excel-viewer` | Excel照合ビューア | 直接Excel読込、在庫照合 |
| `/analytics` | 集計・分析 | 材料別集計、入出庫推移、金額分析、CSV/Excel出力 |
| `/settings` | 設定 | 比重プリセット、システム設定 |

## 主要ワークフロー

### Excel取込 → 発注管理
1. `/order-flow` でExcel取込ボタンをクリック
2. DRY-RUNで検証 → 実行でDB書き込み
3. 発注一覧に自動表示

### 入庫確認 → 検品（2025-01-07更新）
1. `/order-flow` の入庫確認タブで入庫待ちアイテムを表示
2. **材料名**: Excelから取得したフルネームをそのまま表示（ユーザー入力不要）
3. **計算用パラメータ**: 径・形状・比重を入力（径と形状は材料名から自動抽出）
4. ロット番号・長さ・入庫数量・仕入先を入力
5. 入庫実行 → 材料マスタに`display_name`として登録（新規時）
6. 検品タブで検品ステータスを管理（PENDING/PASSED/FAILED）

### 入出庫管理（2025-10更新）
1. `/movements` で統合フォームから出庫/戻しを選択
2. 在庫一覧で対象アイテムを検索または直接選択ボタンをクリック
3. 数量または重量を入力（自動相互換算）
4. 備考を入力して実行
5. 履歴は自動記録され、下部に表示
6. 履歴の編集・削除は各行の「編集」「削除」ボタンから実行可能

## データベース設計（2025-01更新）

### 重要なテーブル
- `materials`: 材料マスタ（Excel取込のフルネームで管理）
  - **削除**: `name`（材質名）, `detail_info`（詳細情報）, `product_id`, `usage_type`, `dedicated_part_number`
  - **必須**: `display_name`（Excelから取得したフルネーム・例: "SUS303 φ10.0 研磨"）
  - **計算用**: `shape`, `diameter_mm`, `current_density`（重量⇔本数換算のみに使用）
  - **その他**: `part_number`, `description`, `is_active`, `created_at`, `updated_at`
- `material_aliases`: 材料別名（表記揺れ対応）
- `material_groups`: 材料グループ（同等品管理）
- `material_group_members`: グループ所属（多対多）
- `lots`: ロット管理（束単位、検品ステータス）
- `items`: アイテム管理（UUID管理コード、現在本数・置き場）
- `movements`: 入出庫履歴（種別・数量・備考・処理者・処理日時）
  - **削除**: `instruction_number`（未実装の指示書機能）
- `purchase_orders`: 発注管理（発注番号、仕入先、状態管理）
  - **削除**: `purpose`（用途・製品名） → 品番は`notes`に記録
- `purchase_order_items`: 発注アイテム（材料仕様文字列、数量）
  - **削除**: `management_code`（入庫時にItem側で生成）
  - `item_name`: Excelから取得した材料名フルネーム（入庫時に`Material.display_name`として登録）
- `audit_logs`: 監査ログ（全ての編集・削除操作を記録）

### データフロー
1. **Excel取込**: 材料管理.xlsx → PurchaseOrder + PurchaseOrderItem（`item_name`にフルネームを保存）
2. **入庫確認**:
   - **材料名**: PurchaseOrderItem.item_name（Excelのフルネーム）→ Material.display_name（そのまま保存）
   - **計算用パラメータ**: ユーザーが径・形状・比重を入力 → Material.diameter_mm, shape, current_density（計算専用）
   - **自動抽出**: JavaScriptが材料名から径・形状を自動抽出してフォームに設定
   - Lot → Item（UUID生成）
3. **検品**: Lot.inspection_status 更新
4. **在庫管理**: Item（UUID管理コード、現在本数、置き場）
5. **入出庫**: Item.current_quantity 更新 → Movement履歴記録 → AuditLog記録
6. **履歴編集・削除（2025-10-09追加）**: Movement更新/削除 → Item.current_quantity 再計算 → AuditLog記録

### フロントエンド技術
- **テンプレートエンジン**: Jinja2（サーバーサイドレンダリング）
- **CSS フレームワーク**: Tailwind CSS v3.4（CDN経由）
- **JavaScript**: ES6（モジュールパターン、クラスベース設計）
- **アイコン**: Font Awesome 6.4
- **主要JavaScriptクラス**:
  - `InventoryManager`: 在庫管理画面のメインロジック
  - `InventoryFilterManager`: フィルタ機能
  - `MovementManager`: 入出庫処理（統合フォーム）
- **QRコード**: getUserMedia API（カメラスキャン）、jsQR ライブラリ

## API設計（2025-10更新）

### 発注管理
- `GET /api/purchase-orders/` - 発注一覧取得（ページネーション対応）
- `GET /api/purchase-orders/{order_id}` - 発注詳細取得
- `POST /api/purchase-orders/external-import-test` - Excel取込
- `PUT /api/purchase-orders/{order_id}` - 発注ヘッダー編集（仕入先・納期・備考）
- `PUT /api/purchase-orders/items/{item_id}` - 発注アイテム編集（数量・単価・金額、未入庫のみ）
- `DELETE /api/purchase-orders/{order_id}` - 発注削除（未入庫のみ）
- `GET /api/purchase-orders/pending-or-inspection/items/` - 入庫待ち・検品未完了アイテム取得
- `POST /api/purchase-orders/items/{item_id}/receive/` - 入庫確認
- `PUT /api/purchase-orders/items/{item_id}/receive/` - 入庫内容再編集
- `GET /api/purchase-orders/items/{item_id}/inspection-target/` - 検品対象取得

### 在庫管理
- `GET /api/inventory/` - 在庫一覧取得
- `GET /api/inventory/summary/` - 在庫サマリー取得
- `GET /api/inventory/search/{code}` - UUID検索
- `GET /api/inventory/low-stock/` - 低在庫検知
- `GET /api/inventory/locations/` - 置き場一覧

### 材料管理
- `GET /api/materials/count` - 材料総件数取得（フィルタ対応）
- `GET /api/materials/` - 材料一覧取得（ページネーション対応）
- `GET /api/materials/{material_id}` - 材料詳細取得
- `POST /api/materials/` - 材料作成
- `PUT /api/materials/{material_id}` - 材料更新
- `DELETE /api/materials/{material_id}` - 材料削除（論理削除）
- `GET /api/materials/{material_id}/calculate-weight` - 重量計算
- `GET /api/materials/search/` - 材料横断検索（別名・在庫含む）
- `GET /api/materials/aliases/` - 別名一覧取得
- `POST /api/materials/aliases/` - 別名作成

### 入出庫管理（2025-10更新）
- `GET /api/movements/` - 入出庫履歴取得（フィルタ: movement_type, item_id）
- `POST /api/movements/in/{item_id}` - 入庫（戻し）処理
- `POST /api/movements/out/{item_id}` - 出庫処理
- `PUT /api/movements/{movement_id}` - 履歴編集（数量・重量・備考、在庫数も再計算）
- `DELETE /api/movements/{movement_id}` - 履歴削除（在庫数を巻き戻し）
  - 数量または重量を指定（相互換算対応）
  - 備考記入可能
  - 自動的にMovementとAuditLog記録

### 集計・分析（2025-01実装）
- `GET /api/analytics/summary/` - 集計検索（日付、材料名、購入月、仕入先、入出庫種別で絞り込み）
- `GET /api/analytics/graph/timeline/` - 時系列推移グラフ（日別入出庫）
- `GET /api/analytics/graph/material-composition/` - 材料別構成比（円グラフ）
- `GET /api/analytics/graph/supplier-amount/` - 仕入先別金額（棒グラフ）
- `GET /api/analytics/export/csv/` - CSV出力（UTF-8 BOM付き）
- `GET /api/analytics/export/excel/` - Excel出力（openpyxl使用）

## 重要な制約事項

### データベース
- **SQLite3は使用禁止**（MySQL必須）
- **スキーマ変更後は必ず `python reset_db.py` で完全リセット**
- **マイグレーションスクリプトは使用しない**

### 開発ルール
- **APIエンドポイントURLには必ず末尾スラッシュを付ける**
- **Pydanticスキーマとモデル定義の整合性を常に確認**
- **削除したDBカラムがレスポンススキーマに残っていないか注意**
- **長さ単位はmm統一**（例: 2.5m → 2500mm）

### ビジネスルール
- **発注作成は手動不可、Excel取込のみ**
- **入庫時にUUID管理コードを自動生成**（事前生成しない）
- **汎用/専用区分は廃止、グループ運用で統一**
- **検品は入庫後に別フローで実施**

## リファクタリング履歴（2025-01）

### 実施内容
1. ✅ **不要なDBテーブル削除**: MaterialStandard, MaterialGrade, MaterialProduct
2. ✅ **不要なカラム削除**:
   - materials.product_id, usage_type, dedicated_part_number → detail_info に統一
   - purchase_order_items.management_code
   - movements.instruction_number
3. ✅ **発注管理API簡素化**: 手動作成API削除、Excel取込専用化
4. ✅ **発注管理UI簡素化**: モーダル1500行削除、Excel取込+一覧表示のみ
5. ✅ **materials.py完全リファクタリング** (2025-01-06):
   - 欠落CRUD実装（POST/GET/PUT）
   - 未使用関数削除（parse_material_specification等、約200行）
   - 削除済みテーブル参照削除
   - `/count` エンドポイント追加
6. ✅ **入出庫管理完全実装**: 統合フォーム実装、重複コード約500行削除
7. ✅ **入庫確認ページ最適化**: N+1問題解消（API呼び出し95%削減）
8. ✅ **履歴編集・削除機能追加** (2025-10-09):
   - 発注ヘッダー・アイテム編集API追加
   - 発注削除API追加（未入庫のみ）
   - 入出庫履歴編集・削除API追加（在庫数自動再計算）
   - movements.html に編集・削除UI追加

### 削除理由
- **MaterialStandard/Grade/Product**: 未実装の3層構造、実運用で不要
- **UsageType（汎用/専用区分）**: MaterialGroup運用へ移行済み
- **management_code事前生成**: 入庫時にItem側でUUID生成するため重複
- **手動発注作成API**: Excel取込のみ使用、UI削除済みのため不要
- **instruction_number**: 指示書機能は未実装で使用されていない
- **重複フォーム（movements）**: 統合フォームで機能統一、旧フォームは不要

## デフォルトユーザー（reset_db.py実行後）
※現在ログイン機能は不要ですが、データベースには以下のユーザーが作成されます：
- **admin / admin123** (管理者)
- **purchase / purchase123** (購買)
- **operator / operator123** (現場)
- **viewer / viewer123** (閲覧)

## トラブルシューティング

### よくあるエラー

1. **307 Redirect エラー**
   - 原因: APIエンドポイントURLの末尾にスラッシュが付いていない
   - 解決: すべてのAPIエンドポイントURLに末尾スラッシュを付ける（例: `/api/inventory/`）

2. **データベース起動エラー**
   - 原因: MySQLサーバーが起動していない、または接続情報が間違っている
   - 解決: MySQLサービス起動確認、`.env`ファイルのDB接続設定確認

3. **スキーマ変更後の不整合エラー**
   - 原因: モデル定義とPydanticスキーマの不一致
   - 解決: `python reset_db.py` で完全リセット（※全データ削除）

4. **Pydantic ValidationError**
   - 原因: 削除したDBカラムがレスポンススキーマに残っている
   - 解決: API のレスポンススキーマ（Pydantic BaseModel）から該当フィールドを削除

5. **Excel取込エラー**
   - 原因: 列マッピングが不正、または必須列が空
   - 解決: DRY-RUNモードで検証、エラーログで詳細確認

## 開発のベストプラクティス

### コードスタイル
- **Python**: PEP 8準拠、型ヒント必須
- **JavaScript**: ES6+、クラスベース設計、`const`/`let`使用（`var`禁止）
- **HTML**: インデント2スペース、Tailwind ユーティリティクラス優先

### データベース操作
- スキーマ変更時は必ず `python reset_db.py` で検証
- マイグレーションスクリプトは使用しない（開発環境のみ）
- N+1問題に注意（eager loading活用）

### API開発
- エンドポイントURLには必ず末尾スラッシュ
- Pydanticスキーマで入出力を厳密に定義
- エラーハンドリングは明示的に（HTTPException使用）

### UI/UXパターン
- **モーダル操作**: ESCキーで閉じる、背景クリックで閉じる、コンテンツクリックは伝播停止
- **フォーム操作**: 数量⇔重量の相互換算、リアルタイムバリデーション
- **QRスキャン**: getUserMedia API + jsQR ライブラリ、カメラ選択機能実装済み

### UI/UX特記事項
- **ナビゲーション配置**: 集計・分析機能はユーザーメニュー（右上プロフィールアイコン）内に配置
- **グラフライブラリ**: Chart.js v4（CDN経由）を使用
- **ブラウザ拡張エラー**: `chrome-extension://invalid/` エラーは無視（拡張機能の誤動作）

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
