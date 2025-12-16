#!/usr/bin/env python3
"""
強化版レポート生成モジュール
SimpleSummarizerの良い点とIntelligentReporterの構造化を統合
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import hashlib


class EnhancedReporter:
    """強化版レポート生成クラス"""

    def __init__(self, config: Optional[Dict] = None):
        """初期化"""
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # LLM設定
        self.api_base_url = self.config.get('api_base_url', 'http://localhost:11434')
        self.model_name = self.config.get('model', 'gpt-oss:20b')
        self.temperature = self.config.get('temperature', 0.3)  # より決定的な出力のため低めに
        self.max_tokens = self.config.get('max_tokens', 8192)

    def generate_enhanced_report(self,
                                transcript_data: Dict,
                                existing_summaries: Optional[Dict] = None) -> str:
        """強化版レポートを生成"""
        self.logger.info("強化版レポート生成開始")

        # データ準備
        segments = transcript_data.get('segments', [])

        # データクレンジング
        cleaned_segments = self._deep_clean_segments(segments)

        # セミナー全体のコンテキストを理解
        seminar_context = self._analyze_seminar_context(cleaned_segments)

        # 各セクションを生成
        report_sections = []

        # 1. エグゼクティブサマリー
        executive_summary = self._generate_executive_summary_with_llm(
            cleaned_segments, seminar_context, existing_summaries
        )
        report_sections.append(executive_summary)

        # 2. 背景と実績
        background = self._generate_background_with_llm(
            cleaned_segments, seminar_context
        )
        report_sections.append(background)

        # 3. 核心的内容（収益化手法）
        main_content = self._generate_main_content_with_llm(
            cleaned_segments, seminar_context
        )
        report_sections.append(main_content)

        # 4. 成功と失敗の分析
        success_failure = self._generate_success_failure_analysis_with_llm(
            cleaned_segments, seminar_context
        )
        report_sections.append(success_failure)

        # 5. 実践ロードマップ
        roadmap = self._generate_roadmap_with_llm(
            cleaned_segments, seminar_context
        )
        report_sections.append(roadmap)

        # レポート統合
        final_report = self._integrate_report_sections(report_sections, seminar_context)

        self.logger.info("強化版レポート生成完了")
        return final_report

    def _deep_clean_segments(self, segments: List[Dict]) -> List[Dict]:
        """徹底的なデータクレンジング"""
        cleaned = []

        # ノイズパターンを拡張
        noise_patterns = [
            r'^ご視聴ありがとうございました[。\.]*$',
            r'^\.{2,}$',
            r'^はい[。\.]*$',
            r'^ありがとうございます[。\.]*$',
            r'^えー+[、,]*$',
            r'^あの[ー]*[、,]*$',
            r'^その[ー]*[、,]*$',
            r'^まあ[、,]*$',
            r'^ちょっと[、,]*$',
            r'^[、。！？\s]+$'
        ]

        # 連続重複の検出
        seen_texts = []
        duplicate_threshold = 0.9  # 90%以上一致したら重複とみなす

        for segment in segments:
            text = segment.get('text', '').strip()

            # 基本フィルタ
            if not text or len(text) < 10:
                continue

            # ノイズチェック
            is_noise = any(re.match(pattern, text, re.IGNORECASE) for pattern in noise_patterns)
            if is_noise:
                continue

            # 重複チェック（類似度ベース）
            is_duplicate = False
            for seen in seen_texts[-5:]:  # 直近5個と比較
                similarity = self._calculate_similarity(text, seen)
                if similarity > duplicate_threshold:
                    is_duplicate = True
                    break

            if not is_duplicate:
                cleaned.append(segment)
                seen_texts.append(text)

        self.logger.info(f"データクレンジング: {len(segments)} → {len(cleaned)} セグメント")
        return cleaned

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """テキスト類似度を計算"""
        if not text1 or not text2:
            return 0.0

        # 簡易的な文字ベース類似度
        set1 = set(text1.lower().split())
        set2 = set(text2.lower().split())

        if not set1 and not set2:
            return 1.0
        if not set1 or not set2:
            return 0.0

        intersection = set1 & set2
        union = set1 | set2

        return len(intersection) / len(union)

    def _analyze_seminar_context(self, segments: List[Dict]) -> Dict[str, Any]:
        """セミナー全体のコンテキストを分析"""
        context = {
            'main_topic': None,
            'speaker_name': None,
            'target_audience': None,
            'key_numbers': [],
            'frameworks': [],
            'success_stories': [],
            'teaching_points': [],
            'total_duration': 0
        }

        # 全テキストを結合
        full_text = ' '.join([s.get('text', '') for s in segments])

        # 主題の推定（最頻出キーワードから）
        topic_keywords = {
            'インスタグラム': 0,
            'マーケティング': 0,
            'コンテンツ': 0,
            '収益化': 0,
            'ビジネス': 0,
            'フォロワー': 0,
            '売上': 0,
            '教材': 0
        }

        for keyword in topic_keywords:
            topic_keywords[keyword] = full_text.count(keyword)

        # 最頻出3つを主題とする
        sorted_topics = sorted(topic_keywords.items(), key=lambda x: x[1], reverse=True)
        context['main_topic'] = ', '.join([t[0] for t in sorted_topics[:3] if t[1] > 5])

        # 重要な数値を抽出
        number_patterns = [
            r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*([万億]?円)',
            r'月?\s*(\d+)\s*万',
            r'(\d+)\s*フォロワー',
            r'(\d+(?:\.\d+)?)\s*(%|パーセント)',
        ]

        for pattern in number_patterns:
            matches = re.findall(pattern, full_text)
            for match in matches[:20]:
                if isinstance(match, tuple):
                    context['key_numbers'].append(''.join(match))
                else:
                    context['key_numbers'].append(match)

        # フレームワークを抽出
        framework_patterns = [
            r'(\d+)\s*つの\s*(要素|ステップ|ポイント|方法)',
            r'(ステップ\d+)[：:]\s*([^。、\n]{5,50})',
            r'(第[一二三四五])[：:]\s*([^。、\n]{5,50})',
        ]

        for pattern in framework_patterns:
            matches = re.findall(pattern, full_text)
            for match in matches[:10]:
                if isinstance(match, tuple):
                    context['frameworks'].append(' '.join(match))

        # 成功事例を探す
        success_patterns = [
            r'([^。]*(?:達成|成功|実現)[^。]*)',
            r'([^。]*\d+[万億]円[^。]*)',
            r'([^。]*\d+フォロワー[^。]*)'
        ]

        for pattern in success_patterns:
            matches = re.findall(pattern, full_text)
            for match in matches[:10]:
                if len(match) > 20 and len(match) < 200:
                    context['success_stories'].append(match)

        # 総時間を計算
        if segments:
            last_segment = segments[-1]
            context['total_duration'] = last_segment.get('end', 0)

        return context

    def _generate_executive_summary_with_llm(self,
                                            segments: List[Dict],
                                            context: Dict,
                                            existing_summaries: Optional[Dict]) -> str:
        """LLMを使ってエグゼクティブサマリーを生成"""

        # 既存のサマリーがあれば活用
        existing_text = ""
        if existing_summaries and 'executive_summary' in existing_summaries:
            existing_text = existing_summaries['executive_summary']

        # 重要セグメントを選択
        important_segments = self._select_important_segments(segments, 20)
        segment_texts = '\n'.join([s.get('text', '') for s in important_segments])

        prompt = f"""あなたはビジネスセミナーの内容を分析する専門家です。
