# 材料管理システム 要件定義書（最終版）

**版:** 1.1  
**作成日:** 2025-09-26  
**対象:** 旋盤用棒材の材料管理（本数・重量のハイブリッド管理）  
**技術スタック:** Python 3.12 / FastAPI / MySQL（ローカル） / Jinja2 + JavaScript（統合フロント）

---

## 1. 目的・背景

- 発注 → 受入 → 在庫 → 出庫 → 戻り（返却）までを一貫管理し、**トレーサビリティ**と**棚卸精度**を高める。
- 現品票（ラベル）を発行し、**スマホカメラ**での QR 読取により入出庫を効率化。
- 現場では「**本数管理**」と「**重量管理**」が混在するため、**材質比重**（ユーザー入力）と寸法から相互換算できる仕組みを提供。

---

## 2. 基本方針（確定）

- **フロント/バック統合 Web アプリ**：FastAPI（バック） + Jinja2（SSR） + JavaScript（動的 UI）
- **UI/UX**：シンプル & 高速。モバイル最適、最小操作で完結、アクセシビリティ配慮（コントラスト/フォーカス/キーボード操作）
- **DB**：**MySQL ローカル**のみ（**SQLite3 は使用しない**）。DB 名は **`matemane`** に固定
- **ディレクトリ構造**：`src/` 採用（後述）
- **ラベル**：初版は**PDF 出力**（将来：ZPL/SATO 等へ切替可能）
- **スキャン**：スマホカメラの **getUserMedia** / QR（推奨）
- **マイグレーション**：開発段階は**起動時にスキーマ自動生成**。`reset_db.py` でリセット可能

---

## 3. スコープ

- 対象プロセス：発注登録、受入、ラベル発行、入庫、出庫、戻り、棚移動、棚卸、在庫照会、帳票出力
- 対象外（初版）：会計連携、外部購買連携、MES/PLC 連携、複数拠点間在庫移動（将来拡張）

### 3.1 決定事項（要件の核）

- **ロット粒度**：**束**単位が基本（出庫/戻りは**本数** or **重量** いずれでも可）
- **長さ単位**：**mm** に統一（例：2.5m → 2500mm）
- **出庫紐付け**：**指示書番号必須**（書式：`IS-YYYY-NNNN`）
- **置き場（ロケーション）**：**1〜250**を初期登録。ユーザー設定で追加/名称変更/無効化が可能
- **端材計算**：初版では**不要**（後続フェーズで検討）

---

## 4. 主要ユースケース

1. **発注登録**：仕入先・材料・サイズ・数量/重量・希望納期を登録
2. **受入**：納品照合 → 受入登録 →**ロット生成**→**社内管理コード**（UUID）発番 →**ラベル PDF 出力**→ 入庫
3. **出庫**：QR スキャン → 対象呼出 →**指示書番号**入力 → 本数/重量指定 → 出庫確定
4. **戻り**：余剰や未使用分を戻し、本数/重量を加算（端材計算は当面なし）
5. **棚移動**：置き場変更の履歴化（スキャン →From/To）
6. **棚卸**：スキャン連続入力 → 差異調整（承認後に在庫反映）
7. **照会/帳票**：在庫一覧、ロット履歴、受入・出庫日報、棚卸差異（CSV/PDF）

---

## 5. 機能要件

### 5.1 材料マスタ

- 属性：材質、断面形状（丸/六角/角…）、寸法（直径/幅 × 長さ mm）、標準長さ、単位（本/kg）、備考
- **比重**（g/cm³）：ユーザーが材質ごとに登録・更新（履歴保持）
- **CSV インポート**：
  - **新形式**: 材質名、形状・寸法、品番、用途区分、専用品番
  - **原始形式**: 製品番号、材質＆材料径（`convert_material_master.py`による変換をスキップして直接インポート可能）
  - エンコーディング自動検出（UTF-8, Shift_JIS, CP932 等）
  - 形状・寸法の自動解析（∅10.0, φ8.0CM, Hex4.0, □15 等）
  - 比重の自動判定（材質名から標準値設定、不明時はデフォルト 7.85）

### 5.2 換算ロジック

