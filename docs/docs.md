# 2025-10-13 変更ログ（続き）

## 入出庫管理画面UIのプロフェッショナル化

### 変更内容
ダッシュボード・在庫管理画面・発注フロー画面と同じプロフェッショナルデザイン原則を適用。

#### 1. 統一デザインパターンの適用
- **テンプレートガイド**: `docs/ui_professional_template.md` に定義された13項目の変更パターンを完全適用
- **CSS変数**: 全画面共通のカラーパレット（`--primary-blue`, `--success-green`, `--danger-red`, `--neutral-*`等）を定義
- **一貫性**: ダッシュボード・在庫管理画面・発注フロー画面と100%同じデザイン言語

#### 2. CSS削除・簡素化
- **削除したアニメーション**: `@keyframes gradient-shift`, `@keyframes float`, `@keyframes shimmer`, ホバー時の `transform: translateY(-2px) scale(1.02)` / `translateX(4px)`
- **削除したグラデーション**: `.movement-in-gradient` / `.movement-out-gradient` / `.history-card-in` / `.history-card-out` の複雑なグラデーション背景とシャドウ
- **簡素化**: 入庫・出庫ボタンは単色（`bg-success-green` / `bg-danger-red`）、履歴カードは左ボーダー（3px solid）のみ
- **保持**: `.table-row-hover:hover { background: var(--neutral-50); }`, 履歴カードの左ボーダー（in/out判定）

#### 3. 背景・レイアウト
- **背景**: `gradient-bg` → `bg-neutral-50`
- **パディング**: `py-8 px-4 sm:px-6 lg:px-8` → `py-4 px-4`、カード `p-8` → `p-4`、フォーム `space-y-6` → `space-y-4`、テーブルヘッダー `px-6 py-4` → `px-4 py-3`
- **ギャップ**: `gap-6` / `gap-8` → `gap-3` / `gap-4`

#### 4. ヘッダーセクション
- **タイトル**: `text-5xl font-black text-transparent bg-clip-text bg-gradient-to-r from-red-600 via-orange-600 to-pink-600` → `text-2xl font-bold text-neutral-800`
- **サブタイトル**: `text-lg text-gray-600 font-medium` → `text-sm text-neutral-600`
- **アイコンボックス**: `p-4 bg-gradient-to-br from-purple-500 to-indigo-600 rounded-2xl shadow-lg icon-float` → `p-3 bg-primary-blue bg-opacity-10 rounded-lg`
- **アイコン**: `text-3xl text-white` → `text-xl text-primary-blue`
- **ヘッダーボタン**: `glass-card px-6 py-4 rounded-2xl shadow-lg hover:shadow-2xl` → `bg-white border border-neutral-200 px-4 py-2 rounded-lg hover:bg-neutral-50`

#### 5. カードコンポーネント
- **削除**: `glass-card rounded-3xl p-8 shadow-xl` + `.icon-float` + `.progress-shimmer`
- **適用**: `bg-white rounded-lg p-4 border border-neutral-200 shadow-sm`
- **カードタイトル**: `text-2xl font-black text-gray-900` → `text-lg font-bold text-neutral-800`
- **装飾削除**: プログレスバー（shimmerアニメーション）、アイコンの浮遊アニメーション

#### 6. フォームコンポーネント
- **ラベル**: `text-sm font-bold text-gray-700 mb-3` → `text-sm font-semibold text-neutral-700 mb-2`
- **入力欄**: `p-4 border-2 border-gray-300 rounded-2xl focus:ring-4 focus:ring-blue-300` → `p-3 border border-neutral-200 rounded-lg focus:ring-2 focus:ring-primary-blue focus:ring-opacity-20`
- **ボタン（種別トグル）**: `px-6 py-4 rounded-2xl font-bold text-lg` → `px-4 py-3 rounded-lg font-semibold`
- **ボタン（送信）**: `py-5 px-6 rounded-2xl font-black text-xl shadow-2xl` → `py-3 px-4 rounded-lg font-semibold text-lg`
- **情報ボックス**: `glass-card p-4 rounded-2xl border-l-4 border-blue-500` → `bg-neutral-50 p-3 rounded-lg border-l-3 border-primary-blue`

#### 7. テーブルスタイル（全テーブル共通）
- **コンテナ**: `rounded-2xl border-2 border-gray-200` → `rounded-lg border border-neutral-200`
- **ヘッダー削除**: `bg-gradient-to-r from-gray-50 to-gray-100`
- **ヘッダー適用**: `bg-neutral-50`
- **テキスト**: `text-xs font-black text-gray-700 uppercase tracking-wider` → `text-sm font-semibold text-neutral-700`
- **パディング**: `px-6 py-4` → `px-4 py-3`
- **行ホバー削除**: `background: linear-gradient(90deg, #f0f9ff, #dbeafe); transform: translateX(4px); box-shadow: 0 4px 12px rgba(59, 130, 246, 0.1);`
- **行ホバー適用**: `hover:bg-neutral-50`

#### 8. ボタンスタイル
- **プライマリ削除**: `.movement-in-gradient { background: linear-gradient(135deg, #10b981, #059669, #047857); box-shadow: 0 10px 30px rgba(16, 185, 129, 0.3); }`
- **プライマリ適用**: `.movement-in-gradient { background-color: var(--success-green); } .movement-in-gradient:hover { opacity: 0.9; }`
- **セカンダリ削除**: `.movement-out-gradient { background: linear-gradient(135deg, #ef4444, #dc2626, #b91c1c); box-shadow: 0 10px 30px rgba(239, 68, 68, 0.3); }`
- **セカンダリ適用**: `.movement-out-gradient { background-color: var(--danger-red); } .movement-out-gradient:hover { opacity: 0.9; }`
- **サイズ**: `px-8 py-4 rounded-2xl font-bold` → `px-4 py-3 rounded-lg font-semibold`（トグルボタン）、`px-6 py-3 rounded-xl font-bold` → `px-3 py-2 rounded-lg font-semibold`（テーブル内ボタン）

