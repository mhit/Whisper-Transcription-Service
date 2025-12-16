"""
AI分析モジュール

OpenAI APIを使用した文字起こし内容の分析機能を提供：
- 内容要約
- 重要ポイント抽出
- 話者分析
- 感情分析
- キーワード抽出
"""

import os
import logging
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import re

try:
    import openai
except ImportError:
    print("OpenAI ライブラリが見つかりません。以下のコマンドでインストールしてください:")
    print("pip install openai")
    openai = None

from .utils import (
    format_duration,
    check_ollama_installed,
    is_ollama_running,
    start_ollama_server,
    pull_ollama_model,
    get_ollama_models,
    unload_ollama_model
)


class ContentAnalyzer:
    """AI文字起こし分析クラス"""

    def __init__(self, config: Dict[str, Any], api_key: Optional[str] = None):
        """
        初期化

        Args:
            config: 分析設定
            api_key: OpenAI APIキー
        """
        self.config = config
        self.logger = logging.getLogger('VideoTranscriptAnalyzer.analyzer')

        # 設定値
        self.model = config.get('model', 'gpt-4-turbo-preview')
        self.temperature = config.get('temperature', 0.7)
        self.max_tokens = config.get('max_tokens', 4000)
        self.chunk_size = config.get('chunk_size', 8000)  # トークン単位

        # API設定（環境変数優先、次にconfig、最後にデフォルト）
        api_base_url = os.getenv('OPENAI_API_BASE_URL') or config.get('api_base_url')
        api_type = os.getenv('OPENAI_API_TYPE') or config.get('api_type')

        # モデル名も環境変数でオーバーライド可能
        self.model = os.getenv('OPENAI_MODEL') or self.model

        # OpenAI クライアント初期化
        self.client = None

        # APIキーがない場合、またはOllamaエンドポイントが指定されている場合
        is_ollama_endpoint = api_base_url and ('localhost:11434' in api_base_url or 'ollama' in api_base_url.lower())

        if (not api_key or is_ollama_endpoint) and openai:
            if is_ollama_endpoint:
                self.logger.info("Ollamaエンドポイントが設定されています。Ollamaモードで動作します...")
            else:
                self.logger.info("APIキーが設定されていません。ローカルOllamaへのフォールバックを試みます...")

            # Ollama設定
            ollama_config = config.get('ollama_fallback', {})
            ollama_enabled = ollama_config.get('enabled', True)
            ollama_auto_start = ollama_config.get('auto_start', True)
            # config.yamlで指定されているモデルを優先、なければollama_fallbackのモデル
            ollama_model = self.model if is_ollama_endpoint else ollama_config.get('model', 'qwen2.5:32b')
            ollama_timeout = ollama_config.get('model_pull_timeout', 1800)  # 30分

            if ollama_enabled and check_ollama_installed():
                try:
                    # Ollamaサーバーを起動
                    if ollama_auto_start and not is_ollama_running():
                        self.logger.info("Ollamaサーバーを起動中...")
                        if not start_ollama_server():
                            raise RuntimeError("Ollamaサーバーの起動に失敗しました")

                    # モデルをダウンロード（必要な場合）
                    self.logger.info(f"Ollamaモデル {ollama_model} を準備中...")
                    if not pull_ollama_model(ollama_model, timeout=ollama_timeout):
                        # フォールバックモデルを試す
                        fallback_models = ['llama2:7b', 'mistral:7b']
                        for fallback_model in fallback_models:
                            self.logger.warning(f"代替モデル {fallback_model} を試します...")
                            if pull_ollama_model(fallback_model, timeout=300):
                                ollama_model = fallback_model
                                break
                        else:
                            raise RuntimeError("Ollamaモデルのダウンロードに失敗しました")

                    # Ollama APIクライアントを設定
                    if not api_key:
                        api_key = "ollama"  # ダミーキー
                    if not api_base_url:
                        api_base_url = "http://localhost:11434/v1"
                    self.model = ollama_model

                    self.logger.info(f"✅ Ollamaフォールバックモード有効 (モデル: {ollama_model})")

                    # GPUメモリ節約のため、接続テスト後にモデルをアンロード
                    self.logger.info("GPUメモリ節約のため、Ollamaモデルを一時的にアンロードします...")
                    unload_ollama_model(ollama_model)
                    self.logger.info("Ollamaモデルをアンロードしました（必要時に自動的に再ロードされます）")

                except Exception as e:
                    self.logger.error(f"Ollamaフォールバック失敗: {e}")
                    self.logger.info("Ollamaのインストールと設定を確認してください:")
                    self.logger.info("  - Linux/Mac: curl -fsSL https://ollama.ai/install.sh | sh")
                    self.logger.info("  - Windows: https://ollama.ai/download/windows")
            elif ollama_enabled:
                self.logger.warning("Ollamaがインストールされていません")
                self.logger.info("インストール方法:")
                self.logger.info("  - Linux/Mac: curl -fsSL https://ollama.ai/install.sh | sh")
                self.logger.info("  - Windows: https://ollama.ai/download/windows")

        # API クライアントの初期化（通常のOpenAIまたはOllama経由）
        if api_key and openai:
            try:
                # OpenAI互換API対応
                if api_base_url:
                    self.logger.info(f"カスタムAPIエンドポイント使用: {api_base_url}")
                    self.client = openai.OpenAI(
                        api_key=api_key,
                        base_url=api_base_url
                    )
                else:
                    # 標準OpenAI API
                    self.client = openai.OpenAI(api_key=api_key)

                self.logger.info(f"APIクライアント初期化完了 (モデル: {self.model})")
            except Exception as e:
                self.logger.warning(f"APIクライアント初期化失敗: {e}")
                self.client = None
        else:
            # APIキーがない場合の警告（すでにOllamaフォールバックを試みた後）
            if not self.client:
                self.logger.warning("API分析が無効です（APIキーまたはOllamaが利用できません）")

    def analyze(self, transcript_data: Dict[str, Any], output_dir: Path) -> Dict[str, Any]:
        """
        文字起こし内容を分析

        Args:
            transcript_data: 文字起こしデータ
            output_dir: 出力ディレクトリ

        Returns:
            分析結果辞書

        Raises:
            RuntimeError: 分析失敗
        """
        if not self.client:
            self.logger.warning("OpenAI APIが利用できません。基本的な分析のみ実行します")
            return self._basic_analysis(transcript_data, output_dir)

        # GPUメモリ確保のため、念のためOllamaモデルをアンロード
        # （Whisperが実行済みなので、今度はOllamaのために場所を空ける）
        try:
            unload_ollama_model()
        except Exception:
            pass  # エラーは無視（ベストエフォート）

        self.logger.info("AI分析開始...")
        start_time = time.time()

        try:
            # テキストを取得
            full_text = transcript_data.get('text', '')
            segments = transcript_data.get('segments', [])

            if not full_text:
                raise RuntimeError("分析対象のテキストが見つかりません")

            # テキストをチャンクに分割
            text_chunks = self._split_text_into_chunks(full_text, self.chunk_size)
            self.logger.info(f"テキストを {len(text_chunks)} チャンクに分割")

            # 各種分析を実行
            analysis_result = {
                'summary': self._generate_summary(text_chunks),
                'key_points': self._extract_key_points(text_chunks),
                'topics': self._extract_topics(text_chunks),
                'sentiment': self._analyze_sentiment(text_chunks),
                'keywords': self._extract_keywords(text_chunks),
                'speaker_analysis': self._analyze_speakers(segments),
                'time_analysis': self._analyze_time_distribution(segments),
                'quality_metrics': self._calculate_quality_metrics(transcript_data),
                'recommendations': self._generate_recommendations(transcript_data),
                'metadata': {
                    'analysis_time': time.time() - start_time,
                    'model_used': self.model,
                    'chunk_count': len(text_chunks),
                    'total_tokens_estimated': sum(len(chunk.split()) for chunk in text_chunks) * 1.3,
                    'language': transcript_data.get('language', 'unknown')
                }
            }

            # 分析結果をファイルに保存
            self._save_analysis_files(analysis_result, output_dir)

            analysis_time = time.time() - start_time
            self.logger.info(f"✅ AI分析完了 ({analysis_time:.1f}秒)")

            return analysis_result

        except Exception as e:
            error_msg = f"AI分析エラー: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg)

    def _basic_analysis(self, transcript_data: Dict[str, Any], output_dir: Path) -> Dict[str, Any]:
        """
        APIなしでの基本分析

        Args:
            transcript_data: 文字起こしデータ
            output_dir: 出力ディレクトリ

        Returns:
            基本分析結果
        """
        self.logger.info("基本分析を実行中...")

        text = transcript_data.get('text', '')
        segments = transcript_data.get('segments', [])

        basic_result = {
            'summary': {'main_summary': 'AI分析が利用できません。基本統計のみ提供されます。'},
            'key_points': [],
            'topics': [],
            'sentiment': {'overall': 'neutral', 'confidence': 0.0},
            'keywords': self._extract_basic_keywords(text),
            'speaker_analysis': {'speaker_count': 1, 'distribution': {}},
            'time_analysis': self._analyze_time_distribution(segments),
            'quality_metrics': self._calculate_quality_metrics(transcript_data),
            'recommendations': ['OpenAI APIキーを設定すると詳細なAI分析が利用できます'],
            'metadata': {
                'analysis_type': 'basic',
                'ai_analysis_available': False
            }
        }

        self._save_analysis_files(basic_result, output_dir)
        return basic_result

    def _split_text_into_chunks(self, text: str, max_tokens: int) -> List[str]:
        """
        テキストをトークン数でチャンクに分割

        Args:
            text: 分割するテキスト
            max_tokens: 最大トークン数

        Returns:
            チャンクのリスト
        """
        # 簡易的なトークン推定（単語数 × 1.3）
        words = text.split()
        estimated_tokens_per_word = 1.3
        words_per_chunk = int(max_tokens / estimated_tokens_per_word)

        chunks = []
        for i in range(0, len(words), words_per_chunk):
            chunk_words = words[i:i + words_per_chunk]
            chunks.append(' '.join(chunk_words))

        return chunks

    def _generate_summary(self, text_chunks: List[str]) -> Dict[str, Any]:
        """
        要約を生成

        Args:
            text_chunks: テキストチャンク

        Returns:
            要約結果
        """
        try:
            # 各チャンクの要約を生成
            chunk_summaries = []
            for i, chunk in enumerate(text_chunks):
                self.logger.info(f"チャンク {i+1}/{len(text_chunks)} の要約生成中...")

                prompt = f"""
以下のテキストを日本語で要約してください。重要なポイントを3-5文で簡潔にまとめてください。

テキスト:
{chunk}

要約:
"""

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.temperature,
                    max_tokens=300
                )

                summary = response.choices[0].message.content.strip()
                chunk_summaries.append(summary)

            # 全体要約を生成
            combined_summaries = '\n\n'.join(chunk_summaries)
            final_prompt = f"""
以下は複数のセクションの要約です。これらを統合して、全体の内容を日本語で簡潔に要約してください。

セクション要約:
{combined_summaries}

全体要約:
"""

            final_response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": final_prompt}],
                temperature=self.temperature,
                max_tokens=500
            )

            return {
                'main_summary': final_response.choices[0].message.content.strip(),
                'section_summaries': chunk_summaries,
                'summary_length': len(final_response.choices[0].message.content.split())
            }

        except Exception as e:
            self.logger.error(f"要約生成エラー: {e}")
            return {
                'main_summary': 'エラー: 要約を生成できませんでした',
                'section_summaries': [],
                'summary_length': 0
            }

    def _extract_key_points(self, text_chunks: List[str]) -> List[Dict[str, Any]]:
        """
        重要ポイントを抽出

        Args:
            text_chunks: テキストチャンク

        Returns:
            重要ポイントのリスト
        """
        try:
            all_key_points = []

            for chunk in text_chunks:
                prompt = f"""
以下のテキストから重要なポイントを5個以下で抽出してください。
各ポイントは以下のJSON形式で回答してください：

{{
  "points": [
    {{
      "point": "重要ポイントの内容",
      "importance": "high/medium/low",
      "category": "カテゴリ名"
    }}
  ]
}}

テキスト:
{chunk}
"""

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.temperature,
                    max_tokens=800
                )

                try:
                    result = json.loads(response.choices[0].message.content)
                    all_key_points.extend(result.get('points', []))
                except json.JSONDecodeError:
                    self.logger.warning("重要ポイント抽出でJSON解析エラー")

            return all_key_points[:20]  # 最大20ポイント

        except Exception as e:
            self.logger.error(f"重要ポイント抽出エラー: {e}")
            return []

    def _extract_topics(self, text_chunks: List[str]) -> List[Dict[str, Any]]:
        """
        トピックを抽出

        Args:
            text_chunks: テキストチャンク

        Returns:
            トピックのリスト
        """
        try:
            combined_text = ' '.join(text_chunks[:2])  # 最初の2チャンクのみ使用

            prompt = f"""
以下のテキストから主要なトピックを抽出してください。
以下のJSON形式で回答してください：

{{
  "topics": [
    {{
      "topic": "トピック名",
      "description": "トピックの説明",
      "relevance": "high/medium/low"
    }}
  ]
}}

テキスト:
{combined_text}
"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=1000
            )

            try:
                result = json.loads(response.choices[0].message.content)
                return result.get('topics', [])
            except json.JSONDecodeError:
                self.logger.warning("トピック抽出でJSON解析エラー")
                return []

        except Exception as e:
            self.logger.error(f"トピック抽出エラー: {e}")
            return []

    def _analyze_sentiment(self, text_chunks: List[str]) -> Dict[str, Any]:
        """
        感情分析

        Args:
            text_chunks: テキストチャンク

        Returns:
            感情分析結果
        """
        try:
            # 最初のチャンクのみで感情分析
            sample_text = text_chunks[0] if text_chunks else ""

            prompt = f"""
