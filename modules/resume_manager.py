"""
レジューム機能管理モジュール

プロジェクトの状態管理と中断からの再開機能を提供：
- プロジェクト状態の保存/読み込み
- インタラクティブなプロジェクト選択
- 進捗状況の表示
- 特定ステップからの再実行
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
import logging
from enum import Enum


class ProcessStep(Enum):
    """処理ステップの定義"""
    INITIALIZE = "initialize"
    DOWNLOAD = "download"
    TRANSCRIBE = "transcribe"
    ANALYZE = "analyze"
    HIERARCHICAL = "hierarchical"
    REPORT = "report"
    COMPLETE = "complete"

    def __str__(self):
        return self.value

    @property
    def display_name(self):
        """表示用の日本語名"""
        names = {
            "initialize": "初期化",
            "download": "動画ダウンロード",
            "transcribe": "文字起こし",
            "analyze": "AI分析",
            "hierarchical": "階層的要約",
            "report": "レポート生成",
            "complete": "完了"
        }
        return names.get(self.value, self.value)


class StepStatus(Enum):
    """ステップの状態"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ERROR = "error"
    SKIPPED = "skipped"

    def __str__(self):
        return self.value

    @property
    def icon(self):
        """状態を表すアイコン"""
        icons = {
            "not_started": "⬜",
            "in_progress": "🔄",
            "completed": "✅",
            "error": "❌",
            "skipped": "⏭️"
        }
        return icons.get(self.value, "❓")