#### 9. モーダル（アイテム検索・置き場変更・履歴編集）
- **オーバーレイ削除**: `backdrop-blur-sm` + `animation: fadeIn 0.3s ease-out;`
- **オーバーレイ適用**: `bg-black bg-opacity-50`
- **コンテナ削除**: `glass-card rounded-3xl shadow-2xl border-2 border-gray-200`
- **コンテナ適用**: `bg-white rounded-lg shadow-lg border border-neutral-200`
- **ヘッダー削除**: `p-8 border-b-2 border-gray-200 bg-gradient-to-r from-blue-50 to-indigo-50` / `from-purple-50 to-indigo-50`
- **ヘッダー適用**: `p-4 bg-neutral-50 border-b border-neutral-200` + `text-xl font-bold text-neutral-800`
- **アイコンボックス**: `p-3 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-2xl shadow-lg` → `p-3 bg-primary-blue bg-opacity-10 rounded-lg`
- **閉じるボタン**: `action-btn p-3 bg-white rounded-xl hover:bg-gray-100 text-gray-600` → `p-2 rounded-lg hover:bg-neutral-100 text-neutral-400 hover:text-neutral-600`
- **本体パディング**: `p-8` → `p-4`

#### 10. JavaScript内の動的生成HTML
- **在庫テーブル行**:
  - バッジ（形状）: `bg-green-100 text-green-800 rounded-full px-3 py-1 font-bold` → `bg-success-green bg-opacity-10 text-success-green rounded-full px-2 py-1 font-semibold`
  - バッジ（ロット）: `bg-yellow-100 text-gray-900 font-bold` → `bg-warning-amber bg-opacity-10 text-neutral-800 font-semibold`
  - バッジ（置き場）: `bg-red-100 text-red-800 rounded-full px-3 py-1 font-bold` → `bg-danger-red bg-opacity-10 text-danger-red rounded-full px-2 py-1 font-semibold`
  - ボタン: `action-btn movement-in-gradient text-white text-xs px-4 py-2 rounded-xl font-bold transition-all duration-300 hover:shadow-lg` → `movement-in-gradient text-white text-xs px-3 py-2 rounded-lg font-semibold hover:opacity-90 transition-opacity`
  - 置き場移動ボタン: `bg-gradient-to-br from-purple-500 to-indigo-600 rounded-xl` → `bg-primary-blue rounded-lg`
- **履歴テーブル行**:
  - バッジ（種別）: `bg-gradient-to-r from-green-500 to-emerald-600 rounded-xl px-4 py-2 font-black shadow-lg` → `bg-success-green rounded-lg px-3 py-1 font-semibold`
  - 数量表示: `text-base font-black text-green-700` → `text-base font-bold text-success-green`
  - 編集ボタン: `bg-blue-500 hover:bg-blue-600 font-bold shadow-md hover:shadow-lg` → `bg-primary-blue hover:bg-opacity-90 font-semibold`
  - 削除ボタン: `bg-red-500 hover:bg-red-600 font-bold shadow-md hover:shadow-lg` → `bg-danger-red hover:bg-opacity-90 font-semibold`
- **`setMovementType()` 関数**:
  - 非アクティブボタン: `bg-gradient-to-br from-gray-400 to-gray-500` → `bg-neutral-400`
  - アイコンサイズ: `text-2xl mr-3` → `mr-2`

#### 11. 変更していない部分
- **機能ロジック**: データ取得、フィルタリング、ページネーション、モーダル開閉、フォーム送信、数量⇔重量換算、QRスキャンはすべて保持
- **JavaScript構造**: イベントリスナー、API呼び出し、状態管理ロジックは一切変更なし
- **id/class属性**: JavaScript連携に必要な識別子はすべて保持

### 変更ファイル
- `src/templates/movements.html`（約2000行）
  - CSS: 約120行 → 45行（過剰なアニメーション・グラデーション削除）
  - HTML: 全セクション（ヘッダー、フォーム、在庫一覧、履歴、モーダル3個）のスタイル統一
  - JavaScript: 動的生成HTML内のスタイル修正（`renderInventoryTable()`, `renderMovementsTable()`, `setMovementType()`）

### 機能への影響
- **影響なし**: すべてのid属性は保持、JavaScriptロジックは未変更
- **動作保証**: データ取得・フィルタ・ページネーション・モーダル・フォーム送信・履歴編集削除はすべて従来通り
- **デザイン一貫性**: ダッシュボード・在庫管理画面・発注フロー画面と完全に統一されたプロフェッショナルUI

### 次の画面への展開予定
- 材料マスタ管理画面 (`materials.html`)
- 生産スケジュール画面 (`production_schedule.html`)
- Excel照合ビューア (`excel_viewer.html`)
- 集計・分析画面 (`analytics.html`)
- 設定画面 (`settings.html`)

---

## 発注フロー画面UIのプロフェッショナル化

### 変更内容
ダッシュボード・在庫管理画面と同じプロフェッショナルデザイン原則を適用。

#### 1. 統一デザインパターンの適用
- **テンプレートガイド**: `docs/ui_professional_template.md` に定義された13項目の変更パターンを完全適用
- **CSS変数**: 全画面共通のカラーパレット（`--primary-blue`, `--neutral-*`, `--success-green`等）を定義
- **一貫性**: ダッシュボード・在庫管理画面と100%同じデザイン言語

#### 2. 背景・レイアウト
- **背景**: `gradient-bg` → `bg-neutral-50`
- **パディング**: `py-8 px-6` → `py-4 px-4`、`p-8` → `p-4`、`mb-8` → `mb-4`
- **タブコンテンツ**: `max-w-[1600px] mx-auto px-6 py-8` → `px-4 py-4`

#### 3. ヘッダーセクション
- **タイトル**: `text-3xl font-black bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent` → `text-2xl font-bold text-neutral-800`
- **サブタイトル**: `text-gray-600 mt-1 font-medium` → `text-sm text-neutral-600 mt-1`
- **アイコンボックス**: `p-4 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl shadow-lg` → `p-3 bg-primary-blue bg-opacity-10 rounded-lg`
- **アイコン**: `text-white text-3xl` → `text-primary-blue text-xl`

