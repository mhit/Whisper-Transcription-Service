# VideoTranscriptAnalyzer Web UI・Docker化 調査レポート

**調査日**: 2025-12-17
**ステータス**: 構想段階調査完了

---

## 1. エグゼクティブサマリー

### 現状評価
VideoTranscriptAnalyzerは、日本語の長時間会議音声の文字起こしにおいて優れた性能を発揮している。10GB超の大容量ファイルも安定して処理可能。ただし、以下の課題がある：

| 項目 | 現状 | 目標 |
|------|------|------|
| UI | コンソールベース | Web UI |
| デプロイ | ローカル実行 | Docker |
| AI機能 | Gemini（動作不良） | 削除予定 |

### 結論
- **コア機能（Whisper文字起こし）**: 高品質で保持すべき
- **Gemini関連コード**: 完全削除可能（約2,000行）
- **Web UI化**: FastAPI + WebSocket推奨
- **Docker化**: GPU対応必須、大容量ファイル用のボリュームマウント設計が重要

---

## 2. システムアーキテクチャ分析

### 2.1 現在のパイプライン

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Download   │ → │   Extract   │ → │ Transcribe  │ → │   Report    │
│  (yt-dlp)   │    │   (ffmpeg)  │    │  (Whisper)  │    │  (Markdown) │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
      ↓                  ↓                  ↓                  ↓
   動画DL            音声抽出           文字起こし          レポート生成
   (MP4)          (16kHz WAV)         (JSON/TXT)         (MD/HTML)
                                           ↓
                                    ┌─────────────┐
                                    │   Gemini    │ ← 削除対象
                                    │  Analysis   │
                                    └─────────────┘
```

### 2.2 ProcessStep列挙型（7ステップ）

```python
class ProcessStep(Enum):
    INITIALIZE = 0      # 初期化
    DOWNLOAD = 1        # ダウンロード
    TRANSCRIBE = 2      # 文字起こし
    ANALYZE = 3         # 分析 ← Gemini依存（削除候補）
    HIERARCHICAL = 4    # 階層分析 ← Gemini依存（削除候補）
    REPORT = 5          # レポート生成
    COMPLETE = 6        # 完了
```

### 2.3 モジュール依存関係

```
video_transcript_analyzer.py (メイン)
    ├── modules/transcriber.py      [保持] Whisper統合
    ├── modules/downloader.py       [保持] yt-dlp統合
    ├── modules/resume_manager.py   [改修] コンソールメニュー→API化
    ├── modules/reporter.py         [保持] Markdown/HTML生成
    ├── modules/utils.py            [部分保持] Ollama関数削除
    │
    ├── modules/gemini_ultimate_generator.py  [削除] 全体
    ├── modules/analyzer.py                   [削除] Ollama/OpenAI依存
    ├── modules/hierarchical_analyzer.py      [削除] LangChain/LlamaIndex
    └── modules/simple_summarizer.py          [削除] Ollama依存
