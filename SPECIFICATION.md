# Whisper Transcription Service - 仕様書

**バージョン**: 1.0
**作成日**: 2025-12-17
**ステータス**: 要件確定

---

## 1. システム概要

### 1.1 目的
動画・音声ファイルの日本語文字起こしをDocker環境で提供するマイクロサービス。
Web UIおよびREST APIを通じて、ユーザーやN8Nワークフローから利用可能。

### 1.2 主要機能
- 動画/音声の文字起こし（Whisper large-v3）
- 複数出力形式対応（JSON, TXT, SRT, Markdown）
- ジョブキュー管理
- GPUメモリ効率管理（オンデマンドロード/アンロード）
- Cloudflare Tunnel統合
- N8N Webhook連携

---

## 2. アーキテクチャ

### 2.1 構成図

```
┌─────────────────────────────────────────────────────────────────┐
│                      Docker Container                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                      FastAPI                             │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐               │    │
│  │  │  Web UI  │  │ REST API │  │  Admin   │               │    │
│  │  └──────────┘  └──────────┘  └──────────┘               │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   Job Processor                          │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐  │    │
│  │  │Downloader│─▶│ Extractor│─▶│ Whisper  │─▶│Formatter│  │    │
│  │  │ (yt-dlp) │  │ (ffmpeg) │  │ Manager  │  │         │  │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └─────────┘  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                      SQLite                              │    │
│  │         ジョブ状態・メタデータ永続化                      │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌──────────────┐                                               │
│  │  cloudflared │◀── CLOUDFLARE_TUNNEL_TOKEN                    │
│  └──────────────┘                                               │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│  Volume Mounts:                                                  │
│    /data/jobs/   - ジョブデータ（入力・出力）                     │
│    /data/db/     - SQLite データベース                           │
│    /data/export/ - エクスポートデータ                            │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 技術スタック

| コンポーネント | 技術 |
|----------------|------|
| Web Framework | FastAPI |
| 非同期処理 | asyncio + BackgroundTasks |
| データベース | SQLite（aiosqlite） |
| ジョブキュー | asyncio.Queue |
| 文字起こし | OpenAI Whisper (large-v3) |
| 動画DL | yt-dlp |
| 音声抽出 | FFmpeg |
| トンネル | cloudflared |
| コンテナ | Docker (nvidia/cuda) |

---

## 3. 機能仕様

### 3.1 ジョブ投入

#### URL指定
```http
POST /api/jobs
Content-Type: application/json
X-API-Key: {api_key}  # オプション

{
  "url": "https://www.youtube.com/watch?v=xxxxx",
  "webhook_url": "https://n8n.example.com/webhook/callback"  # オプション
}
```

#### ファイルアップロード
```http
POST /api/jobs
Content-Type: multipart/form-data
X-API-Key: {api_key}  # オプション

