# 生産中スケジュール在庫予測 改修メモ

## 概要
- Excel `セット予定表.xlsx` の「生産中」シートから取得した `前回日産` (U列) / `取り数` (W列) を元に1日あたりの材料使用本数を計算。
- Webページ `production-schedule` にて、材料の在庫切れ予測をテーブルの各行に表示できるようにした。

## 主な変更点
- `/api/material-management/usage` API:
  - `COLUMN_MAP` で `前回   日産` などエクセル側の表記揺れに対応する複数エイリアスを追加。
  - `daily_output` に含まれる文字列のプレフィックスを除去し数値化する処理を追加。
  - `bars_per_day` を適切に算出できるよう修正。
- `/api/production-schedule/stockout-forecast` API:
  - `daily_usage` と `bars_per_day` の情報を使って、残在庫数から在庫枯渇までの日数を計算。
- `src/templates/production_schedule.html`:
  - テーブルに在庫切れ予測列を追加し、`残り n 日` バッジや在庫本数を表示する。
  - 前回日産/取り数の情報が取得できない場合はフォールバックとして従来計算を使用。

## 実装メモ
- Excel読み込み時は `usecols=lambda col: col in USE_COLUMNS` で使用列を限定。
- 文字列正規化で全角空白→半角、連続空白→1個。
- `bars_per_day` の値を `row_number` や `machine_no|item_code|spec` の組み合わせでキャッシュし、前後の行揺れに対応。
- `MaterialUsageDetail` モデルに `daily_output` / `bars_per_day` を追加。

## 確認手順
1. `uvicorn src.main:app --reload` でローカルサーバーを起動。
2. ブラウザで `http://127.0.0.1:8000/production-schedule` を開く。
3. 各行の「在庫切れ予測」列に `残り n 日` と表示され、Excel `前回日産` / `取り数` の計算値が反映されていること。
4. `/api/material-management/usage` で `bars_per_day` が数値化されていることを確認。

## 2025-10-05 ページ統合後の調整
- 旧 `http://127.0.0.1:8000/material-management` ページを削除し、`production-schedule` へ統合済み。
- FastAPI ルート `@app.get("/material-management")` を削除、テンプレート `src/templates/material_management.html` を廃止。
- ナビゲーションおよびモバイルメニューからリンクを削除。
- `/api/material-management/usage` は在庫予測の内部計算で利用されるため継続提供。

## 2025-10-05 ダッシュボード刷新
- KPI カードを在庫総量・材料件数・入庫待ち・在庫切れ予測の4指標へ差し替え。
- クイックアクションを最新のページ構成（入庫確認・同等品ビュー・生産中一覧など）に対応。
- 下部セクションを「同等品グループスナップショット」「入庫待ち/検品待ち」へ集約し、一覧系ページへのハブとして機能強化。
- 最近の入出庫履歴や在庫切れ予測(API `/api/movements`, `/api/production-schedule/stockout-forecast`)をダッシュボードで可視化。
- 新規 `src/static/js/dashboard.js` で `APIClient` を利用した集約ロジックを実装。