- 丸棒の例：
  - 体積(cm³) = π × (直径(cm)/2)² × 長さ(cm)
  - 重量(kg) = 体積(cm³) × 比重(g/cm³) ÷ 1000
- 入出庫時に **本数基準** / **重量基準** を選択可能。片方入力時は換算で片方を自動算出（手修正可）。
- 換算根拠（density_id, formula_type）を履歴化。

### 5.3 発注・受入

- 発注伝票・明細、CSV インポート（初版）
- 受入時に**ロット生成**（メーカー Lot/社内 Lot）
- 受入単位（**束**/本/重量）で**社内管理コード**（UUID）発番
- 入庫確定で在庫反映

### 5.4 入出庫・戻り・移動

- **QR/Code128**のスキャンで高速呼出（QR 推奨）
- 出庫：**指示書番号必須**、出庫単位は本/重量
- 戻り：管理コード単位で数量/重量を戻す
- 棚移動：置き場変更の履歴を保持
- 監査：誰が・いつ・どの端末から操作したかを保持

### 5.5 ラベル（現品票）

- **PDF 出力**（A4 レイアウトまたはラベル 50×30mm、203dpi 目安、**QR は 20mm 角以上**）
- 印字項目：社内管理コード（QR）、材質、寸法、長さ、ロット、受入日、受入先、数量/重量、置き場、注意事項
- エンコード例：`M:{item_code};LOT:{lot};MAT:{material};D:{dia};L:{length};PCS:{qty};KG:{weight};LOC:{loc}`
- 将来：ZPL/SATO 等の直接印刷に対応（設定切替）

### 5.6 棚卸

- スマホスキャン連続入力、差異調整は承認後に反映（調整履歴保持）

### 5.7 照会・帳票

- 在庫一覧（材質/サイズ/ロット/場所/本数/重量）
- ロットトレース（入出庫履歴、操作ユーザー、タイムスタンプ）
- 日次出庫・受入一覧、棚卸差異一覧（CSV/PDF 出力）

### 5.8 ユーザー・権限

- 役割：管理者 / 購買 / 現場 / 閲覧
- 認証：ローカルユーザー + JWT、パスワードは bcrypt ハッシュ
- 機能権限：発注・受入・出庫・戻り・調整・マスタ編集ごとに制御

---

## 6. 非機能要件

- **性能**：スキャン → 応答 < 500ms（LAN 想定）
- **可用性**：単拠点・ローカル稼働（日次バックアップ）
- **セキュリティ**：パスワードハッシュ、JWT、監査ログ、CSRF/クリックジャッキング対策
- **拡張性**：複数拠点・外部連携にスケール可能なスキーマ/API 設計
- **ログ/監査**：操作ログ、監査エクスポート（CSV）

---

## 7. データモデル（確定案）

**materials**(id, code, name, material_grade, shape, diameter_mm, std_length_mm, default_unit, notes)  
**densities**(id, material_grade, density_g_cm3, effective_from, effective_to)  
**vendors**(id, code, name)  
**purchase_orders**(id, po_no, vendor_id, order_date, due_date, status)  
**purchase_order_items**(id, po_id, material_id, size_spec, order_qty_pcs, order_weight_kg, unit_price)  
**lots**(id, lot_no_internal, lot_no_supplier, po_item_id, received_at, received_by, base_unit=BUNDLE)  
**items**(id, lot_id, internal_item_code(UUID), length_mm, qty_pcs, weight_kg, location_id, label_version)  
**movements**(id, occurred_at, type(IN/OUT/RETURN/TRANSFER/ADJUST), item_id, qty_pcs, weight_kg, instruction_no, user_id, note)  
**locations**(id, code, name, is_active) ※初期 1〜250 を自動生成、ユーザー編集可  
**users**(id, username, password_hash, role)  
**audit_logs**(id, at, user_id, action, target_table, target_id, payload)

> 方針：`qty_pcs` と `weight_kg` の両方を保持。片方入力時は換算で自動算出（手修正可）。

---

## 8. API 設計（FastAPI 概要）

