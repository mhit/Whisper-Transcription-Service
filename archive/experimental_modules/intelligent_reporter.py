#!/usr/bin/env python3
"""
インテリジェント構造化レポート生成モジュール
セミナー文字起こしから知的価値のある構造化レポートを生成
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import timedelta
import hashlib


class IntelligentReporter:
    """知的レポート生成クラス"""

    def __init__(self, config: Optional[Dict] = None):
        """初期化"""
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # LLM設定
        self.api_base_url = self.config.get('api_base_url', 'http://localhost:11434')
        self.model_name = self.config.get('model', 'gpt-oss:20b')
        self.temperature = self.config.get('temperature', 0.7)
        self.max_tokens = self.config.get('max_tokens', 8192)

        # レポート構造定義
        self.report_structure = {
            'executive_summary': {'weight': 0.15, 'required': True},
            'background_context': {'weight': 0.10, 'required': True},
            'main_content': {'weight': 0.40, 'required': True},
            'success_patterns': {'weight': 0.15, 'required': True},
            'failure_patterns': {'weight': 0.10, 'required': True},
            'practical_actions': {'weight': 0.10, 'required': True}
        }

    def generate_intelligent_report(self,
                                  transcript_data: Dict,
                                  analysis_data: Optional[Dict] = None) -> Dict[str, Any]:
        """知的レポートを生成"""
        self.logger.info("インテリジェントレポート生成開始")

        # データクレンジング
        cleaned_segments = self._clean_transcript_data(transcript_data)

        # コンテンツ分析
        content_analysis = self._analyze_content_structure(cleaned_segments)

        # 重要情報の抽出
        key_information = self._extract_key_information(cleaned_segments, content_analysis)

        # 構造化レポートの生成
        structured_report = self._generate_structured_report(
            cleaned_segments,
            content_analysis,
            key_information
        )

        # 品質検証
        quality_score = self._validate_report_quality(structured_report)

        self.logger.info(f"レポート生成完了 - 品質スコア: {quality_score:.1f}/100")

        return {
            'report': structured_report,
            'metadata': {
                'quality_score': quality_score,
                'content_analysis': content_analysis,
                'key_information': key_information
            }
        }

    def _clean_transcript_data(self, transcript_data: Dict) -> List[Dict]:
        """文字起こしデータをクレンジング"""
        segments = transcript_data.get('segments', [])
        cleaned = []

        # ノイズパターン定義
        noise_patterns = [
            r'^ご視聴ありがとうございました[。\.]*$',
            r'^\.+$',
            r'^はい[。\.]*$',
            r'^ありがとうございます[。\.]*$',
            r'^えー+[、,]*$',
            r'^あのー*[、,]*$'
        ]

        # 重複検出用
        last_text = None
        duplicate_count = 0
        max_duplicates = 3

        for segment in segments:
            text = segment.get('text', '').strip()

            # 空またはノイズの場合はスキップ
            if not text or len(text) < 5:
                continue

            # ノイズパターンチェック
            is_noise = any(re.match(pattern, text, re.IGNORECASE) for pattern in noise_patterns)
            if is_noise:
                continue

            # 重複チェック
            if text == last_text:
                duplicate_count += 1
                if duplicate_count >= max_duplicates:
                    continue
            else:
                duplicate_count = 0
                last_text = text

            cleaned.append(segment)

        self.logger.info(f"クレンジング完了: {len(segments)} → {len(cleaned)} セグメント")
        return cleaned

    def _analyze_content_structure(self, segments: List[Dict]) -> Dict[str, Any]:
        """コンテンツ構造を分析"""
        structure = {
            'sections': [],
            'topics': [],
            'flow_type': None,
            'presentation_style': None
        }

        # セクション境界の検出
        section_markers = [
            r'第[一二三四五六七八九十\d]+[章節部]',
            r'ステップ[1-9０-９]',
            r'その[1-9０-９]',
            r'まず|次に|最後に|そして',
            r'背景|問題|解決|結果|まとめ'
        ]

        current_section = {'start_idx': 0, 'title': 'イントロダクション', 'segments': []}

        for idx, segment in enumerate(segments):
            text = segment.get('text', '')

            # セクション開始を検出
            for pattern in section_markers:
                if re.search(pattern, text[:50]):  # 最初の50文字で判定
                    if current_section['segments']:
                        structure['sections'].append(current_section)
                    current_section = {
                        'start_idx': idx,
                        'title': self._extract_section_title(text),
                        'segments': []
                    }
                    break

            current_section['segments'].append(idx)

        # 最後のセクションを追加
        if current_section['segments']:
            structure['sections'].append(current_section)

        # トピック分析
        structure['topics'] = self._identify_topics(segments)

        # プレゼンテーションスタイルの判定
        structure['presentation_style'] = self._identify_presentation_style(segments)

        return structure

    def _extract_section_title(self, text: str) -> str:
        """セクションタイトルを抽出"""
        # 最初の句読点までを取得
        match = re.match(r'^([^。、！？\n]{1,50})', text)
        if match:
            return match.group(1).strip()
        return text[:30] + "..."

    def _identify_topics(self, segments: List[Dict]) -> List[Dict]:
        """主要トピックを識別"""
        topics = []

        # トピックキーワード群
        topic_patterns = {
            'ビジネスモデル': ['ビジネス', '収益', '売上', 'マネタイズ', '収入'],
            'マーケティング': ['マーケティング', '集客', 'SNS', 'フォロワー', '広告'],
            'セールス': ['販売', '売る', '購入', '成約', 'クロージング'],
            'コンテンツ': ['コンテンツ', '教材', '講座', 'プログラム', 'カリキュラム'],
            '成功事例': ['成功', '達成', '実績', '結果', '成果'],
            '失敗分析': ['失敗', 'ミス', '間違い', '問題', '課題']
        }

        # 各トピックの出現頻度をカウント
        for topic_name, keywords in topic_patterns.items():
            count = 0
            segments_with_topic = []

            for idx, segment in enumerate(segments):
                text = segment.get('text', '').lower()
                if any(kw in text for kw in keywords):
                    count += 1
                    segments_with_topic.append(idx)

            if count > 3:  # 3回以上出現したトピックを記録
                topics.append({
                    'name': topic_name,
                    'frequency': count,
                    'segments': segments_with_topic[:10]  # 最初の10個
                })

        # 頻度順でソート
        topics.sort(key=lambda x: x['frequency'], reverse=True)
        return topics[:5]  # 上位5トピック

    def _identify_presentation_style(self, segments: List[Dict]) -> str:
        """プレゼンテーションスタイルを判定"""
        # スタイル判定用パターン
        styles = {
            'educational': ['教える', '説明', 'ポイント', '理解', '学習'],
            'motivational': ['できる', '成功', '達成', '夢', '目標'],
            'analytical': ['分析', 'データ', '数値', '結果', '検証'],
            'narrative': ['私は', '体験', '経験', 'ストーリー', '事例']
        }

        style_scores = {style: 0 for style in styles}

        # スコア計算
        for segment in segments[:50]:  # 最初の50セグメントで判定
            text = segment.get('text', '').lower()
            for style, keywords in styles.items():
                style_scores[style] += sum(1 for kw in keywords if kw in text)

        # 最高スコアのスタイルを返す
        return max(style_scores, key=style_scores.get)

    def _extract_key_information(self,
                                segments: List[Dict],
                                content_analysis: Dict) -> Dict[str, Any]:
        """重要情報を抽出"""
        key_info = {
            'numbers': [],
            'frameworks': [],
            'success_factors': [],
            'action_items': [],
            'key_quotes': []
        }

        all_text = ' '.join([s.get('text', '') for s in segments])

        # 数値データの抽出
        number_patterns = [
            r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*([万億]?円)',
            r'(\d+(?:\.\d+)?)\s*(%|パーセント)',
            r'(\d+)\s*(人|名|社|件|個|回)',
            r'(\d+)\s*倍',
            r'月?\s*(\d+)\s*万'
        ]

        for pattern in number_patterns:
            matches = re.findall(pattern, all_text)
            for match in matches[:10]:  # 各パターン最大10個
                if isinstance(match, tuple):
                    key_info['numbers'].append(''.join(match))
                else:
                    key_info['numbers'].append(match)

        # フレームワークの抽出
        framework_patterns = [
            r'(\d+)\s*つ?の?\s*(要素|ステップ|段階|ポイント|方法)',
            r'(第[一二三四五]|ステップ\d+)[：:]\s*([^。、]{1,30})',
        ]

        for pattern in framework_patterns:
            matches = re.findall(pattern, all_text)
            for match in matches[:5]:
                if isinstance(match, tuple):
                    key_info['frameworks'].append(' '.join(match))
                else:
                    key_info['frameworks'].append(match)

        # 成功要因の抽出
        success_sentences = []
        for segment in segments:
            text = segment.get('text', '')
            if any(kw in text for kw in ['成功', '達成', '実現', '効果']):
                # 理由や要因を含む文を優先
                if any(kw in text for kw in ['ため', '理由', 'から', 'ので']):
                    success_sentences.append(text)

        key_info['success_factors'] = success_sentences[:5]

        # アクション項目の抽出
        action_patterns = [
            r'[ぜひ|必ず|まず]\s*([^。、]{10,50})[して|する|しよう]',
            r'重要なのは([^。、]{10,50})',
            r'ポイントは([^。、]{10,50})'
        ]

        for pattern in action_patterns:
            matches = re.findall(pattern, all_text)
            key_info['action_items'].extend(matches[:3])

        return key_info

    def _generate_structured_report(self,
                                   segments: List[Dict],
                                   content_analysis: Dict,
                                   key_information: Dict) -> Dict[str, str]:
        """構造化レポートを生成"""
        report = {}

        # エグゼクティブサマリー
        report['executive_summary'] = self._generate_executive_summary(
            segments, content_analysis, key_information
        )

        # 背景と実績
        report['background_context'] = self._generate_background_section(
            segments, content_analysis, key_information
        )

        # メインコンテンツ（収益化手法など）
        report['main_content'] = self._generate_main_content_section(
            segments, content_analysis, key_information
        )

        # 成功パターン
        report['success_patterns'] = self._generate_success_patterns_section(
            segments, key_information
        )

        # 失敗パターン
        report['failure_patterns'] = self._generate_failure_patterns_section(
            segments, key_information
        )

        # 実践アクション
        report['practical_actions'] = self._generate_practical_actions_section(
            segments, key_information
        )

        return report

    def _generate_executive_summary(self,
                                   segments: List[Dict],
                                   content_analysis: Dict,
                                   key_information: Dict) -> str:
        """エグゼクティブサマリーを生成"""
        try:
            # LLMを使用して生成
            prompt = self._create_executive_summary_prompt(
                segments[:20],  # 最初の20セグメント
                content_analysis,
                key_information
            )

            summary = self._call_llm(prompt)

            if summary:
                return summary

        except Exception as e:
            self.logger.warning(f"エグゼクティブサマリー生成失敗: {e}")

        # フォールバック
        summary_parts = ["## エグゼクティブサマリー\n\n"]

        # 主要トピック
        if content_analysis.get('topics'):
            topics = [t['name'] for t in content_analysis['topics'][:3]]
            summary_parts.append(f"**主要テーマ**: {', '.join(topics)}\n\n")

        # 重要数値
        if key_information.get('numbers'):
            summary_parts.append("**重要数値**:\n")
            for num in key_information['numbers'][:5]:
                summary_parts.append(f"- {num}\n")
            summary_parts.append("\n")

        # 核心メッセージ
        if key_information.get('success_factors'):
            summary_parts.append("**成功の鍵**:\n")
            for factor in key_information['success_factors'][:3]:
                if len(factor) > 100:
                    factor = factor[:100] + "..."
                summary_parts.append(f"- {factor}\n")

        return ''.join(summary_parts)

    def _create_executive_summary_prompt(self,
                                        segments: List[Dict],
                                        content_analysis: Dict,
                                        key_information: Dict) -> str:
        """エグゼクティブサマリー生成用プロンプト"""
        segment_texts = '\n'.join([s.get('text', '') for s in segments[:10]])

        prompt = f"""以下のセミナー内容から、経営者向けのエグゼクティブサマリーを生成してください。