以下のセミナー内容から、経営者・ビジネスパーソン向けのエグゼクティブサマリーを作成してください。

【セミナー情報】
主題: {context.get('main_topic', 'ビジネス成長戦略')}
重要数値: {', '.join(context.get('key_numbers', [])[:10])}
成功事例数: {len(context.get('success_stories', []))}

【セミナー内容（重要部分）】
{segment_texts[:3000]}

【要求事項】
1. 3つの核心的洞察を箇条書きで（各100文字程度）
2. 最も重要な数値成果を2-3個含める
3. このセミナーから得られる実践的価値を明確にする
4. ビジネスへの即効性のあるインパクトを強調

【出力形式】
# エグゼクティブサマリー

## 核心的洞察
1. [洞察1]
2. [洞察2]
3. [洞察3]

## 重要な成果指標
- [数値成果1]
- [数値成果2]

## ビジネスインパクト
[実践的価値とROIの説明]

エグゼクティブサマリー:"""

        # LLM呼び出し
        summary = self._call_llm_with_retry(prompt)

        if not summary:
            # フォールバック
            summary = self._create_fallback_executive_summary(context)

        return summary

    def _generate_background_with_llm(self, segments: List[Dict], context: Dict) -> str:
        """背景と実績セクションを生成"""

        # 冒頭のセグメントから講師情報を抽出
        intro_segments = segments[:15]
        intro_text = '\n'.join([s.get('text', '') for s in intro_segments])

        # 実績に関連するセグメントを探す
        achievement_segments = []
        for segment in segments[:50]:
            text = segment.get('text', '')
            if any(kw in text for kw in ['実績', '達成', '経験', '成果', '月収', '売上']):
                achievement_segments.append(text)
                if len(achievement_segments) >= 5:
                    break

        prompt = f"""セミナー講師の背景と実績を整理してください。