以下のテキストの感情を分析してください。
以下のJSON形式で回答してください：

{{
  "overall": "positive/negative/neutral",
  "confidence": 0.8,
  "emotions": ["emotion1", "emotion2"],
  "tone": "tone_description"
}}

テキスト:
{sample_text}
"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=300
            )

            try:
                result = json.loads(response.choices[0].message.content)
                return result
            except json.JSONDecodeError:
                return {'overall': 'neutral', 'confidence': 0.0}

        except Exception as e:
            self.logger.error(f"感情分析エラー: {e}")
            return {'overall': 'neutral', 'confidence': 0.0}

    def _extract_keywords(self, text_chunks: List[str]) -> List[str]:
        """
        キーワードを抽出

        Args:
            text_chunks: テキストチャンク

        Returns:
            キーワードのリスト
        """
        try:
            combined_text = ' '.join(text_chunks[:2])

            prompt = f"""
以下のテキストから重要なキーワードを10-15個抽出してください。
カンマ区切りで回答してください。

テキスト:
{combined_text}

キーワード:
"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=200
            )

            keywords_text = response.choices[0].message.content.strip()
            keywords = [kw.strip() for kw in keywords_text.split(',')]
            return keywords[:15]

        except Exception as e:
            self.logger.error(f"キーワード抽出エラー: {e}")
            return self._extract_basic_keywords(' '.join(text_chunks))

    def _extract_basic_keywords(self, text: str) -> List[str]:
        """
        基本的なキーワード抽出（頻度ベース）

        Args:
            text: 対象テキスト

        Returns:
            キーワードのリスト
        """
        # 簡単な単語頻度分析
        words = re.findall(r'\b\w{3,}\b', text.lower())
        word_freq = {}

        for word in words:
            if word not in ['です', 'ます', 'ある', 'いる', 'する', 'なる']:
                word_freq[word] = word_freq.get(word, 0) + 1

        # 頻度順でソート
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, freq in sorted_words[:10]]

    def _analyze_speakers(self, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        話者分析

        Args:
            segments: セグメントデータ

        Returns:
            話者分析結果
        """
        # 簡易的な話者検出（実際の話者分離は高度な処理が必要）
        return {
            'speaker_count': 1,  # 現在は1話者として扱う
            'distribution': {'Speaker 1': 100.0},
            'note': '話者分離機能は将来の実装予定です'
        }

    def _analyze_time_distribution(self, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        時間分布分析

        Args:
            segments: セグメントデータ

        Returns:
            時間分布分析結果
        """
        if not segments:
            return {}

        total_duration = max(seg.get('end', 0) for seg in segments) if segments else 0
        segment_count = len(segments)
        avg_segment_length = total_duration / segment_count if segment_count > 0 else 0

        # 10分間隔での分析
        interval_minutes = 10
        interval_seconds = interval_minutes * 60
        interval_count = int(total_duration // interval_seconds) + 1

        intervals = []
        for i in range(interval_count):
            start_time = i * interval_seconds
            end_time = min((i + 1) * interval_seconds, total_duration)

            # この区間のセグメント数をカウント
            segments_in_interval = sum(
                1 for seg in segments
                if seg.get('start', 0) < end_time and seg.get('end', 0) > start_time
            )

            intervals.append({
                'start': start_time,
                'end': end_time,
                'start_formatted': format_duration(start_time),
                'end_formatted': format_duration(end_time),
                'segment_count': segments_in_interval
            })

        return {
            'total_duration': total_duration,
            'total_duration_formatted': format_duration(total_duration),
            'segment_count': segment_count,
            'average_segment_length': avg_segment_length,
            'intervals': intervals
        }

    def _calculate_quality_metrics(self, transcript_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        品質メトリクスを計算

        Args:
            transcript_data: 文字起こしデータ

        Returns:
            品質メトリクス
        """
        segments = transcript_data.get('segments', [])
        text = transcript_data.get('text', '')

        if not segments:
            return {}

        # 信頼度メトリクス
        confidences = [seg.get('confidence', 0.0) for seg in segments]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # テキスト品質メトリクス
        total_words = len(text.split()) if text else 0
        total_chars = len(text) if text else 0

        return {
            'average_confidence': avg_confidence,
            'confidence_distribution': {
                'high': sum(1 for c in confidences if c > 0.8),
                'medium': sum(1 for c in confidences if 0.5 <= c <= 0.8),
                'low': sum(1 for c in confidences if c < 0.5)
            },
            'text_metrics': {
                'total_words': total_words,
                'total_characters': total_chars,
                'average_words_per_segment': total_words / len(segments) if segments else 0
            }
        }

    def _generate_recommendations(self, transcript_data: Dict[str, Any]) -> List[str]:
        """
        推奨事項を生成

        Args:
            transcript_data: 文字起こしデータ

        Returns:
            推奨事項のリスト
        """
        recommendations = []

        # 音声品質に基づく推奨
        quality_metrics = self._calculate_quality_metrics(transcript_data)
        avg_confidence = quality_metrics.get('average_confidence', 0.0)

        if avg_confidence < 0.6:
            recommendations.append("音声品質が低い可能性があります。より明瞭な音声での録音を推奨します。")

        if avg_confidence > 0.9:
            recommendations.append("優れた音声品質です。文字起こし精度が高いです。")

        # セグメント数に基づく推奨
        segments = transcript_data.get('segments', [])
        if len(segments) > 1000:
            recommendations.append("長時間の音声です。必要に応じてセクションに分割することを検討してください。")

        return recommendations

    def _save_analysis_files(self, analysis_result: Dict[str, Any], output_dir: Path) -> None:
        """
        分析結果をファイルに保存

        Args:
            analysis_result: 分析結果
            output_dir: 出力ディレクトリ
        """
        # 詳細な分析結果（JSON）
        analysis_file = output_dir / "analysis_detailed.json"
        with open(analysis_file, 'w', encoding='utf-8') as f:
            json.dump(analysis_result, f, ensure_ascii=False, indent=2)

        # 要約のみ（テキスト）
        summary_file = output_dir / "summary.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("=== 内容要約 ===\n")
            f.write(analysis_result.get('summary', {}).get('main_summary', '要約がありません'))
            f.write("\n\n=== 重要ポイント ===\n")
            for i, point in enumerate(analysis_result.get('key_points', [])[:10], 1):
                f.write(f"{i}. {point.get('point', '')}\n")

        self.logger.info(f"分析結果保存: {analysis_file}")
        self.logger.info(f"要約保存: {summary_file}")