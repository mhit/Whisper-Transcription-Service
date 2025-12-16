# 📝 APIキー設定ガイド

## ✅ 実装完了内容

### APIキーをconfig.yamlに直接記述可能にしました

プライベート環境用に、APIキーをconfig.yamlに直接記述できるようになりました。
セキュリティを気にしない環境での利用を想定しています。

---

## ⚙️ 設定方法

### 1. config.yaml での設定

```yaml
# Gemini設定
gemini:
  api_key: AIzaSyBz_UzoO48NKu9mU6BOlGBohQvloxISAz0  # 直接記述可能
  model: gemini-1.5-pro  # デフォルトモデル
  default_generator: gemini  # デフォルトでGemini使用

# OpenAI設定（必要な場合）
analyzer:
  api_key: sk-xxxxxx  # OpenAI APIキー（オプション）
```

### 2. 優先順位

設定は以下の優先順位で読み込まれます（高い順）:

1. **コマンドライン引数** （最優先）
   ```bash
   python video_transcript_analyzer.py --gemini-api-key YOUR_KEY
   ```

2. **環境変数** （.envファイル または export）
   ```bash
   export GEMINI_API_KEY=YOUR_KEY
   ```

3. **config.yaml** （最低優先度）
   ```yaml
   gemini:
     api_key: YOUR_KEY
   ```

---

## 🚀 使用例

### 基本的な使用（config.yamlの設定を使用）

```bash
# config.yamlに設定済みなら、そのまま実行可能
python video_transcript_analyzer.py --input video.mp4
```

### 環境変数で上書き

```bash
# 一時的に別のモデルを使用
export GEMINI_MODEL=gemini-1.5-flash
python video_transcript_analyzer.py --input video.mp4
```

### コマンドラインで上書き

```bash
# 一時的に別のAPIキーを使用
python video_transcript_analyzer.py --input video.mp4 \
  --gemini-api-key TEMP_KEY \
  --report-type gemini
```

---

## 📊 現在の設定

### config.yaml の内容

- **Gemini API Key**: ✅ 設定済み
- **Model**: gemini-1.5-pro（最高品質）
- **Default Generator**: gemini（100点品質レポート）

### デフォルト動作

- 何も指定しなければ **Gemini Ultimate Generator** が使用されます
- **gemini-1.5-pro** モデルで100点品質レポートを生成
- APIキーは **config.yaml** から自動読み込み

---

## 🧪 設定確認方法

```bash
# 設定の優先順位と読み込み元を確認
python test_config_priority.py
```

出力例:
```
✅ Gemini設定は正常に読み込まれています
  • APIキー取得元: config.yaml
  • モデル: gemini-1.5-pro (config.yaml)
  • デフォルトエンジン: gemini (config.yaml)
```

---

## 💡 推奨設定

### プライベート環境（あなたの環境）
```yaml
# config.yaml に直接記述（簡単・便利）
gemini:
  api_key: YOUR_ACTUAL_KEY
  model: gemini-1.5-pro
```

### 共有環境
```bash
# .envファイルを使用（セキュア）
# .gitignoreに追加して共有を防ぐ
GEMINI_API_KEY=YOUR_KEY
```

### テスト環境
```bash
# コマンドライン引数で指定（柔軟）
python video_transcript_analyzer.py --gemini-api-key TEST_KEY
```

---

## ⚠️ セキュリティ注意事項

- **config.yaml** にAPIキーを記述した場合、Gitにコミットしないよう注意
- プライベートリポジトリでの使用を推奨
- 公開リポジトリの場合は **.env** ファイルを使用

---

## 📝 まとめ

1. ✅ **config.yaml** にAPIキー直接記述可能
2. ✅ **gemini-1.5-pro** がデフォルトモデル
3. ✅ 優先順位: CLI引数 > 環境変数 > config.yaml
4. ✅ プライベート環境でセキュリティを気にせず簡単設定

これで、環境変数を設定しなくても、config.yamlだけで動作するようになりました！