#### 4. カードコンポーネント
- **削除**: `glass-card rounded-3xl p-8 shadow-xl` + `animate-fade-in-up` + `animation-delay`
- **適用**: `bg-white rounded-lg p-4 border border-neutral-200 shadow-sm`
- **装飾バー削除**: `<div class="w-2 h-8 bg-gradient-to-b from-yellow-400 to-orange-500 rounded-full mr-3"></div>`

#### 5. タブナビゲーション
- **コンテナ**: `glass-card shadow-md border-b sticky top-20 z-40 animate-fade-in-up` → `bg-white shadow-sm border-b border-neutral-200 sticky top-20 z-40`
- **アクティブタブ**: `background: linear-gradient(135deg, #3b82f6, #8b5cf6); box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4); transform: translateY(-2px);` → `bg-primary-blue text-white`
- **非アクティブタブ**: `bg-white text-neutral-600 border border-neutral-200 hover:bg-neutral-50`
- **ボタンサイズ**: `px-6 py-3 text-sm font-bold rounded-xl` → `px-4 py-2 text-sm font-semibold rounded-lg`

#### 6. フィルターエリア（全タブ共通）
- **削除**: `bg-gradient-to-br from-blue-50 to-indigo-50 border-2 border-blue-300 rounded-2xl p-6 shadow-inner`
- **適用**: `bg-neutral-50 rounded-lg p-4 border border-neutral-200`
- **タイトル**: `text-sm font-bold text-gray-800` → `text-sm font-semibold text-neutral-800`
- **入力欄**: `border-2 border-gray-300 rounded-xl focus:border-blue-500 focus:ring-2 focus:ring-blue-200` → `border border-neutral-200 rounded-lg focus:border-primary-blue focus:ring-2 focus:ring-primary-blue focus:ring-opacity-20`
- **ギャップ**: `gap-4` → `gap-3`

#### 7. テーブルスタイル（全タブ共通）
- **コンテナ**: `rounded-2xl border-2 border-gray-200 shadow-lg` → `rounded-lg border border-neutral-200`
- **ヘッダー削除**: `bg-gradient-to-r from-blue-500 to-indigo-600` / `from-green-500 to-emerald-600` / `from-purple-500 to-indigo-600` / `from-pink-500 to-rose-600`
- **ヘッダー適用**: `bg-neutral-50`
- **テキスト**: `text-sm font-bold text-white` → `text-sm font-semibold text-neutral-700`（`text-xs`の箇所も統一）
- **パディング**: `px-6 py-4` → `px-4 py-3`（小テーブルは`px-3 py-2`）
- **行ホバー削除**: `background: linear-gradient(90deg, #f0f9ff, #f5f3ff); transform: scale(1.01);`
- **行ホバー適用**: `hover:bg-neutral-50`

#### 8. ボタンスタイル
- **プライマリ削除**: `bg-gradient-to-r from-yellow-500 to-orange-600 hover:from-yellow-600 hover:to-orange-700 shadow-lg hover:shadow-xl`
- **プライマリ適用**: `bg-primary-blue text-white hover:bg-opacity-90`
- **セカンダリ削除**: `bg-gradient-to-r from-gray-600 to-gray-700 hover:from-gray-700 hover:to-gray-800 shadow-lg hover:shadow-xl`
- **セカンダリ適用**: `bg-white border border-neutral-200 text-neutral-700 hover:bg-neutral-50`
- **サイズ**: `px-8 py-3 rounded-xl font-bold` → `px-6 py-2 rounded-lg font-semibold`（アクションボタン）、`px-4 py-2`（通常ボタン）

#### 9. モーダル（入庫確認・印刷確認）
- **オーバーレイ削除**: `backdrop-blur-sm` + `modal-overlay` + `animation: fadeIn 0.3s ease-out;`
- **コンテナ削除**: `glass-card rounded-3xl shadow-2xl animate-fade-in-up`
- **コンテナ適用**: `bg-white rounded-lg shadow-lg`
- **ヘッダー削除**: グラデーションタイトル（`bg-gradient-to-r from-green-600 to-emerald-600 bg-clip-text text-transparent`）
- **ヘッダー適用**: `p-4 bg-neutral-50 border-b border-neutral-200` + `text-xl font-bold text-neutral-800`
- **アイコン色**: `text-green-600` → `text-success-green`、`text-pink-600` → `text-primary-blue`
- **閉じるボタン**: `text-gray-400 hover:text-green-600 p-2 rounded-xl hover:bg-green-50` → `text-neutral-400 hover:text-neutral-600 p-2 rounded-lg hover:bg-neutral-100`

#### 10. CSS削除・簡素化
- **削除したアニメーション**: `@keyframes fadeInUp`, `@keyframes fadeIn`, ホバー時の `transform: translateY(-2px)` / `scale(1.01)`
- **削除したスタイル**: `.tab-panel { animation: fadeInUp 0.4s ease-out both; }`, `button:hover { transform: translateY(-2px); }`, `tbody tr:hover { transform: scale(1.01); }`
- **保持**: タブのアクティブ切り替え、テーブル行のシンプルなホバー（`background: var(--neutral-50)`）、スピナーアニメーション

#### 11. タブ別の変更
- **Excel取込タブ**: 実行結果エリア、使い方説明セクションのグラデーション削除
- **発注一覧タブ**: フィルター4項目のスタイル統一
- **入庫確認タブ**: フィルター3項目、チェックボックスカラー統一
- **検品タブ**:
  - 入庫済みアイテム一覧: `bg-gradient-to-br from-purple-50 to-indigo-50 border border-purple-200` → `bg-neutral-50 border border-neutral-200`
  - 検品済み一覧: `bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200` → `bg-neutral-50 border border-neutral-200`
  - リセットボタン: `bg-purple-600 / bg-indigo-600` → `bg-primary-blue`
- **印刷タブ**: フィルター2項目のスタイル統一

#### 12. 変更していない部分
- **検品フォーム**: 入力フィールドの構造（寸法1/寸法2の左端・中央・右端）
- **入庫確認モーダル内部**: ロット情報入力、計算用パラメータ、合計表示ロジック
- **JavaScript**: `src/static/js/order_flow.js` は一切変更なし
- **機能**: データ取得、フィルタリング、ページネーション、モーダル開閉、フォーム送信ロジックはすべて保持