【要件】
1. 3-5行で核心を伝える
2. 具体的な数値や成果を含める
3. 実践的な価値を明確にする
4. ビジネスインパクトを強調する

【主要トピック】
{', '.join([t['name'] for t in content_analysis.get('topics', [])[:3]])}

【重要数値】
{', '.join(key_information.get('numbers', [])[:5])}

【セミナー冒頭部分】
{segment_texts[:1500]}

【エグゼクティブサマリー】:"""

        return prompt

    def _generate_background_section(self,
                                    segments: List[Dict],
                                    content_analysis: Dict,
                                    key_information: Dict) -> str:
        """背景セクションを生成"""
        section_parts = ["## 第1部：背景と実績\n\n"]

        # 講師の実績を探す
        achievement_segments = []
        for segment in segments[:30]:  # 最初の30セグメント
            text = segment.get('text', '')
            if any(kw in text for kw in ['実績', '達成', '経験', '年間', '月間']):
                achievement_segments.append(text)

        if achievement_segments:
            section_parts.append("### 講師の実績\n\n")
            for achievement in achievement_segments[:3]:
                if len(achievement) > 150:
                    achievement = achievement[:150] + "..."
                section_parts.append(f"- {achievement}\n")
            section_parts.append("\n")

        # 市場背景
        market_segments = []
        for segment in segments:
            text = segment.get('text', '')
            if any(kw in text for kw in ['市場', '業界', 'トレンド', '現状', '問題']):
                market_segments.append(text)
                if len(market_segments) >= 3:
                    break

        if market_segments:
            section_parts.append("### 市場背景\n\n")
            section_parts.append('\n\n'.join(market_segments[:2]))
            section_parts.append("\n")

        return ''.join(section_parts)

    def _generate_main_content_section(self,
                                      segments: List[Dict],
                                      content_analysis: Dict,
                                      key_information: Dict) -> str:
        """メインコンテンツセクションを生成"""
        section_parts = ["## 第2部：核心的内容\n\n"]

        # フレームワークがあれば優先的に表示
        if key_information.get('frameworks'):
            section_parts.append("### 提示されたフレームワーク\n\n")
            for framework in key_information['frameworks'][:5]:
                section_parts.append(f"- {framework}\n")
            section_parts.append("\n")

        # 主要トピックごとにサブセクション作成
        for topic in content_analysis.get('topics', [])[:3]:
            section_parts.append(f"### {topic['name']}\n\n")

            # トピックに関連するセグメントを取得
            topic_texts = []
            for seg_idx in topic.get('segments', [])[:3]:
                if seg_idx < len(segments):
                    text = segments[seg_idx].get('text', '')
                    if len(text) > 200:
                        text = text[:200] + "..."
                    topic_texts.append(text)

            if topic_texts:
                section_parts.append('\n\n'.join(topic_texts))
                section_parts.append("\n\n")

        return ''.join(section_parts)

    def _generate_success_patterns_section(self,
                                          segments: List[Dict],
                                          key_information: Dict) -> str:
        """成功パターンセクションを生成"""
        section_parts = ["## 第3部：成功パターンと要因\n\n"]

        if key_information.get('success_factors'):
            section_parts.append("### 成功の要因\n\n")
            for i, factor in enumerate(key_information['success_factors'][:5], 1):
                section_parts.append(f"{i}. {factor}\n")
            section_parts.append("\n")

        # 成功事例を探す
        success_examples = []
        for segment in segments:
            text = segment.get('text', '')
            if any(kw in text for kw in ['成功例', '成功事例', '実例', 'ケース']):
                success_examples.append(text)
                if len(success_examples) >= 3:
                    break

        if success_examples:
            section_parts.append("### 成功事例\n\n")
            for example in success_examples[:2]:
                if len(example) > 200:
                    example = example[:200] + "..."
                section_parts.append(f"{example}\n\n")

        return ''.join(section_parts)

    def _generate_failure_patterns_section(self,
                                          segments: List[Dict],
                                          key_information: Dict) -> str:
        """失敗パターンセクションを生成"""
        section_parts = ["## 第4部：避けるべき失敗パターン\n\n"]

        # 失敗に関する言及を探す
        failure_segments = []
        for segment in segments:
            text = segment.get('text', '')
            if any(kw in text for kw in ['失敗', 'ミス', '間違い', 'ダメ', '注意']):
                failure_segments.append(text)
                if len(failure_segments) >= 5:
                    break

        if failure_segments:
            section_parts.append("### よくある失敗\n\n")
            for i, failure in enumerate(failure_segments[:3], 1):
                if len(failure) > 150:
                    failure = failure[:150] + "..."
                section_parts.append(f"{i}. {failure}\n")
            section_parts.append("\n")

        # 警告や注意点を追加
        warning_segments = []
        for segment in segments:
            text = segment.get('text', '')
            if any(kw in text for kw in ['注意', '警告', '気をつけ', '避け']):
                warning_segments.append(text)
                if len(warning_segments) >= 3:
                    break

        if warning_segments:
            section_parts.append("### 注意点\n\n")
            for warning in warning_segments[:2]:
                if len(warning) > 150:
                    warning = warning[:150] + "..."
                section_parts.append(f"- {warning}\n")

        return ''.join(section_parts)

    def _generate_practical_actions_section(self,
                                           segments: List[Dict],
                                           key_information: Dict) -> str:
        """実践アクションセクションを生成"""
        section_parts = ["## 第5部：今すぐ実践できるアクション\n\n"]

        if key_information.get('action_items'):
            section_parts.append("### 推奨アクション\n\n")
            for i, action in enumerate(key_information['action_items'][:5], 1):
                section_parts.append(f"{i}. {action}\n")
            section_parts.append("\n")

        # ステップバイステップの指示を探す
        step_segments = []
        for segment in segments:
            text = segment.get('text', '')
            if any(kw in text for kw in ['ステップ', '手順', 'まず', '次に', '最後に']):
                step_segments.append(text)
                if len(step_segments) >= 5:
                    break

        if step_segments:
            section_parts.append("### 実践ステップ\n\n")
            for i, step in enumerate(step_segments[:3], 1):
                if len(step) > 150:
                    step = step[:150] + "..."
                section_parts.append(f"**ステップ{i}**: {step}\n\n")

        # チェックリストを追加
        section_parts.append("### チェックリスト\n\n")
        checklist_items = [
            "目標と現状のギャップを明確化",
            "必要なリソースの確保",
            "実行計画の策定",
            "進捗測定指標の設定",
            "定期的な振り返りの実施"
        ]
        for item in checklist_items:
            section_parts.append(f"- [ ] {item}\n")

        return ''.join(section_parts)

    def _call_llm(self, prompt: str) -> Optional[str]:
        """LLMを呼び出して応答を取得"""
        try:
            import requests

            url = f"{self.api_base_url}/api/generate"

            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "temperature": self.temperature,
                "stream": False,
                "options": {
                    "num_predict": self.max_tokens
                }
            }

            response = requests.post(url, json=payload, timeout=30)

            if response.status_code == 200:
                result = response.json()
                return result.get('response', '').strip()

        except Exception as e:
            self.logger.warning(f"LLM呼び出し失敗: {e}")

        return None

    def _validate_report_quality(self, report: Dict[str, str]) -> float:
        """レポート品質を検証"""
        score = 0.0
        max_score = 100.0

        # 各セクションの存在チェック
        for section_name, config in self.report_structure.items():
            if section_name in report and report[section_name]:
                # セクションが存在し、内容がある
                section_score = config['weight'] * 100

                # 内容の長さチェック
                content_length = len(report[section_name])
                if content_length < 100:
                    section_score *= 0.5  # 短すぎる場合は半減
                elif content_length > 3000:
                    section_score *= 0.9  # 長すぎる場合は少し減点

                # 構造チェック（見出しがあるか）
                if '###' in report[section_name] or '##' in report[section_name]:
                    section_score *= 1.1  # 構造化ボーナス

                score += min(section_score, config['weight'] * 100)

        return min(score, max_score)

    def format_as_markdown(self, structured_report: Dict[str, str]) -> str:
        """構造化レポートをMarkdown形式にフォーマット"""
        markdown_parts = []

        # ヘッダー
        markdown_parts.append("# インテリジェント分析レポート\n\n")
        markdown_parts.append("*このレポートは知的分析により構造化されています*\n\n")
        markdown_parts.append("---\n\n")

        # 各セクションを追加
        section_order = [
            'executive_summary',
            'background_context',
            'main_content',
            'success_patterns',
            'failure_patterns',
            'practical_actions'
        ]

        for section_name in section_order:
            if section_name in structured_report:
                content = structured_report[section_name]
                if content:
                    markdown_parts.append(content)
                    markdown_parts.append("\n\n---\n\n")

        # フッター
        markdown_parts.append("\n## 付録\n\n")
        markdown_parts.append("*本レポートは自動生成されたものです。")
        markdown_parts.append("内容の正確性については元のセミナー内容をご確認ください。*\n")

        return ''.join(markdown_parts)