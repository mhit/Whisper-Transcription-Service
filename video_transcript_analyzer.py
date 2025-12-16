#!/usr/bin/env python3
"""
VideoTranscriptAnalyzer (Gemini専用版)
動画から文字起こし・要約・レポート生成を自動化する統合ツール
すべての分析・要約をGeminiで実行

Usage:
    python video_transcript_analyzer_gemini_only.py --input <VIDEO_URL_or_FILE> [options]
    python video_transcript_analyzer_gemini_only.py --resume [options]
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Union
from enum import Enum
import yaml
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()

# モジュールのインポート
from modules.downloader import VideoDownloader
from modules.transcriber import AudioTranscriber
from modules.reporter import ReportGenerator
from modules.utils import setup_logging, check_dependencies
from modules.resume_manager import ResumeManager, ProcessStep, StepStatus

# Gemini Ultimate Generatorのインポート
try:
    from modules.gemini_ultimate_generator import GeminiUltimateGenerator
    GEMINI_AVAILABLE = True
except ImportError:
    print("⚠️ Gemini Ultimate Generator が見つかりません")
    GEMINI_AVAILABLE = False
    sys.exit(1)


class VideoTranscriptAnalyzerGeminiOnly:
    """Gemini専用の統合分析クラス（レジューム機能付き）"""

    def _ensure_transcriber_loaded(self):
        """音声文字起こしモジュールを必要時にロード"""
        if self.transcriber is None:
            self.logger.info("🎙️ Whisperモデルを初期化中...")
            self.transcriber = AudioTranscriber(self.transcriber_config)
            self.logger.info("✅ Whisperモデル読み込み完了")

    def __init__(self, config_path: str = 'config.yaml'):
        """
        初期化

        Args:
            config_path: 設定ファイルのパス
        """
        # ロガーの設定
        self.logger = setup_logging(self.__class__.__name__)

        # 設定ファイルの読み込み
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        # configが正しく読み込まれたか確認
        if not isinstance(self.config, dict):
            self.logger.error(f"❌ configが辞書ではありません: {type(self.config)}")
            sys.exit(1)

        # レジュームマネージャーの初期化
        self.resume_manager = ResumeManager()

        # 作業ディレクトリの設定
        self.work_dir = Path(self.config.get('work_dir', './output'))
        self.work_dir.mkdir(parents=True, exist_ok=True)

        # Gemini APIキーの取得
        gemini_config = self.config.get('gemini', {})

        # 優先順位: 環境変数 > config.yaml
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        if not self.gemini_api_key:
            self.gemini_api_key = gemini_config.get('api_key')

        if not self.gemini_api_key:
            self.logger.error("❌ Gemini APIキーが設定されていません")
            self.logger.error("   環境変数 GEMINI_API_KEY または config.yaml の gemini.api_key を設定してください")
            sys.exit(1)

        # Geminiモデル名
        self.gemini_model = os.getenv('GEMINI_MODEL')
        if not self.gemini_model:
            self.gemini_model = gemini_config.get('model', 'gemini-1.5-pro')

        # モジュールの初期化設定を保持（遅延ロード用）
        self.transcriber_config = self.config.get('transcriber', {})

        # 初期化時はNoneに設定（必要時にロード）
        self.transcriber = None
        self.reporter = ReportGenerator(self.config.get('reporter', {}))

        # Gemini Ultimate Generatorの初期化
        self.gemini_generator = None
        if GEMINI_AVAILABLE and self.gemini_api_key:
            self.logger.info("🚀 Gemini Ultimate Generator を初期化中...")
            self.logger.info(f"  📝 APIキー取得元: {'環境変数' if os.getenv('GEMINI_API_KEY') else 'config.yaml'}")
            self.logger.info(f"  📝 モデル: {self.gemini_model}")

            try:
                self.gemini_generator = GeminiUltimateGenerator(
                    api_key=self.gemini_api_key,
                    model_name=self.gemini_model
                )
                self.logger.info("✅ Gemini Ultimate Generator 準備完了")
                self.logger.info("  ➡ 100点品質レポート生成が可能です")
            except Exception as e:
                self.logger.error(f"❌ Gemini初期化エラー: {e}")
                sys.exit(1)

        # ビデオダウンローダーの初期化
        self.downloader = VideoDownloader(self.config.get('downloader', {}))

        # 処理時間の記録
        self.process_times = {}

    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        """
        デフォルト設定を取得

        Returns:
            デフォルトの設定辞書
        """
        return {
            'work_dir': './output',
            'logging': {
                'level': 'INFO'
            },
            'downloader': {
                'format': 'best'
            },
            'transcriber': {
                'model': 'large-v3',
                'language': 'ja',
                'device': 'cuda'
            },
            'reporter': {
                'format': 'both'
            },
            'gemini': {
                'model': 'gemini-1.5-pro',
                'temperature': 0.7,
                'max_tokens': 32000
            }
        }

    def process_with_resume(self, input_source: str,
                            output_dir: Optional[str] = None,
                            whisper_model: Optional[str] = None,
                            skip_transcription: bool = False,
                            skip_analysis: bool = False) -> Dict[str, Any]:
        """
        レジューム機能を含むメイン処理

        Args:
            input_source: 動画のURL/パス
            output_dir: 出力ディレクトリ（Noneの場合は自動生成）
            whisper_model: Whisperのモデル名（オプション）
            skip_transcription: 文字起こしをスキップ
            skip_analysis: AI分析をスキップ

        Returns:
            処理結果
        """
        try:
            return self._process_internal(
                input_source=input_source,
                output_dir=output_dir,
                whisper_model=whisper_model,
                skip_transcription=skip_transcription,
                skip_analysis=skip_analysis
            )
        except AttributeError as e:
            self.logger.error(f"❌ process_with_resumeでAttributeError: {e}")
            import traceback
            traceback.print_exc()
            return {'status': 'error', 'message': f'AttributeError: {e}'}

    def resume(self, project_dir: Optional[str] = None,
              restart_from: Optional[str] = None) -> Dict[str, Any]:
        """
        中断したプロジェクトを再開

        Args:
            project_dir: 再開するプロジェクトディレクトリ
            restart_from: 再開するステップ

        Returns:
            処理結果
        """
        try:
            # プロジェクトが指定されていない場合は選択メニューを表示
            if not project_dir:
                try:
                    selected = self.resume_manager.show_project_menu()
                except AttributeError as e:
                    self.logger.error(f"❌ show_project_menu()でAttributeError: {e}")
                    return {'status': 'error', 'message': f'Menu error: {e}'}
                except Exception as e:
                    self.logger.error(f"❌ show_project_menu()でエラー: {e}")
                    return {'status': 'error', 'message': f'Menu error: {e}'}

                if not selected:
                    self.logger.error("プロジェクトが選択されませんでした")
                    return {'status': 'error', 'message': 'No project selected'}
                project_dir, status = selected
            else:
                # プロジェクトディレクトリが指定されている場合はステータスをロード
                # 文字列をPathオブジェクトに変換
                project_dir = Path(project_dir)
                status = self.resume_manager.load_status(project_dir)
        except AttributeError as e:
            self.logger.error(f"❌ resume初期処理でAttributeError: {e}")
            import traceback
            traceback.print_exc()
            return {'status': 'error', 'message': f'AttributeError in resume: {e}'}
        if not status:
            self.logger.error(f"プロジェクトステータスの読み込みに失敗: {project_dir}")
            return {'status': 'error', 'message': 'Failed to load project status'}

        # 再開ポイントを選択
        if restart_from:
            # コマンドラインから指定された場合
            resume_from = ProcessStep(restart_from)
        else:
            # メニューから選択
            resume_from = self.resume_manager.show_step_selection_menu(status)

        # 入力ソースを取得
        input_source = status['input_source']

        # 処理を再開
        self.logger.info(f"📂 プロジェクトを再開: {project_dir}")
        return self._process_internal(
            input_source=input_source,
            output_dir=str(project_dir),  # Path → str変換
            resume_from=resume_from
        )

    def _process_internal(self, input_source: str,
                         output_dir: Optional[str] = None,
                         whisper_model: Optional[str] = None,
                         skip_transcription: bool = False,
                         skip_analysis: bool = False,
                         resume_from: Optional[ProcessStep] = None) -> Dict[str, Any]:
        """
        内部処理メソッド（Gemini専用）
        """
        start_time = time.time()
        results = {}

        # プロジェクトディレクトリを設定/作成
        if output_dir and Path(output_dir).exists():
            project_dir = Path(output_dir)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            project_dir = self.work_dir / f"project_{timestamp}"
            project_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info("=" * 60)
        self.logger.info("📹 VideoTranscriptAnalyzer (Gemini専用) - 処理開始")
        if resume_from:
            self.logger.info(f"🔄 {resume_from.display_name}から再開")
        else:
            self.logger.info(f"📂 新規プロジェクト: {project_dir}")
        self.logger.info("=" * 60)

        # レジューム状態の初期化または読み込み
        if not resume_from:
            # プロジェクトステータスの作成
            self.logger.info(f"📝 プロジェクトステータスを作成中...")
            status = self.resume_manager.create_project_status(
                project_dir,
                input_source,
                self.config
            )
            self.logger.info(f"   create_project_status戻り値の型: {type(status)}")
            if not isinstance(status, dict):
                self.logger.error(f"❌ create_project_statusが辞書を返していません: {type(status)}")
                return {'status': 'error', 'message': 'create_project_status returned non-dict'}

            self.resume_manager.save_status(project_dir, status)
            self.logger.info(f"   ステータスを保存しました")

        # ステータスの読み込み
        self.logger.info(f"📖 ステータスを読み込み中...")
        status = self.resume_manager.load_status(project_dir)
        self.logger.info(f"   load_status戻り値の型: {type(status)}")

        if status is None:
            self.logger.error(f"❌ ステータスの読み込みに失敗しました")
            return {'status': 'error', 'message': 'Failed to load status'}

        if not isinstance(status, dict):
            self.logger.error(f"❌ load_statusが辞書を返していません: {type(status)}")
            self.logger.error(f"   内容: {status}")
            return {'status': 'error', 'message': f'load_status returned {type(status)} instead of dict'}

        # 進捗表示の初期化
        self._display_progress(status)

        try:
            # ========================================
            # 1. 動画ダウンロード/準備
            # ========================================
            if not resume_from or resume_from.value <= ProcessStep.DOWNLOAD.value:
                force_rerun = resume_from == ProcessStep.DOWNLOAD
                if force_rerun or status['steps'][ProcessStep.DOWNLOAD.value]['status'] != StepStatus.COMPLETED.value:
                    # ローカルファイルかURLかを判定
                    input_path = Path(input_source)
                    is_local_file = input_path.exists() and input_path.is_file()

                    if is_local_file:
                        # ローカルファイルの場合はダウンロードをスキップ
                        self.logger.info(f"📂 ローカルファイルを使用: {input_source}")
                        self.resume_manager.update_step_status(
                            project_dir, ProcessStep.DOWNLOAD, StepStatus.IN_PROGRESS
                        )

                        # ファイルを作業ディレクトリにコピーまたはリンク
                        video_path = str(input_path)
                        video_info = {
                            'title': input_path.stem,
                            'duration': 0,
                            'description': 'Local file'
                        }
                        results['video_path'] = video_path
                        results['video_info'] = video_info

                        # ステップ完了
                        self.resume_manager.update_step_status(
                            project_dir, ProcessStep.DOWNLOAD, StepStatus.COMPLETED,
                            data={'video_path': video_path, 'video_info': video_info}
                        )
                        self.logger.info(f"✅ ローカルファイル準備完了: {video_path}")
                    else:
                        # URLの場合は通常のダウンロード処理
                        self.logger.info("📥 ステップ1: 動画ダウンロード中...")
                        self.resume_manager.update_step_status(
                            project_dir, ProcessStep.DOWNLOAD, StepStatus.IN_PROGRESS
                        )

                        try:
                            video_path, video_info = self.downloader.download(input_source, str(project_dir))
                            results['video_path'] = video_path
                            results['video_info'] = video_info

                            # ステップ完了
                            self.resume_manager.update_step_status(
                                project_dir, ProcessStep.DOWNLOAD, StepStatus.COMPLETED,
                                data={'video_path': video_path, 'video_info': video_info}
                            )
                            self.logger.info(f"✅ 動画準備完了: {video_path}")
                        except Exception as e:
                            self.logger.error(f"❌ 動画ダウンロードエラー: {e}")
                            self.resume_manager.update_step_status(
                                project_dir, ProcessStep.DOWNLOAD, StepStatus.ERROR
                            )
                            raise
                else:
                    # 既存データを使用
                    step_data = status['steps'][ProcessStep.DOWNLOAD.value].get('data', {})
                    video_path = step_data.get('video_path')
                    results['video_path'] = video_path
                    self.logger.info(f"✅ 動画準備済み: {video_path}")

            # ========================================
            # 2. 文字起こし
            # ========================================
            transcript_data = None
            transcript_file = project_dir / 'transcript.json'

            if not skip_transcription:
                if not resume_from or resume_from.value <= ProcessStep.TRANSCRIBE.value:
                    force_rerun = resume_from == ProcessStep.TRANSCRIBE
                    if force_rerun or status['steps'][ProcessStep.TRANSCRIBE.value]['status'] != StepStatus.COMPLETED.value:
                        self.logger.info("📝 ステップ2: 文字起こし実行中...")
                        self.resume_manager.update_step_status(
                            project_dir, ProcessStep.TRANSCRIBE, StepStatus.IN_PROGRESS
                        )

                        try:
                            # Transcriber を必要時にロード
                            self._ensure_transcriber_loaded()
                            transcript_data = self.transcriber.transcribe(
                                Path(results.get('video_path', video_path)),
                                project_dir
                            )

                            # 文字起こし結果を保存
                            with open(transcript_file, 'w', encoding='utf-8') as f:
                                json.dump(transcript_data, f, ensure_ascii=False, indent=2)

                            # ステップ完了
                            segments_count = len(transcript_data.get('segments', []))
                            self.resume_manager.update_step_status(
                                project_dir, ProcessStep.TRANSCRIBE, StepStatus.COMPLETED,
                                data={'segments_count': segments_count, 'transcript_file': str(transcript_file)}
                            )
                            results['transcription'] = transcript_data
                            self.logger.info(f"✅ 文字起こし完了: {segments_count}セグメント")
                        except Exception as e:
                            self.logger.error(f"❌ 文字起こしエラー: {e}")
                            self.resume_manager.update_step_status(
                                project_dir, ProcessStep.TRANSCRIBE, StepStatus.ERROR
                            )
                            raise
                    else:
                        # 既存の文字起こしデータを使用
                        self.logger.info(f"✅ 文字起こし済み: {transcript_file}")

                # 文字起こしファイルを読み込み
                if transcript_file.exists():
                    with open(transcript_file, 'r', encoding='utf-8') as f:
                        transcript_data = json.load(f)
                    results['transcription'] = transcript_data

            # ========================================
            # 3. Gemini AI分析
            # ========================================
            analysis_result = None
            if not skip_analysis and transcript_data:
                if not resume_from or resume_from.value <= ProcessStep.ANALYZE.value:
                    force_rerun = resume_from == ProcessStep.ANALYZE
                    if force_rerun or status['steps'][ProcessStep.ANALYZE.value]['status'] != StepStatus.COMPLETED.value:
                        self.logger.info("🤖 ステップ3: Gemini AI分析実行中...")
                        self.resume_manager.update_step_status(
                            project_dir, ProcessStep.ANALYZE, StepStatus.IN_PROGRESS
                        )

                        try:
                            # Geminiで分析（generateメソッドを使用）
                            analysis_result = self.gemini_generator.generate(transcript_data)

                            # 分析結果を保存
                            analysis_file = project_dir / 'gemini_analysis.json'
                            with open(analysis_file, 'w', encoding='utf-8') as f:
                                json.dump(analysis_result, f, ensure_ascii=False, indent=2)

                            results['analysis'] = analysis_result
                            self.resume_manager.update_step_status(
                                project_dir, ProcessStep.ANALYZE, StepStatus.COMPLETED,
                                data={'analysis_file': str(analysis_file)}
                            )
                            self.logger.info(f"✅ Gemini分析完了: {analysis_file}")
                        except Exception as e:
                            self.logger.error(f"❌ Gemini分析エラー: {e}")
                            self.resume_manager.update_step_status(
                                project_dir, ProcessStep.ANALYZE, StepStatus.ERROR
                            )
                            raise
                    else:
                        self.logger.info("✅ Gemini分析済み")
                        analysis_file = project_dir / 'gemini_analysis.json'
                        if analysis_file.exists():
                            with open(analysis_file, 'r') as f:
                                analysis_result = json.load(f)
                            results['analysis'] = analysis_result

            # ========================================
            # 4. 階層的要約（Geminiで実行）
            # ========================================
            if transcript_data:
                if not resume_from or resume_from.value <= ProcessStep.HIERARCHICAL.value:
                    force_rerun = resume_from == ProcessStep.HIERARCHICAL
                    if force_rerun or status['steps'][ProcessStep.HIERARCHICAL.value]['status'] != StepStatus.COMPLETED.value:
                        self.logger.info("📊 ステップ4: Gemini階層的要約実行中...")
                        self.resume_manager.update_step_status(
                            project_dir, ProcessStep.HIERARCHICAL, StepStatus.IN_PROGRESS
                        )

                        try:
                            # Geminiで階層的要約（generateメソッドを使用）
                            hierarchical_result = self.gemini_generator.generate(transcript_data)

                            # 要約結果を保存
                            summary_file = project_dir / 'gemini_summary.json'
                            with open(summary_file, 'w', encoding='utf-8') as f:
                                json.dump(hierarchical_result, f, ensure_ascii=False, indent=2)

                            results['hierarchical'] = hierarchical_result
                            self.resume_manager.update_step_status(
                                project_dir, ProcessStep.HIERARCHICAL, StepStatus.COMPLETED,
                                data={'summary_file': str(summary_file)}
                            )
                            self.logger.info(f"✅ Gemini階層的要約完了: {summary_file}")
                        except Exception as e:
                            self.logger.error(f"❌ Gemini要約エラー: {e}")
                            self.resume_manager.update_step_status(
                                project_dir, ProcessStep.HIERARCHICAL, StepStatus.ERROR
                            )
                            raise
                    else:
                        self.logger.info("✅ Gemini要約済み")

            # ========================================
            # 5. レポート生成（Gemini Ultimate）
            # ========================================
            if not resume_from or resume_from.value <= ProcessStep.REPORT.value:
                force_rerun = resume_from == ProcessStep.REPORT
                if force_rerun or status['steps'][ProcessStep.REPORT.value]['status'] != StepStatus.COMPLETED.value:
                    if self.gemini_generator and transcript_data:
                        self.logger.info("🚀 ステップ5: Gemini Ultimate Report (100点品質) を生成中...")
                        self.resume_manager.update_step_status(
                            project_dir, ProcessStep.REPORT, StepStatus.IN_PROGRESS
                        )

                        try:
                            # Geminiレポート生成
                            gemini_report = self.gemini_generator.generate(transcript_data)

                            # レポート保存
                            report_path = project_dir / 'gemini_ultimate_report.md'
                            with open(report_path, 'w', encoding='utf-8') as f:
                                f.write(gemini_report['report'])

                            results['gemini_report'] = gemini_report
                            self.logger.info(f"✅ Gemini Ultimate Report 生成完了:")
                            self.logger.info(f"   📄 {report_path}")
                            self.logger.info(f"   📊 品質スコア: {gemini_report.get('quality_score', 'N/A')}/100")
                            self.logger.info(f"   📝 文字数: {gemini_report.get('total_chars', 0):,}")

                            # ステップ完了
                            self.resume_manager.update_step_status(
                                project_dir, ProcessStep.REPORT, StepStatus.COMPLETED,
                                data={'report_file': str(report_path),
                                 'quality_score': gemini_report.get('quality_score'),
                                 'total_chars': gemini_report.get('total_chars')}
                            )
                        except Exception as e:
                            self.logger.error(f"❌ レポート生成エラー: {e}")
                            self.resume_manager.update_step_status(
                                project_dir, ProcessStep.REPORT, StepStatus.ERROR
                            )
                            raise
                    else:
                        self.logger.info("⏭️ レポート生成スキップ（Geminiなし）")
                        self.resume_manager.update_step_status(
                            project_dir, ProcessStep.REPORT, StepStatus.SKIPPED
                        )
                else:
                    self.logger.info("✅ レポート生成済み")

            # ========================================
            # 処理完了
            # ========================================
            self.resume_manager.update_project_status(project_dir, 'completed')
            self.logger.info("=" * 60)
            self.logger.info("🎉 全ての処理が完了しました！")
            self.logger.info(f"📁 出力ディレクトリ: {project_dir}")
            self.logger.info("=" * 60)

        except AttributeError as e:
            self.logger.error(f"❌ AttributeError in _process_internal: {e}")
            import traceback
            self.logger.error(f"スタックトレース: {traceback.format_exc()}")
            # プロジェクト全体のエラー状態を記録
            status = self.resume_manager.load_status(project_dir)
            if status:
                status['updated_at'] = datetime.now().isoformat()
                status['error'] = str(e)
                self.resume_manager.save_status(project_dir, status)
            return {'status': 'error', 'message': f'AttributeError: {e}'}
        except Exception as e:
            self.logger.error(f"❌ 処理エラー: {e}")
            # プロジェクト全体のエラー状態を記録
            status = self.resume_manager.load_status(project_dir)
            if status:
                status['updated_at'] = datetime.now().isoformat()
                status['error'] = str(e)
                self.resume_manager.save_status(project_dir, status)
            return {'status': 'error', 'message': str(e)}

        # 処理時間の記録
        self.process_times['total'] = time.time() - start_time
        results['process_times'] = self.process_times
        results['output_dir'] = str(project_dir)

        return results

    def _display_progress(self, status: Dict[str, Any]):
        """進捗状況を表示"""
        self.logger.info("\n📊 処理進捗:")

        # デバッグ情報
        self.logger.debug(f"_display_progress - status type: {type(status)}")
        if not isinstance(status, dict):
            self.logger.error(f"❌ _display_progress: statusが辞書ではない: {type(status)}")
            return

        if 'steps' not in status:
            self.logger.error(f"❌ _display_progress: statusに'steps'キーがない")
            self.logger.error(f"   statusのキー: {list(status.keys())}")
            return

        for step in ProcessStep:
            step_info = status['steps'].get(step.value, {})
            if not isinstance(step_info, dict):
                self.logger.error(f"❌ step_infoが辞書ではない: {type(step_info)}")
                continue

            step_status = step_info.get('status', StepStatus.NOT_STARTED.value)
            if step_status == StepStatus.COMPLETED.value:
                symbol = "✅"
            elif step_status == StepStatus.IN_PROGRESS.value:
                symbol = "🔄"
            elif step_status == StepStatus.ERROR.value:
                symbol = "❌"
            elif step_status == StepStatus.SKIPPED.value:
                symbol = "⏭️"
            else:
                symbol = "⏸️"
            print(f"{symbol} {step.display_name}", flush=True)


def main():
    """メイン実行関数"""
    parser = argparse.ArgumentParser(
        description='VideoTranscriptAnalyzer - Gemini専用版',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # 基本オプション
    parser.add_argument('--input', '-i', type=str,
                       help='動画のURLまたはファイルパス')
    parser.add_argument('--output', '-o', type=str,
                       help='出力ディレクトリ（デフォルト: output/project_[timestamp]）')

    # レジュームオプション
    parser.add_argument('--resume', action='store_true',
                       help='中断したプロジェクトを再開')
    parser.add_argument('--project-dir', type=str,
                       help='再開するプロジェクトディレクトリ')
    parser.add_argument('--restart-from', type=str,
                       help='特定のステップから再開 (download/transcription/analyze/hierarchical/report)')

    # 処理オプション
    parser.add_argument('--whisper-model', type=str,
                       help='Whisperモデル（tiny/base/small/medium/large/large-v2/large-v3）')
    parser.add_argument('--skip-transcription', action='store_true',
                       help='文字起こしをスキップ（既存の文字起こしファイルを使用）')
    parser.add_argument('--skip-analysis', action='store_true',
                       help='AI分析をスキップ')

    # APIキー（環境変数より優先）
    parser.add_argument('--gemini-api-key', type=str,
                       help='Gemini APIキー（環境変数より優先）')

    # 設定ファイル
    parser.add_argument('--config', type=str, default='config.yaml',
                       help='設定ファイルのパス（デフォルト: config.yaml）')

    args = parser.parse_args()

    # APIキーの設定（コマンドライン引数が最優先）
    if args.gemini_api_key:
        os.environ['GEMINI_API_KEY'] = args.gemini_api_key

    # 入力チェック
    if not args.resume and not args.input:
        parser.error('--input または --resume のいずれかを指定してください')

    # メイン処理実行
    try:
        analyzer = VideoTranscriptAnalyzerGeminiOnly(args.config)

        if args.resume:
            # レジュームモード
            results = analyzer.resume(
                project_dir=args.project_dir,
                restart_from=args.restart_from
            )
        else:
            # 通常モード
            results = analyzer.process_with_resume(
                input_source=args.input,
                output_dir=args.output,
                whisper_model=args.whisper_model,
                skip_transcription=args.skip_transcription,
                skip_analysis=args.skip_analysis
            )

        # 結果のサマリー表示
        if not isinstance(results, dict):
            print(f"❌ エラー: resultsが辞書ではありません。型: {type(results)}")
            print(f"内容: {results}")
            sys.exit(1)

        if results.get('status') != 'error':
            print("\n📊 処理結果サマリー:")
            print("-" * 40)
            if results.get('video_path'):
                print(f"動画: {results['video_path']}")
            if results.get('transcription'):
                segments = len(results['transcription'].get('segments', []))
                print(f"文字起こし: {segments}セグメント")
            if results.get('analysis'):
                print(f"AI分析: 完了")
            if results.get('gemini_report'):
                report = results['gemini_report']
                print(f"レポート品質: {report.get('quality_score', 'N/A')}/100")
                print(f"レポート文字数: {report.get('total_chars', 0):,}")

            # 処理時間
            if results.get('process_times'):
                total_time = results['process_times'].get('total', 0)
                print(f"\n総処理時間: {total_time:.1f}秒")

    except KeyboardInterrupt:
        print("\n\n⚠️ 処理が中断されました")
        print("レジュームするには以下を実行してください:")
        print("python video_transcript_analyzer_gemini_only.py --resume")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ エラー: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()