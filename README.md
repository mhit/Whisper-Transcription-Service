# Whisper Transcription Service

GPU対応の高品質な日本語文字起こしサービス。Docker で簡単にデプロイでき、Web UI と REST API の両方からアクセス可能です。

## 特徴

- **高品質な日本語文字起こし**: OpenAI Whisper large-v3 を使用した最適化設定
- **OpenAI SDK 互換 API**: 既存の OpenAI クライアントからそのまま利用可能
- **複数の入力方法**: URL (YouTube, Vimeo 等) またはファイルアップロード
- **5種類の出力形式**: JSON, テキスト, SRT字幕, VTT字幕, Markdown
- **GPU メモリ最適化**: アイドル時に自動でモデルをアンロード
- **N8N 連携対応**: Webhook 通知によるワークフロー統合
- **シンプルなジョブ管理**: `JOB-XXXXXX` 形式の短いジョブID

## クイックスタート

### 前提条件

- Docker & Docker Compose
- NVIDIA GPU (CUDA 12.1+)
- NVIDIA Container Toolkit

### 1. 環境設定

```bash
# リポジトリをクローン
git clone https://github.com/mhit/Whisper-Transcription-Service.git
cd Whisper-Transcription-Service

# 環境変数を設定
cp .env.example .env

# .env ファイルを編集し、ADMIN_PASSWORD を設定
nano .env
```

### 2. 起動

```bash
# ビルドして起動
docker-compose up -d

# ログを確認
docker-compose logs -f
```

### 3. アクセス

- **Web UI**: http://localhost:8000
- **API ドキュメント**: http://localhost:8000/docs
- **ヘルスチェック**: http://localhost:8000/api/health

## 使い方

### Web UI

1. ブラウザで http://localhost:8000 を開く
2. URL を入力するか、ファイルをアップロード
3. 「文字起こしを開始」をクリック
4. ジョブIDが発行され、ステータスページに遷移
5. 完了後、各形式でダウンロード可能

### REST API

#### ジョブ作成 (URL)

```bash
curl -X POST http://localhost:8000/api/jobs \
  -F "url=https://www.youtube.com/watch?v=..."
```

#### ジョブ作成 (ファイルアップロード)

```bash
curl -X POST http://localhost:8000/api/jobs \
  -F "file=@video.mp4"
```

#### ジョブ作成 (Webhook 付き)

```bash
curl -X POST http://localhost:8000/api/jobs \
  -F "url=https://www.youtube.com/watch?v=..." \
  -F "webhook_url=https://n8n.example.com/webhook/xxx"
```

#### ステータス確認

```bash
curl http://localhost:8000/api/jobs/JOB-ABC123
```

レスポンス例:
```json
{
  "job_id": "JOB-ABC123",
  "status": "transcribing",
  "stage": "transcribing",
  "progress": 45,
  "created_at": "2025-01-15T10:30:00Z"
}
```

#### 結果ダウンロード

```bash
# JSON形式
curl -O http://localhost:8000/api/jobs/JOB-ABC123/download?format=json

# テキスト形式
curl -O http://localhost:8000/api/jobs/JOB-ABC123/download?format=txt

# SRT字幕形式
curl -O http://localhost:8000/api/jobs/JOB-ABC123/download?format=srt

# Markdown形式
curl -O http://localhost:8000/api/jobs/JOB-ABC123/download?format=md
```

#### ジョブ削除

```bash
curl -X DELETE http://localhost:8000/api/jobs/JOB-ABC123
```

## API リファレンス

### エンドポイント一覧

| Method | Endpoint | 説明 |
|--------|----------|------|
| POST | `/api/jobs` | ジョブ作成 |
| GET | `/api/jobs` | ジョブ一覧 |
| GET | `/api/jobs/{job_id}` | ステータス取得 |
| GET | `/api/jobs/{job_id}/download` | 結果ダウンロード |
| DELETE | `/api/jobs/{job_id}` | ジョブ削除 |
| GET | `/api/health` | ヘルスチェック |

### 管理者エンドポイント

`X-Admin-Password` ヘッダーに管理者パスワードが必要です。

| Method | Endpoint | 説明 |
|--------|----------|------|
| GET | `/api/admin/stats` | システム統計 |
| POST | `/api/admin/cleanup` | 期限切れジョブ削除 |
| POST | `/api/admin/model/unload` | モデルをアンロード |
| POST | `/api/admin/model/load` | モデルをロード |

### OpenAI 互換 API

既存の OpenAI SDK やツールからそのまま利用できる互換 API です。

| Method | Endpoint | 説明 |
|--------|----------|------|
| POST | `/v1/audio/transcriptions` | 音声文字起こし |
| POST | `/v1/audio/translations` | 英語への翻訳 |
| GET | `/v1/audio/models` | 利用可能モデル一覧 |

#### OpenAI Python SDK での使用例

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="not-needed"  # または設定した API キー
)

# 音声ファイルを文字起こし
with open("audio.mp3", "rb") as f:
    transcription = client.audio.transcriptions.create(
        model="whisper-1",
        file=f,
        language="ja",
        response_format="verbose_json"
    )