### 変更ファイル
- `src/templates/order_flow.html`（約940行）
  - CSS: 約70行 → 35行（過剰なアニメーション・グラデーション削除）
  - HTML: 全タブ（5タブ）+ モーダル2個のスタイル統一
  - パディング・ギャップ・フォントサイズ全体を縮小

### 機能への影響
- **影響なし**: すべてのid属性は保持、JavaScriptロジックは未変更
- **動作保証**: データ取得・フィルタ・ページネーション・モーダル・フォーム送信はすべて従来通り
- **デザイン一貫性**: ダッシュボード・在庫管理画面と完全に統一されたプロフェッショナルUI

### 次の画面への展開予定
- 入出庫管理画面 (`movements.html`)
- 材料マスタ管理画面 (`materials.html`)
- 生産スケジュール画面 (`production_schedule.html`)
- Excel照合ビューア (`excel_viewer.html`)
- 集計・分析画面 (`analytics.html`)
- 設定画面 (`settings.html`)

---

## 在庫管理画面UIのプロフェッショナル化

### 変更内容
ダッシュボードと同じプロフェッショナルデザイン原則を適用。

#### 1. CSS変更
- **削除したアニメーション**: `@keyframes gradient-shift`, `@keyframes float`, `@keyframes fadeInUp`
- **削除した要素**:
  - `.gradient-bg` のアニメーション背景
  - `.icon-float` の浮遊アニメーション
  - `.gradient-number` のグラデーションテキスト
  - `.btn-primary::before` の波紋エフェクト
- **簡素化**:
  - `.summary-card` のホバー → `transform: translateY(-2px)` のみ
  - `.btn-primary` のホバー → `opacity: 0.9` のみ
  - テーブル行のホバー → `background: var(--neutral-50)` のみ

#### 2. HTML構造変更
- **背景**: `gradient-bg` → `bg-neutral-50`
- **ヘッダータイトル**: `text-5xl font-black` + グラデーションテキスト → `text-2xl font-bold text-neutral-800`
- **サブタイトル**: `text-lg` → `text-sm`
- **パディング**: `py-8 mb-10` → `py-4 mb-4`
- **カード**: `glass-card rounded-3xl p-8 shadow-xl` → `bg-white rounded-lg p-4 border border-neutral-200 shadow-sm`
- **サマリーカード**: `p-8 text-4xl font-black gradient-number` → `p-4 text-3xl font-bold text-neutral-800`
- **バッジ**: グラデーション背景 → `bg-primary-blue bg-opacity-10 text-primary-blue`
- **アイコン**: `bg-gradient-to-br from-blue-500 to-blue-600 rounded-2xl shadow-lg text-white text-3xl` → `bg-primary-blue bg-opacity-10 rounded-lg text-primary-blue text-2xl`
- **ボタン**: グラデーション → `bg-primary-blue text-white hover:bg-opacity-90`
- **モーダル**: グラデーション背景 → `bg-neutral-50 border-b border-neutral-200`

#### 3. JavaScript内のHTML生成部分も更新
- テーブル行: `hover:bg-gradient-to-r` → `hover:bg-neutral-50`
- ボタン: `bg-gradient-to-r from-blue-500 to-indigo-600` → `bg-primary-blue hover:bg-opacity-90`
- フォント: `font-black` → `font-bold` / `font-semibold`
- テキスト色: `text-gray-*` → `text-neutral-*`

### 変更ファイル
- `src/templates/inventory.html`（約1400行）
  - CSS: 約110行 → 48行（過剰なアニメーション削減）
  - HTML: 全カード・モーダルのスタイル簡素化
  - JavaScript: 動的生成HTML内のスタイルも統一

### 機能への影響
- **影響なし**: すべてのid属性は保持、JavaScriptロジックは未変更
- **動作保証**: データ取得・フィルタ・ページネーション・モーダル機能はすべて従来通り

---

## ダッシュボードUIのプロフェッショナル化

### 目的
- 材料管理システムのダッシュボードをプロフェッショナルな企業向けデザインに刷新
- ポップすぎる配色とAI感を排除し、業務アプリケーションとしての信頼性を向上
- 画面スクロールを最小化し、1画面で主要情報を把握できるコンパクト設計

### 主な変更内容

#### 1. 配色の刷新（派手なグラデーション → 企業向けカラーパレット）
- **削除した要素**:
  - 虹色グラデーションタイトル（`from-blue-600 via-purple-600 to-pink-600`）
  - 派手なグラスモーフィズム背景
  - アニメーションする背景グラデーション（`gradient-shift`）
  - 複数色が混在するプログレスバー
- **新規追加した配色**:
  - CSS変数で統一されたカラーパレット（`--primary-navy`, `--primary-blue`, `--success-green`, `--warning-amber`, `--danger-red`, `--neutral-*`）
  - 明瞭な白背景 + 細いボーダー（`border: 1px solid var(--neutral-200)`）
  - 色の役割を明確化（プライマリ、成功、警告、危険）

#### 2. レイアウトのコンパクト化（スクロール最小化）
- **ヘッダー**: `text-5xl` → `text-2xl`、`py-8` → `py-4`、`mb-10` → `mb-4`
- **KPIカード**: `p-8` → `p-4`、`gap-8` → `gap-4`、`text-4xl` → `text-3xl`
- **セクション高さ制限**: `.compact-section { max-height: 320px; overflow-y: auto; }`
- **グリッド**: 最下部を2列から4列（2x2）グリッドに変更し、縦スクロールを削減

#### 3. 過剰なアニメーション・エフェクトの削減
- **削除したアニメーション**:
  - `@keyframes float` - アイコンの浮遊アニメーション
  - `@keyframes shimmer` - プログレスバーの光沢効果
  - `@keyframes gradient-shift` - 背景のグラデーション移動
  - カードホバー時の `scale(1.02)` + `rotate(-1deg)`
  - カードホバー時の波紋エフェクト（`::after` 疑似要素）
  - ボタンホバー時の180度回転（`group-hover:rotate-180`）
- **保持したアニメーション**:
  - `@keyframes pulse` - ステータスインジケーターのみ（opacity変化のみ）
