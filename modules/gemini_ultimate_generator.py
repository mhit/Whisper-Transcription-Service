#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gemini Ultimate Report Generator - 100点品質レポート生成
Claude直接処理と同等の品質を、Geminiの大規模コンテキストで実現
"""

import os
import json
import logging
import time
import yaml
from typing import Dict, List, Any, Optional
from pathlib import Path
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold


class GeminiUltimateGenerator:
    """
    Gemini APIを使用した究極品質レポート生成器

    特徴:
    - 全セグメント処理（6,298セグメント対応）
    - 100点品質の詳細レポート生成
    - 具体例、数値、フレームワークの完全抽出
    - 実践可能なアクションプラン
    """

    def __init__(self, api_key: str = None, model_name: str = "gemini-1.5-pro"):
        """
        初期化

        Args:
            api_key: Gemini API キー
            model_name: 使用モデル ("gemini-2.0-flash-exp", "gemini-1.5-pro", etc.)
        """
        self.logger = logging.getLogger(__name__)

        # APIキー設定
        if api_key:
            self.api_key = api_key
        else:
            self.api_key = os.getenv("GEMINI_API_KEY")

        if not self.api_key:
            raise ValueError(
                "Gemini API key not provided. "
                "Set GEMINI_API_KEY environment variable or pass api_key parameter."
            )

        # Gemini設定
        genai.configure(api_key=self.api_key)

        # モデル選択
        self.model_name = model_name
        self.logger.info(f"Initializing Gemini Ultimate Generator with {model_name}")

        # モデル設定
        self.generation_config = {
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 32000,  # 大量出力対応
        }

        # 安全設定（コンテンツフィルタを緩和）
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }

        # モデル初期化
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config=self.generation_config,
            safety_settings=self.safety_settings
        )

    def generate_ultimate_report(
        self,
        transcript_data: Dict,
        output_path: Optional[str] = None
    ) -> str:
        """
        100点品質のレポート生成

        Args:
            transcript_data: 文字起こしデータ（全セグメント含む）
            output_path: 出力ファイルパス（オプション）

        Returns:
            生成されたレポート（Markdown形式）
        """
        self.logger.info("Starting Ultimate Report Generation with Gemini")
        start_time = time.time()

        # 1. 全セグメントの準備（サンプリングなし！）
        full_transcript = self._prepare_full_transcript(transcript_data)
        self.logger.info(f"Prepared {len(full_transcript)} characters of transcript")

        # 2. 包括的プロンプトの作成
        prompt = self._create_comprehensive_prompt(full_transcript)

        # 3. Gemini APIで生成
        try:
            self.logger.info("Calling Gemini API...")
            response = self.model.generate_content(prompt)

            if response.text:
                report = response.text
                self.logger.info(f"Generated report with {len(report)} characters")
            else:
                self.logger.error("No response from Gemini")
                report = self._create_error_report()

        except Exception as e:
            self.logger.error(f"Gemini API error: {e}")
            report = self._create_error_report(str(e))

        # 4. レポート保存
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report)
            self.logger.info(f"Report saved to {output_path}")

        generation_time = time.time() - start_time
        self.logger.info(f"Ultimate report generated in {generation_time:.1f} seconds")

        return report

    def _prepare_full_transcript(self, transcript_data: Dict) -> str:
        """
        全セグメントを統合（制限なし）
        """
        segments = transcript_data.get('segments', [])

        # タイムスタンプ付きで全セグメントを整形
        transcript_lines = []

        for i, segment in enumerate(segments):
            text = segment.get('text', '').strip()
            if text:  # 空でないセグメントのみ
                # タイムスタンプがあれば追加
                start = segment.get('start', 0)
                minutes = int(start / 60)
                seconds = int(start % 60)

                # 重要度の高いセグメントにマーク
                importance_keywords = [
                    '重要', '成功', '失敗', '売上', '利益', '戦略',
                    'ポイント', '結論', '理由', '方法', '秘訣', '注意'
                ]

                is_important = any(kw in text for kw in importance_keywords)
                marker = "★" if is_important else ""

                transcript_lines.append(
                    f"[{minutes:02d}:{seconds:02d}] {marker} {text}"
                )

        # 統計情報の追加
        total_segments = len(segments)
        total_duration = segments[-1].get('end', 0) if segments else 0
        duration_min = int(total_duration / 60)

        header = f"""===== TRANSCRIPT INFORMATION =====