file: (binary)
webhook_url: https://n8n.example.com/webhook/callback  # オプション
```

#### レスポンス
```json
{
  "job_id": "JOB-A1B2C3",
  "status": "queued",
  "created_at": "2025-12-17T10:00:00Z",
  "expires_at": "2025-12-24T10:00:00Z"
}
```

### 3.2 ジョブ状態確認

```http
GET /api/jobs/{job_id}
```

#### レスポンス（処理中）
```json
{
  "job_id": "JOB-A1B2C3",
  "status": "processing",
  "stage": "transcribing",
  "progress": 75,
  "created_at": "2025-12-17T10:00:00Z",
  "expires_at": "2025-12-24T10:00:00Z"
}
```

#### レスポンス（完了）
```json
{
  "job_id": "JOB-A1B2C3",
  "status": "completed",
  "stage": "completed",
  "progress": 100,
  "duration_seconds": 3600,
  "created_at": "2025-12-17T10:00:00Z",
  "completed_at": "2025-12-17T10:15:00Z",
  "expires_at": "2025-12-24T10:00:00Z",
  "download_urls": {
    "json": "/api/jobs/JOB-A1B2C3/download?format=json",
    "txt": "/api/jobs/JOB-A1B2C3/download?format=txt",
    "srt": "/api/jobs/JOB-A1B2C3/download?format=srt",
    "md": "/api/jobs/JOB-A1B2C3/download?format=md"
  }
}
```

#### レスポンス（失敗）
```json
{
  "job_id": "JOB-A1B2C3",
  "status": "failed",
  "stage": "downloading",
  "error": {
    "type": "download_error",
    "message": "Video unavailable",
    "details": "yt-dlp: ERROR: Video unavailable..."
  },
  "created_at": "2025-12-17T10:00:00Z",
  "failed_at": "2025-12-17T10:01:00Z",
  "expires_at": "2025-12-24T10:00:00Z"
}
```

### 3.3 結果ダウンロード

```http
GET /api/jobs/{job_id}/download?format={format}
```

| format | Content-Type | 説明 |
|--------|--------------|------|
| json | application/json | タイムスタンプ付きセグメント |
| txt | text/plain | プレーンテキスト |
| srt | text/plain | SRT字幕形式 |
| md | text/markdown | Markdownレポート |

### 3.4 ジョブ削除

```http
DELETE /api/jobs/{job_id}
```

### 3.5 Webhook通知

処理完了/失敗時にWebhook URLへPOST:

```json
{
  "event": "job.completed",
  "job_id": "JOB-A1B2C3",
  "status": "completed",
  "download_urls": {
    "json": "https://xxx.trycloudflare.com/api/jobs/JOB-A1B2C3/download?format=json",
    ...
  }
}
```

---

## 4. 管理者機能

### 4.1 認証
- 環境変数 `ADMIN_PASSWORD` で設定
- Basic認証: `admin:{ADMIN_PASSWORD}`

### 4.2 管理者API

```http
# 全ジョブ一覧
GET /api/admin/jobs
Authorization: Basic {base64(admin:password)}

# ジョブ詳細（ログ含む）
GET /api/admin/jobs/{job_id}

# ジョブ強制削除
DELETE /api/admin/jobs/{job_id}

# キュー状態
GET /api/admin/queue

# システム状態
GET /api/admin/system
```

### 4.3 管理者UI

```
/admin - 管理者ダッシュボード
  - ジョブ一覧（ステータス別フィルタ）
  - キュー状態
  - GPU/モデル状態
  - ジョブ削除機能
```

---

## 5. GPUメモリ管理

### 5.1 モデルライフサイクル

```
[アンロード状態]
      │
      │ ジョブ到着
      ▼
[ロード中] ─── 15-30秒
      │
      ▼
[ロード済み] ◀─────┐
      │            │
      │ ジョブ処理  │
      ▼            │
[処理中] ──────────┘
      │
      │ キュー空 AND アイドル5分
      ▼
[アンロード実行]
      │
      ▼
[アンロード状態]
```

### 5.2 アンロード条件
- ジョブキューが空
- AND 最後のジョブ完了から5分経過

### 5.3 Whisper設定（レガシーから継承）

```python
WHISPER_CONFIG = {
    "model": "large-v3",
    "language": "ja",
    "task": "transcribe",
    "temperature": 0.0,
    "beam_size": 5,
    "best_of": 5,
    "patience": 1.0,
    "condition_on_previous_text": False,  # 幻覚防止（重要）
    "compression_ratio_threshold": 2.4,
    "logprob_threshold": -1.0,
    "no_speech_threshold": 0.6,
    "word_timestamps": False,
}
```

---

## 6. データ管理

### 6.1 ジョブデータ構造

```
/data/jobs/{job_id}/
├── input/
│   ├── source.mp4      # ダウンロード/アップロードファイル
│   └── audio.wav       # 抽出音声（処理後削除）
├── output/
│   ├── transcript.json # Whisper生出力
│   ├── result.txt      # プレーンテキスト
│   ├── result.srt      # SRT形式
│   └── result.md       # Markdown
└── logs/
    └── process.log     # 処理ログ