- **新規追加したホバー**:
  - 控えめな `transform: translateY(-2px)` + 軽いシャドウ

#### 4. タイポグラフィとアイコンの最適化
- **フォントウェイト**: `font-black` → `font-bold`（過度な太字を削減）
- **大文字変換**: `uppercase tracking-wider` を維持（ラベルの視認性向上）
- **アイコンサイズ**: `text-3xl` → `text-2xl`、アイコンボックスは `p-3 bg-opacity-10` に統一
- **アイコン配置**: 右上配置に統一し、データを左側に集約

#### 5. プロフェッショナルなデザイン原則
- **データファースト**: 数値を大きく、装飾を最小限に
- **情報密度向上**: 1画面でKPI + クイックアクション + 4セクションを表示
- **視認性重視**: 明瞭なコントラスト、統一されたフォントサイズ
- **企業向けUI**: 落ち着いた配色、シンプルなアイコン配置、過剰な装飾の排除

### 変更ファイル
- `src/templates/dashboard.html`
  - CSS: 約150行の派手なアニメーション定義を削除、40行のシンプルなスタイルに置き換え
  - HTML: 全セクションの構造を簡素化（`glass-card rounded-3xl p-8` → `bg-white rounded-lg p-4`）
  - レイアウト: 3段構成（KPI → 2カラム → 2x2グリッド）に変更

### 機能への影響
- **影響なし**: CSSとHTML構造のみの変更。JavaScriptのDOM操作（`id`属性）はすべて保持。
- **動作保証**: 既存のdashboard.jsは一切変更せず、すべてのデータ取得・表示ロジックは従来通り動作。
- **後方互換性**: 他画面への影響なし（base.htmlは未変更）。

### 今後の展開予定
- 他画面（在庫管理、発注フロー、入出庫、材料マスタなど）にも同様のプロフェッショナル化を適用
- 変更時は機能に影響がないこと（CSSとHTML構造のみ）を厳守

---

# 2025-10-09 変更ログ

## 入庫確認ロット再編集の改善
- **削除済みロットが復活する不具合を解消**
  - 再編集フォームでロットを削除した場合、バックエンドのDELETE APIを追加し、削除を確実に反映
  - 入庫済みロットを削除する際、入出庫履歴が存在する場合は削除できないようチェック
  - 残存ロットから入庫数量と重量を再集計し、発注アイテムと発注全体のステータスを再評価
- **フロントエンドの差分送信ロジックを改良**
  - 既存ロットとフォーム入力の差分を判定し、新規ロットはPOST、既存ロットはPUT、削除ロットはDELETEを呼び分け
  - 削除失敗時の警告表示を追加し、ユーザーへフィードバック
  - 入力欄をより柔軟に取得（`select`/`input`どちらにも対応）

### 変更ファイル
- `src/api/purchase_orders.py`
  - `DELETE /api/purchase-orders/items/{item_id}/receive/{lot_number}/` を追加
  - 適用後に数量・重量の再集計と発注ステータス更新
- `src/static/js/order_flow.js`
  - ロット差分判定と削除APIコールを実装
  - 成功・警告メッセージの改善、置き場入力の取得方式を拡張

---

# 2025-10-07 変更ログ

## 入庫確認機能の改善
- **材料仕様の表示形式変更**: 入庫確認モーダル内の材料仕様部分を、選択可能なテキストエリアからラベル表示のみに変更。他の項目（発注番号、仕入先など）と同じ表示スタイルに統一。
- **単価・金額の入力機能追加**: 入庫確認モーダルに「単価・金額」セクションを追加。
  - 単価（円）と合計金額（円）の入力欄を用意
  - 単価入力時、発注数量または発注重量を基に合計金額を自動計算
  - 手動での上書きも可能
  - データは `PurchaseOrderItem` テーブルの `unit_price` と `amount` フィールドに保存
  - Lotテーブルの `received_unit_price` と `received_amount` にも保存（ロット単位の履歴管理）

### 追加メモ（2025-10-09）
- 再編集PUT `/api/purchase-orders/items/{item_id}/receive/` のレスポンスから存在しない `management_code` フィールドを削除。`Item` モデルに当該カラムがないため、ロット削除後の再編集で500エラーが発生していた。
  - 影響範囲: `src/api/purchase_orders.py`
  - 変更効果: 再編集時に残存ロットのみ更新するケースでも正しく200レスポンスを返す。
- 再編集フォームでロットを削除した場合に保持されていた古いロット番号リストをリセットするよう修正。
  - 影響範囲: `src/static/js/order_flow.js`
  - 変更効果: フォームから削除したロットがPUTで再登録されることを防止。

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

---

## 材料マスタ管理画面UIのプロフェッショナル化

### 変更内容
ダッシュボード・在庫管理画面・発注フロー画面・入出庫管理画面と同じプロフェッショナルデザイン原則を適用。

#### 1. 統一デザインパターンの適用
- **テンプレートガイド**: `docs/ui_professional_template.md` に定義された13項目の変更パターンを完全適用
- **CSS変数**: 全画面共通のカラーパレット（`--primary-blue`, `--success-green`, `--danger-red`, `--neutral-*`等）を定義
- **一貫性**: 既存の更新画面と100%同じデザイン言語

#### 2. CSS削除・簡素化
- **追加したCSS変数**: 11個のカラー変数（`--primary-navy`, `--primary-blue`, `--success-green`, `--warning-amber`, `--danger-red`, `--neutral-*`系列）
- **保持した既存スタイル**: 
  - `.table-row-hover:hover { background: var(--neutral-50); }`
  - `.search-container` と関連スタイル（検索アイコン）
  - テーブルホバーエフェクト

#### 3. 背景・レイアウト
- **背景**: `bg-white` → `bg-neutral-50`
- **パディング**: `py-4 px-4 sm:px-6 lg:px-8` → `py-4 px-4`、カード `p-8` → `p-4`、フォーム `space-y-6` → `space-y-4`
- **コンテナ**: `max-w-[1600px]` を維持