Total Segments: {total_segments}
Duration: {duration_min} minutes
Important Segments Marked with ★
===================================

"""

        return header + "\n".join(transcript_lines)

    def _create_comprehensive_prompt(self, full_transcript: str) -> str:
        """
        100点品質を生成するための包括的プロンプト
        """
        return f"""あなたは世界最高レベルのビジネスアナリスト兼テクニカルライターです。
以下のセミナー/講演の完全な文字起こしから、究極品質の総合レポートを作成してください。

【重要】このレポートは、実際にセミナーに参加できなかった人が、
このレポートだけで完全に内容を理解し、実践できるレベルの品質が求められます。

# 文字起こし全文
================
{full_transcript}
================

# レポート作成要件

## 1. 必須セクション（すべて含めること）

### 📊 セミナー概要
- 基本情報（講師名、所属、実績、タイトル、時間、参加者情報など）
- 講師の詳細な背景と信頼性の根拠
- セミナーの明確な目的とゴール

### 📈 講師の実績と背景（タイムライン形式）
- 過去の失敗経験（具体的なエピソード）
- 転換点となった出来事
- 現在の成功（具体的な数値）
- 実現したライフスタイル

### 💰 メインコンテンツ（各セクション10-20分）
- 各セクションごとに詳細に記述
- 具体的な手法、フレームワーク、ステップ
- 実例と数値データ
- 計算式やシミュレーション（```で囲んだコードブロック使用）

### ⚠️ 重要な警告・落とし穴
- よくある誤解と真実
- 失敗パターンの詳細
- 回避方法

### 🎯 成功のための戦略・フレームワーク
- ステップバイステップの説明
- 各ステップの詳細と例
- 実装のポイント

### 🔑 核となる要素・原則
- 成功の鍵となる要素の詳細解説
- 具体例での説明（例：パン屋の例など、記憶に残る比喩）
- 実際の適用方法

### 📱 具体的なテクニック・実装方法
- 詳細な手順
- テンプレートや構成例
- Before/Afterの例

### 📊 成功事例集
- 複数の具体的な成功事例
- 多様なジャンルでの適用例
- 具体的な数値と成果

### 💡 重要な気づきとマインドセット
- 番号付きリストで整理
- 各ポイントの詳細説明
- 誤解と正解の対比

### 🎬 セミナーの特徴
- 提供された価値
- 参加者への約束
- 最終メッセージ

### 📝 実践へのアクションステップ
- 優先順位付きのステップ
- 各ステップの具体的な内容
- タイムラインと期待成果

## 2. フォーマット要件

- **見出し**: #, ##, ### を適切に使用した階層構造
- **強調**: 重要部分は **太字** で強調
- **リスト**: 箇条書きと番号付きリストを適切に使用
- **引用**: > を使用して重要な発言を引用
- **コードブロック**: 計算式やシミュレーションは ``` で囲む
- **テーブル**: 比較や数値データは表形式で
- **絵文字**: セクション見出しに適切な絵文字を使用
- **区切り線**: --- でセクションを明確に区切る

## 3. 内容の品質基準

- **具体性**: 抽象的な表現を避け、具体的な数値、名称、例を使用
- **完全性**: セミナーの最初から最後まですべての重要情報を網羅
- **実用性**: 読者がすぐに実践できる具体的なステップ
- **記憶に残る**: 印象的な例、比喩、ストーリーを含める
- **論理的**: 明確な構造と流れで、理解しやすく構成

## 4. 分量目標

- 全体で **300行以上** の詳細なレポート
- 各主要セクションは最低20-30行
- 具体例や数値を豊富に含める

## 5. 最終チェック項目

✅ 講師の人物像が明確に伝わるか
✅ セミナーの核心的価値が理解できるか
✅ 具体的な手法・フレームワークが実践可能なレベルで説明されているか
✅ 成功事例と失敗事例の両方が含まれているか
✅ 読者が明日から実行できるアクションが明確か

---

上記の要件をすべて満たした、究極品質のレポートを生成してください。
セミナーに参加していない人でも、このレポートだけで完全に内容を理解し、
実践できるレベルの詳細さと具体性を持たせてください。"""

    def _create_error_report(self, error_msg: str = "") -> str:
        """
        エラー時のフォールバックレポート
        """
        timestamp = time.strftime('%Y年%m月%d日 %H:%M')

        return f"""# レポート生成エラー

