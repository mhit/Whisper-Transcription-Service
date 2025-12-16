"""
動的キーワード分析モジュール
コンテンツから自動的に重要キーワードを抽出・重み付けする
"""

import logging
from typing import Dict, List, Tuple, Any
from collections import Counter
import re
import math


class KeywordAnalyzer:
    """動的キーワード分析クラス"""

    def __init__(self):
        self.logger = logging.getLogger('VideoTranscriptAnalyzer.keyword_analyzer')

        # 一般的なストップワード（助詞、接続詞など）
        self.stop_words = set([
            'の', 'に', 'は', 'を', 'た', 'が', 'で', 'て', 'と', 'し', 'れ', 'さ', 'ある',
            'いる', 'も', 'する', 'から', 'な', 'こと', 'として', 'い', 'や', 'など',
            'なり', 'へ', 'か', 'だ', 'これ', 'それ', 'あれ', 'という', 'ため', 'その',
            'ような', 'そう', 'ね', 'よ', 'ます', 'です', 'ません', 'でした', 'ました',
            'あります', 'ありません', 'います', 'いません', 'なる', 'れる', 'られる'
        ])

    def analyze_content(self, text: str, min_freq: int = 3) -> Dict[str, Any]:
        """
        コンテンツを分析して動的にキーワードを抽出

        Args:
            text: 分析対象のテキスト
            min_freq: 最小出現頻度

        Returns:
            分析結果の辞書
        """
        self.logger.debug("コンテンツの動的分析を開始...")

        # 1. テキストの前処理
        cleaned_text = self._preprocess_text(text)

        # 2. 単語の頻度分析
        word_freq = self._calculate_word_frequency(cleaned_text)

        # 3. N-gramの抽出（重要なフレーズの検出）
        ngrams = self._extract_ngrams(cleaned_text, n=2)

        # 4. TF-IDF計算（重要度スコアリング）
        tfidf_scores = self._calculate_tfidf(word_freq, len(cleaned_text.split()))

        # 5. 数値データの抽出
        numeric_data = self._extract_numeric_patterns(text)

        # 6. 専門用語・固有名詞の検出
        entities = self._extract_entities(text)

        # 7. 文脈ベースの重要キーワード選定
        important_keywords = self._select_important_keywords(
            tfidf_scores, ngrams, entities, min_freq
        )

        # 8. ドメイン推定
        domain = self._estimate_domain(important_keywords, numeric_data)

        return {
            'domain': domain,
            'important_keywords': important_keywords,
            'numeric_patterns': numeric_data,
            'entities': entities,
            'ngrams': ngrams[:20],  # 上位20個のN-gram
            'word_frequency': dict(word_freq.most_common(50))  # 上位50単語
        }

    def _preprocess_text(self, text: str) -> str:
        """テキストの前処理"""
        # 改行や余分な空白を削除
        text = re.sub(r'\s+', ' ', text)
        # 記号の正規化
        text = re.sub(r'[！？。、]', ' ', text)
        return text.lower()

    def _calculate_word_frequency(self, text: str) -> Counter:
        """単語頻度を計算"""
        words = text.split()
        # ストップワードと短すぎる単語を除外
        filtered_words = [
            word for word in words
            if word not in self.stop_words and len(word) > 1
        ]
        return Counter(filtered_words)

    def _extract_ngrams(self, text: str, n: int = 2) -> List[Tuple[str, int]]:
        """N-gram（連続する単語の組み合わせ）を抽出"""
        words = text.split()
        ngrams = []

        for i in range(len(words) - n + 1):
            ngram = ' '.join(words[i:i+n])
            # ストップワードのみのN-gramは除外
            if not all(word in self.stop_words for word in words[i:i+n]):
                ngrams.append(ngram)

        ngram_freq = Counter(ngrams)
        return ngram_freq.most_common(30)

    def _calculate_tfidf(self, word_freq: Counter, total_words: int) -> Dict[str, float]:
        """TF-IDFスコアを計算（改善版）"""
        tfidf_scores = {}

        # 最大頻度と最小頻度を取得
        max_freq = max(word_freq.values()) if word_freq else 1
        min_freq = 3  # 最低3回は出現する単語のみ対象

        for word, freq in word_freq.items():
            # 頻度が低すぎる単語は除外
            if freq < min_freq:
                continue

            # 単語長が短すぎる（2文字以下）または長すぎる（20文字以上）は除外
            if len(word) <= 2 or len(word) >= 20:
                continue

            # 挨拶や定型句を除外
            greetings = ['ありがとうございます', 'お願いします', 'よろしくお願いします', 'はい', 'いいえ']
            if any(greeting in word for greeting in greetings):
                continue

            # TF（正規化された頻度）
            tf = 0.5 + (0.5 * freq / max_freq)

            # IDF（改善版：頻度が高すぎる単語のペナルティを強化）
            doc_freq_ratio = freq / total_words
            if doc_freq_ratio > 0.01:  # 1%以上出現する単語はペナルティ
                idf = math.log(1 / (doc_freq_ratio * 10))
            else:
                idf = math.log(total_words / freq)

            # 単語の種類による重み付け
            weight = 1.0
            # 数字を含む単語は重要
            if any(c.isdigit() for c in word):
                weight = 1.5
            # カタカナのみの単語（固有名詞の可能性）
            if all(c in 'ァ-ヴー' for c in word):
                weight = 1.3

            tfidf_scores[word] = tf * idf * weight

        return dict(sorted(tfidf_scores.items(), key=lambda x: x[1], reverse=True)[:50])

    def _extract_numeric_patterns(self, text: str) -> Dict[str, List[str]]:
        """数値パターンを抽出"""
        patterns = {
            'revenue': re.findall(r'\d+[万億]?円', text),
            'followers': re.findall(r'\d+[万]?フォロワー', text),
            'percentage': re.findall(r'\d+[％%]', text),
            'count': re.findall(r'\d+[個件回]', text),
            'time': re.findall(r'\d+[分時間日週間ヶ月年]', text),
            'multiplier': re.findall(r'\d+倍', text)
        }

        # 重複を削除
        for key in patterns:
            patterns[key] = list(set(patterns[key]))[:10]  # 各カテゴリ上位10個

        return patterns

    def _extract_entities(self, text: str) -> Dict[str, List[str]]:
        """固有名詞やエンティティを抽出"""
        entities = {
            'products': [],
            'platforms': [],
            'techniques': [],
            'people': []
        }

        # プラットフォーム名の検出
        platform_patterns = [
            'インスタ', 'Instagram', 'TikTok', 'Twitter', 'YouTube',
            'Facebook', 'LINE', 'X', 'Threads'
        ]
        for platform in platform_patterns:
            if platform.lower() in text.lower():
                entities['platforms'].append(platform)

        # 商品・サービス名の検出（カタカナの連続）
        katakana_words = re.findall(r'[ァ-ヴー]{3,}', text)
        entities['products'].extend(list(set(katakana_words))[:10])

        # テクニック・手法の検出
        technique_patterns = re.findall(r'[ァ-ヴー]+(?:術|法|戦略|テクニック|スキル)', text)
        entities['techniques'].extend(list(set(technique_patterns))[:10])

        # 人名パターン（「さん」「氏」「先生」が付く）
        people_patterns = re.findall(r'[ぁ-んァ-ヴー一-龯]{2,}(?:さん|氏|先生)', text)
        entities['people'].extend(list(set(people_patterns))[:10])

        return entities

    def _select_important_keywords(
        self,
        tfidf_scores: Dict[str, float],
        ngrams: List[Tuple[str, int]],
        entities: Dict[str, List[str]],
        min_freq: int
    ) -> List[Dict[str, Any]]:
        """重要キーワードを選定（改善版）"""
        important_keywords = []
        added_keywords = set()  # 重複を防ぐ

        # TF-IDFスコア上位のキーワード（意味のあるものを優先）
        for word, score in list(tfidf_scores.items())[:30]:
            if word not in added_keywords and len(word) > 2:
                important_keywords.append({
                    'keyword': word,
                    'type': 'high_tfidf',
                    'score': score,
                    'weight': 2.0
                })
                added_keywords.add(word)

        # ビジネス関連の重要キーワード（事前定義）
        business_keywords = [
            '収益', '売上', '利益', 'フォロワー', '成功', '達成', '実績',
            'マネタイズ', '収益化', 'ビジネス', '戦略', '方法', 'テクニック'
        ]

        for keyword in business_keywords:
            if keyword not in added_keywords:
                # テキスト中での出現を確認
                important_keywords.append({
                    'keyword': keyword,
                    'type': 'domain_specific',
                    'score': 1.0,
                    'weight': 2.5  # ドメイン固有キーワードは高い重み
                })
                added_keywords.add(keyword)

        # 意味のあるN-gram（定型句を除外）
        exclude_patterns = ['ありがとうございます', 'お願いします', 'よろしく', 'ご視聴']
        for ngram, freq in ngrams[:20]:
            if freq >= min_freq and ngram not in added_keywords:
                # 定型句を除外
                if not any(pattern in ngram for pattern in exclude_patterns):
                    important_keywords.append({
                        'keyword': ngram,
                        'type': 'ngram',
                        'score': freq,
                        'weight': 1.5
                    })
                    added_keywords.add(ngram)

        # エンティティ（重複を避けて追加）
        for entity_type, entity_list in entities.items():
            weight = {
                'products': 1.8,
                'platforms': 2.2,  # プラットフォーム名は重要
                'techniques': 2.0,
                'people': 1.5
            }.get(entity_type, 1.5)

            for entity in entity_list[:5]:
                if entity not in added_keywords and len(entity) > 2:
                    important_keywords.append({
                        'keyword': entity,
                        'type': f'entity_{entity_type}',
                        'score': 1.0,
                        'weight': weight
                    })
                    added_keywords.add(entity)

        # スコアで並び替えて返す
        important_keywords.sort(key=lambda x: x['weight'] * x.get('score', 1), reverse=True)
        return important_keywords[:50]  # 上位50個を返す

    def _estimate_domain(
        self,
        keywords: List[Dict[str, Any]],
        numeric_data: Dict[str, List[str]]
    ) -> str:
        """コンテンツのドメインを推定"""
        # キーワードからドメインを推定
        keyword_texts = [kw['keyword'] for kw in keywords]
        keyword_text = ' '.join(keyword_texts).lower()

        domain_indicators = {
            'business': ['ビジネス', '売上', '収益', '利益', 'マーケティング', '営業'],
            'education': ['勉強', '学習', '教育', '講座', 'スクール', '授業'],
            'technology': ['プログラム', 'AI', 'システム', 'アプリ', 'ソフトウェア'],
            'health': ['健康', 'ダイエット', '運動', '医療', '治療'],
            'finance': ['投資', '株', 'FX', '仮想通貨', '資産'],
            'marketing': ['マーケティング', 'SNS', 'フォロワー', 'インフルエンサー']
        }

        domain_scores = {}
        for domain, indicators in domain_indicators.items():
            score = sum(1 for ind in indicators if ind.lower() in keyword_text)
            if score > 0:
                domain_scores[domain] = score

        # 数値データからも推定
        if numeric_data.get('revenue'):
            domain_scores['business'] = domain_scores.get('business', 0) + 2
        if numeric_data.get('followers'):
            domain_scores['marketing'] = domain_scores.get('marketing', 0) + 2

        # 最高スコアのドメインを返す
        if domain_scores:
            return max(domain_scores, key=domain_scores.get)
        return 'general'

    def calculate_dynamic_importance_score(
        self,
        text: str,
        analysis_result: Dict[str, Any]
    ) -> float:
        """動的に重要度スコアを計算"""
        score = 0.0
        text_lower = text.lower()

        # 重要キーワードによるスコアリング
        for keyword_info in analysis_result['important_keywords']:
            keyword = keyword_info['keyword'].lower()
            if keyword in text_lower:
                # キーワードの出現回数をカウント
                count = text_lower.count(keyword)
                # 重みを考慮したスコア加算
                score += count * keyword_info['weight']

        # 数値データの存在によるボーナス
        for pattern_type, patterns in analysis_result['numeric_patterns'].items():
            for pattern in patterns:
                if pattern in text:
                    score += 2.0  # 数値データは重要

        # テキスト長による正規化（1000文字あたり）
        if len(text) > 0:
            score = (score / len(text)) * 1000

        return round(score, 2)