```

---

## 3. コア機能詳細分析

### 3.1 日本語文字起こし最適化（保持必須）

**ファイル**: `modules/transcriber.py` (490行)

```python
# 日本語最適化パラメータ（lines 241-256）
result = self.model.transcribe(
    str(audio_path),
    language="ja",
    task="transcribe",
    verbose=True,
    temperature=0.0,          # 確定的出力
    beam_size=5,              # ビームサーチ幅
    best_of=5,                # 候補数
    patience=1.0,             # デコード忍耐度
    condition_on_previous_text=False,  # 幻覚防止（重要）
    compression_ratio_threshold=2.4,
    logprob_threshold=-1.0,
    no_speech_threshold=0.6,  # 無音判定閾値
    word_timestamps=False,
    initial_prompt=None,
    suppress_tokens=[-1],
    without_timestamps=False
)
```

**重要ポイント**:
- `condition_on_previous_text=False`: 長時間音声での「幻覚」（繰り返しや架空テキスト生成）を防止
- `temperature=0.0`: 出力の一貫性確保
- `beam_size=5, best_of=5`: 品質と速度のバランス

### 3.2 大容量ファイル処理機構

**ファイル**: `modules/downloader.py` (330行)

```python
# 大容量ファイル対応設定
ydl_opts = {
    'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]/best',
    'outtmpl': str(output_path),
    'merge_output_format': 'mp4',
    'http_chunk_size': 1024 * 1024,      # 1MBチャンク
    'concurrent_fragment_downloads': 4,   # 4並列ダウンロード
    'retries': 10,
    'fragment_retries': 10,
    'continuedl': True,                   # 中断再開対応
}
```

**ファイル**: `modules/transcriber.py`

```python
# 音声抽出設定（Whisper最適形式）
ffmpeg_cmd = [
    'ffmpeg', '-i', str(video_path),
    '-vn',                    # 映像除去
    '-acodec', 'pcm_s16le',   # 16bit PCM
    '-ar', '16000',           # 16kHz（Whisper最適）
    '-ac', '1',               # モノラル
    str(audio_path)
]
```

### 3.3 レジューム・チェックポイント機能

**ファイル**: `modules/resume_manager.py` (620行)

```python
# status.json構造
{
    "project_name": "meeting_2024",
    "video_url": "https://...",
    "current_step": "TRANSCRIBE",
    "steps": {
        "DOWNLOAD": {"status": "COMPLETED", "timestamp": "..."},
        "TRANSCRIBE": {"status": "IN_PROGRESS", "timestamp": "..."},
        ...
    },
    "files": {
        "video": "output/videos/meeting.mp4",
        "audio": "output/audio/meeting.wav",
        "transcript": null
    }
}
```

### 3.4 GPU対応状況

**ファイル**: `modules/transcriber.py` (lines 83-96)

```python
# RTX 50シリーズ（Blackwell）対応チェック
def _check_rtx50_compatibility(self):
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        # RTX 5090, 5080, 5070等を検出
        if any(x in gpu_name for x in ['5090', '5080', '5070', '5060', '5050']):
            self.console.print("[yellow]RTX 50 series detected[/yellow]")
            # 互換性設定を適用
```

---

## 4. Gemini関連コード削除マッピング

### 4.1 完全削除対象ファイル（4ファイル）

| ファイル | 行数 | 説明 |
|----------|------|------|
| `modules/gemini_ultimate_generator.py` | 462行 | Geminiレポート生成 |
| `modules/analyzer.py` | 714行 | OpenAI/Ollama分析 |
| `modules/hierarchical_analyzer.py` | 582行 | LangChain階層分析 |
| `modules/simple_summarizer.py` | 507行 | Ollama要約 |

**合計**: 約2,265行削除

### 4.2 部分削除対象

**`modules/utils.py`** (lines 359-557 削除)
```python
# 削除対象関数
- check_ollama_installed()
- is_ollama_running()
- start_ollama_server()
- pull_ollama_model()
- get_ollama_models()
- unload_ollama_model()
```

**`video_transcript_analyzer.py`** (大幅改修必要)
- クラス名: `VideoTranscriptAnalyzerGeminiOnly` → `VideoTranscriptAnalyzer`
- Geminiインポート削除
- パイプラインステップ簡略化

### 4.3 設定ファイル変更

**`config.yaml`** (lines 45-70 削除)
```yaml
# 削除対象セクション
gemini:
  api_key: ${GEMINI_API_KEY}  # ← セキュリティ問題もあり
  model: gemini-2.0-flash-exp
  ...
```

**`requirements.txt`** 削除パッケージ
```
openai
tiktoken
langchain
langchain-community
llama-index
llama-index-llms-ollama
```

---

## 5. Web UI設計提案

### 5.1 フレームワーク比較

| 項目 | FastAPI | Flask |
|------|---------|-------|
| 非同期処理 | ネイティブサポート | 要拡張 |
| WebSocket | 標準サポート | Flask-SocketIO必要 |
| 大容量アップロード | ストリーミング対応 | 制限あり |
| APIドキュメント | 自動生成 | 手動 |
| **推奨度** | **★★★★★** | ★★★☆☆ |

### 5.2 推奨アーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│                        Web UI (Frontend)                     │
│                   React / Vue.js / Vanilla JS                │
└─────────────────────────────────────────────────────────────┘
                              │
                    HTTP / WebSocket
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                          │
├─────────────────────────────────────────────────────────────┤
│  POST /api/upload          - 動画/音声アップロード           │
│  POST /api/transcribe/url  - URL指定で処理開始               │
│  GET  /api/status/{job_id} - 処理状況取得                    │
│  WS   /ws/progress/{job_id} - リアルタイム進捗               │
│  GET  /api/download/{job_id} - 結果ダウンロード              │
└─────────────────────────────────────────────────────────────┘
                              │
                     Background Tasks
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   Processing Pipeline                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │ Downloader│→│ Extractor│→│Transcriber│→│ Reporter │     │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### 5.3 大容量ファイル対応設計

```python
# FastAPI大容量アップロード例
from fastapi import FastAPI, UploadFile, BackgroundTasks
from starlette.requests import Request

