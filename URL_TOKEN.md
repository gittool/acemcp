# BASE_URLとTOKENが必要な理由と処理フロー

## 概要

`acemcp`はコードベースのインデックス化と検索を行うMCPサーバーです。BASE_URLとTOKENは、外部のコード解析APIサービスと通信するために必要な認証情報です。

## BASE_URLとTOKENの役割

### BASE_URL
- **役割**: 外部のコード解析APIサービスのエンドポイントURL
- **デフォルト値**: `https://api.example.com`
- **使用箇所**: 
  - バッチアップロード: `{BASE_URL}/batch-upload`
  - コードベース検索: `{BASE_URL}/agents/codebase-retrieval`

### TOKEN
- **役割**: APIサービスへの認証トークン
- **デフォルト値**: `your-token-here`
- **使用方法**: HTTPリクエストのAuthorizationヘッダーに `Bearer {TOKEN}` として付与

## 処理フロー

### 1. 初期化フロー

```
起動時
  ↓
server.py: init_config(base_url, token)
  ↓
config.py: Config.__init__()
  ↓
設定の優先順位:
  1. コマンドライン引数 (--base-url, --token)
  2. 環境変数 (ACEMCP_BASE_URL, ACEMCP_TOKEN)
  3. ユーザー設定ファイル (~/.acemcp/settings.toml)
  4. デフォルト値
```

### 2. インデックス化フロー

```
search_context_tool() 呼び出し
  ↓
IndexManager.search_context()
  ↓
【自動インデックス化】
IndexManager.index_project()
  ↓
1. プロジェクトファイルの収集
   - テキストファイルを再帰的にスキャン
   - .gitignoreとexclude_patternsで除外
   - 大きなファイルは複数のblobに分割
  ↓
2. 差分検出（インクリメンタル）
   - 各blobのハッシュ値を計算
   - 既存のblob_namesと比較
   - 新規/変更されたblobのみを抽出
  ↓
3. APIへのアップロード
   ┌─────────────────────────────┐
   │ POST {BASE_URL}/batch-upload │
   │ Authorization: Bearer {TOKEN}│
   │ Body: { blobs: [...] }      │
   └─────────────────────────────┘
   - バッチサイズ単位で分割アップロード
   - タイムアウト/エラー時は自動リトライ（最大3回）
   - 指数バックオフで再試行間隔を調整
  ↓
4. blob_namesの保存
   - APIから返されたblob_namesを記録
   - ~/.acemcp/data/projects.jsonに保存
```

### 3. 検索フロー

```
【検索実行】
IndexManager.search_context()
  ↓
1. インデックス化完了後、blob_namesを取得
  ↓
2. APIへの検索リクエスト
   ┌──────────────────────────────────────────┐
   │ POST {BASE_URL}/agents/codebase-retrieval │
   │ Authorization: Bearer {TOKEN}             │
   │ Body: {                                   │
   │   information_request: "検索クエリ",       │
   │   blobs: {                                │
   │     added_blobs: [blob_names...]          │
   │   }                                       │
   │ }                                         │
   └──────────────────────────────────────────┘
   - セマンティック検索を実行
   - タイムアウト60秒、リトライ3回
  ↓
3. 検索結果の取得
   - formatted_retrievalフィールドを抽出
   - ファイルパス、行番号付きのコードスニペット
```

## API通信の詳細

### バッチアップロードAPI

**エンドポイント**: `POST {BASE_URL}/batch-upload`

**リクエスト**:
```json
{
  "blobs": [
    {
      "path": "src/main.py",
      "content": "ファイルの内容..."
    }
  ]
}
```

**レスポンス**:
```json
{
  "blob_names": [
    "hash1234...",
    "hash5678..."
  ]
}
```

### コードベース検索API

**エンドポイント**: `POST {BASE_URL}/agents/codebase-retrieval`

**リクエスト**:
```json
{
  "information_request": "ログ設定の初期化コード",
  "blobs": {
    "checkpoint_id": null,
    "added_blobs": ["hash1234...", "hash5678..."],
    "deleted_blobs": []
  },
  "dialog": [],
  "max_output_length": 0,
  "disable_codebase_retrieval": false,
  "enable_commit_retrieval": false
}
```

**レスポンス**:
```json
{
  "formatted_retrieval": "検索結果のフォーマット済みテキスト..."
}
```

## エラーハンドリング

### リトライ機構
- **対象エラー**: タイムアウト、接続エラー、読み取りタイムアウト
- **リトライ回数**: 最大3回
- **バックオフ**: 指数関数的（1秒 → 2秒 → 4秒）
- **非リトライエラー**: その他の例外は即座に失敗

### バッチアップロード失敗時
- 失敗したバッチをスキップして次のバッチを継続
- 部分的な成功でも処理を続行
- 失敗したバッチ番号を記録してレポート

## 設定方法

### 1. コマンドライン引数（最優先）
```bash
python -m acemcp.server --base-url https://your-api.com --token your-secret-token
```

### 2. 環境変数
```bash
export ACEMCP_BASE_URL=https://your-api.com
export ACEMCP_TOKEN=your-secret-token
python -m acemcp.server
```

### 3. 設定ファイル
`~/.acemcp/settings.toml`を編集:
```toml
BASE_URL = "https://your-api.com"
TOKEN = "your-secret-token"
```

## セキュリティ考慮事項

1. **TOKENの保護**
   - 環境変数または設定ファイルで管理
   - コードにハードコーディングしない
   - バージョン管理システムにコミットしない

2. **HTTPS通信**
   - BASE_URLは必ずHTTPSを使用
   - 通信内容の暗号化

3. **アクセス制御**
   - TOKENによる認証でAPIへのアクセスを制限
   - 不正なアクセスを防止

## まとめ

- **BASE_URL**: 外部コード解析APIのエンドポイント
- **TOKEN**: API認証トークン
- **必要な理由**: コードのインデックス化と検索をクラウドサービスで実行するため
- **処理の流れ**: ローカルでファイル収集 → API経由でアップロード → blob_names取得 → 検索時にblob_namesを使用
- **インクリメンタル**: 変更されたファイルのみをアップロードして効率化
- **信頼性**: 自動リトライとエラーハンドリングで安定した通信を実現
