# VideoTranscriptAnalyzer

動画ファイルから自動で文字起こしを行い、AI分析レポートを生成するツール

## 🚀 クイックスタート

### 1. セットアップ（初回のみ）
```powershell
.\setup.ps1
```

このコマンド1つで以下が自動実行されます：
- Python仮想環境の作成
- GPU自動検出と最適化
- RTX 5070 Ti自動対応
- 全依存パッケージのインストール

### 2. 使い方
```powershell
python video_transcript_analyzer.py --input "動画ファイル.mp4"
```

## 📋 主な機能

- **動画ダウンロード**: YouTube等からの自動ダウンロード
- **音声抽出**: ffmpegによる高品質音声抽出
- **文字起こし**: OpenAI Whisper (large-v3) による高精度認識
- **AI分析**: GPT-4/Claude/Ollamaによる内容分析
- **レポート生成**: Markdown形式の詳細レポート

## 🔧 システム要件

- Windows 10/11
- Python 3.10以上
- ffmpeg（動画処理用）
- 16GB以上のRAM推奨

## 🎮 GPU対応状況

| GPU | 対応状況 | 備考 |
|-----|---------|------|
| RTX 5070 Ti/5080/5090 | ✅ | 自動でCPUモードに切り替え |
| RTX 4090/4080/4070 | ✅ | GPU高速処理 |
| RTX 3090/3080/3070 | ✅ | GPU高速処理 |
| その他NVIDIA GPU | ✅ | CUDA対応GPU |
| CPU only | ✅ | 自動検出してCPU版インストール |

## 📁 出力ファイル

処理完了後、以下のファイルが生成されます：

```
output/
├── audio/          # 抽出音声
├── segments/       # タイムスタンプ付き文字起こし
├── screenshots/    # スクリーンショット
└── reports/        # 分析レポート（Markdown）
```

## ⚙️ 設定

`config.yaml` で各種設定を変更できます：

- Whisperモデルサイズ
- AI分析モデル（GPT-4/Claude/Ollama）
- 出力形式
- 言語設定

## 🆘 トラブルシューティング

**Q: ffmpegが見つからない**
A: https://ffmpeg.org/download.html からダウンロードしてPATHに追加

**Q: メモリ不足エラー**
A: config.yamlでWhisperモデルを'base'や'small'に変更

**Q: CUDA関連エラー**
A: setup.ps1を再実行（自動で最適な設定を適用）

## 📄 ライセンス

MIT License