app = FastAPI()

@app.post("/api/upload")
async def upload_file(request: Request):
    # ストリーミング受信（メモリ効率的）
    async with aiofiles.open(temp_path, 'wb') as f:
        async for chunk in request.stream():
            await f.write(chunk)

@app.websocket("/ws/progress/{job_id}")
async def progress_websocket(websocket: WebSocket, job_id: str):
    await websocket.accept()
    while True:
        progress = get_job_progress(job_id)
        await websocket.send_json(progress)
        if progress["status"] == "completed":
            break
        await asyncio.sleep(1)
```

### 5.4 フロントエンド要件

```
必須機能:
├── URL入力フォーム（YouTube等）
├── ファイルアップロード（ドラッグ&ドロップ）
├── リアルタイム進捗バー
│   ├── ダウンロード進捗
│   ├── 音声抽出進捗
│   └── 文字起こし進捗
├── 結果プレビュー（Markdownレンダリング）
└── ダウンロードボタン（JSON/TXT/SRT/VTT）
```

---

## 6. Docker化設計提案

### 6.1 システム要件

| リソース | 最小要件 | 推奨要件 |
|----------|----------|----------|
| CPU | 4コア | 8コア |
| RAM | 8GB | 16GB |
| GPU VRAM | 4GB | 8GB+ |
| ストレージ | 50GB | 200GB+ |

### 6.2 イメージサイズ見積もり

```
ベースイメージ (Python 3.11)         ~1.0 GB
PyTorch + CUDA                       ~2.5 GB
Whisper large-v3 モデル              ~3.0 GB
FFmpeg                               ~0.1 GB
その他依存関係                       ~0.5 GB
─────────────────────────────────────────────
合計                                 ~7.1 GB
```

### 6.3 Dockerfile設計案

```dockerfile
# マルチステージビルド
FROM nvidia/cuda:12.1-cudnn8-runtime-ubuntu22.04 AS base