#### 4. ヘッダーセクション
- **タイトル**: `text-2xl font-bold text-neutral-800`（既に最適化済み）
- **サブタイトル**: `text-sm text-neutral-600`（既に最適化済み）
- **ボタン**: `bg-primary-blue text-white px-6 py-2 rounded-lg font-semibold hover:bg-opacity-90`（既に最適化済み）

#### 5. フィルターセクション
- **カード**: `bg-white rounded-lg p-4 mb-4 border border-neutral-200 shadow-sm`（既に最適化済み）
- **ヘッダーアイコン**: `p-3 bg-primary-blue bg-opacity-10 rounded-lg mr-3`（既に最適化済み）
- **セクションタイトル**: `text-lg font-semibold text-neutral-800`（既に最適化済み）

#### 6. テーブルスタイル
- **コンテナ**: `bg-white rounded-lg border border-neutral-200 shadow-sm overflow-hidden`（既に最適化済み）
- **ヘッダー**: `bg-neutral-50` + `text-sm font-semibold text-neutral-700`（既に最適化済み）
- **パディング**: `px-4 py-3`（既に最適化済み）
- **行ホバー**: `table-row-hover` を維持

#### 7. モーダル（材料登録/編集・重量計算）
- **オーバーレイ**: `modal-backdrop hidden z-50` → `bg-black bg-opacity-50 hidden items-center justify-center z-50`
- **コンテナ**: `modal-content rounded-3xl max-w-md w-full max-h-[90vh] overflow-y-auto shadow-2xl animate-fade-in-up` → `bg-white rounded-xl max-w-md w-full max-h-[90vh] overflow-y-auto shadow-lg`
- **ヘッダー**: 
  - パディング: `px-8 py-6` → `px-6 py-4`
  - ボーダー: `border-b border-gray-100` → `border-b border-neutral-200`
  - タイトル: `text-2xl font-black text-gray-900` → `text-xl font-semibold text-neutral-900`
- **アイコンボックス**: 
  - 材料: `p-2 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl shadow-lg mr-3` → `p-2 bg-primary-blue bg-opacity-10 rounded-lg mr-3`
  - 重量計算: `p-2 bg-gradient-to-br from-green-500 to-emerald-600 rounded-xl shadow-lg mr-3` → `p-2 bg-success-green bg-opacity-10 rounded-lg mr-3`
- **アイコン色**: `text-white` → `text-primary-blue` / `text-success-green`
- **フォーム**: 
  - パディング: `p-8` → `p-6`
  - ラベル: `text-sm font-black text-gray-700 mb-3 uppercase tracking-wide` → `text-sm font-semibold text-neutral-700 mb-2`
  - 入力欄: `input-focus w-full px-4 py-3 border-2 border-gray-200 rounded-xl` → `w-full px-4 py-3 border border-neutral-200 rounded-lg focus:ring-2 focus:ring-primary-blue focus:ring-opacity-20`
  - プレースホルダー: `placeholder-gray-400` → `placeholder-neutral-500`
- **ボタン**: 
  - キャンセル: `bg-white hover:bg-gray-50 text-gray-700 font-bold py-3 px-8 rounded-xl border-2 border-gray-300` → `bg-white border border-neutral-200 text-neutral-700 font-semibold py-2 px-6 rounded-lg hover:bg-neutral-50`
  - 登録/計算: `btn-gradient-primary/btn-gradient-success` → `bg-primary-blue/bg-success-green`
  - サイズ: `py-3 px-8 rounded-xl font-bold` → `py-2 px-6 rounded-lg font-semibold`
  - ホバー: `shadow-xl focus:ring-4` → `hover:bg-opacity-90 focus:ring-2 focus:ring-opacity-20`

#### 8. JavaScript内の動的生成HTML（materials.js）
- **空データ表示**: 
  - アイコンボックス: `bg-gradient-to-br from-gray-100 to-gray-200 rounded-full mb-6 shadow-inner` → `bg-neutral-100 rounded-full mb-6`
  - アイコン色: `text-gray-400` → `text-neutral-400`
  - タイトル: `text-xl font-bold text-gray-700` → `text-xl font-semibold text-neutral-700`
  - 説明: `text-sm text-gray-500` → `text-sm text-neutral-500`
  - ボタン: `btn-gradient-primary` → `bg-primary-blue`
- **材料カード（未使用）**: 
  - 色: `text-gray-*` → `text-neutral-*`
  - 状態バッジ: `bg-green-100 text-green-800` / `bg-red-100 text-red-800` → `bg-success-green bg-opacity-10 text-success-green` / `bg-danger-red bg-opacity-10 text-danger-red`
  - ボタン: `bg-neutral-100 hover:bg-neutral-200`
- **材料テーブル行**: 
  - パディング: `px-8 py-5` → `px-4 py-3`
  - 文字: `font-bold text-gray-900` → `font-semibold text-neutral-900`
  - 操作ボタン: 
    - サイズ: `p-3 rounded-xl` → `p-2 rounded-lg`
    - 色: `bg-gradient-to-br from-blue-50 to-blue-100 text-blue-600` → `bg-primary-blue bg-opacity-10 text-primary-blue`
    - ホバー: `hover:from-blue-100 hover:to-blue-200 hover:scale-110` → `hover:bg-opacity-20`
    - アイコン: `text-lg` → デフォルトサイズ
- **計算結果表示**: 
  - アイコンボックス: `bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl shadow-lg` → `bg-success-green bg-opacity-10 rounded-lg`
  - アイコン: `text-white` → `text-success-green`
  - タイトル: `text-lg font-black text-gray-900` → `text-lg font-semibold text-neutral-900`
  - 結果カード: 
    - 体積: `bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl border border-blue-200` + `font-black text-blue-600` → `bg-primary-blue bg-opacity-5 rounded-lg border border-primary-blue border-opacity-20` + `font-semibold text-primary-blue`
    - 重量: `bg-gradient-to-r from-green-50 to-emerald-50 rounded-xl border border-green-200` + `font-black text-green-600` → `bg-success-green bg-opacity-5 rounded-lg border border-success-green border-opacity-20` + `font-semibold text-success-green`
    - 総重量: `bg-gradient-to-br from-purple-500 to-indigo-600 rounded-2xl shadow-xl` + `text-3xl font-black` → `bg-primary-blue rounded-lg` + `text-2xl font-semibold text-white text-center`

