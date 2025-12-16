#!/usr/bin/env python3
"""
VideoTranscriptAnalyzer (レジューム機能付き)
動画から文字起こし・要約・レポート生成を自動化する統合ツール

Usage:
    python video_transcript_analyzer.py --input <VIDEO_URL_or_FILE> [options]
    python video_transcript_analyzer.py --resume [options]
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
from modules.resume_manager import ResumeManager, ProcessStep, StepStatus

# 階層的要約モジュール（オプション）
try:
    from modules.hierarchical_analyzer import HierarchicalAnalyzer
    HIERARCHICAL_AVAILABLE = True
except ImportError:
    HIERARCHICAL_AVAILABLE = False

# 環境変数の読み込み
load_dotenv()


class VideoTranscriptAnalyzer:
    """メインの統合分析クラス（レジューム機能付き）"""

    def __init__(self, config_path: str = "config.yaml"):
        """
        初期化

        Args:
            config_path: 設定ファイルのパス
        """
        self.config = self._load_config(config_path)
        self.logger = setup_logging(self.config.get('logging', {}))

        # 作業ディレクトリ
        self.work_dir = Path(self.config.get('work_dir', './output'))
        self.work_dir.mkdir(parents=True, exist_ok=True)

        # レジュームマネージャー
        self.resume_manager = ResumeManager(self.work_dir)

        # APIキーの取得（環境変数優先）
        self.openai_api_key = os.getenv('OPENAI_API_KEY')

        # Ollama設定の確認
        analyzer_config = self.config.get('analyzer', {})
        ollama_config = analyzer_config.get('ollama_fallback', {})

        # Ollamaが有効かチェック
        self.is_ollama_enabled = (
            ollama_config.get('enabled', False) or
            (analyzer_config.get('api_base_url') and 'localhost:11434' in analyzer_config.get('api_base_url', ''))
        )

        # モジュールの初期化
        # ContentAnalyzer（AI分析）を先に初期化（Ollamaモデルのダウンロード/アンロードのため）
        self.analyzer = ContentAnalyzer(
            analyzer_config,
            self.openai_api_key
        )

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

        self.downloader = VideoDownloader(self.config.get('downloader', {}))

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

    def process_with_resume(self,
                            input_source: str,
                            output_dir: Optional[str] = None,
                            project_dir: Optional[Path] = None,
                            resume_from: Optional[ProcessStep] = None,
                            skip_download: bool = False,
                            skip_transcription: bool = False,
                            skip_analysis: bool = False) -> Dict[str, Any]:
        """
        レジューム機能を含むメイン処理

        Args:
            input_source: 入力ソース（URL、ファイルパス）
            output_dir: 出力ディレクトリ
            project_dir: 再開時のプロジェクトディレクトリ
            resume_from: 再開するステップ
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

        # プロジェクトディレクトリの作成または取得
        if project_dir:
            # レジューム時
            self.logger.info(f"📂 プロジェクトを再開: {project_dir.name}")
            status = self.resume_manager.load_status(project_dir)
            if status:
                # 前回の設定を復元
                input_source = status.get('input_source', input_source)
                results = status.get('results', {})
        else:
            # 新規プロジェクト
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            project_dir = self.work_dir / f"project_{timestamp}"
            project_dir.mkdir(parents=True, exist_ok=True)

            # ステータスファイルを作成
            status = self.resume_manager.create_project_status(
                project_dir, input_source, self.config
            )

        self.logger.info("=" * 60)
        self.logger.info("📹 VideoTranscriptAnalyzer - 処理開始")
        if resume_from:
            self.logger.info(f"🔄 {resume_from.display_name}から再開")
        self.logger.info("=" * 60)

        # 進捗表示
        print("\n" + self.resume_manager.get_progress_summary(project_dir))

        try:
            # ステップ1: 動画ダウンロード/準備
            if not skip_download and (not resume_from or resume_from.value <= ProcessStep.DOWNLOAD.value):
                if status['steps'][ProcessStep.DOWNLOAD.value]['status'] != StepStatus.COMPLETED.value:
                    self.logger.info("📥 ステップ1: 動画ダウンロード中...")
                    self.resume_manager.update_step_status(
                        project_dir, ProcessStep.DOWNLOAD, StepStatus.IN_PROGRESS
                    )

                    video_path = input_source
                    if input_source.startswith('http') or input_source.endswith('.m3u8'):
                        video_path = self.downloader.download(input_source, project_dir)
                        results['video_path'] = str(video_path)

                        self.resume_manager.update_step_status(
                            project_dir, ProcessStep.DOWNLOAD, StepStatus.COMPLETED,
                            output_file=str(video_path), progress=100
                        )
                        self.logger.info(f"✅ 動画保存先: {video_path}")
                    else:
                        video_path = Path(input_source)
                        if not video_path.exists():
                            raise FileNotFoundError(f"動画ファイルが見つかりません: {video_path}")
                        results['video_path'] = str(video_path)

                        self.resume_manager.update_step_status(
                            project_dir, ProcessStep.DOWNLOAD, StepStatus.SKIPPED
                        )
                else:
                    # 完了済みの場合はスキップ
                    video_path = Path(status['steps'][ProcessStep.DOWNLOAD.value].get('output_file', input_source))
                    results['video_path'] = str(video_path)
                    self.logger.info(f"✅ ダウンロード済み: {video_path}")
            else:
                video_path = Path(input_source)
                results['video_path'] = str(video_path)
                self.logger.info("⏭️ ステップ1: ダウンロードスキップ")

            # ステップ2: 音声抽出と文字起こし
            transcript_data = None
            if not skip_transcription and (not resume_from or resume_from.value <= ProcessStep.TRANSCRIBE.value):
                if status['steps'][ProcessStep.TRANSCRIBE.value]['status'] != StepStatus.COMPLETED.value:
                    self.logger.info("🎵 ステップ2: 音声抽出中...")
                    self.resume_manager.update_step_status(
                        project_dir, ProcessStep.TRANSCRIBE, StepStatus.IN_PROGRESS,
                        progress=0
                    )

                    audio_path = self.transcriber.extract_audio(video_path, project_dir)
                    results['audio_path'] = str(audio_path)

                    self.logger.info("📝 ステップ3: 文字起こし実行中...")
                    self.resume_manager.update_step_status(
                        project_dir, ProcessStep.TRANSCRIBE, StepStatus.IN_PROGRESS,
                        progress=30, message="文字起こし中..."
                    )

                    transcript_data = self.transcriber.transcribe(audio_path, project_dir)
                    results['transcript'] = transcript_data

                    # 文字起こし結果を保存
                    transcript_file = project_dir / "transcript.json"
                    with open(transcript_file, 'w', encoding='utf-8') as f:
                        json.dump(transcript_data, f, ensure_ascii=False, indent=2)

                    self.resume_manager.update_step_status(
                        project_dir, ProcessStep.TRANSCRIBE, StepStatus.COMPLETED,
                        progress=100,
                        output_file=str(transcript_file),
                        segments_processed=len(transcript_data.get('segments', [])),
                        total_segments=len(transcript_data.get('segments', []))
                    )
                    self.logger.info(f"✅ 文字起こし完了: {transcript_file}")
                else:
                    # 完了済みの場合は既存のデータを読み込む
                    transcript_file = Path(status['steps'][ProcessStep.TRANSCRIBE.value].get(
                        'output_file',
                        project_dir / "transcript.json"
                    ))
                    if transcript_file.exists():
                        with open(transcript_file, 'r', encoding='utf-8') as f:
                            transcript_data = json.load(f)
                        results['transcript'] = transcript_data
                        self.logger.info(f"✅ 文字起こし済み: {transcript_file}")
            else:
                self.logger.info("⏭️ ステップ2-3: 文字起こしスキップ")
                # 既存の文字起こしファイルを探す
                transcript_file = project_dir / "transcript.json"
                if transcript_file.exists():
                    with open(transcript_file, 'r', encoding='utf-8') as f:
                        transcript_data = json.load(f)
                    results['transcript'] = transcript_data

            # ステップ3: AI分析または階層的要約
            analysis_result = None
            if not skip_analysis and transcript_data and (not resume_from or resume_from.value <= ProcessStep.ANALYZE.value):
                step_to_update = ProcessStep.HIERARCHICAL if self.hierarchical_analyzer else ProcessStep.ANALYZE

                if status['steps'][step_to_update.value]['status'] != StepStatus.COMPLETED.value:
                    # 階層的要約が有効な場合は優先的に使用
                    if self.hierarchical_analyzer:
                        self.logger.info("🎯 ステップ4: 階層的要約実行中（LangChain + LlamaIndex）...")
                        self.resume_manager.update_step_status(
                            project_dir, ProcessStep.HIERARCHICAL, StepStatus.IN_PROGRESS,
                            progress=0, message="階層的要約処理中..."
                        )

                        try:
                            hierarchical_result = self.hierarchical_analyzer.analyze(transcript_data, project_dir)

                            # 進捗更新
                            self.resume_manager.update_step_status(
                                project_dir, ProcessStep.HIERARCHICAL, StepStatus.IN_PROGRESS,
                                progress=50, level1_done=True, message="Level 2処理中..."
                            )

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

                            self.resume_manager.update_step_status(
                                project_dir, ProcessStep.HIERARCHICAL, StepStatus.COMPLETED,
                                progress=100,
                                level1_done=True, level2_done=True, level3_done=True,
                                output_file=str(analysis_file)
                            )
                            self.logger.info(f"✅ 階層的要約完了: {analysis_file}")

                        except Exception as e:
                            self.logger.error(f"階層的要約エラー: {e}")
                            self.resume_manager.update_step_status(
                                project_dir, ProcessStep.HIERARCHICAL, StepStatus.ERROR,
                                error_message=str(e)
                            )

                            self.logger.info("通常のAI分析にフォールバック...")
                            # フォールバック: 通常のAI分析を試みる
                            if self.openai_api_key or self.is_ollama_enabled:
                                analysis_result = self.analyzer.analyze(transcript_data, project_dir)
                                results['analysis'] = analysis_result
                                self.resume_manager.update_step_status(
                                    project_dir, ProcessStep.ANALYZE, StepStatus.COMPLETED
                                )

                    # 通常のAI分析（OpenAI APIまたはOllamaが利用可能な場合）
                    elif self.openai_api_key or self.is_ollama_enabled:
                        self.logger.info("🤖 ステップ4: AI分析実行中...")
                        self.resume_manager.update_step_status(
                            project_dir, ProcessStep.ANALYZE, StepStatus.IN_PROGRESS,
                            progress=0, message="AI分析処理中..."
                        )

                        analysis_result = self.analyzer.analyze(transcript_data, project_dir)
                        results['analysis'] = analysis_result

                        # 分析結果を保存
                        analysis_file = project_dir / "analysis.json"
                        with open(analysis_file, 'w', encoding='utf-8') as f:
                            json.dump(analysis_result, f, ensure_ascii=False, indent=2)

                        self.resume_manager.update_step_status(
                            project_dir, ProcessStep.ANALYZE, StepStatus.COMPLETED,
                            progress=100, output_file=str(analysis_file)
                        )
                        self.logger.info(f"✅ AI分析完了: {analysis_file}")
                    else:
                        self.logger.warning("⚠️ AI分析スキップ（APIキー未設定かつOllamaも無効）")
                        self.resume_manager.update_step_status(
                            project_dir, ProcessStep.ANALYZE, StepStatus.SKIPPED
                        )
                else:
                    # 完了済みの場合は既存のデータを読み込む
                    analysis_file = Path(status['steps'][step_to_update.value].get(
                        'output_file',
                        project_dir / "analysis.json"
                    ))
                    if analysis_file.exists():
                        with open(analysis_file, 'r', encoding='utf-8') as f:
                            analysis_result = json.load(f)
                        results['analysis'] = analysis_result
                        self.logger.info(f"✅ 分析済み: {analysis_file}")
            elif skip_analysis:
                self.logger.info("⏭️ ステップ4: AI分析スキップ")

            # ステップ4: スクリーンショット抽出とレポート生成
            if not resume_from or resume_from.value <= ProcessStep.REPORT.value:
                if status['steps'][ProcessStep.REPORT.value]['status'] != StepStatus.COMPLETED.value:
                    self.logger.info("📸 ステップ5: スクリーンショット抽出中...")
                    self.resume_manager.update_step_status(
                        project_dir, ProcessStep.REPORT, StepStatus.IN_PROGRESS,
                        progress=30, message="スクリーンショット抽出中..."
                    )

                    screenshots = self.reporter.extract_screenshots(
                        video_path,
                        analysis_result if analysis_result else transcript_data,
                        project_dir
                    )
                    results['screenshots'] = screenshots

                    # レポート生成
                    self.logger.info("📄 ステップ6: レポート生成中...")
                    self.resume_manager.update_step_status(
                        project_dir, ProcessStep.REPORT, StepStatus.IN_PROGRESS,
                        progress=60, message="レポート生成中..."
                    )

                    report_files = self.reporter.generate_report(
                        transcript_data,
                        analysis_result,
                        screenshots,
                        project_dir
                    )
                    results['report'] = str(report_files)

                    self.resume_manager.update_step_status(
                        project_dir, ProcessStep.REPORT, StepStatus.COMPLETED,
                        progress=100,
                        output_files=[str(f) for f in report_files]
                    )
                    self.logger.info(f"✅ レポート生成完了: {report_files}")

            # 全体の結果を保存
            result_file = project_dir / "results.json"
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2, default=str)

            # 完了ステータスを更新
            self.resume_manager.update_step_status(
                project_dir, ProcessStep.COMPLETE, StepStatus.COMPLETED
            )

            self.logger.info("=" * 60)
            self.logger.info("🎉 全ての処理が完了しました！")
            self.logger.info(f"📁 出力ディレクトリ: {project_dir}")
            self.logger.info("=" * 60)

        except Exception as e:
            self.logger.error(f"❌ エラーが発生しました: {e}", exc_info=True)
            # エラー時にステータスを保存
            current_step = None
            for step in ProcessStep:
                if status['steps'][step.value]['status'] == StepStatus.IN_PROGRESS.value:
                    current_step = step
                    break
            if current_step:
                self.resume_manager.update_step_status(
                    project_dir, current_step, StepStatus.ERROR,
                    error_message=str(e)
                )
            results['error'] = str(e)
            raise

        return results

    def resume(self) -> Dict[str, Any]:
        """
        中断されたプロジェクトを再開

        Returns:
            処理結果
        """
        # プロジェクト選択メニューを表示
        selected = self.resume_manager.show_project_menu()

        if not selected:
            self.logger.info("レジュームがキャンセルされました")
            return {}

        project_dir, status = selected

        # ステップ選択メニューを表示
        resume_from = self.resume_manager.show_step_selection_menu(status)

        if not resume_from:
            self.logger.info("ステップ選択がキャンセルされました")
            return {}

        # 処理を再開
        return self.process_with_resume(
            input_source=status.get('input_source', ''),
            project_dir=project_dir,
            resume_from=resume_from
        )


def main():
    """メインエントリーポイント"""
    parser = argparse.ArgumentParser(
        description='動画から文字起こし・要約・レポートを自動生成（レジューム機能付き）'
    )

    # 入力オプション（--resumeと排他的）
    input_group = parser.add_mutually_exclusive_group(required=True)

    input_group.add_argument(
        '--input', '-i',
        help='入力ソース（動画URL、M3U8ストリームURL、またはローカルファイルパス）'
    )

    input_group.add_argument(
        '--resume', '-r',
        action='store_true',
        help='中断されたプロジェクトを再開'
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

        if args.resume:
            # レジュームモード
            results = analyzer.resume()
        else:
            # 通常モード
            results = analyzer.process_with_resume(
                input_source=args.input,
                output_dir=args.output,
                skip_download=args.skip_download,
                skip_transcription=args.skip_transcription,
                skip_analysis=args.skip_analysis
            )

        # 結果を表示
        if results:
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