# 依存関係インストール
RUN apt-get update && apt-get install -y \
    python3.11 python3-pip ffmpeg git \
    && rm -rf /var/lib/apt/lists/*

# Whisperモデル事前ダウンロード
FROM base AS model-downloader
RUN pip install openai-whisper
RUN python -c "import whisper; whisper.load_model('large-v3')"

# 最終イメージ
FROM base AS production
COPY --from=model-downloader /root/.cache/whisper /root/.cache/whisper
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app
WORKDIR /app

# ボリュームマウントポイント
VOLUME ["/app/input", "/app/output"]

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 6.4 docker-compose.yml設計案

```yaml
version: '3.8'

services:
  transcriber:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./input:/app/input       # 入力ファイル
      - ./output:/app/output     # 出力ファイル
      - whisper_cache:/root/.cache/whisper  # モデルキャッシュ
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - CUDA_VISIBLE_DEVICES=0

volumes:
  whisper_cache:
```

### 6.5 大容量ファイル処理の考慮事項

```
1. ボリュームマウント戦略
   - /app/input: 入力動画用（ホストからマウント）
   - /app/output: 出力ファイル用（永続化）
   - tmpfs: 中間ファイル用（高速処理）

2. メモリ管理
   - 10GB動画 → 約2-3GBの音声ファイル生成
   - Whisper処理時: +3GB (モデル) + 2GB (処理用)
   - 推奨: 16GB RAM以上

3. GPU メモリ管理
   - large-v3モデル: 約3GB VRAM使用
   - 長時間音声: 追加1-2GB
   - 推奨: 6GB VRAM以上

4. ディスク管理
   - 中間ファイル自動削除機能の実装
   - 出力ファイルの圧縮オプション
   - 古いジョブの自動クリーンアップ
```

---

## 7. 移行ロードマップ（提案）

### Phase 1: コードクリーンアップ（推定2-3日）
```
□ Gemini関連ファイル削除（4ファイル）
□ utils.py からOllama関数削除
□ video_transcript_analyzer.py 簡略化
□ requirements.txt 整理
□ config.yaml 簡略化
□ 不要ドキュメント削除
```

### Phase 2: API層実装（推定3-5日）
```
□ FastAPI基本構造
□ アップロードエンドポイント
□ 処理開始エンドポイント
□ 進捗WebSocket
□ 結果ダウンロードエンドポイント
□ エラーハンドリング
```

### Phase 3: フロントエンド実装（推定3-5日）
```
□ 基本UI（HTML/CSS/JS）
□ ファイルアップロード機能
□ URL入力フォーム
□ リアルタイム進捗表示
□ 結果プレビュー・ダウンロード
```

### Phase 4: Docker化（推定2-3日）
```
□ Dockerfile作成
□ docker-compose.yml作成
□ GPU対応テスト
□ ボリューム設計
□ 本番環境テスト
```

### Phase 5: テスト・最適化（推定2-3日）
```
□ 大容量ファイル（10GB+）テスト
□ 長時間処理テスト
□ メモリリーク確認
□ パフォーマンス最適化
□ ドキュメント作成
```

---

## 8. リスクと対策

### 8.1 技術的リスク

| リスク | 影響度 | 対策 |
|--------|--------|------|
| Docker内GPU認識失敗 | 高 | NVIDIA Container Toolkit事前検証 |
| 大容量ファイルタイムアウト | 中 | チャンク処理、進捗通知 |
| メモリ不足 | 中 | スワップ設定、処理分割 |
| Whisperモデル読込遅延 | 低 | モデル事前ロード、キャッシュ |

### 8.2 運用リスク

| リスク | 影響度 | 対策 |
|--------|--------|------|
| ディスク容量枯渇 | 高 | 自動クリーンアップ、監視 |
| 同時処理による負荷 | 中 | ジョブキュー、同時実行制限 |
| ネットワーク切断 | 中 | レジューム機能維持 |

---

## 9. 参考：現在のファイル構成

```
VideoTranscriptAnalyzer/
├── video_transcript_analyzer.py    [改修] メインスクリプト
├── config.yaml                     [改修] 設定ファイル
├── requirements.txt                [改修] 依存関係
├── .env                            [保持] 環境変数
│
├── modules/
│   ├── transcriber.py              [保持] Whisper統合
│   ├── downloader.py               [保持] yt-dlp統合
│   ├── resume_manager.py           [改修] コンソール→API
│   ├── reporter.py                 [保持] レポート生成
│   ├── utils.py                    [改修] Ollama削除
│   ├── gemini_ultimate_generator.py [削除]
│   ├── analyzer.py                 [削除]
│   ├── hierarchical_analyzer.py    [削除]
│   └── simple_summarizer.py        [削除]
│
├── output/
│   ├── videos/                     [保持]
│   ├── audio/                      [保持]
│   ├── transcripts/                [保持]
│   └── reports/                    [保持]
│
└── (バックアップ・一時ファイル)    [削除] CLEANUP_RECOMMENDATIONS.md参照
```

---

## 10. 結論と推奨事項

### 即座に実施可能
1. **セキュリティ**: 露出したAPIキーのローテーション
2. **クリーンアップ**: バックアップファイル・不要ドキュメント削除

### 優先度高
1. **Gemini削除**: 動作不良コードの完全削除
2. **API層設計**: FastAPIによるREST/WebSocket API

### 慎重に検討
1. **Docker GPU設定**: 環境依存性が高い
2. **フロントエンド技術選定**: React/Vue/Vanillaの選択

### 保持すべき価値
- **日本語最適化パラメータ**: `condition_on_previous_text=False`等
- **大容量対応設計**: チャンク処理、レジューム機能
- **RTX 50対応**: 最新GPU互換性

---

*Report generated: 2025-12-17*
*Investigation scope: Full codebase analysis for Web UI and Docker deployment planning*
