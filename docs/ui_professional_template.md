# UI プロフェッショナル化テンプレート

このファイルは全画面に適用する統一デザインパターンです。

## CSS変数（全画面共通）

```css
:root {
  --primary-navy: #1e3a5f;
  --primary-blue: #2563eb;
  --accent-blue: #3b82f6;
  --success-green: #10b981;
  --warning-amber: #f59e0b;
  --danger-red: #ef4444;
  --neutral-50: #f8fafc;
  --neutral-100: #f1f5f9;
  --neutral-200: #e2e8f0;
  --neutral-700: #334155;
  --neutral-800: #1e293b;
}
```

## 変更パターン

### 1. 背景
- **削除**: `gradient-bg`（アニメーションする背景）
- **適用**: `bg-neutral-50`

### 2. ヘッダー
- **削除**: `text-5xl font-black text-transparent bg-clip-text bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600`
- **適用**: `text-2xl font-bold text-neutral-800`
- **サブタイトル**: `text-lg` → `text-sm text-neutral-600`

### 3. カード
- **削除**: `glass-card rounded-3xl p-8 shadow-xl`
- **適用**: `bg-white rounded-lg p-4 border border-neutral-200 shadow-sm`

### 4. アイコンボックス
- **削除**: `p-4 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl shadow-lg`
- **適用**: `p-3 bg-primary-blue bg-opacity-10 rounded-lg`
- **アイコン色**: `text-white text-3xl` → `text-primary-blue text-xl`

### 5. ボタン
- **削除**: `bg-gradient-to-r from-yellow-500 to-orange-600` + 派手なホバー
- **適用**: `bg-primary-blue text-white hover:bg-opacity-90`
- **セカンダリ**: `bg-white border border-neutral-200 hover:bg-neutral-50`

### 6. テーブルヘッダー
- **削除**: `bg-gradient-to-r from-blue-500 to-indigo-600 text-white font-bold`
- **適用**: `bg-neutral-50 text-neutral-700 font-semibold`

### 7. テーブル行ホバー
- **削除**: `background: linear-gradient(90deg, #f0f9ff, #f5f3ff); transform: scale(1.01);`
- **適用**: `hover:bg-neutral-50`

### 8. タブボタン
- **アクティブ削除**: `background: linear-gradient(135deg, #3b82f6, #8b5cf6); box-shadow: ...; transform: translateY(-2px);`
- **アクティブ適用**: `bg-primary-blue text-white`
- **非アクティブ**: `bg-white text-neutral-600 border border-neutral-200 hover:bg-neutral-50`

### 9. フィルターエリア
- **削除**: `bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200`
- **適用**: `bg-neutral-50 border border-neutral-200`

### 10. モーダル
- **ヘッダー削除**: グラデーションタイトル、派手な背景
- **ヘッダー適用**: `bg-neutral-50 border-b border-neutral-200`
- **タイトル**: `text-xl font-bold text-neutral-800`

### 11. フォーム入力
- **削除**: `border-2 border-gray-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-200`
- **適用**: `border border-neutral-200 focus:border-primary-blue focus:ring-2 focus:ring-primary-blue focus:ring-opacity-20`

### 12. 削除するアニメーション
- `@keyframes float`
- `@keyframes shimmer`
- `@keyframes gradient-shift`
- `animation: fadeInUp` の過剰な使用
- ホバー時の `scale`、`rotate`

### 13. パディング縮小
- `py-8 px-6` → `py-4 px-4`
- `p-8` → `p-4`
- `mb-10` → `mb-4`
- `gap-8` → `gap-4`
