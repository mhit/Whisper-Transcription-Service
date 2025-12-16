#!/usr/bin/env python3
"""
深層トランスクリプト分析システム
LLMの性能制限を補完する高度な前処理・分析モジュール
"""

import json
import re
import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from collections import Counter, defaultdict
from datetime import timedelta
import numpy as np
from dataclasses import dataclass


@dataclass
class AnalysisResult:
    """分析結果を格納するデータクラス"""
    key_concepts: Dict[str, float]  # 概念と重要度スコア
    frameworks: List[Dict[str, Any]]  # 抽出されたフレームワーク
    success_patterns: List[Dict[str, Any]]  # 成功パターン
    failure_patterns: List[Dict[str, Any]]  # 失敗パターン
    psychological_mechanisms: List[Dict[str, Any]]  # 心理メカニズム
    action_items: List[Dict[str, Any]]  # 実践項目
    numerical_insights: List[Dict[str, Any]]  # 数値的洞察
    speaker_emphasis: List[Dict[str, Any]]  # 講師の強調ポイント
    story_arc: Dict[str, Any]  # ストーリー構造
    personas: Dict[str, List[Dict]]  # ペルソナ別分析


class DeepTranscriptAnalyzer:
    """深層トランスクリプト分析クラス"""

    def __init__(self):
        """初期化"""
        self.logger = logging.getLogger(__name__)

        # 重要キーワード辞書
        self.importance_keywords = {
            'critical': ['重要', '絶対', '必ず', '最も', '核心', 'ポイント', '鍵'],
            'success': ['成功', '達成', '実現', '獲得', '到達', '突破', '勝つ'],
            'failure': ['失敗', 'ミス', '間違い', 'ダメ', '落とし穴', '注意', '避ける'],
            'method': ['方法', 'やり方', '手法', 'ステップ', 'フレームワーク', 'システム'],
            'money': ['円', '売上', '収益', '利益', '収入', 'コスト', '投資'],
            'psychology': ['心理', '感情', '動機', '欲求', 'ニーズ', '行動', '判断'],
            'action': ['実践', '実行', '始める', 'やる', '取り組む', '導入']
        }

        # 感情強度辞書
        self.emotion_markers = {
            'strong_positive': ['素晴らしい', '最高', '完璧', '圧倒的', '驚異的'],
            'positive': ['良い', '効果的', '有効', 'うまく', '成果'],
            'negative': ['悪い', '問題', '課題', '困難', '厳しい'],
            'strong_negative': ['最悪', '絶対ダメ', '致命的', '破滅', '崩壊']
        }

    def analyze_transcript(self, transcript_data: Dict) -> AnalysisResult:
        """トランスクリプトを深層分析"""
        self.logger.info("深層トランスクリプト分析開始")

        segments = transcript_data.get('segments', [])

        # 1. セグメントの前処理と注釈付け
        annotated_segments = self._annotate_segments(segments)

        # 2. キーコンセプトの抽出
        key_concepts = self._extract_key_concepts(annotated_segments)

        # 3. フレームワークの検出
        frameworks = self._detect_frameworks(annotated_segments)

        # 4. 成功・失敗パターンの抽出
        success_patterns = self._extract_success_patterns(annotated_segments)
        failure_patterns = self._extract_failure_patterns(annotated_segments)

        # 5. 心理メカニズムの分析
        psychological_mechanisms = self._analyze_psychological_mechanisms(annotated_segments)

        # 6. アクション項目の抽出
        action_items = self._extract_action_items(annotated_segments)

        # 7. 数値的洞察の抽出
        numerical_insights = self._extract_numerical_insights(annotated_segments)

        # 8. 講師の強調ポイントの検出
        speaker_emphasis = self._detect_speaker_emphasis(annotated_segments)

        # 9. ストーリーアークの分析
        story_arc = self._analyze_story_arc(annotated_segments)

        # 10. ペルソナ別の分析
        personas = self._analyze_by_persona(annotated_segments)

        result = AnalysisResult(
            key_concepts=key_concepts,
            frameworks=frameworks,
            success_patterns=success_patterns,
            failure_patterns=failure_patterns,
            psychological_mechanisms=psychological_mechanisms,
            action_items=action_items,
            numerical_insights=numerical_insights,
            speaker_emphasis=speaker_emphasis,
            story_arc=story_arc,
            personas=personas
        )

        self.logger.info(f"深層分析完了: {len(key_concepts)}個のキーコンセプト、{len(frameworks)}個のフレームワーク検出")
        return result

    def _annotate_segments(self, segments: List[Dict]) -> List[Dict]:
        """セグメントに注釈を付ける"""
        annotated = []

        for i, segment in enumerate(segments):
            text = segment.get('text', '')

            # 重要度スコア計算
            importance_score = self._calculate_importance_score(text)

            # 感情強度計算
            emotion_score = self._calculate_emotion_score(text)

            # トピック分類
            topic = self._classify_topic(text)

            # セグメントタイプ（説明、例示、強調、質問など）
            segment_type = self._classify_segment_type(text)

            # 数値情報の抽出
            numbers = self._extract_numbers(text)

            annotated_segment = {
                **segment,
                'index': i,
                'importance_score': importance_score,
                'emotion_score': emotion_score,
                'topic': topic,
                'segment_type': segment_type,
                'numbers': numbers,
                'word_count': len(text.split()),
                'has_emphasis': self._has_emphasis(text)
            }

            annotated.append(annotated_segment)

        return annotated

    def _calculate_importance_score(self, text: str) -> float:
        """重要度スコアを計算"""
        score = 0.0
        text_lower = text.lower()

        # キーワードベースのスコアリング
        for category, keywords in self.importance_keywords.items():
            category_weight = {
                'critical': 3.0,
                'success': 2.5,
                'failure': 2.5,
                'method': 2.0,
                'money': 2.0,
                'psychology': 1.5,
                'action': 1.5
            }.get(category, 1.0)

            for keyword in keywords:
                count = text_lower.count(keyword)
                score += count * category_weight

        # 数値を含む場合ボーナス
        if re.search(r'\d+[万億]?円|\d+%', text):
            score += 2.0

        # 箇条書きや番号付きリストの場合ボーナス
        if re.match(r'^[・\-\*\d]+[\.\)]\s', text):
            score += 1.5

        # 文の長さによる正規化
        if len(text) > 0:
            score = score / (len(text) / 100)  # 100文字あたりのスコア

        return round(score, 2)

    def _calculate_emotion_score(self, text: str) -> float:
        """感情強度スコアを計算"""
        score = 0.0
        text_lower = text.lower()

        for emotion_type, markers in self.emotion_markers.items():
            emotion_weight = {
                'strong_positive': 2.0,
                'positive': 1.0,
                'negative': -1.0,
                'strong_negative': -2.0
            }.get(emotion_type, 0)

            for marker in markers:
                if marker in text_lower:
                    score += emotion_weight

        return score

    def _classify_topic(self, text: str) -> str:
        """トピックを分類"""
        text_lower = text.lower()

        topic_scores = {
            'business_model': 0,
            'marketing': 0,
            'sales': 0,
            'content': 0,
            'mindset': 0,
            'technical': 0,
            'case_study': 0
        }

        # トピック関連キーワード
        topic_keywords = {
            'business_model': ['ビジネス', 'モデル', '収益', '仕組み', 'システム'],
            'marketing': ['マーケティング', '集客', 'SNS', 'インスタ', 'フォロワー'],
            'sales': ['販売', 'セールス', '売る', '購入', 'クロージング'],
            'content': ['コンテンツ', '教材', '講座', '動画', '記事'],
            'mindset': ['マインド', '考え方', '思考', '意識', '姿勢'],
            'technical': ['技術', 'ツール', '設定', 'アルゴリズム', 'データ'],
            'case_study': ['事例', '実例', 'ケース', '成功例', '失敗例']
        }

        for topic, keywords in topic_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    topic_scores[topic] += 1

        # 最もスコアの高いトピックを返す
        if max(topic_scores.values()) > 0:
            return max(topic_scores, key=topic_scores.get)
        return 'general'

    def _classify_segment_type(self, text: str) -> str:
        """セグメントタイプを分類"""
        # パターンマッチング
        if re.match(r'^[一二三四五六七八九十\d]+[\.\)、]', text):
            return 'enumeration'
        elif '例えば' in text or '実際に' in text:
            return 'example'
        elif '？' in text or 'でしょうか' in text:
            return 'question'
        elif any(word in text for word in ['重要', '大切', 'ポイント']):
            return 'emphasis'
        elif 'なぜなら' in text or 'つまり' in text or '理由は' in text:
            return 'explanation'
        elif any(word in text for word in ['ステップ', '手順', 'やり方']):
            return 'method'
        elif re.search(r'\d+[万億]?円', text):
            return 'numerical'
        else:
            return 'statement'

    def _extract_numbers(self, text: str) -> List[Dict[str, Any]]:
        """数値情報を抽出"""
        numbers = []

        # 金額
        money_pattern = r'(\d{1,4}(?:,\d{3})*(?:\.\d+)?)\s*([万億]?)円'
        for match in re.finditer(money_pattern, text):
            amount_str, unit = match.groups()
            amount = float(amount_str.replace(',', ''))
            if unit == '万':
                amount *= 10000
            elif unit == '億':
                amount *= 100000000
            numbers.append({
                'type': 'money',
                'value': amount,
                'original': match.group(0)
            })

        # パーセンテージ
        percent_pattern = r'(\d+(?:\.\d+)?)\s*[%％]'
        for match in re.finditer(percent_pattern, text):
            numbers.append({
                'type': 'percentage',
                'value': float(match.group(1)),
                'original': match.group(0)
            })

        # その他の数値
        general_pattern = r'(\d+)\s*(人|名|社|件|個|回|倍|フォロワー)'
        for match in re.finditer(general_pattern, text):
            numbers.append({
                'type': 'count',
                'value': int(match.group(1)),
                'unit': match.group(2),
                'original': match.group(0)
            })

        return numbers

    def _has_emphasis(self, text: str) -> bool:
        """強調表現があるか判定"""
        emphasis_patterns = [
            r'！',
            r'絶対',
            r'必ず',
            r'最も',
            r'一番',
            r'ここ.{0,5}重要',
            r'ポイント'
        ]

        for pattern in emphasis_patterns:
            if re.search(pattern, text):
                return True
        return False

    def _extract_key_concepts(self, segments: List[Dict]) -> Dict[str, float]:
        """キーコンセプトを抽出"""
        concept_scores = defaultdict(float)

        # 重要セグメントから名詞句を抽出
        for segment in segments:
            if segment['importance_score'] > 1.0:
                text = segment['text']

                # 重要な名詞句パターン
                patterns = [
                    r'([ァ-ヴー]+)(?:の|を|が|は|に)',  # カタカナ語
                    r'([一-龥]+[一-龥ァ-ヴー]*)',  # 漢字熟語
                    r'(\d+[つの要素|ステップ|段階|方法|ポイント])'  # 数値付きフレーズ
                ]

                for pattern in patterns:
                    for match in re.finditer(pattern, text):
                        concept = match.group(1)
                        if len(concept) >= 2:  # 2文字以上
                            concept_scores[concept] += segment['importance_score']

        # スコア順でソートして上位を返す
        sorted_concepts = sorted(concept_scores.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_concepts[:30])  # 上位30個

    def _detect_frameworks(self, segments: List[Dict]) -> List[Dict[str, Any]]:
        """フレームワークを検出"""
        frameworks = []

        # フレームワークのパターン
        framework_patterns = [
            r'(\d+)\s*つの\s*([^。、\n]+)',
            r'ステップ(\d+)[：:]\s*([^。、\n]+)',
            r'第([一二三四五六七八九十\d]+)[：:]\s*([^。、\n]+)',
            r'([①②③④⑤⑥⑦⑧⑨⑩])\s*([^。、\n]+)'
        ]

        for i, segment in enumerate(segments):
            text = segment['text']

            for pattern in framework_patterns:
                for match in re.finditer(pattern, text):
                    framework = {
                        'type': 'structured_method',
                        'name': match.group(0)[:50],
                        'segment_index': i,
                        'importance': segment['importance_score'],
                        'context': text[:200]
                    }

                    # 関連する後続セグメントも収集
                    related_segments = []
                    for j in range(i + 1, min(i + 10, len(segments))):
                        if segments[j]['segment_type'] in ['enumeration', 'method']:
                            related_segments.append(j)
                        elif segments[j]['importance_score'] < 0.5:
                            break

                    framework['related_segments'] = related_segments
                    frameworks.append(framework)

        return frameworks

    def _extract_success_patterns(self, segments: List[Dict]) -> List[Dict[str, Any]]:
        """成功パターンを抽出"""
        success_patterns = []

        for i, segment in enumerate(segments):
            if segment['topic'] in ['business_model', 'case_study'] and \
               any(word in segment['text'] for word in ['成功', '達成', '実現', '獲得']):

                pattern = {
                    'description': segment['text'][:200],
                    'segment_index': i,
                    'importance': segment['importance_score'],
                    'numbers': segment['numbers']
                }

                # 前後のコンテキストを収集
                context_before = segments[max(0, i-2):i]
                context_after = segments[i+1:min(i+3, len(segments))]

                pattern['context'] = {
                    'before': [s['text'][:100] for s in context_before],
                    'after': [s['text'][:100] for s in context_after]
                }

                success_patterns.append(pattern)

        return success_patterns

    def _extract_failure_patterns(self, segments: List[Dict]) -> List[Dict[str, Any]]:
        """失敗パターンを抽出"""
        failure_patterns = []

        for i, segment in enumerate(segments):
            if any(word in segment['text'] for word in ['失敗', 'ミス', '間違い', 'ダメ', '注意']):

                pattern = {
                    'description': segment['text'][:200],
                    'segment_index': i,
                    'importance': segment['importance_score'],
                    'emotion': segment['emotion_score']
                }

                # 原因と対策を探す
                cause = None
                solution = None

                # 前のセグメントから原因を探す
                if i > 0 and 'なぜ' in segments[i-1]['text']:
                    cause = segments[i-1]['text'][:150]

                # 後のセグメントから対策を探す
                if i < len(segments) - 1 and any(word in segments[i+1]['text'] for word in ['対策', '解決', '改善']):
                    solution = segments[i+1]['text'][:150]

                pattern['cause'] = cause
                pattern['solution'] = solution

                failure_patterns.append(pattern)

        return failure_patterns

    def _analyze_psychological_mechanisms(self, segments: List[Dict]) -> List[Dict[str, Any]]:
        """心理メカニズムを分析"""
        mechanisms = []

        # 心理学的原理のパターン
        psychology_patterns = {
            'social_proof': ['みんな', '多くの人', 'フォロワー', '人気', '評判'],
            'scarcity': ['限定', '残り', '今だけ', '期間限定', '先着'],
            'authority': ['専門', '実績', '経験', '成功', '達成'],
            'reciprocity': ['無料', 'プレゼント', '特典', 'ボーナス', 'サービス'],
            'consistency': ['一度', '最初', 'コミット', '約束', '継続'],
            'liking': ['好き', '共感', '親近感', '信頼', '関係']
        }

        for principle, keywords in psychology_patterns.items():
            relevant_segments = []

            for i, segment in enumerate(segments):
                if any(keyword in segment['text'] for keyword in keywords):
                    relevant_segments.append({
                        'index': i,
                        'text': segment['text'][:150],
                        'importance': segment['importance_score']
                    })

            if relevant_segments:
                mechanisms.append({
                    'principle': principle,
                    'evidence': relevant_segments[:3],  # 上位3つの証拠
                    'frequency': len(relevant_segments)
                })

        return mechanisms

    def _extract_action_items(self, segments: List[Dict]) -> List[Dict[str, Any]]:
        """アクション項目を抽出"""
        action_items = []

        action_triggers = ['実践', 'やる', '始める', 'する', 'してください', 'しましょう']

        for i, segment in enumerate(segments):
            if segment['segment_type'] in ['method', 'enumeration'] or \
               any(trigger in segment['text'] for trigger in action_triggers):

                action = {
                    'text': segment['text'][:200],
                    'segment_index': i,
                    'type': segment['segment_type'],
                    'priority': 'high' if segment['has_emphasis'] else 'normal'
                }

                # タイムフレームを探す
                timeframe_patterns = [
                    r'今すぐ', r'まず', r'最初に',
                    r'\d+日', r'\d+週間', r'\d+ヶ月'
                ]

                for pattern in timeframe_patterns:
                    if re.search(pattern, segment['text']):
                        action['timeframe'] = pattern
                        break

                action_items.append(action)

        return action_items

    def _extract_numerical_insights(self, segments: List[Dict]) -> List[Dict[str, Any]]:
        """数値的洞察を抽出"""
        insights = []

        # 全セグメントから数値を収集
        all_numbers = []
        for segment in segments:
            for num in segment['numbers']:
                all_numbers.append({
                    **num,
                    'segment_index': segment['index'],
                    'context': segment['text'][:100]
                })

        # 金額の分析
        money_values = [n for n in all_numbers if n['type'] == 'money']
        if money_values:
            # 最大値、最小値、平均値
            values = [n['value'] for n in money_values]
            insights.append({
                'type': 'money_range',
                'min': min(values),
                'max': max(values),
                'average': sum(values) / len(values),
                'examples': money_values[:3]
            })

        # パーセンテージの分析
        percentages = [n for n in all_numbers if n['type'] == 'percentage']
        if percentages:
            insights.append({
                'type': 'percentages',
                'values': percentages[:5]
            })

        # カウントの分析
        counts = [n for n in all_numbers if n['type'] == 'count']
        if counts:
            # 単位別に整理
            by_unit = defaultdict(list)
            for count in counts:
                by_unit[count.get('unit', 'その他')].append(count)

            insights.append({
                'type': 'counts_by_unit',
                'data': dict(by_unit)
            })

        return insights

    def _detect_speaker_emphasis(self, segments: List[Dict]) -> List[Dict[str, Any]]:
        """講師の強調ポイントを検出"""
        emphasis_points = []

        # 連続する高重要度セグメントを検出
        i = 0
        while i < len(segments):
            if segments[i]['importance_score'] > 2.0 or segments[i]['has_emphasis']:
                # 強調ブロックの開始
                emphasis_block = [segments[i]]
                j = i + 1

                # 連続する強調セグメントを収集
                while j < len(segments) and (
                    segments[j]['importance_score'] > 1.5 or
                    segments[j]['has_emphasis']
                ):
                    emphasis_block.append(segments[j])
                    j += 1

                if len(emphasis_block) >= 2:  # 2セグメント以上の強調
                    emphasis_points.append({
                        'start_index': i,
                        'end_index': j - 1,
                        'segments': len(emphasis_block),
                        'total_importance': sum(s['importance_score'] for s in emphasis_block),
                        'main_topic': Counter([s['topic'] for s in emphasis_block]).most_common(1)[0][0],
                        'preview': emphasis_block[0]['text'][:150]
                    })

                i = j
            else:
                i += 1

        # 重要度順でソート
        emphasis_points.sort(key=lambda x: x['total_importance'], reverse=True)

        return emphasis_points[:10]  # 上位10個

    def _analyze_story_arc(self, segments: List[Dict]) -> Dict[str, Any]:
        """ストーリーアークを分析"""
        total_segments = len(segments)
        if total_segments == 0:
            return {}

        # セミナーを5つの段階に分割
        phases = {
            'introduction': segments[:total_segments // 5],
            'problem': segments[total_segments // 5:total_segments * 2 // 5],
            'solution': segments[total_segments * 2 // 5:total_segments * 3 // 5],
            'examples': segments[total_segments * 3 // 5:total_segments * 4 // 5],
            'conclusion': segments[total_segments * 4 // 5:]
        }

        story_arc = {}

        for phase_name, phase_segments in phases.items():
            if not phase_segments:
                continue

            # 各フェーズの特徴を分析
            phase_analysis = {
                'segment_count': len(phase_segments),
                'avg_importance': sum(s['importance_score'] for s in phase_segments) / len(phase_segments),
                'avg_emotion': sum(s['emotion_score'] for s in phase_segments) / len(phase_segments),
                'main_topics': Counter([s['topic'] for s in phase_segments]).most_common(3),
                'key_numbers': sum([s['numbers'] for s in phase_segments], [])[:5],
                'emphasis_count': sum(1 for s in phase_segments if s['has_emphasis'])
            }

            story_arc[phase_name] = phase_analysis

        # クライマックスの特定（最も重要度が高い部分）
        importance_window = 10  # 10セグメントの移動窓
        max_importance = 0
        climax_index = 0

        for i in range(len(segments) - importance_window):
            window_importance = sum(
                s['importance_score'] for s in segments[i:i+importance_window]
            )
            if window_importance > max_importance:
                max_importance = window_importance
                climax_index = i

        story_arc['climax'] = {
            'start_index': climax_index,
            'end_index': min(climax_index + importance_window, len(segments)),
            'importance': max_importance,
            'preview': segments[climax_index]['text'][:200] if climax_index < len(segments) else ""
        }

        return story_arc

    def _analyze_by_persona(self, segments: List[Dict]) -> Dict[str, List[Dict]]:
        """ペルソナ別の分析"""
        personas = {
            'beginner': {
                'keywords': ['初心者', '始める', '最初', '基礎', '入門', '０から', 'ゼロから'],
                'segments': []
            },
            'intermediate': {
                'keywords': ['中級', '成長', '拡大', '改善', '効率化', '最適化'],
                'segments': []
            },
            'advanced': {
                'keywords': ['上級', 'スケール', '自動化', 'システム化', '組織化', '仕組み'],
                'segments': []
            }
        }

        for segment in segments:
            text_lower = segment['text'].lower()

            for persona_name, persona_data in personas.items():
                if any(keyword in text_lower for keyword in persona_data['keywords']):
                    persona_data['segments'].append({
                        'index': segment['index'],
                        'text': segment['text'][:150],
                        'importance': segment['importance_score'],
                        'numbers': segment['numbers']
                    })

        # 各ペルソナ向けの分析結果を整理
        result = {}
        for persona_name, persona_data in personas.items():
            if persona_data['segments']:
                # 重要度順でソート
                persona_data['segments'].sort(key=lambda x: x['importance'], reverse=True)

                result[persona_name] = {
                    'relevant_segments': persona_data['segments'][:10],  # 上位10個
                    'total_segments': len(persona_data['segments']),
                    'key_numbers': [
                        num for seg in persona_data['segments'][:5]
                        for num in seg['numbers']
                    ][:5]
                }

        return result

    def export_analysis(self, analysis_result: AnalysisResult, output_path: Path):
        """分析結果をエクスポート"""
        export_data = {
            'key_concepts': analysis_result.key_concepts,
            'frameworks': analysis_result.frameworks,
            'success_patterns': analysis_result.success_patterns,
            'failure_patterns': analysis_result.failure_patterns,
            'psychological_mechanisms': analysis_result.psychological_mechanisms,
            'action_items': analysis_result.action_items,
            'numerical_insights': analysis_result.numerical_insights,
            'speaker_emphasis': analysis_result.speaker_emphasis,
            'story_arc': analysis_result.story_arc,
            'personas': analysis_result.personas
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        self.logger.info(f"分析結果をエクスポート: {output_path}")