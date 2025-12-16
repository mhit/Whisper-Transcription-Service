# 🚀 Gemini専用モードへの移行ガイド

## 📋 現在の問題

1. **config.yamlが複雑すぎる**: Ollama、OpenAI、Geminiの設定が混在
2. **Ollamaが優先される**: AI分析でOllamaを使おうとしてしまう
3. **不要なコードが残っている**: ローカルLLM関連のコードが大量に残存

## 🎯 解決策

### 方法1: 簡単な設定変更（現在のconfig.yamlを修正）

現在のconfig.yamlで以下の箇所を変更：

```yaml
# AI分析設定を無効化（104行目〜）
analyzer:
  enabled: false  # ← この行を追加して無効化

# シンプル要約を無効化（46行目〜）
simple_summarization:
  use_simple: false  # ← falseに変更

# 階層的要約を無効化（89行目〜）
hierarchical_summarization:
  enabled: false  # ← 既にfalseになっているはず

# Geminiセクション（147行目〜）はそのまま
gemini:
  enabled: true  # ← 確認
  api_key: AIzaSyBz_UzoO48NKu9mU6BOlGBohQvloxISAz0
  model: gemini-1.5-pro
  default_generator: gemini  # ← 確認
```

### 方法2: クリーンな設定ファイルを使用（推奨）

新しく作成した`config_gemini_only.yaml`を使用：

```bash
# バックアップを取る
cp config.yaml config_backup.yaml

# Gemini専用設定に切り替え
cp config_gemini_only.yaml config.yaml

# 実行
python video_transcript_analyzer.py --input video.mp4 --report-type gemini
```

## 📊 設定の違い

### 削除された設定（不要になったもの）

| セクション | 内容 | 理由 |
|-----------|------|------|
| `analyzer` | OpenAI/Ollama API設定 | Geminiで代替 |
| `simple_summarization` | ローカルLLM要約 | Geminiで代替 |
| `hierarchical_summarization` | LangChain/LlamaIndex | Geminiで代替 |
| `ollama_fallback` | Ollamaフォールバック | 不要 |

### 残された設定（必要なもの）

| セクション | 内容 | 用途 |
|-----------|------|------|
| `transcriber` | Whisper設定 | 文字起こし |
| `gemini` | Gemini API設定 | 全ての分析・要約 |
| `reporter` | レポート出力設定 | レポート生成 |
| `downloader` | 動画ダウンロード | 動画取得 |

## 🔧 コマンドラインオプション

### Gemini専用モードで実行

```bash
# 基本実行（Geminiが自動的に使われる）
python video_transcript_analyzer.py --input video.mp4

# 明示的にGeminiを指定
python video_transcript_analyzer.py --input video.mp4 --report-type gemini

# 高品質レポート生成
python video_transcript_analyzer.py --input video.mp4 \
  --report-type gemini \
  --output output/gemini_report
```

## 🎨 処理フローの変更

### Before（複雑なフロー）
```
動画 → Whisper → [Ollama/OpenAI/階層的/シンプル] → レポート
                    ↑
                  どれを使うか不明確
```

### After（シンプルなフロー）
```
動画 → Whisper → Gemini → 高品質レポート
                   ↑
                 全て統一
```

## ✅ メリット

1. **設定がシンプル**: 1つのAPIキーだけ管理
2. **品質が安定**: 常に100点品質のGeminiレポート
3. **処理が高速**: ローカルLLMの起動待ちなし
4. **メモリ効率**: ローカルモデルのロード不要
5. **一貫性**: 全ての処理が同じエンジン

## 🚨 注意事項

1. **APIコスト**: Geminiは有料API（ただし無料枠あり）
2. **ネットワーク必須**: インターネット接続が必要
3. **レート制限**: 大量処理時は制限に注意

## 📝 移行チェックリスト

- [ ] config.yamlをバックアップ
- [ ] config_gemini_only.yamlをconfig.yamlにコピー
- [ ] Gemini APIキーが設定されているか確認
- [ ] `--report-type gemini`オプションを使用
- [ ] 不要なローカルLLMモデルを削除（オプション）

## 🔍 動作確認

```bash
# 設定確認
python test_config_priority.py

# 期待される出力
✅ Gemini設定は正常に読み込まれています
  • APIキー取得元: config.yaml
  • モデル: gemini-1.5-pro
  • デフォルトエンジン: gemini

# テスト実行
python test_gemini_ultimate.py
```

## 💡 トラブルシューティング

### まだOllamaを使おうとする場合

1. config.yamlの`analyzer`セクション全体をコメントアウト：
```yaml
# analyzer:
#   api_base_url: http://localhost:11434/v1
#   ...
```

2. または`enabled: false`を追加：
```yaml
analyzer:
  enabled: false
```

### Geminiが使われない場合

コマンドラインで明示的に指定：
```bash
python video_transcript_analyzer.py --input video.mp4 \
  --report-type gemini \
  --gemini-api-key YOUR_KEY
```

## 🎯 結論

`config_gemini_only.yaml`を使用することで、全ての処理がGeminiに統一され、設定も大幅にシンプルになります。ローカルLLMの複雑な設定やメモリ消費を気にする必要がなくなり、常に高品質なレポートが生成されます。

---
*作成日: 2025年9月23日*