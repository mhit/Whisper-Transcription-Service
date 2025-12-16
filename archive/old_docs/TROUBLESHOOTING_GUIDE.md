# トラブルシューティングガイド

## 🔍 診断された問題と解決方法

### 問題1: LangChainの非推奨警告
**症状:**
```
LangChainDeprecationWarning: The class `Ollama` was deprecated in LangChain 0.3.1
```

**原因:** LangChain 0.3.1以降で`Ollama`クラスが非推奨になった

**解決方法:**
```bash
# Windows (venv使用)
.\venv\Scripts\pip.exe install -U langchain-ollama

# 修正後のインポート（modules/hierarchical_analyzer.py）
from langchain_ollama import OllamaLLM
```

※ 現時点では警告のみで動作に影響はないため、後日対応でも問題ありません。

---

### 問題2: セグメント数が0になる
**症状:**
```
サンプルセグメント数: 0
セグメント数: 0
```

**原因:** JSONファイルの最初の8分（480秒）が無音セグメントのため、5分のサンプルでは有効なデータが取得できない

**解決方法:** ✅ 修正済み
- サンプル抽出ロジックを修正（最初の有効セグメントから計算）
- デフォルトのテストモードを10分に変更

---

## 🚀 修正後の実行方法

### 1. simple_test_hierarchical.py（テストデータ使用）
```bash
python simple_test_hierarchical.py
```
✅ **結果:** 正常動作（テストデータで要約生成成功）

### 2. test_hierarchical_with_real_json.py（実際のJSONファイル使用）
```bash
python test_hierarchical_with_real_json.py
```
✅ **修正内容:**
- 最初の10分を使用（無音部分をスキップ）
- 有効セグメントのみを処理

---

## 📊 動作確認のポイント

### 成功の兆候:
- ✅ セグメント数が1以上
- ✅ Level 1, 2, 3の要約が生成される
- ✅ 処理時間が表示される
- ✅ 圧縮率が0%以上

### 失敗の兆候:
- ❌ セグメント数が0
- ❌ "段階的な要約の内容が表示されていない"というメッセージ
- ❌ 総セグメント: 0

---

## 🛠️ その他の注意点

1. **Ollamaサーバーの確認**
   ```bash
   ollama serve  # 別ターミナルで実行
   ```

2. **モデルの確認**
   ```bash
   ollama list  # gpt-oss:20bがあることを確認
   ```

3. **メモリ使用量**
   - 初回は遅い（モデルロード）
   - GPUメモリ12GB以上推奨

---

## 📝 テスト結果の見方

**正常な出力例:**
```
📊 セグメント情報:
   総セグメント数: 2502
   有効セグメント数: 2485  ← ✅ 0以上
   無音セグメント数: 17

🎯 10分のサンプルでテスト実行
   サンプルセグメント数: 35  ← ✅ 0以上

📍 Level 1（詳細要約）:
   要約数: 5  ← ✅ 生成されている

📍 Level 2（中間要約）:
   要約数: 2  ← ✅ 生成されている

📍 Level 3（最終要約）:
   [実際の要約内容]  ← ✅ 内容がある
```