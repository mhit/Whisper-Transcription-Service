#!/usr/bin/env python3
"""
VideoTranscriptAnalyzer
動画から文字起こし・要約・レポート生成を自動化する統合ツール

Usage:
    python video_transcript_analyzer.py --input <VIDEO_URL_or_FILE> [options]
"""

import argparse
import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
import yaml
from dotenv import load_dotenv

# モジュールのインポート
from modules.downloader import VideoDownloader
from modules.transcriber import AudioTranscriber
from modules.analyzer import ContentAnalyzer
from modules.reporter import ReportGenerator
from modules.utils import setup_logging, check_dependencies

# 階層的要約モジュール（オプション）
try:
    from modules.hierarchical_analyzer import HierarchicalAnalyzer
    HIERARCHICAL_AVAILABLE = True
except ImportError:
    HIERARCHICAL_AVAILABLE = False

# 環境変数の読み込み
load_dotenv()


class VideoTranscriptAnalyzer:
    """メインの統合分析クラス"""

    def __init__(self, config_path: str = "config.yaml"):
        """
        初期化

        Args:
            config_path: 設定ファイルのパス
        """
        self.config = self._load_config(config_path)
        self.logger = setup_logging(self.config.get('logging', {}))

        # 作業ディレクトリの設定
        self.work_dir = Path(self.config.get('work_dir', './output'))
        self.work_dir.mkdir(parents=True, exist_ok=True)

        # OpenAI APIキーまたはOllama設定の確認
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        analyzer_config = self.config.get('analyzer', {})
        ollama_config = analyzer_config.get('ollama_fallback', {})

        # Ollamaが有効かどうかを判定（重要: AI分析の実行条件に使用）
        self.is_ollama_enabled = (
            ollama_config.get('enabled', False) or
            (analyzer_config.get('api_base_url') and 'localhost:11434' in analyzer_config.get('api_base_url', ''))
        )

        # APIキーがなくてもOllamaが設定されていれば警告を出さない
        if not self.openai_api_key:
            if self.is_ollama_enabled:
                self.logger.info("Ollamaフォールバックが有効です。ローカルLLMを使用します。")
            elif analyzer_config.get('api_base_url'):
                self.logger.info(f"カスタムAPIエンドポイントが設定されています: {analyzer_config.get('api_base_url')}")
            else:
                self.logger.warning("警告: OPENAI_API_KEYが設定されていません。AI分析機能は制限されます。")

        # 各モジュールの初期化（メモリ効率を考慮した順序）
        self.downloader = VideoDownloader(self.config.get('downloader', {}))
        # Analyzerを先に初期化（Ollamaモデルをロード→アンロード）
        self.analyzer = ContentAnalyzer(self.config.get('analyzer', {}), self.openai_api_key)
        # その後Transcriberを初期化（Whisperモデルをロード）
        self.transcriber = AudioTranscriber(self.config.get('transcriber', {}))
        self.reporter = ReportGenerator(self.config.get('reporter', {}))

        # 階層的要約の初期化（利用可能な場合）
        self.hierarchical_analyzer = None
        hierarchical_config = self.config.get('hierarchical_summarization', {})
        if HIERARCHICAL_AVAILABLE and hierarchical_config.get('enabled', False):
            self.logger.info("階層的要約（LangChain + LlamaIndex）を初期化中...")
            try:
                # analyzer設定からapi_base_urlを階層的要約設定にコピー
                analyzer_config = self.config.get('analyzer', {})
                if 'api_base_url' in analyzer_config:
                    hierarchical_config['api_base_url'] = analyzer_config['api_base_url']

                self.hierarchical_analyzer = HierarchicalAnalyzer(hierarchical_config)
                self.logger.info("✅ 階層的要約システムが有効です")
            except Exception as e:
                self.logger.warning(f"階層的要約の初期化に失敗: {e}")
                self.logger.info("通常の要約モードで続行します")
        elif hierarchical_config.get('enabled', False) and not HIERARCHICAL_AVAILABLE:
            self.logger.warning("階層的要約が有効に設定されていますが、依存関係がインストールされていません")
            self.logger.info("pip install -r requirements_hierarchical.txt を実行してください")

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """設定ファイルを読み込む"""
        config_file = Path(config_path)
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        else:
            # デフォルト設定
            return {
                'work_dir': './output',
                'logging': {
                    'level': 'INFO',
                    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                },
                'downloader': {
                    'format': 'best',
                    'timeout': 3600
                },
                'transcriber': {
                    'model': 'large-v3',
                    'language': 'ja',
                    'device': 'cuda'
                },
                'analyzer': {
                    'model': 'gpt-4-turbo-preview',
                    'temperature': 0.7,
                    'max_tokens': 4000
                },
                'reporter': {
                    'format': 'markdown',
                    'include_screenshots': True,
                    'screenshot_count': 10
                }
            }

    def process(self,
                input_source: str,
                output_dir: Optional[str] = None,
                skip_download: bool = False,
                skip_transcription: bool = False,
                skip_analysis: bool = False) -> Dict[str, Any]:
        """
        メイン処理を実行

        Args:
            input_source: 入力ソース（URL、ファイルパス）
            output_dir: 出力ディレクトリ
            skip_download: ダウンロードをスキップ
            skip_transcription: 文字起こしをスキップ
            skip_analysis: AI分析をスキップ

        Returns:
            処理結果の辞書
        """
        results = {}

        # 出力ディレクトリの設定
        if output_dir:
            self.work_dir = Path(output_dir)
            self.work_dir.mkdir(parents=True, exist_ok=True)

        # タイムスタンプ付きプロジェクトディレクトリ作成
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        project_dir = self.work_dir / f"project_{timestamp}"
        project_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info("=" * 60)
        self.logger.info("📹 VideoTranscriptAnalyzer - 処理開始")
        self.logger.info("=" * 60)

        try:
            # ステップ1: 動画ダウンロード/準備
            video_path = input_source
            if not skip_download and (input_source.startswith('http') or input_source.endswith('.m3u8')):
                self.logger.info("📥 ステップ1: 動画ダウンロード中...")
                video_path = self.downloader.download(input_source, project_dir)
                results['video_path'] = str(video_path)
                self.logger.info(f"✅ 動画保存先: {video_path}")
            else:
                self.logger.info("⏭️ ステップ1: ダウンロードスキップ（ローカルファイル使用）")
                video_path = Path(input_source)
                if not video_path.exists():
                    raise FileNotFoundError(f"動画ファイルが見つかりません: {video_path}")
                results['video_path'] = str(video_path)

            # ステップ2: 音声抽出と文字起こし
            if not skip_transcription:
                self.logger.info("🎵 ステップ2: 音声抽出中...")
                audio_path = self.transcriber.extract_audio(video_path, project_dir)
                results['audio_path'] = str(audio_path)

                self.logger.info("📝 ステップ3: 文字起こし実行中...")
                transcript_data = self.transcriber.transcribe(audio_path, project_dir)
                results['transcript'] = transcript_data

                # 文字起こし結果を保存
                transcript_file = project_dir / "transcript.json"
                with open(transcript_file, 'w', encoding='utf-8') as f:
                    json.dump(transcript_data, f, ensure_ascii=False, indent=2)
                self.logger.info(f"✅ 文字起こし完了: {transcript_file}")
            else:
                self.logger.info("⏭️ ステップ2-3: 文字起こしスキップ")
                # 既存の文字起こしファイルを探す
                transcript_file = project_dir / "transcript.json"
                if transcript_file.exists():
                    with open(transcript_file, 'r', encoding='utf-8') as f:
                        transcript_data = json.load(f)
                    results['transcript'] = transcript_data
                else:
                    self.logger.warning("警告: 文字起こしデータが見つかりません")
                    transcript_data = None

            # ステップ3: AI分析または階層的要約
            if not skip_analysis and transcript_data:
                # 階層的要約が有効な場合は優先的に使用
                if self.hierarchical_analyzer:
                    self.logger.info("🎯 ステップ4: 階層的要約実行中（LangChain + LlamaIndex）...")
                    try:
                        hierarchical_result = self.hierarchical_analyzer.analyze(transcript_data, project_dir)

                        # 階層的要約の結果を通常の分析形式に変換
                        analysis_result = {
                            'summary': {'main_summary': hierarchical_result.level3_summary.get('text', '')},
                            'key_points': [moment['preview'] for moment in hierarchical_result.key_moments[:5]],
                            'hierarchical_summaries': {
                                'level1': hierarchical_result.level1_summaries,
                                'level2': hierarchical_result.level2_summaries,
                                'level3': hierarchical_result.level3_summary
                            },
                            'key_moments': hierarchical_result.key_moments,
                            'metadata': hierarchical_result.metadata
                        }
                        results['analysis'] = analysis_result

                        # 分析結果を保存
                        analysis_file = project_dir / "hierarchical_analysis.json"
                        with open(analysis_file, 'w', encoding='utf-8') as f:
                            json.dump(analysis_result, f, ensure_ascii=False, indent=2)
                        self.logger.info(f"✅ 階層的要約完了: {analysis_file}")

                    except Exception as e:
                        self.logger.error(f"階層的要約エラー: {e}")
                        self.logger.info("通常のAI分析にフォールバック...")
                        # フォールバック: 通常のAI分析を試みる
                        if self.openai_api_key or self.is_ollama_enabled:
                            analysis_result = self.analyzer.analyze(transcript_data, project_dir)
                            results['analysis'] = analysis_result
                        else:
                            analysis_result = None

                # 通常のAI分析（OpenAI APIまたはOllamaが利用可能な場合）
                elif self.openai_api_key or self.is_ollama_enabled:
                    self.logger.info("🤖 ステップ4: AI分析実行中...")
                    analysis_result = self.analyzer.analyze(transcript_data, project_dir)
                    results['analysis'] = analysis_result

                    # 分析結果を保存
                    analysis_file = project_dir / "analysis.json"
                    with open(analysis_file, 'w', encoding='utf-8') as f:
                        json.dump(analysis_result, f, ensure_ascii=False, indent=2)
                    self.logger.info(f"✅ AI分析完了: {analysis_file}")
                else:
                    self.logger.warning("⚠️ AI分析スキップ（APIキー未設定かつOllamaも無効）")
                    analysis_result = None

            elif skip_analysis:
                self.logger.info("⏭️ ステップ4: AI分析スキップ")
                analysis_result = None
            else:
                self.logger.warning("⚠️ AI分析スキップ（文字起こしデータなし）")
                analysis_result = None

            # ステップ4: スクリーンショット抽出
            self.logger.info("📸 ステップ5: スクリーンショット抽出中...")
            screenshots = self.reporter.extract_screenshots(
                video_path,
                analysis_result if analysis_result else transcript_data,
                project_dir
            )
            results['screenshots'] = screenshots
            self.logger.info(f"✅ {len(screenshots)}枚のスクリーンショットを抽出")

            # ステップ5: レポート生成
            self.logger.info("📊 ステップ6: レポート生成中...")
            report_path = self.reporter.generate_report(
                transcript_data,
                analysis_result,
                screenshots,
                project_dir
            )
            results['report'] = str(report_path)
            self.logger.info(f"✅ レポート生成完了: {report_path}")

            # 処理サマリーを保存
            summary_file = project_dir / "processing_summary.json"
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2, default=str)

            self.logger.info("=" * 60)
            self.logger.info("🎉 全ての処理が完了しました！")
            self.logger.info(f"📁 出力ディレクトリ: {project_dir}")
            self.logger.info("=" * 60)

        except Exception as e:
            self.logger.error(f"❌ エラーが発生しました: {e}", exc_info=True)
            results['error'] = str(e)
            raise

        return results