【講師情報（推定）】
{intro_text[:1000]}

【実績関連の発言】
{chr(10).join(achievement_segments[:5])}

【重要数値】
{', '.join(context.get('key_numbers', [])[:10])}

【要求事項】
1. 講師の専門分野と経験年数（推定可）
2. 具体的な実績（数値付き）を3-5個
3. なぜこの講師から学ぶ価値があるのか

【出力形式】
## 第1部：背景と実績

### 講師プロフィール
[専門分野と経験]

### 主要実績
- [実績1: 具体的数値付き]
- [実績2: 具体的数値付き]
- [実績3: 具体的数値付き]

### このセミナーの価値
[なぜ聞く価値があるのか]

背景と実績:"""

        result = self._call_llm_with_retry(prompt)

        if not result:
            result = self._create_fallback_background(achievement_segments, context)

        return result

    def _generate_main_content_with_llm(self, segments: List[Dict], context: Dict) -> str:
        """核心的内容セクションを生成"""

        # 中盤の重要セグメントを選択
        middle_start = len(segments) // 4
        middle_end = (len(segments) * 3) // 4
        middle_segments = segments[middle_start:middle_end]

        # 手法・メソッドに関連するセグメントを抽出
        method_segments = []
        for segment in middle_segments:
            text = segment.get('text', '')
            if any(kw in text for kw in ['方法', 'やり方', 'ステップ', '手順', 'ポイント', 'コツ']):
                method_segments.append(text)
                if len(method_segments) >= 10:
                    break

        prompt = f"""セミナーの核心的な内容（収益化手法・成功メソッド）を整理してください。

【フレームワーク】
{chr(10).join(context.get('frameworks', [])[:5])}

【手法・メソッドの説明】
{chr(10).join(method_segments[:7])}

【成功事例】
{chr(10).join(context.get('success_stories', [])[:3])}

【要求事項】
1. 提示された主要な手法・メソッドを体系的に整理
2. 各手法の具体的なステップや実践方法
3. 期待される成果や効果
4. 実例を交えた説明

【出力形式】
## 第2部：収益化メソッドと実践手法

### 提示された主要メソッド

