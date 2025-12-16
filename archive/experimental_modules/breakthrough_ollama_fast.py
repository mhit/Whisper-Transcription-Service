#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Breakthrough Ollama Fast - 軽量高速版
タイムアウトを回避しつつ95点突破を実現
"""

import json
import logging
import time
import requests
from typing import Dict, List, Any, Tuple
from pathlib import Path
import numpy as np

from .breakthrough_synthesizer import (
    BreakthroughTextSynthesizer,
    ContentCharacteristicsVector,
    QualityMetrics
)


class BreakthroughOllamaFast:
    """高速軽量版 Breakthrough Generator"""

    def __init__(self, config: Dict[str, Any] = None):
        """初期化"""
        self.logger = logging.getLogger(__name__)

        # デフォルト設定（高速化重視）
        default_config = {
            'api_base_url': 'http://192.168.43.245:11434',
            'fast_models': ['gpt-oss:20b', 'qwen3:30b'],  # 高速モデル優先
            'quality_model': 'qwen2.5:32b',  # 品質用（オプション）
            'timeout': 120,  # 短めのタイムアウト
            'use_fast_mode': True
        }

        self.config = {**default_config, **(config or {})}

        # Breakthrough Synthesizer初期化
        self.synthesizer = BreakthroughTextSynthesizer()

        # モデル選択
        self.current_model = self._select_fast_model()

        # 高速化設定
        self.fast_options = {
            'num_ctx': 4096,          # コンテキスト削減
            'num_predict': 2048,       # 出力長制限
            'temperature': 0.3,
            'top_p': 0.90,
            'top_k': 30,
            'num_batch': 512,
            'num_gpu': 99,
            'repeat_penalty': 1.05
        }

        self.logger.info(f"Fast Breakthrough Generator initialized: {self.current_model}")

    def _select_fast_model(self) -> str:
        """高速モデルを選択"""
        try:
            response = requests.get(f"{self.config['api_base_url']}/api/tags", timeout=3)
            if response.status_code == 200:
                available = [m['name'] for m in response.json().get('models', [])]

                for model in self.config['fast_models']:
                    if model in available:
                        self.logger.info(f"Fast model selected: {model}")
                        return model

                # qwen2.5があれば品質モードとして使用
                if self.config['quality_model'] in available:
                    self.logger.info(f"Using quality model: {self.config['quality_model']}")
                    return self.config['quality_model']

        except Exception as e:
            self.logger.error(f"Model selection error: {e}")

        return 'gpt-oss:20b'  # デフォルト

    def generate_fast_breakthrough_report(
        self, transcript_data: Dict, analysis_result: Any
    ) -> str:
        """高速版Breakthroughレポート生成"""

        self.logger.info("Starting FAST Breakthrough Generation")
        start_time = time.time()

        # 1. 簡易前処理（高速化）
        content = self._fast_preprocess(transcript_data)

        # 2. コンテンツ特性の高速分析
        ccv = self._fast_content_analysis(content)
        self.logger.info(f"Fast analysis: density={ccv.information_density:.2f}")

        # 3. 戦略決定（簡略版）
        strategy = self._fast_strategy(ccv)

        # 4. 統合コンテンツ準備
        enriched = self._fast_integrate(content, analysis_result)

        # 5. 単一候補生成（パレート最適化スキップ）
        if self.config['use_fast_mode']:
            report = self._generate_single_optimized(enriched, strategy)
        else:
            # 3候補のみ生成（27→3に削減）
            report = self._generate_minimal_candidates(enriched, strategy)

        # 6. 簡易改善（1回のみ）
        if ccv.information_density > 0.5:  # 高密度の場合のみ
            report = self._fast_refinement(report)

        # 7. 最終フォーマット
        final_report = self._fast_format(report, ccv)

        generation_time = time.time() - start_time
        self.logger.info(f"Fast report generated in {generation_time:.1f} seconds")

        return final_report

    def _fast_preprocess(self, transcript_data: Dict) -> str:
        """高速前処理"""
        segments = transcript_data.get('segments', [])[:200]  # 最初の200セグメントのみ

        # キーワードスコアリング（簡易版）
        keywords = ['億', '売上', '成功', '戦略', '重要']
        important = []

        for seg in segments:
            text = seg.get('text', '').strip()
            if text and any(kw in text for kw in keywords):
                important.append(text)

        return " ".join(important[:100])  # 最大100セグメント

    def _fast_content_analysis(self, content: str) -> ContentCharacteristicsVector:
        """高速コンテンツ分析（5次元のみ）"""
        ccv = ContentCharacteristicsVector()

        # 主要5次元のみ計算
        words = content.split()
        ccv.information_density = min(len(set(words)) / max(len(words), 1), 1.0)
        ccv.numerical_density = len([w for w in words if any(c.isdigit() for c in w)]) / max(len(words), 1)
        ccv.actionability_potential = sum(1 for kw in ['実施', '実行', '適用'] if kw in content) / 10
        ccv.synthesis_readiness = 0.7  # 固定値
        ccv.technical_complexity = 0.5  # 固定値

        return ccv

    def _fast_strategy(self, ccv: ContentCharacteristicsVector) -> Dict[str, Any]:
        """高速戦略決定"""
        return {
            'mode': 'fast_synthesis',
            'quality_targets': {
                'accuracy': 0.90,
                'completeness': 0.85,
                'clarity': 0.90,
                'actionability': 0.85
            },
            'extraction_focus': 'key_insights'
        }

    def _fast_integrate(self, content: str, analysis_result: Any) -> str:
        """高速データ統合"""
        parts = [content]

        # 最重要データのみ追加
        if hasattr(analysis_result, 'key_concepts'):
            top_concepts = list(analysis_result.key_concepts.items())[:10]
            parts.append("キーコンセプト: " + ", ".join([c[0] for c in top_concepts]))

        return "\n".join(parts)

    def _generate_single_optimized(self, content: str, strategy: Dict[str, Any]) -> str:
        """単一最適化レポート生成"""
        prompt = f"""高速かつ高品質なビジネスレポートを生成してください。