```

### 6.2 ライフサイクル

| タイミング | アクション |
|------------|------------|
| ジョブ投入 | ディレクトリ作成、ステータス記録 |
| 処理完了 | 中間ファイル削除（audio.wav等） |
| 7日経過 | 自動削除（全データ） |
| ユーザー削除 | 即座に全データ削除 |

### 6.3 データエクスポート

```http
# 管理者機能: データエクスポート
GET /api/admin/export?from=2025-12-01&to=2025-12-31
```

エクスポート形式:
```
/data/export/export_20251217_100000.zip
├── jobs_metadata.json
└── jobs/
    ├── JOB-A1B2C3/
    │   └── (output files)
    └── ...
```

---

## 7. 環境変数

```bash
# 必須
ADMIN_PASSWORD=your_admin_password

# オプション
API_KEY=wts_xxxxxxxxxxxx          # 設定時: API認証有効
CLOUDFLARE_TUNNEL_TOKEN=xxxxx     # 設定時: トンネル自動開始

# システム設定
PORT=8000                         # デフォルト: 8000
DATA_DIR=/data                    # デフォルト: /data
JOB_RETENTION_DAYS=7              # デフォルト: 7
MODEL_UNLOAD_MINUTES=5            # デフォルト: 5
MAX_UPLOAD_SIZE_MB=10240          # デフォルト: 10GB
```

---

## 8. Docker構成

### 8.1 Dockerfile

```dockerfile
FROM nvidia/cuda:12.1-cudnn8-runtime-ubuntu22.04

