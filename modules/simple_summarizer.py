"""
シンプルな要約分析モジュール
成功していた generate_seminar_report.py のアルゴリズムを採用

主な特徴：
- 時間ベースのセグメント化（10分単位）
- キーワードベースの重要度判定
- 重要ポイントの直接抽出
- シンプルで効果的な要約生成
"""

import logging
import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from .keyword_analyzer import KeywordAnalyzer


@dataclass
class SimpleSummaryResult:
    """シンプル要約の結果を格納"""
    segment_summaries: List[Dict[str, Any]]  # セグメント要約（10分ごと）
    key_moments: List[Dict[str, Any]]        # 重要な瞬間
    executive_summary: str                    # エグゼクティブサマリー
    metadata: Dict[str, Any]                  # メタ情報


class SimpleSummarizer:
    """成功したアルゴリズムベースのシンプル要約クラス"""

    def __init__(self, config: Dict[str, Any]):
        """
        初期化

        Args:
            config: 設定辞書
        """
        self.config = config
        self.logger = logging.getLogger('VideoTranscriptAnalyzer.simple_summarizer')

        # セグメント設定
        self.segment_minutes = config.get('segment_minutes', 10)  # 10分単位

        # 動的キーワード分析器を初期化
        self.keyword_analyzer = KeywordAnalyzer()
        self.content_analysis = None  # 分析結果をキャッシュ

        # 静的キーワード（フォールバック用）
        self.static_keywords = config.get('importance_keywords', [
            # ビジネス・マネタイズ関連
            '収益', '売上', '利益', '万円', '億円', 'マネタイズ', '収益化', 'ビジネス',

            # 成功・実績関連
            '成功', '達成', '実績', '結果', '成果', '効果', '改善', '向上',

            # 戦略・方法関連
            '戦略', '方法', 'コツ', 'テクニック', 'ポイント', '秘訣', 'ノウハウ', '手法',

            # 重要性を示す言葉
            '重要', '大切', '必要', '必須', '基本', '本質', '核心', 'キー',

            # 問題・課題関連
            '問題', '課題', '失敗', 'ミス', '注意', '気をつけ', 'リスク', 'デメリット',

            # 具体的な数値・データ
            'パーセント', '%', '倍', '増加', '減少', '平均', 'データ', '統計',

            # アクション関連
            '実践', '実行', 'やり方', 'ステップ', '手順', '導入', '活用', '使い方',

            # SNS・マーケティング固有
            'フォロワー', 'いいね', 'エンゲージメント', 'リーチ', 'インプレッション',
            'コンバージョン', 'CTR', 'ROI', 'KPI', 'ターゲット', 'ペルソナ'
        ])

        # LLM設定（オプション：より良い要約のため）
        self.use_llm = config.get('use_llm', True)  # デフォルトでLLMを有効化（詳細な要約生成）
        if self.use_llm:
            self.model_name = config.get('model', 'gpt-oss:20b')
            # LangChain用にURLを調整（/v1を除去）
            api_url = config.get('api_base_url', 'http://localhost:11434')
            if api_url.endswith('/v1'):
                self.api_base_url = api_url[:-3]
            else:
                self.api_base_url = api_url
            self.temperature = config.get('temperature', 0.3)
            self.max_tokens = config.get('max_tokens', 500)

    def analyze(self,
                transcript_data: Dict[str, Any],
                output_dir: Path) -> SimpleSummaryResult:
        """
        シンプル要約を実行

        Args:
            transcript_data: 文字起こしデータ
            output_dir: 出力ディレクトリ

        Returns:
            シンプル要約結果
        """
        self.logger.info("シンプル要約分析を開始...")
        start_time = time.time()

        try:
            # 0. 全体テキストの動的分析
            all_text = ' '.join([seg.get('text', '') for seg in transcript_data.get('segments', [])])
            self.logger.info("コンテンツの動的キーワード分析を実行中...")
            self.content_analysis = self.keyword_analyzer.analyze_content(all_text)
            self.logger.info(f"ドメイン推定: {self.content_analysis['domain']}")
            self.logger.info(f"重要キーワード数: {len(self.content_analysis['important_keywords'])}")

            # 1. セグメント化（10分単位）
            segments = self._segment_transcript(transcript_data)
            self.logger.info(f"セグメント数: {len(segments)}")

            # 2. 各セグメントの要約生成
            segment_summaries = []
            for i, segment in enumerate(segments):
                summary = self._summarize_segment(segment, i + 1)
                segment_summaries.append(summary)
                self.logger.debug(f"セグメント {i+1}/{len(segments)} 処理完了")

            # 3. 重要な瞬間を特定
            key_moments = self._identify_key_moments(segment_summaries)
            self.logger.info(f"重要な瞬間: {len(key_moments)}個")

            # 4. エグゼクティブサマリー生成
            executive_summary = self._generate_executive_summary(
                segment_summaries, key_moments
            )

            # 5. メタデータ生成
            metadata = {
                'total_duration': transcript_data.get('duration', 0),
                'total_segments': len(segments),
                'total_words': sum(len(seg['text'].split()) for seg in segments),
                'processing_time': time.time() - start_time,
                'segment_minutes': self.segment_minutes,
                'domain': self.content_analysis.get('domain', 'unknown') if self.content_analysis else 'unknown',
                'top_keywords': [kw['keyword'] for kw in self.content_analysis['important_keywords'][:10]] if self.content_analysis else [],
                'numeric_summary': {
                    k: len(v) for k, v in self.content_analysis['numeric_patterns'].items()
                } if self.content_analysis else {}
            }

            # 結果を返す
            result = SimpleSummaryResult(
                segment_summaries=segment_summaries,
                key_moments=key_moments,
                executive_summary=executive_summary,
                metadata=metadata
            )

            # 結果を保存
            self._save_results(result, output_dir)

            elapsed = time.time() - start_time
            self.logger.info(f"✅ シンプル要約完了（{elapsed:.1f}秒）")

            return result

        except Exception as e:
            self.logger.error(f"要約処理エラー: {str(e)}", exc_info=True)
            raise

    def _segment_transcript(self, transcript_data: Dict[str, Any]) -> List[Dict]:
        """文字起こしを時間ベースでセグメント化"""
        segments = []
        segment_seconds = self.segment_minutes * 60

        current_segment = {
            'start_time': 0,
            'end_time': segment_seconds,
            'text': '',
            'raw_segments': []
        }

        for seg in transcript_data.get('segments', []):
            seg_start = seg.get('start', 0)
            seg_text = seg.get('text', '').strip()

            # 現在のセグメント時間内の場合
            if seg_start < current_segment['end_time']:
                current_segment['text'] += ' ' + seg_text
                current_segment['raw_segments'].append(seg)
            else:
                # 新しいセグメントに移行
                if current_segment['text'].strip():
                    segments.append(current_segment)

                # 新しいセグメント開始
                current_segment = {
                    'start_time': current_segment['end_time'],
                    'end_time': current_segment['end_time'] + segment_seconds,
                    'text': seg_text,
                    'raw_segments': [seg]
                }

        # 最後のセグメントを追加
        if current_segment['text'].strip():
            segments.append(current_segment)

        return segments

    def _summarize_segment(self, segment: Dict, segment_num: int) -> Dict[str, Any]:
        """セグメントを要約"""
        text = segment['text'].strip()

        # 文を分割
        sentences = self._split_sentences(text)

        # 重要度スコアを計算
        importance_score = self._calculate_importance_score(text)

        # キーポイントを抽出
        key_points = self._extract_key_points(sentences, max_points=5)

        # 要約テキストを生成
        if self.use_llm:
            summary_text = self._generate_llm_summary(text, key_points)
        else:
            # シンプルな要約（最初の500文字または重要な文）
            if key_points:
                summary_text = ' '.join(key_points[:3])
            else:
                summary_text = text[:500] + '...' if len(text) > 500 else text

        return {
            'segment_number': segment_num,
            'start_time': segment['start_time'],
            'end_time': segment['end_time'],
            'text': summary_text,
            'key_points': key_points,
            'importance_score': importance_score,
            'word_count': len(text.split())
        }

    def _split_sentences(self, text: str) -> List[str]:
        """テキストを文に分割"""
        # 日本語の文末記号で分割
        import re
        sentences = re.split(r'[。！？\n]+', text)
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]
        return sentences

    def _calculate_importance_score(self, text: str) -> float:
        """テキストの重要度スコアを計算（動的キーワードを使用）"""
        # 動的分析結果がある場合は使用
        if self.content_analysis:
            return self.keyword_analyzer.calculate_dynamic_importance_score(
                text, self.content_analysis
            )

        # フォールバック：静的キーワードを使用
        score = 0
        text_lower = text.lower()

        for keyword in self.static_keywords:
            count = text_lower.count(keyword.lower())
            score += count

        # 文字数で正規化（1000文字あたりのスコア）
        if len(text) > 0:
            score = (score / len(text)) * 1000

        return round(score, 2)

    def _extract_key_points(self, sentences: List[str], max_points: int = 5) -> List[str]:
        """重要な文を抽出"""
        scored_sentences = []

        for sentence in sentences:
            score = self._calculate_importance_score(sentence)
            if score > 0:  # キーワードを含む文のみ
                scored_sentences.append((sentence, score))

        # スコア順でソート
        scored_sentences.sort(key=lambda x: x[1], reverse=True)

        # 上位N個を選択（ただし元の順序を保持）
        selected = scored_sentences[:max_points]
        selected_sentences = [s[0] for s in selected]

        # 元の順序で返す
        key_points = []
        for sentence in sentences:
            if sentence in selected_sentences:
                key_points.append(sentence)
                if len(key_points) >= max_points:
                    break

        return key_points

    def _generate_llm_summary(self, text: str, key_points: List[str]) -> str:
        """LLMを使った詳細な要約生成"""
        try:
            import requests
            import json

            # Ollama APIを直接使用
            url = f"{self.api_base_url}/api/generate"

            # より詳細な要約を生成するプロンプト
            prompt = f"""以下のセミナー内容を分析し、ビジネス価値のある要約を生成してください。

【要約の要件】
1. 具体的な数値や成果があれば必ず含める
2. 実践的なアドバイスやテクニックを抽出
3. 成功事例や失敗事例があれば明記
4. 重要なキーワードや概念を強調

【セミナー内容】
{text[:3000]}

【特に重要なポイント】
{chr(10).join(f'• {point}' for point in key_points[:5])}

【要約】（300-500文字で構造化して記述）："""

            # Ollama APIリクエスト
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
                summary = result.get('response', '').strip()
            else:
                raise Exception(f"API返回错误: {response.status_code}")

            # 要約が短すぎる場合はキーポイントを追加
            if len(summary) < 100 and key_points:
                summary += "\n\n【抽出されたポイント】\n" + "\n".join(f"• {point}" for point in key_points[:3])

            return summary

        except Exception as e:
            self.logger.warning(f"LLM要約失敗、詳細フォールバック使用: {e}")
            # より詳細なフォールバック処理
            fallback_parts = []

            if key_points:
                fallback_parts.append("【重要ポイント】")
                for i, point in enumerate(key_points[:5], 1):
                    fallback_parts.append(f"{i}. {point}")

            # テキストから数値情報を抽出
            import re
            numbers = re.findall(r'\d+[万億]?円|\d+万?フォロワー|\d+%', text)
            if numbers:
                fallback_parts.append("\n【数値データ】")
                fallback_parts.append("• " + ", ".join(set(numbers[:5])))

            # 成功関連のキーワードを含む文を抽出
            success_sentences = [s for s in self._split_sentences(text[:1000])
                                if any(kw in s for kw in ['成功', '達成', '実現', '収益'])]
            if success_sentences:
                fallback_parts.append("\n【成果・実績】")
                fallback_parts.append(success_sentences[0][:200])

            return "\n".join(fallback_parts) if fallback_parts else text[:500] + '...'

    def _identify_key_moments(self, summaries: List[Dict], top_n: int = 10) -> List[Dict]:
        """重要な瞬間を特定"""
        # 重要度スコアでソート
        sorted_summaries = sorted(
            summaries,
            key=lambda x: x['importance_score'],
            reverse=True
        )

        # 上位N個を選択
        key_moments = []
        for summary in sorted_summaries[:top_n]:
            # 各重要セグメントの中間時点
            mid_time = (summary['start_time'] + summary['end_time']) / 2

            key_moments.append({
                'timestamp': mid_time,
                'segment_number': summary['segment_number'],
                'importance_score': summary['importance_score'],
                'description': summary['key_points'][0] if summary['key_points'] else summary['text'][:100],
                'start_time': summary['start_time'],
                'end_time': summary['end_time']
            })

        # 時系列順にソート
        key_moments.sort(key=lambda x: x['timestamp'])

        return key_moments

    def _generate_executive_summary(self,
                                   summaries: List[Dict],
                                   key_moments: List[Dict]) -> str:
        """詳細なエグゼクティブサマリーを生成"""
        import re

        # 最重要ポイントを抽出
        top_moments = sorted(
            key_moments,
            key=lambda x: x['importance_score'],
            reverse=True
        )[:5]

        # 全テキストから数値データを抽出
        all_text = ' '.join([s['text'] for s in summaries])
        revenue_numbers = re.findall(r'\d+[万億]?円', all_text)
        follower_numbers = re.findall(r'\d+万?フォロワー', all_text)
        percentages = re.findall(r'\d+[％%]', all_text)

        # サマリー構築
        summary_parts = []

        # タイトルと概要
        summary_parts.append("# 📊 セミナー要約レポート\n")
        summary_parts.append("## 🎯 エグゼクティブサマリー\n")

        # セミナーの主題を特定（動的分析結果から推定）
        theme_keywords = []
        if self.content_analysis and 'important_keywords' in self.content_analysis:
            for kw_info in self.content_analysis['important_keywords'][:10]:
                kw = kw_info['keyword']
                if all_text.lower().count(kw.lower()) > 3:
                    theme_keywords.append(kw)

        if theme_keywords:
            summary_parts.append(f"**主要テーマ**: {', '.join(theme_keywords[:3])}\n\n")

        # 核心メッセージ
        summary_parts.append("### 💡 核心メッセージ\n")
        if top_moments:
            for i, moment in enumerate(top_moments[:3], 1):
                desc = moment['description']
                # 長すぎる場合は要約
                if len(desc) > 150:
                    desc = desc[:150] + "..."
                summary_parts.append(f"{i}. **{desc}**\n")

        # 数値で見る成果
        if revenue_numbers or follower_numbers:
            summary_parts.append("\n### 📈 数値で見る成果\n")
            if revenue_numbers:
                unique_revenues = list(set(revenue_numbers))[:5]
                summary_parts.append(f"- **収益実績**: {', '.join(unique_revenues)}\n")
            if follower_numbers:
                unique_followers = list(set(follower_numbers))[:5]
                summary_parts.append(f"- **フォロワー数**: {', '.join(unique_followers)}\n")
            if percentages:
                unique_percentages = list(set(percentages))[:3]
                summary_parts.append(f"- **成長率**: {', '.join(unique_percentages)}\n")

        # セグメント別ハイライト
        summary_parts.append("\n### 📋 セクション別ハイライト\n")

        # 高スコアセグメントを時系列順に表示
        high_score_segments = [s for s in summaries if s['importance_score'] > 3][:5]
        high_score_segments.sort(key=lambda x: x['segment_number'])

        for seg in high_score_segments:
            time_range = f"{seg['start_time']//60:.0f}分-{seg['end_time']//60:.0f}分"
            score = seg['importance_score']

            # キーポイントがあれば最初の1つを使用
            if seg['key_points']:
                highlight = seg['key_points'][0][:100]
            else:
                highlight = seg['text'][:100]

            summary_parts.append(f"- **[{time_range}]** (重要度: {score:.1f}) {highlight}...\n")

        # メタ情報
        summary_parts.append(f"\n### 📊 分析概要\n")
        summary_parts.append(f"- **総セグメント数**: {len(summaries)}セグメント（{self.segment_minutes}分単位）\n")
        summary_parts.append(f"- **総単語数**: {sum(s['word_count'] for s in summaries):,}語\n")
        summary_parts.append(f"- **重要セクション**: {len([s for s in summaries if s['importance_score'] > 5])}個\n")

        return ''.join(summary_parts)

    def _save_results(self, result: SimpleSummaryResult, output_dir: Path):
        """結果を保存"""
        output_dir.mkdir(parents=True, exist_ok=True)

        # JSON形式で保存
        result_dict = {
            'segment_summaries': result.segment_summaries,
            'key_moments': result.key_moments,
            'executive_summary': result.executive_summary,
            'metadata': result.metadata,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }

        output_file = output_dir / 'simple_summary.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result_dict, f, ensure_ascii=False, indent=2)

        self.logger.info(f"要約結果を保存: {output_file}")