class ResumeManager:
    """レジューム機能を管理するクラス"""

    STATUS_FILE = "status.json"

    def __init__(self, work_dir: Path = Path("./output")):
        """
        初期化

        Args:
            work_dir: プロジェクトの作業ディレクトリ
        """
        self.work_dir = work_dir
        self.logger = logging.getLogger('VideoTranscriptAnalyzer.resume')
        self.restart_from_step = None  # やり直しステップのフラグ

    def create_project_status(self,
                            project_dir: Path,
                            input_source: str,
                            config: Dict[str, Any]) -> Dict[str, Any]:
        """
        プロジェクトのステータスファイルを作成

        Args:
            project_dir: プロジェクトディレクトリ
            input_source: 入力ソース（URL/ファイルパス）
            config: 使用する設定

        Returns:
            ステータス情報の辞書
        """
        status = {
            "project_id": project_dir.name,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "input_source": input_source,
            "config": config,
            "steps": {
                ProcessStep.INITIALIZE.value: {
                    "status": StepStatus.COMPLETED.value,
                    "started_at": datetime.now().isoformat(),
                    "completed_at": datetime.now().isoformat(),
                    "message": "プロジェクト初期化完了"
                },
                ProcessStep.DOWNLOAD.value: {
                    "status": StepStatus.NOT_STARTED.value,
                    "progress": 0,
                    "output_file": None
                },
                ProcessStep.TRANSCRIBE.value: {
                    "status": StepStatus.NOT_STARTED.value,
                    "progress": 0,
                    "output_file": None,
                    "segments_processed": 0,
                    "total_segments": None
                },
                ProcessStep.ANALYZE.value: {
                    "status": StepStatus.NOT_STARTED.value,
                    "progress": 0,
                    "output_file": None
                },
                ProcessStep.HIERARCHICAL.value: {
                    "status": StepStatus.NOT_STARTED.value,
                    "progress": 0,
                    "level1_done": False,
                    "level2_done": False,
                    "level3_done": False,
                    "output_file": None
                },
                ProcessStep.REPORT.value: {
                    "status": StepStatus.NOT_STARTED.value,
                    "progress": 0,
                    "output_files": []
                },
                ProcessStep.COMPLETE.value: {
                    "status": StepStatus.NOT_STARTED.value,
                    "completed_at": None
                }
            }
        }

        # ステータスファイルを保存
        self.save_status(project_dir, status)
        return status

    def save_status(self, project_dir: Path, status: Dict[str, Any]):
        """
        ステータスをファイルに保存

        Args:
            project_dir: プロジェクトディレクトリ
            status: ステータス情報
        """
        status["updated_at"] = datetime.now().isoformat()
        status_file = project_dir / self.STATUS_FILE

        try:
            with open(status_file, 'w', encoding='utf-8') as f:
                json.dump(status, f, ensure_ascii=False, indent=2)
            self.logger.debug(f"ステータス保存: {status_file}")
        except Exception as e:
            self.logger.error(f"ステータス保存失敗: {e}")

    def load_status(self, project_dir: Path) -> Optional[Dict[str, Any]]:
        """
        ステータスをファイルから読み込み

        Args:
            project_dir: プロジェクトディレクトリ

        Returns:
            ステータス情報（存在しない場合はNone）
        """
        status_file = project_dir / self.STATUS_FILE

        if not status_file.exists():
            return None

        try:
            with open(status_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"ステータス読み込み失敗: {e}")
            return None

    def update_step_status(self,
                          project_dir: Path,
                          step: ProcessStep,
                          status: StepStatus,
                          **kwargs):
        """
        特定ステップのステータスを更新

        Args:
            project_dir: プロジェクトディレクトリ
            step: 処理ステップ
            status: 新しいステータス
            **kwargs: 追加の更新情報
        """
        project_status = self.load_status(project_dir)
        if not project_status:
            return

        step_info = project_status["steps"][step.value]
        step_info["status"] = status.value

        # タイムスタンプの更新
        if status == StepStatus.IN_PROGRESS:
            step_info["started_at"] = datetime.now().isoformat()
        elif status in [StepStatus.COMPLETED, StepStatus.ERROR]:
            step_info["completed_at"] = datetime.now().isoformat()

        # 追加情報の更新
        for key, value in kwargs.items():
            step_info[key] = value

        self.save_status(project_dir, project_status)

    def get_resumable_projects(self, include_completed: bool = True) -> List[Tuple[Path, Dict[str, Any]]]:
        """
        再開可能なプロジェクトのリストを取得

        Args:
            include_completed: 完了済みプロジェクトも含める（やり直し機能用）

        Returns:
            (プロジェクトディレクトリ, ステータス)のタプルのリスト
        """
        resumable = []

        if not self.work_dir.exists():
            return resumable

        # outputディレクトリ内のすべてのプロジェクトをチェック
        for project_dir in sorted(self.work_dir.iterdir(), reverse=True):
            if not project_dir.is_dir():
                continue

            status = self.load_status(project_dir)
            if status:
                # include_completed=Trueの場合はすべてのプロジェクトを含める
                if include_completed:
                    resumable.append((project_dir, status))
                else:
                    # 未完了のプロジェクトのみ
                    if status["steps"][ProcessStep.COMPLETE.value]["status"] != StepStatus.COMPLETED.value:
                        resumable.append((project_dir, status))

        return resumable

    def show_project_menu(self) -> Optional[Tuple[Path, Dict[str, Any]]]:
        """
        インタラクティブなプロジェクト選択メニューを表示

        Returns:
            選択されたプロジェクト情報（キャンセルの場合はNone）
        """
        # 完了済みも含めてすべてのプロジェクトを取得
        projects = self.get_resumable_projects(include_completed=True)

        if not projects:
            print("\n⚠️  利用可能なプロジェクトがありません")
            return None

        print("\n" + "="*70)
        print("📁 利用可能なプロジェクト（再開/やり直し可能）:")
        print("="*70)

        for i, (proj_dir, status) in enumerate(projects, 1):
            # プロジェクト情報を表示
            created = datetime.fromisoformat(status["created_at"])
            updated = datetime.fromisoformat(status["updated_at"])

            # 現在のステップと進捗を取得
            current_step = None
            progress_info = []
            is_completed = status["steps"][ProcessStep.COMPLETE.value]["status"] == StepStatus.COMPLETED.value

            for step_name, step_info in status["steps"].items():
                step_status = StepStatus(step_info["status"])

                if step_status == StepStatus.IN_PROGRESS:
                    current_step = ProcessStep(step_name)
                    if "progress" in step_info:
                        progress_info.append(f"{step_info['progress']}%")

                # 各ステップの状態を収集
                if step_status == StepStatus.COMPLETED:
                    progress_info.append(f"{step_status.icon}")
                elif step_status == StepStatus.ERROR:
                    progress_info.append(f"{step_status.icon}")
                elif step_status == StepStatus.IN_PROGRESS:
                    progress_info.append(f"{step_status.icon}")

            # プロジェクトの状態を表示
            status_label = "✅ 完了" if is_completed else "🔄 未完了"
            print(f"\n{i}. [{created.strftime('%Y-%m-%d %H:%M')}] {status['project_id']} [{status_label}]")
            print(f"   入力: {status['input_source'][:50]}...")
            print(f"   進捗: {' '.join(progress_info)}")

            if current_step:
                print(f"   現在: {current_step.display_name} 実行中")
            elif is_completed:
                print(f"   📝 すべてのステップが完了しています（やり直し可能）")

        print("\n" + "-"*70)
        print("📌 選択オプション:")
        print("  • プロジェクト番号 (1-{}) : そのプロジェクトを選択".format(len(projects)))
        print("  • 'q' : キャンセルして終了")
        print("\n選択してください:")

        while True:
            choice = input("> ").strip()

            if choice.lower() == 'q':
                return None

            try:
                index = int(choice) - 1
                if 0 <= index < len(projects):
                    return projects[index]
                else:
                    print("無効な番号です。もう一度選択してください:")
            except ValueError:
                print("番号を入力してください:")

    def show_step_selection_menu(self, project_status: Dict[str, Any]) -> Optional[ProcessStep]:
        """
        ステップ選択メニューを表示（続きから/やり直し選択）

        Args:
            project_status: プロジェクトのステータス

        Returns:
            選択されたステップ（キャンセルの場合はNone）
        """
        print("\n" + "="*70)
        print("🔧 実行オプションを選択:")
        print("="*70)

        step_options = []
        all_steps = []

        print("\n📋 処理ステップ一覧:")
        print("-" * 40)

        for step in ProcessStep:
            if step == ProcessStep.INITIALIZE or step == ProcessStep.COMPLETE:
                continue

            step_info = project_status["steps"][step.value]
            step_status = StepStatus(step_info["status"])
            all_steps.append((step, step_info, step_status))

            # すべてのステップを表示（番号、状態、名前、説明）
            step_desc = {
                ProcessStep.DOWNLOAD: "動画ファイルのダウンロード",
                ProcessStep.TRANSCRIBE: "音声の文字起こし処理",
                ProcessStep.ANALYZE: "AI による内容分析",
                ProcessStep.HIERARCHICAL: "階層的要約の生成",
                ProcessStep.REPORT: "最終レポートの作成"
            }

            print(f"\n  {len(all_steps)}. {step_status.icon} {step.display_name}")
            print(f"      └─ {step_desc.get(step, '')}")

            # 追加情報の表示
            if step == ProcessStep.DOWNLOAD and step_info.get("output_file"):
                print(f"      └─ ファイル: {Path(step_info['output_file']).name}")
            elif step == ProcessStep.TRANSCRIBE:
                if step_info.get("segments_processed"):
                    print(f"      └─ 進捗: {step_info['segments_processed']}/{step_info.get('total_segments', '?')} セグメント")
            elif step == ProcessStep.HIERARCHICAL:
                levels_done = []
                if step_info.get("level1_done"):
                    levels_done.append("Level1")
                if step_info.get("level2_done"):
                    levels_done.append("Level2")
                if step_info.get("level3_done"):
                    levels_done.append("Level3")
                if levels_done:
                    print(f"      └─ 完了済み: {', '.join(levels_done)}")

        print("\n" + "-" * 40)
        print("📌 選択オプション:")
        print("  • 0    : 🔄 最後の未完了ステップから続行")
        print("  • 1-{} : 📝 特定のステップから続行".format(len(all_steps)))
        print("  • R    : 🔧 任意のステップからやり直し（データ削除＆再実行）")
        print("  • q    : ❌ キャンセルして終了")

        print("\n" + "-"*70)
        print("選択してください:")

        while True:
            choice = input("> ").strip()

            if choice.lower() == 'q':
                return None

            # やり直しモード
            if choice.upper() == 'R':
                print("\n" + "="*70)
                print("🔧 やり直しモード - ステップを選択してください")
                print("="*70)
                print("\n⚠️  注意事項:")
                print("  • 選択したステップ以降のデータがすべて削除されます")
                print("  • 削除されたデータは復元できません")
                print("  • 選択したステップから順番に再実行されます")
                print("\n📋 ステップ番号の対応:")
                for i, (step, _, status) in enumerate(all_steps, 1):
                    print(f"  {i}. {status.icon} {step.display_name}")
                print("\nやり直すステップの番号を入力してください (1-{}, 'c'でキャンセル):".format(len(all_steps)))
                restart_choice = input("> ").strip()

                if restart_choice.lower() == 'c':
                    print("やり直しをキャンセルしました")
                    continue

                try:
                    restart_index = int(restart_choice)
                    if 1 <= restart_index <= len(all_steps):
                        restart_step = all_steps[restart_index - 1][0]
                        # やり直しフラグを設定
                        self.restart_from_step = restart_step
                        return restart_step
                    else:
                        print("無効な番号です。もう一度選択してください:")
                        continue
                except ValueError:
                    print("番号を入力してください:")
                    continue

            try:
                index = int(choice)

                if index == 0:
                    # 最後の未完了ステップを探す
                    for step in ProcessStep:
                        if step == ProcessStep.COMPLETE:
                            continue
                        step_status = StepStatus(project_status["steps"][step.value]["status"])
                        if step_status in [StepStatus.NOT_STARTED, StepStatus.ERROR, StepStatus.IN_PROGRESS]:
                            return step
                    return None
                elif 1 <= index <= len(all_steps):
                    selected_step = all_steps[index - 1][0]
                    # 通常の続行モード
                    self.restart_from_step = None
                    return selected_step
                else:
                    print("無効な番号です。もう一度選択してください:")
            except ValueError:
                print("番号を入力してください:")

    def get_progress_summary(self, project_dir: Path) -> str:
        """
        プロジェクトの進捗サマリーを取得

        Args:
            project_dir: プロジェクトディレクトリ

        Returns:
            進捗サマリー文字列
        """
        status = self.load_status(project_dir)
        if not status:
            return "ステータス情報なし"

        lines = []
        lines.append("📊 処理進捗:")

        for step in ProcessStep:
            step_info = status["steps"][step.value]
            step_status = StepStatus(step_info["status"])

            line = f"{step_status.icon} {step.display_name}"

            # 進捗情報を追加
            if step_status == StepStatus.IN_PROGRESS and "progress" in step_info:
                line += f" ({step_info['progress']}%)"
            elif step_status == StepStatus.ERROR and step_info.get("error_message"):
                line += f" - {step_info['error_message']}"

            lines.append(line)

        return "\n".join(lines)

    def clean_subsequent_steps(self, project_dir: Path, from_step: ProcessStep) -> None:
        """
        指定ステップ以降のデータを削除し、ステータスをリセット

        Args:
            project_dir: プロジェクトディレクトリ
            from_step: このステップ以降をクリーンアップ
        """
        self.logger.info(f"🧹 {from_step.display_name} 以降のデータをクリーンアップ中...")

        status = self.load_status(project_dir)
        if not status:
            return

        # ステップの順序を定義
        step_order = [
            ProcessStep.DOWNLOAD,
            ProcessStep.TRANSCRIBE,
            ProcessStep.ANALYZE,
            ProcessStep.HIERARCHICAL,
            ProcessStep.REPORT
        ]

        # 開始ステップのインデックスを取得
        try:
            start_index = step_order.index(from_step)
        except ValueError:
            self.logger.error(f"無効なステップ: {from_step}")
            return

        # 該当ステップ以降をクリーンアップ
        for i in range(start_index, len(step_order)):
            step = step_order[i]
            step_info = status["steps"][step.value]

            # ファイル削除
            if step == ProcessStep.DOWNLOAD:
                # ダウンロードファイルは保持（再利用可能）
                pass

            elif step == ProcessStep.TRANSCRIBE:
                # 文字起こし関連ファイルを削除
                files_to_delete = [
                    project_dir / "transcript.json",
                    project_dir / "transcript.txt",
                    project_dir / "transcript_timestamped.txt",
                    project_dir / "transcript.srt"
                ]
                for file_path in files_to_delete:
                    if file_path.exists():
                        file_path.unlink()
                        self.logger.debug(f"削除: {file_path}")

            elif step == ProcessStep.ANALYZE or step == ProcessStep.HIERARCHICAL:
                # 分析関連ファイルを削除
                files_to_delete = [
                    project_dir / "analysis.json",
                    project_dir / "hierarchical_analysis.json",
                    project_dir / "simple_summary.json"
                ]
                for file_path in files_to_delete:
                    if file_path.exists():
                        file_path.unlink()
                        self.logger.debug(f"削除: {file_path}")

            elif step == ProcessStep.REPORT:
                # レポート関連ファイルを削除
                files_to_delete = [
                    project_dir / "video_analysis_report.md",
                    project_dir / "video_analysis_report.html"
                ]
                for file_path in files_to_delete:
                    if file_path.exists():
                        file_path.unlink()
                        self.logger.debug(f"削除: {file_path}")

                # スクリーンショットディレクトリを削除
                screenshots_dir = project_dir / "screenshots"
                if screenshots_dir.exists():
                    import shutil
                    shutil.rmtree(screenshots_dir)
                    self.logger.debug(f"削除: {screenshots_dir}")

            # ステータスをリセット
            step_info["status"] = StepStatus.NOT_STARTED.value
            step_info["started_at"] = None
            step_info["completed_at"] = None
            step_info["error_message"] = None
            step_info["output_file"] = None
            step_info["progress"] = 0

            # ステップ固有の情報をクリア
            keys_to_remove = [
                "segments_processed", "total_segments",  # TRANSCRIBE
                "level1_done", "level2_done", "level3_done",  # HIERARCHICAL
                "message", "output_files"  # 共通
            ]
            for key in keys_to_remove:
                step_info.pop(key, None)

        # ステータスファイルを更新
        self.save_status(project_dir, status)
        self.logger.info("✅ クリーンアップ完了")

    def parse_step_name(self, step_name: str) -> Optional[ProcessStep]:
        """
        文字列からProcessStepを解析

        Args:
            step_name: ステップ名（download, transcribe, analyze, report など）

        Returns:
            対応するProcessStep（見つからない場合はNone）
        """
        step_map = {
            'download': ProcessStep.DOWNLOAD,
            'transcribe': ProcessStep.TRANSCRIBE,
            'analyze': ProcessStep.ANALYZE,
            'hierarchical': ProcessStep.HIERARCHICAL,
            'report': ProcessStep.REPORT
        }
        return step_map.get(step_name.lower())