print(transcription.text)
```

#### curl での使用例

```bash
# 音声ファイルを文字起こし (JSON形式)
curl -X POST http://localhost:8000/v1/audio/transcriptions \
  -F "file=@audio.mp3" \
  -F "model=whisper-1" \
  -F "language=ja"

# verbose_json 形式で詳細取得
curl -X POST http://localhost:8000/v1/audio/transcriptions \
  -F "file=@audio.mp3" \
  -F "model=whisper-1" \
  -F "response_format=verbose_json"

# SRT字幕形式で出力
curl -X POST http://localhost:8000/v1/audio/transcriptions \
  -F "file=@audio.mp3" \
  -F "response_format=srt" \
  -o output.srt

# 英語に翻訳
curl -X POST http://localhost:8000/v1/audio/translations \
  -F "file=@japanese_audio.mp3" \
  -F "model=whisper-1"
```

#### サポートする出力形式

| Format | 説明 |
|--------|------|
| `json` | シンプルな JSON (`{"text": "..."}`) |
| `text` | プレーンテキスト |
| `srt` | SRT 字幕形式 |
| `vtt` | WebVTT 字幕形式 |
| `verbose_json` | 詳細 JSON (セグメント、タイムスタンプ含む) |

### ジョブステータス

| Status | 説明 |
|--------|------|
| `queued` | キューで待機中 |
| `downloading` | 動画をダウンロード中 |
| `extracting` | 音声を抽出中 |
| `transcribing` | 文字起こし中 |
| `formatting` | 出力ファイル生成中 |
| `completed` | 完了 |
| `failed` | エラー |

### Webhook ペイロード

ジョブ完了時または失敗時に、指定された Webhook URL に POST リクエストが送信されます。

**完了時:**
```json
{
  "event": "job.completed",
  "job_id": "JOB-ABC123",
  "status": "completed",
  "download_urls": {
    "json": "/api/jobs/JOB-ABC123/download?format=json",
    "txt": "/api/jobs/JOB-ABC123/download?format=txt",
    "srt": "/api/jobs/JOB-ABC123/download?format=srt",
    "md": "/api/jobs/JOB-ABC123/download?format=md"
  }
}
```

**失敗時:**
```json
{
  "event": "job.failed",
  "job_id": "JOB-ABC123",
  "status": "failed",
  "error": {
    "type": "transcription_error",
    "message": "Error details..."
  }
}
```

## N8N 連携

### N8N カスタムノード

専用の N8N カスタムノードを使用して、ワークフローから直接文字起こしサービスを利用できます。

#### インストール

```bash
# ノードをビルド
cd n8n-node
npm install
npm run build

# N8N にインストール (方法1: カスタムディレクトリ)
cd ~/.n8n/custom
npm install /path/to/VideoTranscriptAnalyzer/n8n-node

# N8N を再起動
docker-compose restart n8n
```

#### Docker 環境でのインストール

```yaml
# docker-compose.yml に追加
services:
  n8n:
    volumes:
      - ./n8n-node:/home/node/.n8n/custom/n8n-nodes-whisper-transcription
```

#### Credentials 設定

1. N8N の **Credentials** を開く
2. **Add Credential** → **Whisper Transcription API** を選択
3. 設定:
   - **Base URL**: `http://whisper-service:8000` (Docker 内部) または `http://localhost:8000`
   - **API Key**: (オプション) API キーを設定している場合のみ

#### サポートするオペレーション

| Operation | 説明 |
|-----------|------|
| **Create Job from URL** | YouTube 等の動画 URL から文字起こしジョブを作成 |
| **Create Job from File** | アップロードしたファイルから文字起こしジョブを作成 |
| **Get Job Status** | ジョブの現在のステータスを取得 |
| **Wait for Completion** | ジョブ完了までポーリングして待機 |
| **Download Result** | 完了したジョブの結果をダウンロード (JSON/TXT/SRT/MD) |
| **Delete Job** | ジョブを削除 |

#### ワークフロー例

**例1: URL から文字起こし → メール送信**
```
[Webhook] → [Whisper: Create from URL] → [Whisper: Wait for Completion] → [Whisper: Download] → [Email]
```

**例2: ファイルアップロード → Slack 通知**
```
[Webhook (File)] → [Whisper: Create from File] → [Whisper: Wait] → [Slack]
```

**例3: 非同期処理 (Webhook コールバック使用)**
```
[Trigger] → [Whisper: Create from URL + Webhook] ... [Webhook] → [Process Result]
```

詳細は `n8n-node/README.md` を参照してください。

---

## 設定

### 環境変数

| 変数名 | デフォルト | 説明 |
|--------|----------|------|
| `ADMIN_PASSWORD` | (必須) | 管理者パスワード |
| `WHISPER_MODEL` | `large-v3` | Whisper モデル |
| `MODEL_UNLOAD_MINUTES` | `5` | アイドル後にモデルをアンロードする分数 |
| `JOB_RETENTION_DAYS` | `7` | ジョブデータの保持日数 |
| `API_KEY` | (空) | API 認証キー (オプション) |
| `CLOUDFLARE_TUNNEL_TOKEN` | (空) | Cloudflare Tunnel トークン |
| `DEBUG` | `false` | デバッグモード |