- 認証：`POST /auth/login` → JWT
- マスタ：`GET/POST /materials`、`GET/POST /densities`、`GET/POST /locations`
- **CSV インポート**：`POST /api/materials/import-csv`（材料マスタの一括登録、原始形式/新形式対応）
- 発注：`GET/POST /purchase-orders`、`GET/POST /purchase-orders/{id}/items`
- 受入：`POST /receipts`（受入登録 → ロット+アイテム生成 → ラベル PDF 出力）
- 在庫：`GET /inventory`（filter: material/lot/location）、`GET /trace/{item_code}`
- 入出庫：`POST /movements/in | /out | /return | /transfer | /adjust`
- ラベル：`POST /labels/print`（payload: item_ids/layout）→ PDF バイナリ返却
- 棚卸：`GET/POST /inventory-counts`

**レスポンス共通**：エラーコード、メッセージ、監査 ID。

---

## 9. フロントエンド（Jinja2 + JavaScript）

- **テンプレート構成**：`base.html`（共通ヘッダ/フッタ）＋各ページ（ダッシュボード、受入、出庫、棚卸 等）
- **UI/UX 指針**：
  - ワンクリック主義（主要操作は 1〜2 タップ内で完了）
  - 大型タッチターゲット、固定ボトムアクションバー（モバイル）
  - ミニマル配色（白 + アクセント 1 色）、意味色（成功/警告/エラー）
  - フィードバック（トースト通知/ローディング/エラー理由の即時表示）
- **QR スキャン**：`getUserMedia` + 軽量 JS（ライブラリ併用可）

---

## 10. ディレクトリ構造（src 採用）

```
project-root/
├─ .env.example
├─ requirements.txt
├─ reset_db.py
├─ src/
│  ├─ main.py                  # FastAPI起動・Jinja2設定・起動時スキーマ生成
│  ├─ config.py                # 環境変数ロード（pydantic BaseSettings推奨）
│  ├─ db/
│  │  ├─ __init__.py
│  │  └─ models.py             # SQLAlchemyモデル
│  ├─ api/
│  │  ├─ __init__.py
│  │  ├─ routes_inventory.py
│  │  ├─ routes_orders.py
│  │  ├─ routes_auth.py
│  │  └─ routes_labels.py
│  ├─ services/
│  │  ├─ inventory_service.py
│  │  ├─ label_service.py
│  │  └─ auth_service.py
│  ├─ templates/               # Jinja2テンプレート（base.html / 各画面）
│  ├─ static/                  # JS/CSS/画像
│  │  ├─ css/
│  │  └─ js/
│  └─ utils/
│     └─ security.py           # JWT・パスワードハッシュ等
└─ tests/
```

---

## 11. `.env.example`（雛形・**DB 名は matemane**）

```bash
# App
APP_NAME=MaterialManager
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8000
SECRET_KEY=change_this_secret_key
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Database (MySQL only)
DB_ENGINE=mysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=material_user
DB_PASSWORD=your_password
DB_NAME=matemane

# Logging
LOG_LEVEL=INFO
```

---

## 12. 運用・保守 / DB 管理

- **起動時スキーマ自動生成**（SQLAlchemy）
- **reset_db.py**：開発/テストで任意実行（全テーブル Drop→ 再作成 or 初期データ投入）
- **バックアップ**：日次で DB ダンプ + ラベル PDF 保管
- **監査**：操作ログ/監査エクスポート（CSV）

---

## 13. テスト方針

- 換算精度（直径/長さ/比重に基づく重量算出）
- 入出庫の同時操作（競合制御）
- ラベル再印字の履歴整合（label_version）
- 棚卸差異の承認フロー
- 認可境界（ロールごとの操作可否）

---

## 14. 実装ロードマップ

- **Phase 1**：マスタ・受入・ラベル PDF・入出庫・在庫照会・認証
- **Phase 2**：棚卸・差異承認・レポート強化・移動履歴
- **Phase 3**：ラベルプリンタ直結（ZPL/SATO）・外部連携・複数拠点

---

> 本書は、これまでの合意内容をすべて反映した最終版の要件定義書です。以降は詳細設計（DDL・API スキーマ・画面遷移）と実装へ進みます。
