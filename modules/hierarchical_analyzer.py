"""
階層的要約分析モジュール（LangChain + LlamaIndex）

長時間動画の文字起こしを階層的に要約：
- LlamaIndexで構造化インデックス
- LangChainでMap-Reduce要約
- 段階的な情報集約（10→5→2.5→1）
"""

import logging
import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
from dataclasses import dataclass

# LangChain imports
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.summarize import load_summarize_chain
from langchain.prompts import PromptTemplate
from langchain_community.callbacks.manager import get_openai_callback
from langchain_community.llms import Ollama

# LlamaIndex imports
from llama_index.core import Document, VectorStoreIndex, StorageContext
from llama_index.core.node_parser import HierarchicalNodeParser, SimpleNodeParser
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.llms.ollama import Ollama as LlamaOllama


@dataclass
class HierarchicalSummaryResult:
    """階層的要約の結果を格納"""
    level1_summaries: List[Dict[str, Any]]  # 詳細要約（10分ごと）
    level2_summaries: List[Dict[str, Any]]  # 中間要約（30分ごと）
    level3_summary: Dict[str, Any]          # 最終要約（全体）
    importance_scores: Dict[str, float]     # 重要度スコア
    key_moments: List[Dict[str, Any]]       # 重要な瞬間
    metadata: Dict[str, Any]                # メタ情報


