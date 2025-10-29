# リポジトリアクセス確認機能 実装ドキュメント

## 概要

「確認できるリポジトリは？」という要件に対し、ネットワーク共有ファイル（リポジトリ）へのアクセス可能性を確認する機能を実装しました。

## 実装内容

### 1. APIエンドポイント

**エンドポイント**: `GET /api/repositories/check`

**機能**:
- 設定されているすべてのファイルリポジトリのアクセス状態を確認
- 各リポジトリについて以下の情報を返却:
  - 存在チェック（exists）
  - 読み取り権限（readable）
  - 書き込み権限（writable）
  - アクセス可否（accessible）
  - エラーメッセージ（error_message）

**レスポンス例**:
```json
{
  "repositories": [
    {
      "name": "生産スケジュール (セット予定表)",
      "path": "\\\\192.168.1.200\\共有\\生産管理課\\セット予定表.xlsx",
      "accessible": true,
      "exists": true,
      "readable": true,
      "writable": false,
      "error_message": null
    },
    {
      "name": "材料管理Excel (材料管理.xlsx)",
      "path": "\\\\192.168.1.200\\共有\\生産管理課\\材料管理.xlsx",
      "accessible": false,
      "exists": false,
      "readable": false,
      "writable": false,
      "error_message": "パスが存在しません"
    }
  ],
  "total_count": 2,
  "accessible_count": 1,
  "inaccessible_count": 1
}
```

### 2. ユーザーインターフェース

**場所**: `/settings#repository-check`

**機能**:
- 設定画面に「リポジトリ確認」タブを追加
- タブを開くと自動的にアクセス状態をチェック
- 「再チェック」ボタンで手動更新が可能
- テーブル形式で各リポジトリの状態を表示:
  - リポジトリ名
  - パス
  - 状態（正常/エラー）
  - 存在チェック（✓/✗）
  - 読み取り権限（✓/✗）
  - 書き込み権限（✓/✗）
  - エラーメッセージ

**視覚的フィードバック**:
- アクセス可能: 緑のチェックマーク、白背景
- アクセス不可: 赤のバツマーク、ピンク背景
- 画面上部にサマリーメッセージを表示

### 3. モニタリング対象

現在、以下の2つのリポジトリを監視しています：

1. **生産スケジュール (セット予定表)**
   - パス: `\\192.168.1.200\共有\生産管理課\セット予定表.xlsx`
   - 用途: 生産スケジュール管理機能で使用

2. **材料管理Excel (材料管理.xlsx)**
   - パス: `\\192.168.1.200\共有\生産管理課\材料管理.xlsx`
   - 用途: Excel発注データ取込機能で使用

## 技術詳細

### ファイル構成

1. **src/api/repository_check.py** (新規作成)
   - `check_path_accessibility()`: パスのアクセス可能性をチェックする関数
   - `RepositoryStatus`: リポジトリ状態を表すPydanticモデル
   - `RepositoryCheckResponse`: API レスポンス用Pydanticモデル
   - `GET /api/repositories/check`: APIエンドポイント

2. **src/main.py** (更新)
   - repository_check ルーターを追加

3. **src/templates/settings.html** (更新)
   - 「リポジトリ確認」タブを追加
   - JavaScript関数 `checkRepositories()` を実装

### 依存関係

- FastAPI (既存)
- Pydantic (既存)
- Python標準ライブラリ: `pathlib`, `os`

### エラーハンドリング

以下のエラーケースに対応:
- パスが存在しない
- アクセス権限がない（PermissionError）
- OSレベルのエラー（OSError）
- その他の予期しないエラー

すべてのエラーは適切にキャッチされ、ユーザーに分かりやすいメッセージとして表示されます。

## 使い方

### 管理者向け

1. ブラウザで `http://localhost:8000/settings` にアクセス
2. 左側のメニューから「リポジトリ確認」をクリック
3. 自動的に全リポジトリのアクセス状態がチェックされます
4. 問題があるリポジトリは赤色で表示されます
5. 「再チェック」ボタンで最新の状態に更新できます

### 開発者向け

APIを直接呼び出す場合:

```bash
curl http://localhost:8000/api/repositories/check
```

または、Pythonから:

```python
import requests

response = requests.get('http://localhost:8000/api/repositories/check')
data = response.json()

print(f"アクセス可能: {data['accessible_count']}/{data['total_count']}")
for repo in data['repositories']:
    status = '✓' if repo['accessible'] else '✗'
    print(f"{status} {repo['name']}: {repo['path']}")
```

## トラブルシューティング

### ネットワーク共有にアクセスできない

**症状**: リポジトリ確認画面で赤色のエラーが表示される

**確認事項**:
1. ネットワークパスが正しいか確認
2. ネットワーク接続を確認
3. アクセス権限を確認
4. `config.py` の設定を確認

**解決方法**:
- ネットワーク管理者に連絡してアクセス権限を確認
- パスが正しいか確認
- ファイアウォール設定を確認

## 今後の拡張可能性

このシステムは以下のような拡張が可能です:

1. **追加リポジトリのモニタリング**
   - `src/api/repository_check.py` の `repositories_to_check` リストに追加

2. **定期的な自動チェック**
   - バックグラウンドタスクで定期的にチェック
   - 異常時にアラート送信

3. **詳細な権限情報**
   - ファイル所有者情報
   - より詳細な権限情報（読み取り専用ユーザーなど）

4. **履歴追跡**
   - アクセス状態の変更履歴を記録
   - ダウンタイムの分析

## テスト

テストスクリプト `test_repository_check.py` を実行:

```bash
python test_repository_check.py
```

すべてのテストが成功すれば、機能は正常に動作しています。

## まとめ

この機能により、システム管理者は材料管理システムが必要とするネットワーク共有ファイルへのアクセス状態を簡単に確認できるようになりました。問題が発生した場合も、詳細なエラー情報により迅速な対応が可能です。
