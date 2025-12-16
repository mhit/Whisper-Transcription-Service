#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gemini Report Generator V2 - Single Shot Generation
単一プロンプトで実際の内容を分析する改良版
"""

import os
import time
import json
import logging
from typing import Dict, Any, List
import google.generativeai as genai


class GeminiReportGeneratorV2:
    """Gemini API V2 レポート生成器"""

    def __init__(self, api_key: str = None):
        """初期化"""
        self.logger = logging.getLogger(__name__)

        # APIキーの取得
        if not api_key:
            api_key = os.getenv('GEMINI_API_KEY')

        if not api_key:
            raise ValueError("Gemini APIキーが必要です")

        # Gemini設定
        genai.configure(api_key=api_key)

        # モデル設定（Pro版を使用して品質向上）
        self.model = genai.GenerativeModel('gemini-1.5-pro')

        self.logger.info("Gemini Report Generator V2 初期化完了")

    def generate_ultimate_report(self, transcript_data: Dict, analysis_result: Any) -> str:
        """単一プロンプトで高品質レポート生成"""

        self.logger.info("単一プロンプト方式でレポート生成中...")

        # 実際のトランスクリプトテキストを抽出
        transcript_text = self._extract_full_transcript(transcript_data)

        # 深層分析結果を整理
        insights = self._prepare_deep_insights(analysis_result)

        # 単一メガプロンプトの構築
        mega_prompt = self._build_single_mega_prompt(transcript_text, insights)

        # Geminiで生成
        try:
            start_time = time.time()
            response = self.model.generate_content(
                mega_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,  # 正確性重視
                    max_output_tokens=8192,  # 長大な出力を許可
                    top_p=0.95,
                    top_k=40
                )
            )

            generation_time = time.time() - start_time
            self.logger.info(f"✓ レポート生成完了 ({generation_time:.1f}秒)")

            return response.text

        except Exception as e:
            self.logger.error(f"Gemini生成エラー: {e}")
            raise

    def _extract_full_transcript(self, transcript_data: Dict) -> str:
        """実際のトランスクリプトテキストを抽出"""

        segments = transcript_data.get('segments', [])

        # 全セグメントから重要部分を抽出（最大500セグメント）
        important_segments = []

        # キーワードベースで重要セグメントを選別
        keywords = ['億', '売上', '成長', '成功', '失敗', '戦略', '顧客', 'マーケティング',
                   '方法', '重要', 'ポイント', '注意', '結果', '実績', '事例', '具体的']

        for seg in segments[:500]:
            text = seg.get('text', '').strip()
            if text and (any(kw in text for kw in keywords) or len(important_segments) < 100):
                important_segments.append(text)

        # 最大10000文字まで
        full_text = " ".join(important_segments)
        if len(full_text) > 10000:
            full_text = full_text[:10000]

        return full_text

    def _prepare_deep_insights(self, analysis_result: Any) -> Dict:
        """深層分析結果を詳細に整理"""

        insights = {
            'key_concepts': [],
            'frameworks': [],
            'success_patterns': [],
            'failure_patterns': [],
            'numerical_insights': [],
            'action_items': [],
            'psychological_mechanisms': []
        }

        # 実際のコンテンツを含めて抽出
        if hasattr(analysis_result, 'key_concepts'):
            for concept, score in list(analysis_result.key_concepts.items())[:20]:
                insights['key_concepts'].append({
                    'concept': concept,
                    'score': score
                })

        if hasattr(analysis_result, 'frameworks'):
            for fw in analysis_result.frameworks[:10]:
                insights['frameworks'].append({
                    'name': fw.get('name', ''),
                    'context': fw.get('context', ''),
                    'application': fw.get('application', '')
                })

        if hasattr(analysis_result, 'numerical_insights'):
            for num in analysis_result.numerical_insights[:20]:
                insights['numerical_insights'].append({
                    'value': num.get('value', ''),
                    'context': num.get('context', ''),
                    'significance': num.get('significance', '')
                })

        if hasattr(analysis_result, 'action_items'):
            for action in analysis_result.action_items[:15]:
                insights['action_items'].append({
                    'action': action.get('action', ''),
                    'priority': action.get('priority', ''),
                    'expected_outcome': action.get('expected_outcome', '')
                })

        return insights

    def _build_single_mega_prompt(self, transcript_text: str, insights: Dict) -> str:
        """単一の包括的プロンプトを構築"""

        # 実際の概念とフレームワークを文字列化
        concepts_detail = "\n".join([
            f"- {c['concept']}: スコア{c['score']:.1f}"
            for c in insights['key_concepts'][:15]
        ])

        frameworks_detail = "\n".join([
            f"- {fw['name']}: {fw['context'][:100]}"
            for fw in insights['frameworks'][:10]
        ])

        numbers_detail = "\n".join([
            f"- {n['value']}: {n['context']}"
            for n in insights['numerical_insights'][:10]
        ])

        actions_detail = "\n".join([
            f"- {a['action']}"
            for a in insights['action_items'][:10]
        ])

        prompt = f"""あなたは世界最高レベルのビジネスアナリストです。
