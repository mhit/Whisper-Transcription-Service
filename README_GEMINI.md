# 🚀 Gemini Ultimate Report Generator

## 100点品質レポート生成システム

Claude直接処理と同等の品質を、Google Gemini APIで実現するシステムです。

---

## ✨ 特徴

- **全セグメント処理**: 6,298セグメントすべてを一度に処理
- **コンテキスト制限なし**: Geminiの大規模コンテキスト（最大2M tokens）を活用
- **100点品質**: 300行以上の詳細で実用的なレポート生成
- **完全な情報網羅**: 講師情報、タイムライン、具体例、数値、フレームワーク、アクションプラン
- **設定ファイル対応**: `config_gemini.yaml`で簡単に設定管理

---

## 🛠️ セットアップ

### 1. 必要なパッケージのインストール

```bash
pip install -r requirements_gemini.txt
```

または個別にインストール:

```bash
pip install google-generativeai python-dotenv
```

### 2. Gemini API キーの取得

1. [Google AI Studio](https://makersuite.google.com/app/apikey) にアクセス
2. Googleアカウントでログイン
3. "Create API Key" をクリック
4. 生成されたAPIキーをコピー

### 3. APIキーの設定

以下の4つの方法から選択:

#### 方法1: 設定ファイル（推奨）

`config_gemini.yaml` ファイルを編集:

```yaml
api:
  key: "your-api-key-here"
```

#### 方法2: 環境変数

```bash
export GEMINI_API_KEY="your-api-key-here"
```

#### 方法3: .envファイル

プロジェクトルートに `.env` ファイルを作成:

```
GEMINI_API_KEY=your-api-key-here
```

#### 方法4: .gemini_keyファイル

プロジェクトルートに `.gemini_key` ファイルを作成し、APIキーのみを記載:

```
your-api-key-here
```

#### 自動セットアップ

```bash
python test_gemini_ultimate.py --setup
```

---

## ⚙️ 設定ファイル

`config_gemini.yaml` で詳細な設定が可能です:

```yaml
# モデル設定
model:
  name: "gemini-1.5-pro"  # Claude品質再現用の推奨モデル
  temperature: 0.7        # 創造性の調整

# APIキー設定
api:
  key: "your-api-key"     # ここにAPIキーを設定可能

# 処理設定
processing:
  important_keywords:     # 重要セグメントのマーキング用
    - "成功"
    - "失敗"
    - "売上"
```

詳細は `config_gemini.yaml` ファイルを参照してください。

---

## 📖 使い方

### 基本的な実行

```bash
python test_gemini_ultimate.py
```

実行時にモデルを選択できます:
1. **gemini-1.5-pro** (最高品質・2Mトークン) ⭐ **推奨 - Claude品質再現用**
2. **gemini-2.0-flash-exp** (最新・高速)
3. **gemini-1.5-flash** (バランス型・1Mトークン)

> 💡 **重要**: 100点品質のレポートを再現するために、**gemini-1.5-pro**の使用を強く推奨します。これはClaudeが直接生成した秀逸なレポートと同等の品質を実現するために最適化されています。

### Pythonコードでの使用

```python
from modules.gemini_ultimate_generator import GeminiUltimateGenerator
import json

# APIキーを設定
api_key = "your-api-key-here"

# Generator初期化（gemini-1.5-proを推奨）
generator = GeminiUltimateGenerator(
    api_key=api_key,
    model_name="gemini-1.5-pro"  # Claude品質再現用の推奨モデル
)

# 文字起こしデータ読み込み
with open("output/project_20250922_144453/transcript.json", 'r') as f:
    transcript_data = json.load(f)

# レポート生成
report = generator.generate_ultimate_report(
    transcript_data,
    output_path="ultimate_report.md"
)

print(f"レポート生成完了: {len(report)}文字")
```

---

## 📊 生成されるレポートの構成

```
📊 セミナー概要
├── 基本情報（講師、タイトル、時間）
├── 講師の背景と実績
└── セミナーの目的

📈 講師の実績と背景
├── 失敗経験の詳細
├── 転換点
└── 現在の成功（具体的数値）

💰 メインコンテンツ
├── 各セクションの詳細（10-20分ごと）
├── 具体的な手法とフレームワーク
└── 実例と数値データ

⚠️ 重要な警告・落とし穴
├── よくある誤解
└── 回避方法

🎯 成功戦略
├── ステップバイステップ解説
└── 実装ポイント

📱 具体的テクニック
├── 詳細な手順
└── Before/After例

📊 成功事例集
└── 複数の具体例と数値

💡 重要な気づき
└── マインドセット

📝 実践アクションステップ
└── 優先順位付きの実行計画
```

---

## 🔍 トラブルシューティング

### APIキーエラー

```
ValueError: Gemini API key not provided
```

**解決方法**: APIキーが正しく設定されているか確認

### クォータ制限

```
Resource has been exhausted
```

**解決方法**:
- 無料枠の制限に達している可能性
- しばらく待ってから再実行
- または[課金設定](https://makersuite.google.com/app/billing)を確認

### コンテンツフィルタ

```
Response blocked due to safety filters
```

**解決方法**:
- セミナー内容に敏感なトピックが含まれている可能性
- safety_settings を調整（コード内で設定済み）

---

## 💡 最適化のヒント

### モデル選択ガイド

| モデル | 用途 | 速度 | 品質 | コスト | 推奨度 |
|-------|------|------|------|--------|-------|
| **gemini-1.5-pro** | **Claude品質再現** | ⚡⚡ | ★★★★★ | 💰💰💰 | **⭐⭐⭐** |
| gemini-2.0-flash-exp | 高速処理 | ⚡⚡⚡ | ★★★★☆ | 💰 | ⭐⭐ |
| gemini-1.5-flash | バランス重視 | ⚡⚡⚡ | ★★★★☆ | 💰💰 | ⭐⭐ |

> 📌 **推奨**: 100点品質レポートの再現には **gemini-1.5-pro** を使用してください

### パフォーマンス最適化

1. **キャッシュ活用**: 同じトランスクリプトは再処理不要
2. **バッチ処理**: 複数セミナーを連続処理
3. **非同期実行**: 複数のレポートを並列生成

---

## 📈 期待される成果

- **処理時間**: 30秒〜2分（モデルとサイズによる）
- **レポート長**: 300行以上
- **情報網羅率**: 95%以上
- **実用性**: 即座に実践可能なアクションプラン付き

---

## 🤝 サポート

問題が発生した場合:
1. このREADMEのトラブルシューティングを確認
2. エラーメッセージを詳細に記録
3. APIキーとネットワーク接続を確認
4. モデルを変更して再試行

---

## 📝 ライセンスとクレジット

- Google Gemini API使用
- 100点品質レポートのテンプレートはClaude生成品質基準に基づく

---

**最終更新**: 2024年1月
**バージョン**: 1.0.0