【コンテンツ】
{content[:2000]}

【要件】
1. エグゼクティブサマリー（3つの核心）
2. 戦略的分析（SWOT簡易版）
3. アクションプラン（即実行3項目）

簡潔かつ洞察的なレポートを生成してください。"""

        return self._call_ollama_fast(prompt)

    def _generate_minimal_candidates(self, content: str, strategy: Dict[str, Any]) -> str:
        """最小候補生成（3つのみ）"""
        prompts = [
            self._create_analytical_fast,
            self._create_practical_fast,
            self._create_strategic_fast
        ]

        best_report = ""
        best_score = 0

        for prompt_fn in prompts[:2]:  # 2候補のみでさらに高速化
            prompt = prompt_fn(content)
            report = self._call_ollama_fast(prompt)

            if report:
                # 簡易スコアリング
                score = self._fast_score(report)
                if score > best_score:
                    best_score = score
                    best_report = report

        return best_report

    def _create_analytical_fast(self, content: str) -> str:
        """高速分析プロンプト"""
        return f"""分析レポート生成（高速版）:

{content[:1500]}

必須要素：
- 3つの核心洞察
- データ根拠
- 実践への示唆

簡潔に生成してください。"""

    def _create_practical_fast(self, content: str) -> str:
        """高速実用プロンプト"""
        return f"""実践レポート生成:

{content[:1500]}

重点：
- 即実行アクション
- 期待効果
- リスクと対策

実用的に生成してください。"""

    def _create_strategic_fast(self, content: str) -> str:
        """高速戦略プロンプト"""
        return f"""戦略レポート生成:

{content[:1500]}

焦点：
- 競争優位
- 成長機会
- 長期ビジョン