def main():
    """メインエントリーポイント"""
    parser = argparse.ArgumentParser(
        description='動画から文字起こし・要約・レポートを自動生成'
    )

    parser.add_argument(
        '--input', '-i',
        required=True,
        help='入力ソース（動画URL、M3U8ストリームURL、またはローカルファイルパス）'
    )

    parser.add_argument(
        '--output', '-o',
        help='出力ディレクトリ（デフォルト: ./output）'
    )

    parser.add_argument(
        '--config', '-c',
        default='config.yaml',
        help='設定ファイルのパス（デフォルト: config.yaml）'
    )

    parser.add_argument(
        '--skip-download',
        action='store_true',
        help='動画ダウンロードをスキップ（ローカルファイルを使用）'
    )

    parser.add_argument(
        '--skip-transcription',
        action='store_true',
        help='文字起こしをスキップ（既存データを使用）'
    )

    parser.add_argument(
        '--skip-analysis',
        action='store_true',
        help='AI分析をスキップ'
    )

    parser.add_argument(
        '--api-key',
        help='OpenAI APIキー（環境変数OPENAI_API_KEYより優先）'
    )

    args = parser.parse_args()

    # APIキーの設定
    if args.api_key:
        os.environ['OPENAI_API_KEY'] = args.api_key

    # 依存関係の確認
    try:
        check_dependencies()
    except Exception as e:
        print(f"❌ 依存関係エラー: {e}")
        print("必要なツールをインストールしてください（詳細はREADME.mdを参照）")
        sys.exit(1)

    # メイン処理実行
    try:
        analyzer = VideoTranscriptAnalyzer(args.config)
        results = analyzer.process(
            input_source=args.input,
            output_dir=args.output,
            skip_download=args.skip_download,
            skip_transcription=args.skip_transcription,
            skip_analysis=args.skip_analysis
        )

        # 結果を表示
        print("\n📊 処理結果サマリー:")
        print("-" * 40)
        if 'video_path' in results:
            print(f"動画: {results['video_path']}")
        if 'transcript' in results:
            print(f"文字起こし: {len(results['transcript'].get('segments', []))}セグメント")
        if 'analysis' in results:
            if 'hierarchical_summaries' in results['analysis']:
                print(f"階層的要約: 完了（3層構造）")
                if 'key_moments' in results['analysis']:
                    print(f"  - 重要な瞬間: {len(results['analysis']['key_moments'])}箇所")
            else:
                print(f"AI分析: 完了")
        if 'screenshots' in results:
            print(f"スクリーンショット: {len(results['screenshots'])}枚")
        if 'report' in results:
            print(f"レポート: {results['report']}")

        sys.exit(0)

    except Exception as e:
        print(f"❌ 実行エラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()