#### 9. ローディング表示
- **コンテナ**: `glass-card rounded-3xl p-12 shadow-xl` → `bg-white rounded-lg p-8 border border-neutral-200 shadow-sm`
- **スピナー**: `h-16 w-16 border-4 border-blue-200 border-t-blue-600 mb-6` → `h-12 w-12 border-4 border-neutral-200 border-t-primary-blue mb-4`
- **テキスト**: `text-gray-700 font-bold text-lg` → `text-neutral-700 font-semibold text-base`
- **サブテキスト**: `text-gray-500` → `text-neutral-600`

#### 10. 変更していない部分
- **機能ロジック**: すべてのid属性は保持、JavaScriptのDOM操作ロジックは一切変更なし
- **フォーム機能**: 材料登録、編集、削除、重量計算、検索、フィルタリング、ページネーションはすべて従来通り
- **API連携**: すべてのエンドポイントとデータ送信ロジックは保持

### 変更ファイル
- `src/templates/materials.html`（約350行）
  - CSS: CSS変数追加（11個）、既存CSSクラスは保持
  - HTML: モーダル2個の完全なスタイル統一、ローディング表示の簡素化
- `src/static/js/materials.js`（約900行）
  - 動的生成HTML: `renderMaterialsList()`, `renderMaterialRow()`, `displayCalculationResult()` のスタイル修正

### 機能への影響
- **影響なし**: すべてのid属性は保持、JavaScriptロジックは未変更
- **動作保証**: CRUD操作、検索、フィルタ、ページネーション、モーダル、重量計算はすべて従来通り
- **デザイン一貫性**: これまで更新した画面（ダッシュボード、在庫管理、発注フロー、入出庫管理）と完全に統一

### 完了した画面
- ✅ ダッシュボード (`dashboard.html`)
- ✅ 在庫管理画面 (`inventory.html`) 
- ✅ 発注フロー画面 (`order_flow.html`)
- ✅ 入出庫管理画面 (`movements.html`)
- ✅ 材料マスタ管理画面 (`materials.html`)

---

## 生産スケジュール画面UIのプロフェッショナル化

### 変更内容
ダッシュボード・在庫管理画面・発注フロー画面・入出庫管理画面・材料マスタ管理画面と同じプロフェッショナルデザイン原則を適用。

#### 1. 統一デザインパターンの適用
- **テンプレートガイド**: `docs/ui_professional_template.md` に定義された13項目の変更パターンを完全適用
- **CSS変数**: 全画面共通のカラーパレット（`--primary-blue`, `--success-green`, `--danger-red`, `--warning-amber`, `--neutral-*`等）を定義
- **一貫性**: 既存の更新画面と100%同じデザイン言語

#### 2. CSS削除・簡素化
- **削除したアニメーション**: `@keyframes gradient-shift`（グラデーション背景の移動）
- **削除した効果**: 
  - `.glass-card` のグラスモーフィズム（`backdrop-filter: blur(20px)`）
  - `.gradient-bg` のアニメーション背景
- **追加したCSS変数**: 11個のカラー変数
- **保持したスタイル**: `.table-row-hover:hover`

#### 3. 背景・レイアウト
- **背景**: `gradient-bg` → `bg-neutral-50`
- **パディング**: `py-8 px-4 sm:px-6 lg:px-8` → `py-4 px-4`、`mb-10` → `mb-4`
- **ヘッダースペース**: `space-y-2` → `space-y-1`

#### 4. ヘッダーセクション
- **タイトル**: `text-5xl font-black text-transparent bg-clip-text bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600` → `text-2xl font-bold text-neutral-800`
- **サブタイトル**: `text-lg text-gray-600 font-medium` → `text-sm text-neutral-600`
- **再読み込みボタン**: 
  - `glass-card px-6 py-3 rounded-2xl shadow-lg hover:shadow-2xl hover:scale-110` → `bg-white border border-neutral-200 px-4 py-2 rounded-lg hover:bg-neutral-50`
  - アイコン: `text-gray-600 group-hover:rotate-180` → `text-neutral-600`
  - テキスト: `font-semibold text-gray-700` → `font-semibold text-neutral-700`

#### 5. テーブルスタイル
- **コンテナ**: `glass-card rounded-3xl shadow-xl` → `bg-white rounded-lg border border-neutral-200 shadow-sm`
- **ヘッダー**: 
  - `px-6 py-4 bg-gradient-to-r from-blue-50 to-purple-50 border-b border-gray-200` → `px-4 py-3 bg-neutral-50 border-b border-neutral-200`
  - 総件数: `text-sm font-bold text-gray-700` + `font-black text-blue-600` → `text-sm font-semibold text-neutral-700` + `font-bold text-primary-blue`
  - 最終更新: `text-xs font-semibold text-gray-600` → `text-xs font-medium text-neutral-600`
- **テーブル**: `min-w-full divide-y divide-gray-200` → `min-w-full divide-y divide-neutral-200`
- **ヘッダーセル**: `bg-gradient-to-r from-gray-50 to-gray-100` + `text-xs font-medium text-gray-500 uppercase tracking-wider` → `bg-neutral-50` + `text-sm font-semibold text-neutral-700`
- **ボディ**: `bg-white divide-y divide-gray-100` → `bg-white divide-y divide-neutral-100`

#### 6. ローディング・空データ表示
- **ローディング**: 
  - スピナー: `border-4 border-blue-200 border-t-blue-600` → `border-4 border-neutral-200 border-t-primary-blue`
  - テキスト: `text-gray-500` → `text-neutral-500`
- **空データ**: 
  - アイコンボックス: `bg-gradient-to-br from-gray-100 to-gray-200 rounded-full shadow-inner` → `bg-neutral-100 rounded-full`
  - アイコン: `text-gray-400` → `text-neutral-400`
  - テキスト: `text-gray-700 font-bold` → `text-neutral-700 font-semibold`

#### 7. JavaScript内の動的生成HTML
- **データ行**: 
  - テキスト色: `text-gray-900` / `text-gray-700` → `text-neutral-900` / `text-neutral-700`
  - ホバー: `hover:bg-gray-50` → `table-row-hover`