#### メソッド1: [メソッド名]
**概要**: [簡潔な説明]
**実践ステップ**:
1. [ステップ1]
2. [ステップ2]
3. [ステップ3]
**期待成果**: [具体的な成果]

#### メソッド2: [メソッド名]
[同様の構造]

### 成功の方程式
[全体を通じた成功パターンの要約]

収益化メソッド:"""

        result = self._call_llm_with_retry(prompt)

        if not result:
            result = self._create_fallback_main_content(method_segments, context)

        return result

    def _generate_success_failure_analysis_with_llm(self, segments: List[Dict], context: Dict) -> str:
        """成功と失敗の分析セクションを生成"""

        # 成功・失敗に関するセグメントを収集
        success_segments = []
        failure_segments = []

        for segment in segments:
            text = segment.get('text', '')
            if any(kw in text for kw in ['成功', '達成', '実現', 'うまく']):
                success_segments.append(text)
            if any(kw in text for kw in ['失敗', 'ミス', '間違い', 'ダメ', 'うまくいかない']):
                failure_segments.append(text)

        prompt = f"""成功パターンと失敗パターンを分析してください。

【成功に関する言及】
{chr(10).join(success_segments[:5])}

【失敗に関する言及】
{chr(10).join(failure_segments[:5])}

【成功事例】
{chr(10).join(context.get('success_stories', [])[:3])}

【要求事項】
1. 成功する人の共通パターン（3-5個）
2. 失敗する人の共通パターン（3-5個）
3. 成功と失敗の分岐点
4. 失敗から成功への転換方法

【出力形式】
## 第3部：成功と失敗の分岐点

### 成功パターン
**成功する人の特徴**:
1. [特徴1]
2. [特徴2]
3. [特徴3]

### 失敗パターン
**よくある失敗の原因**:
1. [原因1]
2. [原因2]
3. [原因3]

### 成功への転換ポイント
[失敗を避け、成功に導く重要ポイント]

成功と失敗の分析:"""

        result = self._call_llm_with_retry(prompt)

        if not result:
            result = self._create_fallback_success_failure(success_segments, failure_segments)

        return result

    def _generate_roadmap_with_llm(self, segments: List[Dict], context: Dict) -> str:
        """実践ロードマップセクションを生成"""

        # アクション・実践に関するセグメントを収集
        action_segments = []
        for segment in segments:
            text = segment.get('text', '')
            if any(kw in text for kw in ['実践', 'やる', '始める', 'スタート', '今すぐ', 'まず']):
                action_segments.append(text)
                if len(action_segments) >= 10:
                    break

        prompt = f"""実践的なロードマップを作成してください。

【実践に関する指示】
{chr(10).join(action_segments[:7])}

【提示されたフレームワーク】
{chr(10).join(context.get('frameworks', [])[:3])}

【要求事項】
1. 今すぐできる3つのアクション
2. 1週間以内に実施すべきこと
3. 1ヶ月での目標設定
4. 成果測定方法
5. 継続のためのチェックリスト

【出力形式】
## 第4部：実践ロードマップ

### 今すぐ実践できる3つのアクション
1. **[アクション1]**
   - 具体的な実施内容
   - 期待される効果

2. **[アクション2]**
   - 具体的な実施内容
   - 期待される効果

3. **[アクション3]**
   - 具体的な実施内容
   - 期待される効果

### 1週間プラン
- Day 1-2: [タスク]
- Day 3-4: [タスク]
- Day 5-7: [タスク]

### 1ヶ月目標
- [ ] [目標1]
- [ ] [目標2]
- [ ] [目標3]

### 成果測定指標
- [指標1]: [測定方法]
- [指標2]: [測定方法]