以下の実際のセミナー文字起こしと分析データから、極めて具体的で実用的なレポートを作成してください。

# 実際のセミナー内容（文字起こし）
===============================
{transcript_text}
===============================

# 深層分析で抽出された実際のデータ

## 重要概念（実際に抽出されたもの）
{concepts_detail}

## 検出されたフレームワーク（実際のもの）
{frameworks_detail}

## 数値データ（実際に言及されたもの）
{numbers_detail}

## アクション項目（実際に推奨されたもの）
{actions_detail}

# 厳格なレポート要件

**重要：** 必ず上記の「実際のセミナー内容」と「深層分析データ」に基づいて、具体的な内容を記載すること。
架空の数値や企業名（A社、B社など）は使用禁止。実際にセミナーで言及された内容のみを使用。

以下の構成で、品質スコア95点以上のレポートを生成：

## 1. エグゼクティブサマリー
- セミナーで実際に語られた最重要ポイント3つ
- 実際に言及された数値やデータ
- 講師が強調した具体的なアクション

## 2. 戦略的洞察
- セミナーで提示された成功パターン
- 実際に議論された失敗事例とその教訓
- 講師が推奨した具体的戦略

## 3. 実践フレームワーク
- セミナーで紹介された実際の方法論
- ステップバイステップの実装ガイド
- 成功基準とKPI

## 4. アクションプラン
- 即実行可能な具体的行動（24時間以内）
- 週次・月次の実行計画
- 長期ビジョン（3-6ヶ月）

## 5. 心理学的洞察
- セミナーで語られた心理メカニズム
- 顧客心理の活用法
- 組織心理の最適化

## 6. 成功への道筋
- 具体的な成功指標
- リスクと対策
- サポート体制

**出力形式：**
- Markdown形式
- 各セクションに具体例を含める
- 数値は実際のものを使用
- 実践可能な内容に焦点

**品質基準：**
- データの正確性（セミナー内容に忠実）
- 知的価値の深さ
- 実践可能性
- 論理的構造
- 説得力

さあ、実際のセミナー内容に基づいた究極のレポートを生成してください。"""

        return prompt


if __name__ == "__main__":
    # テスト実行
    import sys
    from pathlib import Path

    # プロジェクトルートをパスに追加
    sys.path.append(str(Path(__file__).parent.parent))

    # テスト用のダミーデータ
    test_transcript = {
        'segments': [
            {'text': 'このセミナーでは売上を1億円達成する方法を説明します'},
            {'text': '重要なのは顧客満足度を高めることです'},
            {'text': '成功事例として、3ヶ月で売上が2倍になった企業があります'}
        ]
    }

    # 簡易テスト
    from types import SimpleNamespace
    test_analysis = SimpleNamespace(
        key_concepts={'売上向上': 0.95, '顧客満足': 0.85},
        frameworks=[{'name': 'PDCAサイクル', 'context': '継続的改善'}],
        numerical_insights=[{'value': '1億円', 'context': '目標売上'}],
        action_items=[{'action': '顧客アンケート実施', 'priority': '高'}]
    )

    # API キー設定
    api_key = os.getenv('GEMINI_API_KEY')
    if api_key:
        generator = GeminiReportGeneratorV2(api_key)
        print("Gemini Report Generator V2 Ready")
    else:
        print("APIキーが設定されていません")