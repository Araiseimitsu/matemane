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

### 開発時の重要な注意事項
```bash
# 【重要】APIエンドポイントURLには必ず末尾にスラッシュを付ける
# 例: '/api/inventory/' (正) vs '/api/inventory' (307リダイレクトエラー)

# データベーススキーマ変更後は必ずリセット
# python reset_db.py でデータベース完全リセット（※データは全て消去されます）

# Pydanticスキーマとモデル定義の整合性を必ず確認
# 特に削除したカラムがレスポンススキーマに残っていないか注意
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

### データベース層（2025-01 リファクタリング済み）
- `src/db/models.py`: SQLAlchemyモデル定義
  - **削除済み**: `MaterialStandard`, `MaterialGrade`, `MaterialProduct` テーブル（未実装の3層構造）
  - **削除済み**: `UsageType` Enum（グループ運用へ移行）
  - **削除済みカラム**: `materials.product_id`, `materials.usage_type`, `materials.dedicated_part_number`
  - **削除済みカラム**: `purchase_order_items.management_code`（入庫時にItem側でUUID生成）

  - 主要テーブル: User, Material, MaterialAlias, MaterialGroup, MaterialGroupMember, Density, Location, Lot, Item, Movement, PurchaseOrder, PurchaseOrderItem, DensityPreset, AuditLog
  - Enumクラス: UserRole, MaterialShape, MovementType, PurchaseOrderStatus, PurchaseOrderItemStatus, OrderType, InspectionStatus

### API層（2025-01 リファクタリング済み）
- `src/api/purchase_orders.py`: **Excel取込専用**
  - **削除済み**: 手動発注作成API (`POST /api/purchase-orders/`)
  - **削除済み**: 発注編集API (`PUT /api/purchase-orders/{order_id}`)
  - **削除済み**: 発注削除API (`DELETE /api/purchase-orders/{order_id}`)
  - **削除済み**: 重量⇔本数換算API (`POST /api/purchase-orders/calculate-conversion/`)
  - **保持**: Excel取込、一覧取得、詳細取得、入庫確認API

- `src/api/materials.py`: 材料マスタ管理
  - **削除済み**: 標準規格/グレード/製品関連のエンドポイント
  - **保持**: 材料CRUD、別名管理、材料検索

- `src/scripts/excel_po_import.py`: Excel取込スクリプト
  - 材料管理.xlsxから発注データを自動作成
  - 条件: I列(品番)非空、L列(材料)非空、Z列(指定納期)入力あり、AC列(入荷日)が空

### テンプレート層（2025-01 リファクタリング済み）
- `src/templates/purchase_orders.html`: **Excel取込と一覧表示のみ**
  - **削除済み**: 発注追加/編集モーダル（1500行以上）
  - **削除済み**: 材料検索・選択機能
  - **保持**: Excel取込ボタン、発注一覧表示、詳細モーダル（読み取り専用）

- `src/templates/receiving.html`: 入庫確認画面
  - 発注待ちアイテム一覧
  - 材料情報入力フォーム
  - 検品ステータス表示

## 実装状況（2025-01更新）

### 完全実装済み
- ✅ **Excel取込による発注管理**: 自動発注作成、一覧表示、詳細確認
- ✅ **入庫確認機能**: ロット登録、材料マスタ自動登録、在庫生成
- ✅ **検品機能**: 検品ステータス管理、再編集機能
- ✅ **在庫管理API**: 一覧取得、検索、サマリー、低在庫検知
- ✅ **材料管理**: 材料CRUD、別名管理、グループ管理
- ✅ **生産スケジュール管理**: Excel解析、材料引当
- ✅ **Excel照合ビューア**: 直接Excel読込、在庫照合

### 実装待ち
- ⏳ **入出庫管理機能**: `src/api/movements.py` - スタブのみ
- ⏳ **ラベル印刷機能**: `src/api/labels.py` - スタブのみ
- ⏳ **テスト**: `tests/` ディレクトリ未作成

## 主要ワークフロー

### Excel取込 → 発注管理
1. `/purchase-orders` でExcel取込ボタンをクリック
2. DRY-RUNで検証 → 実行でDB書き込み
3. 発注一覧に自動表示

### 入庫確認 → 検品
1. `/receiving` で入庫待ちアイテムを表示
2. 材料情報入力（材質・径・長さ・比重）
3. ロット番号・入庫数量を入力
4. 検品ステータスを管理（PENDING/PASSED/FAILED）

## データベース設計（2025-01更新）

### 重要なテーブル
- `materials`: 材料マスタ（材質・形状・寸法・比重・品番）
  - **削除**: `product_id`, `usage_type`, `dedicated_part_number`
- `material_aliases`: 材料別名（表記揺れ対応）
- `material_groups`: 材料グループ（同等品管理）
- `material_group_members`: グループ所属（多対多）
- `lots`: ロット管理（束単位、検品ステータス）
- `items`: アイテム管理（UUID管理コード、現在本数・置き場）
- `purchase_orders`: 発注管理（発注番号、仕入先、状態管理）
- `purchase_order_items`: 発注アイテム（材料仕様文字列、数量）
  - **削除**: `management_code`（入庫時にItem側で生成）

### データフロー
1. **Excel取込**: 材料管理.xlsx → PurchaseOrder + PurchaseOrderItem
2. **入庫確認**: PurchaseOrderItem → Material（新規時）→ Lot → Item（UUID生成）
3. **検品**: Lot.inspection_status 更新
4. **在庫管理**: Item（UUID管理コード、現在本数、置き場）

## API設計（2025-01更新）

### 発注管理（Excel取込専用）
- `GET /api/purchase-orders/` - 発注一覧取得（ページネーション対応）
- `GET /api/purchase-orders/{order_id}` - 発注詳細取得
- `POST /api/purchase-orders/external-import-test` - Excel取込
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
- `GET /api/materials/` - 材料一覧取得
- `POST /api/materials/` - 材料作成
- `PUT /api/materials/{material_id}` - 材料更新
- `GET /api/materials/aliases/` - 別名一覧取得
- `POST /api/materials/aliases/` - 別名作成

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
2. ✅ **不要なカラム削除**: materials.product_id, usage_type, dedicated_part_number / purchase_order_items.management_code
3. ✅ **発注管理API簡素化**: 手動作成/編集/削除API削除、Excel取込専用化
4. ✅ **発注管理UI簡素化**: モーダル1500行削除、Excel取込+一覧表示のみ
5. ✅ **materials.py整理**: 標準規格関連のスキーマ・エンドポイント削除

### 削除理由
- **MaterialStandard/Grade/Product**: 未実装の3層構造、実運用で不要
- **UsageType（汎用/専用区分）**: MaterialGroup運用へ移行済み
- **management_code事前生成**: 入庫時にItem側でUUID生成するため重複
- **手動発注作成API**: Excel取込のみ使用、UI削除済みのため不要

## デフォルトユーザー（reset_db.py実行後）
※現在ログイン機能は不要ですが、データベースには以下のユーザーが作成されます：
- **admin / admin123** (管理者)
- **purchase / purchase123** (購買)
- **operator / operator123** (現場)
- **viewer / viewer123** (閲覧)