実践ロードマップ:"""

        result = self._call_llm_with_retry(prompt)

        if not result:
            result = self._create_fallback_roadmap(action_segments)

        return result

    def _select_important_segments(self, segments: List[Dict], count: int) -> List[Dict]:
        """重要なセグメントを選択"""
        # 簡易的な重要度スコアリング
        scored_segments = []

        important_keywords = [
            '成功', '失敗', '重要', 'ポイント', '結論', '方法',
            '万円', 'フォロワー', '達成', '実現', 'ステップ',
            'なぜ', 'どのように', '理由', '秘訣', 'コツ'
        ]

        for segment in segments:
            text = segment.get('text', '')
            score = 0

            # キーワードスコア
            for keyword in important_keywords:
                score += text.count(keyword) * 10

            # 長さスコア（適度な長さが良い）
            text_len = len(text)
            if 50 <= text_len <= 300:
                score += 5
            elif text_len > 300:
                score += 3

            # 数値を含む場合ボーナス
            if re.search(r'\d+', text):
                score += 15

            scored_segments.append((segment, score))

        # スコア順でソート
        scored_segments.sort(key=lambda x: x[1], reverse=True)

        # 上位N個を返す
        return [seg for seg, score in scored_segments[:count]]

    def _call_llm_with_retry(self, prompt: str, max_retries: int = 2) -> Optional[str]:
        """LLMを呼び出し（リトライ付き）"""
        import requests
        import time

        for attempt in range(max_retries):
            try:
                url = f"{self.api_base_url}/api/generate"

                payload = {
                    "model": self.model_name,
                    "prompt": prompt,
                    "temperature": self.temperature,
                    "stream": False,
                    "options": {
                        "num_predict": self.max_tokens,
                        "top_k": 40,
                        "top_p": 0.9
                    }
                }

                response = requests.post(url, json=payload, timeout=60)

                if response.status_code == 200:
                    result = response.json()
                    generated_text = result.get('response', '').strip()

                    if generated_text and len(generated_text) > 50:
                        return generated_text
                    else:
                        self.logger.warning(f"LLM returned short response: {len(generated_text)} chars")
                else:
                    self.logger.warning(f"LLM API error: {response.status_code}")

            except Exception as e:
                self.logger.warning(f"LLM call failed (attempt {attempt + 1}): {e}")

            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff

        return None

    def _create_fallback_executive_summary(self, context: Dict) -> str:
        """フォールバックエグゼクティブサマリー"""
        summary_parts = ["# エグゼクティブサマリー\n\n"]

        summary_parts.append("## 核心的洞察\n")

        # 主題から洞察を生成
        if context.get('main_topic'):
            summary_parts.append(f"1. {context['main_topic']}における実践的手法を体系化\n")
        else:
            summary_parts.append("1. ビジネス成長のための実践的手法を体系化\n")

        # 数値から洞察を生成
        if context.get('key_numbers'):
            top_numbers = context['key_numbers'][:3]
            summary_parts.append(f"2. 具体的な成果実績: {', '.join(top_numbers)}\n")
        else:
            summary_parts.append("2. 数値に基づく成果重視のアプローチ\n")

        # 成功事例から洞察
        if context.get('success_stories'):
            summary_parts.append(f"3. {len(context['success_stories'])}件の成功事例から導き出された再現可能なパターン\n")
        else:
            summary_parts.append("3. 実践者の成功パターンから学ぶ成長戦略\n")

        summary_parts.append("\n## ビジネスインパクト\n")
        summary_parts.append("本セミナーの内容を実践することで、具体的な成果につながる")
        summary_parts.append("実践的なフレームワークと手法を即座に導入可能\n")

        return ''.join(summary_parts)

    def _create_fallback_background(self, achievement_segments: List[str], context: Dict) -> str:
        """フォールバック背景セクション"""
        parts = ["## 第1部：背景と実績\n\n"]

        if achievement_segments:
            parts.append("### 実績\n")
            for i, achievement in enumerate(achievement_segments[:3], 1):
                if len(achievement) > 150:
                    achievement = achievement[:150] + "..."
                parts.append(f"{i}. {achievement}\n")
            parts.append("\n")

        if context.get('key_numbers'):
            parts.append("### 重要指標\n")
            for num in context['key_numbers'][:5]:
                parts.append(f"- {num}\n")

        return ''.join(parts)

    def _create_fallback_main_content(self, method_segments: List[str], context: Dict) -> str:
        """フォールバックメインコンテンツ"""
        parts = ["## 第2部：収益化メソッドと実践手法\n\n"]

        if context.get('frameworks'):
            parts.append("### 提示されたフレームワーク\n")
            for framework in context['frameworks'][:5]:
                parts.append(f"- {framework}\n")
            parts.append("\n")

        if method_segments:
            parts.append("### 実践手法\n")
            for i, method in enumerate(method_segments[:3], 1):
                if len(method) > 200:
                    method = method[:200] + "..."
                parts.append(f"{i}. {method}\n\n")

        return ''.join(parts)

    def _create_fallback_success_failure(self, success_segments: List[str], failure_segments: List[str]) -> str:
        """フォールバック成功失敗分析"""
        parts = ["## 第3部：成功と失敗の分岐点\n\n"]

        if success_segments:
            parts.append("### 成功パターン\n")
            for i, success in enumerate(success_segments[:3], 1):
                if len(success) > 150:
                    success = success[:150] + "..."
                parts.append(f"{i}. {success}\n")
            parts.append("\n")

        if failure_segments:
            parts.append("### 失敗パターン\n")
            for i, failure in enumerate(failure_segments[:3], 1):
                if len(failure) > 150:
                    failure = failure[:150] + "..."
                parts.append(f"{i}. {failure}\n")

        return ''.join(parts)

    def _create_fallback_roadmap(self, action_segments: List[str]) -> str:
        """フォールバック実践ロードマップ"""
        parts = ["## 第4部：実践ロードマップ\n\n"]

        parts.append("### 今すぐ実践できるアクション\n")

        if action_segments:
            for i, action in enumerate(action_segments[:3], 1):
                if len(action) > 100:
                    action = action[:100] + "..."
                parts.append(f"{i}. {action}\n")
        else:
            parts.append("1. 現状分析と目標設定\n")
            parts.append("2. 必要リソースの確保\n")
            parts.append("3. 実行計画の策定\n")

        parts.append("\n### チェックリスト\n")
        parts.append("- [ ] 目標の明確化\n")
        parts.append("- [ ] 実行計画の作成\n")
        parts.append("- [ ] 進捗測定方法の設定\n")
        parts.append("- [ ] 定期的な振り返り\n")

        return ''.join(parts)

    def _integrate_report_sections(self, sections: List[str], context: Dict) -> str:
        """レポートセクションを統合"""
        report_parts = []

        # ヘッダー
        report_parts.append("# セミナー分析レポート - インテリジェント版\n\n")

        if context.get('main_topic'):
            report_parts.append(f"**主題**: {context['main_topic']}\n\n")

        report_parts.append("---\n\n")

        # 各セクションを追加
        for section in sections:
            if section:
                report_parts.append(section)
                report_parts.append("\n\n---\n\n")

        # 付録
        report_parts.append("## 付録\n\n")

        # 重要数値一覧
        if context.get('key_numbers'):
            report_parts.append("### 重要数値一覧\n")
            for num in context['key_numbers'][:20]:
                report_parts.append(f"- {num}\n")
            report_parts.append("\n")

        # 成功事例一覧
        if context.get('success_stories'):
            report_parts.append("### 成功事例\n")
            for i, story in enumerate(context['success_stories'][:5], 1):
                if len(story) > 150:
                    story = story[:150] + "..."
                report_parts.append(f"{i}. {story}\n")
            report_parts.append("\n")

        # フッター
        report_parts.append("\n---\n\n")
        report_parts.append("*このレポートはAIによる知的分析に基づいて生成されています。")
        report_parts.append("セミナーの全内容を網羅したものではありません。*\n")

        return ''.join(report_parts)