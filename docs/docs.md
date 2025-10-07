# 2025-10-07 変更ログ

## 入庫確認機能の改善
- **材料仕様の表示形式変更**: 入庫確認モーダル内の材料仕様部分を、選択可能なテキストエリアからラベル表示のみに変更。他の項目（発注番号、仕入先など）と同じ表示スタイルに統一。
- **単価・金額の入力機能追加**: 入庫確認モーダルに「単価・金額」セクションを追加。
  - 単価（円）と合計金額（円）の入力欄を用意
  - 単価入力時、発注数量または発注重量を基に合計金額を自動計算
  - 手動での上書きも可能
  - データは `PurchaseOrderItem` テーブルの `unit_price` と `amount` フィールドに保存
  - Lotテーブルの `received_unit_price` と `received_amount` にも保存（ロット単位の履歴管理）

### 変更ファイル
- `src/templates/order_flow.html`: 入庫確認モーダルに単価・金額入力欄を追加、材料仕様の表示を簡素化
- `src/static/js/order_flow.js`: 
  - 単価・金額の初期値設定
  - 単価入力時の自動計算ロジック（数量/重量対応）
  - フォーム送信時に単価・金額をAPIに送信
- `src/api/purchase_orders.py`: 
  - POST/PUT `/items/{item_id}/receive/` で単価・金額を受け取り、`PurchaseOrderItem` に保存
  - 既に `ReceivingConfirmation` スキーマに `unit_price` と `amount` フィールドは定義済み

---

# 2025-10-06 変更ログ

- `src/scripts/excel_po_import.py` の既定Excelパスを `\\192.168.1.200\共有\生産管理課\材料管理.xlsx` に更新。
  - 実運用の共有フォルダを指すよう調整。
  - CLI利用例を最新パスに合わせて修正。

## メモ
- ネットワーク共有パスをデフォルトにする際は、PowerShellでエスケープが必要な点に留意。