- **在庫切れ予測バッジ**: 
  - 予測なし: `bg-gray-100 text-gray-600` → `bg-neutral-100 text-neutral-600`
  - 不明: `bg-gray-100 text-gray-700` → `bg-neutral-100 text-neutral-700`
  - 在庫切れ済: `bg-red-100 text-red-700` → `bg-danger-red bg-opacity-10 text-danger-red`
  - 本日切れ: `bg-amber-100 text-amber-700` → `bg-warning-amber bg-opacity-10 text-warning-amber`
  - 残り日数: `bg-green-100 text-green-700` / `bg-red-100 text-red-700` / `bg-amber-100 text-amber-700` → `bg-success-green bg-opacity-10 text-success-green` / `bg-danger-red bg-opacity-10 text-danger-red` / `bg-warning-amber bg-opacity-10 text-warning-amber`
  - 在庫数: `text-gray-600` → `text-neutral-600`

#### 8. 変更していない部分
- **機能ロジック**: すべてのid属性は保持、JavaScriptのDOM操作ロジックは一切変更なし
- **データ取得**: Excel読み込み、在庫切れ予測、使用計画の取得ロジックはすべて従来通り
- **計算ロジック**: 在庫切れ予測日数の計算、1日使用本数の取得、キーの正規化はすべて保持
- **API連携**: `/api/production-schedule/`、`/api/production-schedule/stockout-forecast`、`/api/material-management/usage` エンドポイントは変更なし

### 変更ファイル
- `src/templates/production_schedule.html`（約400行）
  - CSS: 約30行 → 22行（過剰なアニメーション・グラデーション削除、CSS変数追加）
  - HTML: 全セクション（ヘッダー、テーブル、ローディング）のスタイル統一
  - JavaScript: `buildRowHtml()`, `buildInlineForecastCell()`, `renderRows()` のスタイル修正

### 機能への影響
- **影響なし**: すべてのid属性は保持、JavaScriptロジックは未変更
- **動作保証**: Excel読み込み、在庫切れ予測、使用計算、再読み込みはすべて従来通り
- **デザイン一貫性**: これまで更新した画面（ダッシュボード、在庫管理、発注フロー、入出庫管理、材料マスタ）と完全に統一

### 完了した画面（6/9完了）
- ✅ ダッシュボード (`dashboard.html`) - 2025-10-09完了
- ✅ 在庫管理画面 (`inventory.html`) - 2025-10-09完了  
- ✅ 発注フロー画面 (`order_flow.html`) - 2025-10-09完了
- ✅ 入出庫管理画面 (`movements.html`) - 2025-10-09完了
- ✅ 材料マスタ管理画面 (`materials.html`) - 2025-10-14完了
- ✅ 生産スケジュール画面 (`production_schedule.html`) - 2025-10-14完了

### 次の画面への展開予定
- Excel照合ビューア (`excel_viewer.html`)
- 集計・分析画面 (`analytics.html`)
- 設定画面 (`settings.html`)

---

---

## UI改善プロジェクト状況まとめ（2025-10-14）

### プロジェクト概要
材料管理システムの全画面をプロフェッショナルな企業向けUIに統一するプロジェクト。

### 基本方針
- **テンプレートガイド**: `docs/ui_professional_template.md` に定義された13項目の変更パターンを全画面に適用
- **デザイン原則**: 過剰なアニメーション・グラデーションを排除し、シンプルで信頼性の高い業務アプリケーションUIを実現
- **機能維持**: すべてのid属性とJavaScriptロジックを保持し、機能への影響を最小限に抑える

### 進捗状況
**完了: 6/9画面（67%）**

#### 2025-10-09完了（5画面）
1. ✅ `dashboard.html` - ダッシュボード
2. ✅ `inventory.html` - 在庫管理画面  
3. ✅ `order_flow.html` - 発注フロー画面
4. ✅ `movements.html` - 入出庫管理画面

#### 2025-10-14完了（2画面）
5. ✅ `materials.html` - 材料マスタ管理画面
6. ✅ `production_schedule.html` - 生産スケジュール画面

#### 残り（3画面）
7. ⏳ `excel_viewer.html` - Excel照合ビューア
8. ⏳ `analytics.html` - 集計・分析画面
9. ⏳ `settings.html` - 設定画面

### 統一されたデザイン要素
- **CSS変数**: 11個のカラーパレット（`--primary-blue`, `--success-green`, `--danger-red`, `--warning-amber`, `--neutral-*`）
- **背景**: `bg-neutral-50`（全画面統一）
- **カード**: `bg-white rounded-lg border border-neutral-200 shadow-sm`
- **テーブル**: `bg-neutral-50`ヘッダー + `table-row-hover`ホバー効果
- **ボタン**: グラデーション削除、単色ベース + `hover:bg-opacity-90`
- **タイトル**: `text-2xl font-bold text-neutral-800`
- **モーダル**: シンプルなシャドウ、統一されたパディング

### 削除された要素
- グラスモーフィズム効果 (`glass-card`, `backdrop-filter`)
- アニメーショングラデーション背景 (`@keyframes gradient-shift`)
- 虹色グラデーションテキスト (`bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600`)
- 過剰なシャドウ・ボーダー・アニメーション
- 複雑なホバーエフェクト (`scale`, `rotate`, `translateY`)

### 機能への影響
- **影響なし**: 全画面でid属性とJavaScriptロジックを完全保持
- **動作保証**: CRUD操作、検索、フィルタ、ページネーション、モーダル機能はすべて従来通り
- **API連携**: すべてのエンドポイントとデータ送信ロジックは変更なし

### コメントアウト予定のピン留め
```bash
# 完了画面メモ
- materials.html: CSS変数追加、モーダル2個、JavaScript動的HTML修正完了
- production_schedule.html: 在庫切れ予測バッジ色分け、Excel読み込み機能保持
- 全画面統一設計: 企業向けプロフェッショナルUI完成度67%
```

---

## メモ
- ネットワーク共有パスをデフォルトにする際は、PowerShellでエスケープが必要な点に留意。