class HierarchicalAnalyzer:
    """LangChain + LlamaIndexを使った階層的要約クラス"""

    def __init__(self, config: Dict[str, Any]):
        """
        初期化

        Args:
            config: 設定辞書
        """
        self.config = config
        self.logger = logging.getLogger('VideoTranscriptAnalyzer.hierarchical')

        # 階層設定
        self.levels = config.get('levels', 3)
        self.segment_duration = config.get('segment_duration', 600)  # 10分
        self.reduction_ratio = config.get('reduction_ratio', 0.4)   # 各層で40%に圧縮

        # モデル設定
        self.model_name = config.get('model', 'gpt-oss:20b')
        self.temperature = config.get('temperature', 0.3)
        self.max_tokens = config.get('max_tokens', 2000)

        # API設定を取得（LangChain用にbase_urlを調整）
        self.api_base_url = config.get('api_base_url')
        if self.api_base_url:
            # LangChainのOllamaは/v1エンドポイントを使わないので除去
            if self.api_base_url.endswith('/v1'):
                self.api_base_url = self.api_base_url[:-3]
                self.logger.info(f"LangChain用にURLを調整: {self.api_base_url}")
        else:
            # デフォルトのOllamaエンドポイント
            self.api_base_url = 'http://localhost:11434'

        # LLMの初期化（Ollama）
        self.llm = self._initialize_llm()

        # インデックスストレージ
        self.storage_context = None
        self.hierarchical_index = None

        # キャッシュディレクトリ
        self.cache_dir = Path(config.get('cache_dir', './cache'))
        self.cache_dir.mkdir(exist_ok=True)

    def _initialize_llm(self):
        """LLMを初期化（LangChain用）"""
        self.logger.info(f"Ollamaを初期化中: {self.api_base_url} (モデル: {self.model_name})")
        return Ollama(
            model=self.model_name,
            temperature=self.temperature,
            num_predict=self.max_tokens,
            base_url=self.api_base_url  # 設定から取得したURLを使用
        )

    def analyze(self,
                transcript_data: Dict[str, Any],
                output_dir: Path) -> HierarchicalSummaryResult:
        """
        階層的要約を実行

        Args:
            transcript_data: 文字起こしデータ
            output_dir: 出力ディレクトリ

        Returns:
            階層的要約結果
        """
        self.logger.info("階層的要約分析を開始...")
        start_time = time.time()

        try:
            # 1. セグメントの準備
            segments = self._prepare_segments(transcript_data)
            self.logger.info(f"セグメント数: {len(segments)}")

            # 2. LlamaIndexで階層的インデックスを構築
            hierarchical_nodes = self._build_hierarchical_index(segments)
            self.logger.info(f"階層的ノード構築完了: {len(hierarchical_nodes)}ノード")

            # 3. Level 1: 詳細要約（各セグメント）
            level1_summaries = self._process_level1(segments)
            self.logger.info(f"Level 1完了: {len(level1_summaries)}個の詳細要約")

            # 4. Level 2: 中間要約（グループ化）
            level2_summaries = self._process_level2(level1_summaries)
            self.logger.info(f"Level 2完了: {len(level2_summaries)}個の中間要約")

            # 5. Level 3: 最終要約（全体統合）
            level3_summary = self._process_level3(level2_summaries)
            self.logger.info("Level 3完了: 最終要約生成")

            # 6. 重要度スコアリング
            importance_scores = self._calculate_importance_scores(
                level1_summaries, level2_summaries, hierarchical_nodes
            )

            # 7. 重要な瞬間の抽出
            key_moments = self._extract_key_moments(
                segments, importance_scores, threshold=0.7
            )

            # 結果をまとめる
            result = HierarchicalSummaryResult(
                level1_summaries=level1_summaries,
                level2_summaries=level2_summaries,
                level3_summary=level3_summary,
                importance_scores=importance_scores,
                key_moments=key_moments,
                metadata={
                    'processing_time': time.time() - start_time,
                    'total_segments': len(segments),
                    'model_used': self.model_name,
                    'reduction_achieved': self._calculate_reduction_ratio(
                        transcript_data.get('text', ''),
                        level3_summary.get('text', '')
                    )
                }
            )

            # 結果を保存
            self._save_results(result, output_dir)

            self.logger.info(f"✅ 階層的要約完了（{result.metadata['processing_time']:.1f}秒）")
            return result

        except Exception as e:
            self.logger.error(f"階層的要約エラー: {e}", exc_info=True)
            raise

    def _prepare_segments(self, transcript_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        トランスクリプトをセグメントに分割

        Args:
            transcript_data: 文字起こしデータ

        Returns:
            セグメントのリスト
        """
        segments = transcript_data.get('segments', [])
        if not segments:
            # セグメントがない場合はテキストから作成
            text = transcript_data.get('text', '')
            return self._create_time_based_segments(text)

        # タイムスタンプベースでグループ化
        grouped_segments = []
        current_group = []
        current_duration = 0

        for segment in segments:
            duration = segment.get('end', 0) - segment.get('start', 0)

            if current_duration + duration > self.segment_duration:
                # 現在のグループを保存
                if current_group:
                    grouped_segments.append({
                        'text': ' '.join([s['text'] for s in current_group]),
                        'start': current_group[0].get('start', 0),
                        'end': current_group[-1].get('end', 0),
                        'segments': current_group
                    })
                # 新しいグループを開始
                current_group = [segment]
                current_duration = duration
            else:
                current_group.append(segment)
                current_duration += duration

        # 最後のグループを追加
        if current_group:
            grouped_segments.append({
                'text': ' '.join([s['text'] for s in current_group]),
                'start': current_group[0].get('start', 0),
                'end': current_group[-1].get('end', 0),
                'segments': current_group
            })

        return grouped_segments

    def _build_hierarchical_index(self, segments: List[Dict[str, Any]]) -> List[Any]:
        """
        LlamaIndexで階層的インデックスを構築

        Args:
            segments: セグメントリスト

        Returns:
            階層的ノード
        """
        # ドキュメントの作成
        documents = []
        for i, segment in enumerate(segments):
            doc = Document(
                text=segment['text'],
                metadata={
                    'segment_id': i,
                    'start_time': segment.get('start', 0),
                    'end_time': segment.get('end', 0)
                }
            )
            documents.append(doc)

        # 階層的ノードパーサーの設定
        node_parser = HierarchicalNodeParser.from_defaults(
            chunk_sizes=[2048, 1024, 512],  # 3層のチャンクサイズ
            chunk_overlap=200
        )

        # ノードの取得
        nodes = node_parser.get_nodes_from_documents(documents)

        # ストレージコンテキストの作成
        docstore = SimpleDocumentStore()
        docstore.add_documents(nodes)
        self.storage_context = StorageContext.from_defaults(docstore=docstore)

        return nodes

    def _process_level1(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Level 1: 詳細要約を生成（各セグメント）

        Args:
            segments: セグメントリスト

        Returns:
            詳細要約リスト
        """
        summaries = []

        # プロンプトテンプレート
        map_prompt = PromptTemplate(
            template="""以下は動画の一部分の文字起こしです。
時間: {start_time}秒 〜 {end_time}秒

内容:
{text}

この部分の要点を、以下の観点から簡潔にまとめてください：
1. 主な話題やテーマ
2. 重要なポイントや結論
3. 具体例や説明
4. 次の内容への繋がり

要約:""",
            input_variables=["text", "start_time", "end_time"]
        )

        for segment in segments:
            try:
                # LangChainで要約
                summary_text = self.llm.invoke(
                    map_prompt.format(
                        text=segment['text'][:3000],  # コンテキスト制限
                        start_time=segment.get('start', 0),
                        end_time=segment.get('end', 0)
                    )
                )

                summaries.append({
                    'segment_id': len(summaries),
                    'text': summary_text,
                    'original_text': segment['text'],
                    'start_time': segment.get('start', 0),
                    'end_time': segment.get('end', 0),
                    'word_count': len(segment['text'].split())
                })

            except Exception as e:
                self.logger.warning(f"セグメント要約失敗: {e}")
                summaries.append({
                    'segment_id': len(summaries),
                    'text': segment['text'][:500] + "...",  # フォールバック
                    'original_text': segment['text'],
                    'start_time': segment.get('start', 0),
                    'end_time': segment.get('end', 0),
                    'error': str(e)
                })

        return summaries

    def _process_level2(self, level1_summaries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Level 2: 中間要約を生成（グループ化）

        Args:
            level1_summaries: Level 1の要約リスト

        Returns:
            中間要約リスト
        """
        # 3つずつグループ化
        group_size = 3
        groups = [level1_summaries[i:i+group_size]
                 for i in range(0, len(level1_summaries), group_size)]

        combine_prompt = PromptTemplate(
            template="""以下は動画の複数セクションの要約です。

{summaries}

これらの要約を統合して、以下の観点から包括的な要約を作成してください：
1. 全体のメインテーマ
2. セクション間の関連性
3. 最も重要なポイント（上位3つ）
4. 全体の流れや構成

統合要約:""",
            input_variables=["summaries"]
        )

        level2_summaries = []
        for group in groups:
            combined_text = "\n\n".join([
                f"[{s['start_time']:.1f}秒-{s['end_time']:.1f}秒]\n{s['text']}"
                for s in group
            ])

            try:
                summary_text = self.llm.invoke(
                    combine_prompt.format(summaries=combined_text[:4000])
                )

                level2_summaries.append({
                    'group_id': len(level2_summaries),
                    'text': summary_text,
                    'source_segments': [s['segment_id'] for s in group],
                    'start_time': group[0]['start_time'],
                    'end_time': group[-1]['end_time']
                })

            except Exception as e:
                self.logger.warning(f"グループ要約失敗: {e}")
                level2_summaries.append({
                    'group_id': len(level2_summaries),
                    'text': combined_text[:1000],
                    'source_segments': [s['segment_id'] for s in group],
                    'error': str(e)
                })

        return level2_summaries

    def _process_level3(self, level2_summaries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Level 3: 最終要約を生成（全体統合）

        Args:
            level2_summaries: Level 2の要約リスト

        Returns:
            最終要約
        """
        final_prompt = PromptTemplate(
            template="""以下は長時間動画の段階的な要約です。

{summaries}

これらを基に、動画全体の包括的な要約を作成してください：

【構成】
1. 概要（2-3文）
2. 主要テーマ（箇条書き）
3. 重要ポイント（上位5つ、具体的に）
4. 結論や要点
5. 推奨アクション（もしあれば）

最終要約:""",
            input_variables=["summaries"]
        )

        all_summaries = "\n\n".join([
            f"[パート{s['group_id']+1}]\n{s['text']}"
            for s in level2_summaries
        ])

        try:
            final_text = self.llm.invoke(
                final_prompt.format(summaries=all_summaries[:5000])
            )

            return {
                'text': final_text,
                'source_groups': [s['group_id'] for s in level2_summaries],
                'total_duration': level2_summaries[-1]['end_time'] if level2_summaries else 0
            }

        except Exception as e:
            self.logger.error(f"最終要約生成失敗: {e}")
            return {
                'text': "要約生成に失敗しました",
                'error': str(e)
            }

    def _calculate_importance_scores(self,
                                    level1: List[Dict],
                                    level2: List[Dict],
                                    nodes: List[Any]) -> Dict[str, float]:
        """
        重要度スコアを計算

        Args:
            level1: Level 1要約
            level2: Level 2要約
            nodes: 階層的ノード

        Returns:
            重要度スコア辞書
        """
        scores = {}

        # 各セグメントの重要度を計算
        for summary in level1:
            segment_id = f"segment_{summary['segment_id']}"

            # 要約の長さ（重要な部分は詳しく要約される傾向）
            length_score = len(summary['text']) / 1000.0

            # キーワードの頻度
            keywords = ['重要', '注意', 'ポイント', '結論', 'まとめ']
            keyword_score = sum(1 for kw in keywords if kw in summary['text']) / len(keywords)

            # Level 2での言及回数
            mention_score = sum(
                1 for l2 in level2
                if summary['segment_id'] in l2.get('source_segments', [])
            ) / max(len(level2), 1)

            # 総合スコア
            scores[segment_id] = (length_score + keyword_score + mention_score) / 3

        return scores

    def _extract_key_moments(self,
                            segments: List[Dict],
                            importance_scores: Dict[str, float],
                            threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        重要な瞬間を抽出

        Args:
            segments: セグメントリスト
            importance_scores: 重要度スコア
            threshold: 閾値

        Returns:
            重要な瞬間のリスト
        """
        key_moments = []

        for i, segment in enumerate(segments):
            score = importance_scores.get(f"segment_{i}", 0)

            if score >= threshold:
                key_moments.append({
                    'segment_id': i,
                    'start_time': segment.get('start', 0),
                    'end_time': segment.get('end', 0),
                    'importance_score': score,
                    'preview': segment['text'][:200] + "...",
                    'reason': self._determine_importance_reason(segment['text'])
                })

        # スコア順にソート
        key_moments.sort(key=lambda x: x['importance_score'], reverse=True)

        return key_moments[:10]  # トップ10を返す

    def _determine_importance_reason(self, text: str) -> str:
        """重要な理由を判定"""
        if '結論' in text or 'まとめ' in text:
            return "結論・まとめ"
        elif '重要' in text or 'ポイント' in text:
            return "重要ポイント"
        elif '例えば' in text or '具体的に' in text:
            return "具体例"
        elif '注意' in text or '気をつけ' in text:
            return "注意事項"
        else:
            return "キーコンテンツ"

    def _calculate_reduction_ratio(self, original_text: str, summary_text: str) -> float:
        """圧縮率を計算"""
        if not original_text:
            return 0.0
        return 1.0 - (len(summary_text) / len(original_text))

    def _save_results(self, result: HierarchicalSummaryResult, output_dir: Path):
        """結果を保存"""
        # 各レベルの要約を保存
        (output_dir / 'level1_detailed.json').write_text(
            json.dumps(result.level1_summaries, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )

        (output_dir / 'level2_intermediate.json').write_text(
            json.dumps(result.level2_summaries, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )

        (output_dir / 'level3_final.json').write_text(
            json.dumps(result.level3_summary, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )

        (output_dir / 'key_moments.json').write_text(
            json.dumps(result.key_moments, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )

        # 統合レポートも作成
        report = {
            'final_summary': result.level3_summary['text'],
            'key_moments': result.key_moments,
            'metadata': result.metadata
        }

        (output_dir / 'hierarchical_summary_report.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )

        self.logger.info(f"階層的要約結果を保存: {output_dir}")

    def _create_time_based_segments(self, text: str) -> List[Dict[str, Any]]:
        """テキストから時間ベースのセグメントを作成（フォールバック）"""
        words = text.split()
        words_per_segment = 1000  # 約10分相当
        segments = []

        for i in range(0, len(words), words_per_segment):
            segment_words = words[i:i+words_per_segment]
            segments.append({
                'text': ' '.join(segment_words),
                'start': i * 10,  # 仮の時間
                'end': (i + len(segment_words)) * 10
            })

        return segments