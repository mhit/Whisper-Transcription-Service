# n8n-nodes-whisper-transcription

N8N カスタムノード - Whisper Transcription Service 用

日本語最適化された動画・音声ファイルの文字起こしサービスを N8N から直接利用できます。

## 機能

| Operation | 説明 |
|-----------|------|
| **Create Job from URL** | YouTube 等の動画 URL から文字起こしジョブを作成 |
| **Create Job from File** | アップロードしたファイルから文字起こしジョブを作成 |
| **Get Job Status** | ジョブの現在のステータスを取得 |
| **Wait for Completion** | ジョブ完了までポーリングして待機 |
| **Download Result** | 完了したジョブの結果をダウンロード |
| **Delete Job** | ジョブを削除 |

## インストール

### 方法 1: N8N コミュニティノードとしてインストール

```bash
cd ~/.n8n/custom
npm install /path/to/n8n-node
```

### 方法 2: Docker 環境でインストール

```yaml
# docker-compose.yml に追加
volumes:
  - ./n8n-node:/home/node/.n8n/custom/n8n-nodes-whisper-transcription
```

### 方法 3: npm からインストール (公開後)

N8N の設定画面 → Community Nodes から検索・インストール

## 設定

### 1. Credentials の追加

1. N8N の **Credentials** を開く
2. **Add Credential** → **Whisper Transcription API** を選択
3. 設定:
   - **Base URL**: `http://whisper-service:8000` (Docker 内部) または `http://localhost:8000`
   - **API Key**: (オプション) API キーを設定している場合のみ

### 2. ノードの使用

N8N のエディターで **Whisper Transcription** ノードを追加

## 使用例

### 例 1: URL から文字起こし → 結果をメール送信

```
[Webhook] → [Whisper: Create from URL] → [Whisper: Wait for Completion] → [Whisper: Download] → [Email]
```

1. **Webhook**: 外部からの文字起こしリクエストを受信
2. **Create from URL**: YouTube URL からジョブを作成
3. **Wait for Completion**: 完了まで待機
4. **Download Result**: テキスト形式でダウンロード
5. **Email**: 結果をメールで送信

### 例 2: ファイルアップロード → Slack 通知

```
[Webhook (File)] → [Whisper: Create from File] → [Whisper: Wait] → [Slack]
```

### 例 3: 非同期処理 (Webhook コールバック使用)

```
[Trigger] → [Whisper: Create from URL + Webhook] ... [Webhook] → [Process Result]
```

Webhook URL を指定すると、ジョブ完了時に N8N の Webhook ノードにコールバックが送信されます。

## ノードパラメータ

### Create Job from URL

| パラメータ | 説明 |
|-----------|------|
| Video URL | 文字起こしする動画の URL |
| Webhook URL | (オプション) 完了時の通知先 |

### Create Job from File

| パラメータ | 説明 |
|-----------|------|
| Binary Property | ファイルが格納されているバイナリプロパティ名 |
| Webhook URL | (オプション) 完了時の通知先 |

### Get Job Status / Wait for Completion

| パラメータ | 説明 |
|-----------|------|
| Job ID | ジョブID (JOB-XXXXXX 形式) |
| Polling Interval | (Wait のみ) ポーリング間隔 (秒) |
| Timeout | (Wait のみ) タイムアウト (分) |

### Download Result

| パラメータ | 説明 |
|-----------|------|
| Job ID | ジョブID |
| Output Format | json / txt / srt / md |

## 出力例

### Create Job

```json
{
  "job_id": "JOB-ABC123",
  "status": "queued",
  "message": "Job submitted successfully"
}
```

### Get Status / Wait for Completion

```json
{
  "job_id": "JOB-ABC123",
  "status": "completed",
  "stage": "completed",
  "progress": 100,
  "created_at": "2025-01-15T10:30:00Z",
  "completed_at": "2025-01-15T10:35:00Z",
  "download_urls": {
    "json": "/api/jobs/JOB-ABC123/download?format=json",
    "txt": "/api/jobs/JOB-ABC123/download?format=txt",
    "srt": "/api/jobs/JOB-ABC123/download?format=srt",
    "md": "/api/jobs/JOB-ABC123/download?format=md"
  }
}
```

### Download Result

JSON 出力 + バイナリデータ (ファイル)

```json
{
  "job_id": "JOB-ABC123",
  "format": "txt"
}
```

## 開発

### ビルド

```bash
cd n8n-node
npm install
npm run build
```

### 開発モード

```bash
npm run dev
```

## トラブルシューティング

### 接続エラー

- Base URL が正しいか確認
- Docker 内の場合はサービス名 (`whisper-service`) を使用
- ファイアウォール設定を確認

### タイムアウトエラー

- 長い動画の場合は Timeout 値を増やす
- ネットワーク接続を確認

### ジョブが失敗する

- Whisper サービスのログを確認: `docker-compose logs whisper-service`
- GPU メモリ不足の場合は小さいモデルに変更

## ライセンス

MIT License
