# 材料管理システム (matemane)

旋盤用棒材の在庫管理システム（本数・重量のハイブリッド管理）

## 機能概要

- **発注管理**: 仕入先・材料・サイズ・数量/重量・希望納期を登録
- **受入管理**: 納品照合 → 受入登録 → ロット生成 → 社内管理コード（UUID）発番 → ラベル PDF 出力 → 入庫
- **在庫管理**: QR スキャンによる高速呼出・入出庫・戻り・棚移動
- **棚卸機能**: スマホスキャン連続入力・差異調整（承認後に在庫反映）
- **トレーサビリティ**: ロット履歴・操作ログ・監査エクスポート

## 技術スタック

- **バックエンド**: Python 3.12 / FastAPI / SQLAlchemy
- **データベース**: MySQL 8.0（ローカル）
- **フロントエンド**: Jinja2（SSR） + JavaScript + Tailwind CSS
- **認証**: JWT（ローカルユーザー）
- **スキャン**: getUserMedia API（スマホカメラ）

## セットアップ

### 1. 仮想環境の作成と依存関係のインストール

```bash
python -m venv .venv
source .venv/bin/activate  # Windowsの場合: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 環境設定

`.env`ファイルをプロジェクトルートに作成（`.env.example`を参考に）：

```bash
cp .env.example .env
# 必要に応じて設定を編集
```

### 3. データベースセットアップ

初回起動時に自動でテーブルが作成されます。開発時は以下のコマンドでリセット可能：

```bash
python reset_db.py
```

### 4. サーバー起動

```bash
# 開発モード（ホットリロード有効）
uvicorn src.main:app --reload

# または
python run.py
```

サーバーが起動したら `http://localhost:8000` にアクセスしてください。

## CSV インポート機能

### 材料マスタのインポート

システムでは 2 種類の CSV 形式に対応しています：

#### 1. 新形式（標準）

```csv
材質名,形状・寸法,品番,用途区分,専用品番
C3604LCD,∅6.0,ABC001,汎用,
SUS303,φ8.0CM,DEF002,専用,専用部品001
```

#### 2. 原始形式（製品番号,材質＆材料径）

```csv
製品番号,材質＆材料径
20836030,ASK2600S φ8.0CM
634878064,C3604Lcd Hex4.0
```

**特徴**:

- 原始形式は`convert_material_master.py`による変換をスキップして直接インポート可能
- エンコーディング自動検出（UTF-8, Shift_JIS, CP932 等）
- 形状・寸法の自動解析（∅10.0, φ8.0CM, Hex4.0, □15 等）
- 比重の自動判定（材質名から標準値設定、不明時はデフォルト 7.85）

### インポート手順

1. Web ブラウザで `http://localhost:8000/materials` にアクセス
2. 「CSV インポート」タブを選択
3. 材料マスター CSV ファイルを選択してアップロード
4. インポート結果を確認（成功件数、警告、エラー）

API エンドポイント: `POST /api/materials/import-csv`

## 主要機能の使い方

### 材料マスタ管理

- `http://localhost:8000/materials` で材質・形状・寸法を登録・編集
- 比重は材質ごとにユーザー登録（履歴保持）

### 発注・受入

- `http://localhost:8000/purchase-orders` で発注登録
- 受入時は QR スキャンで高速呼出・ロット生成・ラベル発行

### 在庫管理

- `http://localhost:8000/inventory` で在庫照会（材質/サイズ/ロット/場所/本数/重量）
- `http://localhost:8000/movements` で入出庫・戻り・棚移動

### 棚卸

- `http://localhost:8000/inventory-count` でスキャン連続入力・差異調整

## 開発情報

### ディレクトリ構造

```
src/
├── main.py              # FastAPI起動・ルーティング設定
├── config.py           # 環境変数設定
├── db/
│   ├── models.py       # SQLAlchemyモデル定義
│   └── __init__.py
├── api/                # APIルーター
│   ├── materials.py    # 材料管理（CSVインポート機能含む）
│   ├── inventory.py    # 在庫管理
│   ├── movements.py    # 入出庫管理
│   └── ...
├── templates/          # Jinja2テンプレート
├── static/             # CSS/JS/画像ファイル
└── utils/              # ユーティリティ関数
    ├── auth.py         # 認証関連
    └── automation_info.py  # Automation情報取得
```

### テスト

```bash
# ユニットテスト
pytest

# 直接インポート機能テスト
python test_direct_import.py
```

### Automation情報取得

最新のコミット情報を取得するユーティリティ：

```bash
# 最新のAutomationコミット情報を表示
python get_automation_commit.py

# Pythonモジュールとして使用
python -m src.utils.automation_info
```

### ログ

ログは標準出力に出力されます。ログレベルは `.env` の `LOG_LEVEL` で設定。

## トラブルシューティング

### よくある問題

1. **データベース接続エラー**

   - MySQL が起動しているか確認
   - `.env`のデータベース設定を確認

2. **エンコーディングエラー**

   - CSV ファイルのエンコーディングが Shift_JIS の場合、システムが自動検出

3. **インポートエラー**
   - CSV 形式が対応形式か確認
   - ログに詳細なエラー原因が出力されます

### サポート

ログファイルやエラー詳細を確認してください。開発時はデバッグモードで詳細ログが出力されます。

---

_このシステムは現場のニーズに基づいて開発された、シンプルで高速な材料管理ソリューションです。_