### Whisper モデル

| モデル | VRAM | 精度 | 速度 |
|--------|------|------|------|
| `tiny` | ~1GB | 低 | 最速 |
| `base` | ~1GB | 低 | 速い |
| `small` | ~2GB | 中 | 普通 |
| `medium` | ~5GB | 高 | 遅い |
| `large-v3` | ~10GB | 最高 | 最遅 |

## アーキテクチャ

```
┌─────────────────────────────────────────────────────────┐
│                     Web UI / API                        │
├─────────────────────────────────────────────────────────┤
│                     FastAPI                             │
├──────────────┬──────────────┬─────────────┬────────────┤
│   Jobs API   │  Admin API   │ Health API  │ OpenAI API │
│  /api/jobs   │ /api/admin   │ /api/health │ /v1/audio  │
├──────────────┴──────────────┴─────────────┴────────────┤
│                   Job Processor                         │
│  ┌─────────┬─────────┬─────────────┬──────────────┐   │
│  │Download │ Extract │ Transcribe  │   Format     │   │
│  │(yt-dlp) │(FFmpeg) │  (Whisper)  │(JSON/SRT/MD) │   │
│  └─────────┴─────────┴─────────────┴──────────────┘   │
├─────────────────────────────────────────────────────────┤
│                   SQLite Database                       │
└─────────────────────────────────────────────────────────┘
```

### 処理フロー

1. **ジョブ作成**: URL または ファイルを受け取り、ジョブIDを発行
2. **ダウンロード**: yt-dlp で動画をダウンロード (URLの場合)
3. **音声抽出**: FFmpeg で 16kHz モノラル WAV に変換
4. **文字起こし**: Whisper で日本語最適化設定を使用して文字起こし
5. **フォーマット**: JSON, テキスト, SRT, Markdown 形式で出力
6. **通知**: Webhook URL が設定されている場合、完了/失敗を通知
7. **クリーンアップ**: 中間ファイル (WAV) を自動削除

## 開発

### ローカル開発環境

```bash
# 仮想環境を作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存関係をインストール
pip install -r requirements.txt

# 開発サーバーを起動
python -m app.main
```

### テスト実行

```bash
# 全テストを実行
pytest

# カバレッジ付き
pytest --cov=app --cov-report=html

# 特定のテストを実行
pytest tests/unit/test_whisper_manager.py -v
```

### プロジェクト構造

```
Whisper-Transcription-Service/
├── app/
│   ├── api/
│   │   ├── dependencies.py    # DI コンテナ
│   │   └── routes/
│   │       ├── admin.py       # 管理者API
│   │       ├── health.py      # ヘルスチェック
│   │       ├── jobs.py        # ジョブAPI
│   │       ├── openai_compat.py # OpenAI 互換 API
│   │       └── web.py         # Web UI
│   ├── core/
│   │   ├── audio_extractor.py # FFmpeg 音声抽出
│   │   ├── downloader.py      # yt-dlp ダウンロード
│   │   ├── formatter.py       # 出力フォーマット
│   │   ├── job_processor.py   # パイプライン処理
│   │   └── whisper_manager.py # Whisper 管理
│   ├── db/
│   │   └── database.py        # SQLite データベース
│   ├── models/
│   │   └── job.py             # Pydantic モデル
│   ├── static/                # CSS/JS
│   ├── templates/             # Jinja2 テンプレート
│   ├── config.py              # 設定管理
│   └── main.py                # アプリケーション
├── n8n-node/                   # N8N カスタムノード
│   ├── nodes/
│   │   └── WhisperTranscription/
│   │       ├── WhisperTranscription.node.ts
│   │       └── whisper.svg
│   ├── credentials/
│   │   └── WhisperTranscriptionApi.credentials.ts
│   ├── package.json
│   └── README.md
├── tests/
│   └── unit/                  # ユニットテスト
├── scripts/
│   └── entrypoint.sh          # Docker エントリーポイント
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## トラブルシューティング

### GPU が認識されない

```bash
# NVIDIA ドライバーを確認
nvidia-smi

# NVIDIA Container Toolkit を確認
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

### メモリ不足エラー

`WHISPER_MODEL` を小さいモデルに変更:

```bash
WHISPER_MODEL=medium docker-compose up -d
```

### ダウンロードが失敗する

yt-dlp を最新バージョンに更新:

```bash
docker-compose build --no-cache
```

### 文字起こしの品質が低い

- 音声品質が低い場合、前処理でノイズ除去を検討
- `large-v3` モデルを使用していることを確認
- 音声が日本語であることを確認

## ライセンス

MIT License

## 謝辞

- [OpenAI Whisper](https://github.com/openai/whisper) - 高精度な音声認識モデル
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - 動画ダウンロードツール
- [FastAPI](https://fastapi.tiangolo.com/) - 高速な Web フレームワーク