**生成日時**: {timestamp}
**エラー内容**: {error_msg if error_msg else "不明なエラー"}

---

## エラーが発生しました

Gemini APIでのレポート生成中にエラーが発生しました。

### 考えられる原因

1. **APIキーの問題**: GEMINI_API_KEY が正しく設定されていない
2. **クォータ制限**: API使用量の制限に達している
3. **ネットワーク**: インターネット接続の問題
4. **コンテンツサイズ**: 入力が大きすぎる可能性

### 対処方法

1. APIキーを確認してください
2. しばらく待ってから再実行してください
3. ネットワーク接続を確認してください
4. gemini-1.5-flash モデルを試してください

---

*Gemini Ultimate Generator - Error Report*"""

    def estimate_tokens(self, text: str) -> int:
        """
        テキストのトークン数を推定

        Args:
            text: 入力テキスト

        Returns:
            推定トークン数
        """
        # 日本語の場合、おおよそ1文字=1トークンで推定
        # 英語の場合、おおよそ4文字=1トークン
        japanese_chars = len([c for c in text if ord(c) > 127])
        english_chars = len(text) - japanese_chars

        estimated_tokens = japanese_chars + (english_chars / 4)
        return int(estimated_tokens)

    def check_context_limit(self, transcript_data: Dict) -> bool:
        """
        コンテキスト制限のチェック

        Args:
            transcript_data: 文字起こしデータ

        Returns:
            処理可能かどうか
        """
        full_transcript = self._prepare_full_transcript(transcript_data)
        estimated_tokens = self.estimate_tokens(full_transcript)

        # Gemini 1.5 Proは最大2Mトークン、1.5 Flashは1Mトークン
        if "flash" in self.model_name.lower():
            max_tokens = 1_000_000
        else:
            max_tokens = 2_000_000

        # プロンプトとレスポンス分のマージンを確保（50,000トークン）
        safe_limit = max_tokens - 50_000

        if estimated_tokens > safe_limit:
            self.logger.warning(
                f"Estimated {estimated_tokens} tokens exceeds safe limit {safe_limit}"
            )
            return False

        self.logger.info(
            f"Estimated {estimated_tokens} tokens within limit {safe_limit}"
        )
        return True


# ユーティリティ関数
def load_api_key_from_file(key_file_path: str = ".gemini_key") -> Optional[str]:
    """
    ファイルからAPIキーを読み込む

    Args:
        key_file_path: APIキーファイルのパス

    Returns:
        APIキー文字列、またはNone
    """
    key_path = Path(key_file_path)
    if key_path.exists():
        with open(key_path, 'r') as f:
            return f.read().strip()
    return None


def load_config(config_path: str = "config_gemini.yaml") -> Dict[str, Any]:
    """
    設定ファイルを読み込む

    Args:
        config_path: 設定ファイルのパス

    Returns:
        設定辞書
    """
    config_file = Path(config_path)

    # デフォルト設定
    default_config = {
        'api': {'key': ''},
        'model': {
            'name': 'gemini-1.5-pro',
            'temperature': 0.7,
            'top_p': 0.95,
            'top_k': 40,
            'max_output_tokens': 32000
        },
        'safety': {
            'harassment': 'BLOCK_NONE',
            'hate_speech': 'BLOCK_NONE',
            'sexually_explicit': 'BLOCK_NONE',
            'dangerous_content': 'BLOCK_NONE'
        }
    }

    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f)
                # デフォルト設定とマージ
                for key, value in user_config.items():
                    if key in default_config and isinstance(value, dict):
                        default_config[key].update(value)
                    else:
                        default_config[key] = value
        except Exception as e:
            logging.warning(f"設定ファイル読み込みエラー: {e}")

    return default_config


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 70)
    print("Gemini Ultimate Report Generator")
    print("100点品質のレポート生成システム")
    print("=" * 70)
    print()
    print("使用方法:")
    print("1. GEMINI_API_KEY 環境変数を設定")
    print("2. または .gemini_key ファイルにAPIキーを保存")
    print("3. test_gemini_ultimate.py を実行")
    print()
    print("対応モデル:")
    print("- gemini-2.0-flash-exp (最新、高速)")
    print("- gemini-1.5-pro (最高品質、2Mトークン)")
    print("- gemini-1.5-flash (高速、1Mトークン)")
    print("=" * 70)