# システム依存関係
RUN apt-get update && apt-get install -y \
    python3.11 python3-pip ffmpeg git curl \
    && rm -rf /var/lib/apt/lists/*

# cloudflared
RUN curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
    -o /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared

# Python依存関係
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Whisperモデル事前ダウンロード
RUN python3 -c "import whisper; whisper.load_model('large-v3')"

# アプリケーション
COPY app/ /app/
WORKDIR /app

# ボリューム
VOLUME ["/data"]

# エントリポイント
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
```

### 8.2 entrypoint.sh

```bash
#!/bin/bash

# コンソール出力
echo "┌─────────────────────────────────────────┐"
echo "│ Whisper Transcription Service           │"
echo "├─────────────────────────────────────────┤"
echo "│ Local:    http://localhost:${PORT:-8000}│"

# Cloudflare Tunnel
if [ -n "$CLOUDFLARE_TUNNEL_TOKEN" ]; then
    cloudflared tunnel run --token "$CLOUDFLARE_TUNNEL_TOKEN" &
    echo "│ Tunnel:   Connecting...                │"
fi

# 認証情報
if [ -n "$API_KEY" ]; then
    echo "│ API Key:  ${API_KEY:0:10}...           │"
fi
echo "│ Admin:    admin / ****                  │"

# GPU情報
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | while read line; do
    echo "│ GPU:      $line                        │"
done

echo "│ Model:    Not loaded (on-demand)        │"
echo "└─────────────────────────────────────────┘"

# FastAPI起動
exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
```

### 8.3 docker-compose.yml（オプション）

```yaml
version: '3.8'

services:
  whisper:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/data
    environment:
      - ADMIN_PASSWORD=${ADMIN_PASSWORD}
      - API_KEY=${API_KEY}
      - CLOUDFLARE_TUNNEL_TOKEN=${CLOUDFLARE_TUNNEL_TOKEN}
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

---

## 9. Web UI仕様

### 9.1 メイン画面 (`/`)

```
┌─────────────────────────────────────────────────────────┐
│  🎙️ Whisper Transcription Service                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ 📎 URL入力                                      │   │
│  │ ┌─────────────────────────────────────────────┐ │   │
│  │ │ https://www.youtube.com/watch?v=...        │ │   │
│  │ └─────────────────────────────────────────────┘ │   │
│  │                                                 │   │
│  │ または                                          │   │
│  │                                                 │   │
│  │ 📁 ファイルをドラッグ＆ドロップ                  │   │
│  │ ┌─────────────────────────────────────────────┐ │   │
│  │ │                                             │ │   │
│  │ │     ここにファイルをドロップ                 │ │   │
│  │ │                                             │ │   │
│  │ └─────────────────────────────────────────────┘ │   │
│  │                                                 │   │
│  │            [ 🚀 処理開始 ]                      │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  📋 処理状況                                            │
│  ┌─────────────────────────────────────────────────┐   │
│  │ ジョブID: JOB-A1B2C3                            │   │
│  │ ステータス: 文字起こし中                         │   │
│  │ 進捗: ████████████░░░░░░░░ 60%                  │   │
│  │ 経過時間: 5:32                                  │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  📥 結果取得                                            │
│  ┌─────────────────────────────────────────────────┐   │
│  │ ジョブID: [_______________] [ 🔍 取得 ]         │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ 📄 プレビュー                                   │   │
│  │ ┌─────────────────────────────────────────────┐ │   │
│  │ │ [00:00:00] こんにちは、今日のセミナーを...   │ │   │
│  │ │ [00:00:05] 始めさせていただきます...         │ │   │
│  │ │ ...                                         │ │   │
│  │ └─────────────────────────────────────────────┘ │   │
│  │                                                 │   │
│  │ ダウンロード:                                   │   │
│  │ [JSON] [TXT] [SRT] [Markdown]                  │   │
│  │                                                 │   │
│  │ [ 🗑️ このジョブを削除 ]                         │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 9.2 管理者画面 (`/admin`)

```
┌─────────────────────────────────────────────────────────┐
│  ⚙️ 管理者ダッシュボード                   [ログアウト] │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  📊 システム状態                                        │
│  ┌─────────────────────────────────────────────────┐   │
│  │ GPU: NVIDIA RTX 4090 (24GB)                     │   │
│  │ モデル: ロード済み (VRAM: 3.2GB使用)            │   │
│  │ キュー: 2件待機中                               │   │
│  │ アイドル: 3分 (5分でアンロード)                 │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  📋 ジョブ一覧                                          │
│  [すべて] [処理中] [完了] [失敗] [期限切れ間近]         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ ID          │ ステータス │ 作成日時  │ 操作     │   │
│  ├─────────────────────────────────────────────────┤   │
│  │ JOB-A1B2C3  │ ✅ 完了   │ 12/17 10:00│ [詳細][削除]│   │
│  │ JOB-D4E5F6  │ 🔄 処理中 │ 12/17 10:30│ [詳細][削除]│   │
│  │ JOB-G7H8I9  │ ❌ 失敗   │ 12/17 11:00│ [詳細][削除]│   │
│  │ JOB-J0K1L2  │ ⏳ 待機中 │ 12/17 11:30│ [詳細][削除]│   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  🔧 操作                                                │
│  [ モデルアンロード ] [ データエクスポート ] [ ログ表示 ] │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 10. 処理フロー

### 10.1 ジョブ処理シーケンス

```
Client                API               Processor            Whisper
  │                    │                    │                    │
  │─POST /api/jobs────▶│                    │                    │
  │                    │─キュー追加────────▶│                    │
  │◀─202 job_id────────│                    │                    │
  │                    │                    │                    │
  │                    │                    │─モデルロード?─────▶│
  │                    │                    │◀─ロード完了────────│
  │                    │                    │                    │
  │                    │                    │─ダウンロード開始   │
  │                    │                    │ (並列可能)         │
  │                    │                    │                    │
  │                    │                    │─音声抽出           │
  │                    │                    │ (並列可能)         │
  │                    │                    │                    │
  │                    │                    │─文字起こし────────▶│
  │                    │                    │◀─結果──────────────│
  │                    │                    │                    │
  │                    │                    │─出力形式変換       │
  │                    │                    │                    │
  │                    │                    │─中間ファイル削除   │
  │                    │                    │                    │
  │                    │◀─完了通知──────────│                    │
  │                    │                    │                    │
  │                    │─Webhook送信───────▶ N8N                 │
  │                    │                    │                    │
  │─GET /api/jobs/{id}▶│                    │                    │
  │◀─200 結果──────────│                    │                    │
```

### 10.2 エラーハンドリング

| ステージ | エラー例 | 対応 |
|----------|----------|------|
| ダウンロード | URL無効、動画非公開 | エラー記録、Webhook通知 |
| 音声抽出 | FFmpegエラー | エラー記録、Webhook通知 |
| 文字起こし | GPU OOM、モデルエラー | エラー記録、詳細ログ保存 |
| 出力生成 | ディスク容量不足 | エラー記録、管理者通知 |

---

## 11. APIエンドポイント一覧

### 11.1 公開API

| メソッド | パス | 説明 | 認証 |
|----------|------|------|------|
| POST | `/api/jobs` | ジョブ投入 | APIキー（任意） |
| GET | `/api/jobs/{job_id}` | 状態確認 | なし |
| GET | `/api/jobs/{job_id}/download` | 結果DL | なし |
| DELETE | `/api/jobs/{job_id}` | ジョブ削除 | なし |
| GET | `/api/health` | ヘルスチェック | なし |

### 11.2 管理者API

| メソッド | パス | 説明 | 認証 |
|----------|------|------|------|
| GET | `/api/admin/jobs` | 全ジョブ一覧 | Basic認証 |
| GET | `/api/admin/jobs/{job_id}` | ジョブ詳細（ログ含む） | Basic認証 |
| DELETE | `/api/admin/jobs/{job_id}` | 強制削除 | Basic認証 |
| GET | `/api/admin/queue` | キュー状態 | Basic認証 |
| GET | `/api/admin/system` | システム状態 | Basic認証 |
| POST | `/api/admin/model/unload` | モデルアンロード | Basic認証 |
| GET | `/api/admin/export` | データエクスポート | Basic認証 |

---

## 12. セキュリティ考慮事項

### 12.1 認証レベル

| 機能 | 認証 | 備考 |
|------|------|------|
| ジョブ投入 | APIキー（任意） | 設定時のみ必須 |
| 結果取得 | ジョブID | 推測困難なID |
| 管理者機能 | Basic認証 | ADMIN_PASSWORD必須 |

### 12.2 ジョブID生成

```python
import secrets
import string

def generate_job_id():
    # 形式: JOB-XXXXXX (6文字英数字)
    chars = string.ascii_uppercase + string.digits
    random_part = ''.join(secrets.choice(chars) for _ in range(6))
    return f"JOB-{random_part}"
```

- 36^6 = 約21億通り
- 推測困難
- 人間が読みやすい長さ

### 12.3 Cloudflare Tunnel経由の公開

- APIキー設定推奨
- 管理者ページは追加認証必須
- レート制限の検討（将来）

---

## 13. 将来の拡張性

### 13.1 現時点では実装しない機能

| 機能 | 理由 |
|------|------|
| 複数GPU対応 | シングルGPU前提 |
| 水平スケーリング | SQLite/asyncio構成のため |
| 多言語対応 | 日本語固定 |
| ユーザー管理 | ジョブIDベースで十分 |
| ストリーミング入力 | 複雑性回避 |

### 13.2 将来対応可能な設計

- GPU追加時: Whisper Managerの拡張
- スケール時: Redis + Celeryへの移行
- 多言語時: 設定パラメータの追加

---

## 14. 開発フェーズ

### Phase 1: コア機能（MVP）
- [ ] プロジェクト構造作成
- [ ] FastAPI基本構造
- [ ] Whisper Manager（ロード/アンロード）
- [ ] ジョブキュー（asyncio.Queue）
- [ ] SQLiteジョブ管理
- [ ] ダウンローダー（yt-dlp）
- [ ] 音声抽出（ffmpeg）
- [ ] 出力フォーマッター（4形式）
- [ ] REST API実装

### Phase 2: UI・連携
- [ ] Web UI（メイン画面）
- [ ] Web UI（管理者画面）
- [ ] Webhook通知
- [ ] Cloudflare Tunnel統合

### Phase 3: 運用機能
- [ ] 自動削除（7日経過）
- [ ] データエクスポート
- [ ] エラーログ詳細化
- [ ] ヘルスチェック

### Phase 4: Docker化
- [ ] Dockerfile作成
- [ ] docker-compose.yml
- [ ] GPU対応テスト
- [ ] 本番環境テスト

---

*Document Version: 1.0*
*Created: 2025-12-17*
*Status: Requirements Confirmed*