戦略的に生成してください。"""

    def _call_ollama_fast(self, prompt: str) -> str:
        """高速Ollama呼び出し"""
        try:
            payload = {
                'model': self.current_model,
                'prompt': prompt,
                'options': self.fast_options,
                'stream': False
            }

            response = requests.post(
                f"{self.config['api_base_url']}/api/generate",
                json=payload,
                timeout=self.config['timeout']
            )

            if response.status_code == 200:
                return response.json().get('response', '')

        except requests.Timeout:
            self.logger.warning(f"Timeout with {self.current_model}, trying faster model")
            # より高速なモデルにフォールバック
            if self.current_model != 'gpt-oss:20b':
                self.current_model = 'gpt-oss:20b'
                return self._call_ollama_fast(prompt)

        except Exception as e:
            self.logger.error(f"Ollama error: {e}")

        return ""

    def _fast_score(self, report: str) -> float:
        """高速スコアリング"""
        score = 0.5  # ベーススコア

        # 簡易評価
        if '戦略' in report: score += 0.1
        if 'アクション' in report: score += 0.1
        if '分析' in report: score += 0.1
        if len(report) > 1000: score += 0.1
        if len(report) > 2000: score += 0.1

        return min(score, 1.0)

    def _fast_refinement(self, report: str) -> str:
        """高速改善（1パスのみ）"""
        # 基本的な改善のみ
        if len(report) < 500:
            # 短すぎる場合は拡張要求
            prompt = f"以下のレポートを拡充してください:\n{report}\n\n詳細を追加:"
            additional = self._call_ollama_fast(prompt)
            if additional:
                report += "\n\n" + additional

        return report

    def _fast_format(self, report: str, ccv: ContentCharacteristicsVector) -> str:
        """高速フォーマット"""
        return f"""# 【Fast Breakthrough】高速品質分析レポート

**生成時刻**: {time.strftime('%H:%M:%S')}
**エンジン**: Fast Breakthrough ({self.current_model})
**処理モード**: 高速最適化

---

## 分析指標
- 情報密度: {ccv.information_density:.1%}
- 数値密度: {ccv.numerical_density:.1%}
- 実行可能性: {ccv.actionability_potential:.1%}

---

{report}

---

*Fast Breakthrough Generator - Speed & Quality Optimized*
"""


class HybridBreakthroughGenerator:
    """ハイブリッド版：高速処理＋品質改善"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.fast_gen = BreakthroughOllamaFast()

    def generate_hybrid_report(
        self, transcript_data: Dict, analysis_result: Any
    ) -> str:
        """2段階生成：高速ドラフト→品質改善"""

        self.logger.info("Starting Hybrid Generation")

        # Phase 1: 高速ドラフト生成（gpt-oss）
        self.logger.info("Phase 1: Fast draft generation")
        draft = self.fast_gen.generate_fast_breakthrough_report(
            transcript_data, analysis_result
        )

        # Phase 2: 品質改善（可能ならqwen2.5）
        if self._check_quality_model_available():
            self.logger.info("Phase 2: Quality enhancement")
            draft = self._enhance_with_quality_model(draft)

        return draft

    def _check_quality_model_available(self) -> bool:
        """品質モデルの利用可否確認"""
        try:
            response = requests.get(
                "http://192.168.43.245:11434/api/tags",
                timeout=2
            )
            if response.status_code == 200:
                models = [m['name'] for m in response.json().get('models', [])]
                return 'qwen2.5:32b' in models
        except:
            pass
        return False

    def _enhance_with_quality_model(self, draft: str) -> str:
        """品質モデルによる改善"""
        prompt = f"""以下のドラフトレポートを改善して95点品質にしてください:

{draft[:3000]}

改善点:
- データの具体性向上
- 論理構造の強化
- 実用価値の追加

改善版レポート:"""

        try:
            payload = {
                'model': 'qwen2.5:32b',
                'prompt': prompt,
                'options': {
                    'num_ctx': 4096,
                    'num_predict': 3000,
                    'temperature': 0.2
                },
                'stream': False
            }

            response = requests.post(
                "http://192.168.43.245:11434/api/generate",
                json=payload,
                timeout=180
            )

            if response.status_code == 200:
                enhanced = response.json().get('response', '')
                if enhanced:
                    return enhanced

        except Exception as e:
            self.logger.warning(f"Quality enhancement failed: {e}")

        return draft  # フォールバック


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # 高速版テスト
    fast_gen = BreakthroughOllamaFast()
    print("Fast Breakthrough Generator ready!")

    # ハイブリッド版テスト
    hybrid_gen = HybridBreakthroughGenerator()
    print("Hybrid Breakthrough Generator ready!")