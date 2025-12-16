#!/usr/bin/env python3
"""
レジューム機能のテストスクリプト

このスクリプトは、ResumeManagerの主要機能をテストします：
1. ステータスファイルの作成と読み込み
2. ステップ状態の更新
3. プロジェクトの検索と選択
4. エラー処理とリカバリー
"""

import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
import sys
import os

# プロジェクトのルートディレクトリをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.resume_manager import ResumeManager, ProcessStep, StepStatus


class TestResumeManager:
    """レジューム機能のテストクラス"""

    def __init__(self):
        self.test_dir = None
        self.manager = None
        self.test_results = []

    def setup(self):
        """テスト環境のセットアップ"""
        self.test_dir = Path(tempfile.mkdtemp(prefix="test_resume_"))
        self.manager = ResumeManager(self.test_dir)
        print(f"✅ テスト環境を作成: {self.test_dir}")

    def teardown(self):
        """テスト環境のクリーンアップ"""
        if self.test_dir and self.test_dir.exists():
            shutil.rmtree(self.test_dir)
            print(f"✅ テスト環境を削除: {self.test_dir}")

    def test_create_project_status(self):
        """プロジェクトステータスの作成テスト"""
        print("\n🧪 Test 1: プロジェクトステータスの作成")

        # プロジェクトディレクトリを作成
        project_dir = self.test_dir / "test_project_001"
        project_dir.mkdir(parents=True, exist_ok=True)

        # ステータスを作成
        config = {
            "language": "ja",
            "model_size": "large-v2",
            "compute_type": "float16"
        }

        status = self.manager.create_project_status(
            project_dir,
            "https://example.com/video.mp4",
            config
        )

        # 検証
        assert status["project_id"] == "test_project_001"
        assert status["input_source"] == "https://example.com/video.mp4"
        assert status["config"] == config
        assert ProcessStep.INITIALIZE.value in status["steps"]

        # ファイルが作成されているか確認
        status_file = project_dir / "status.json"
        assert status_file.exists()

        print("  ✅ ステータスファイルが正常に作成されました")
        self.test_results.append(("create_project_status", True))

    def test_load_status(self):
        """ステータスファイルの読み込みテスト"""
        print("\n🧪 Test 2: ステータスファイルの読み込み")

        # プロジェクトを作成
        project_dir = self.test_dir / "test_project_002"
        project_dir.mkdir(parents=True, exist_ok=True)

        original_status = self.manager.create_project_status(
            project_dir,
            "test_video.mp4",
            {"test": "config"}
        )

        # 読み込み
        loaded_status = self.manager.load_status(project_dir)

        # 検証
        assert loaded_status is not None
        assert loaded_status["project_id"] == original_status["project_id"]
        assert loaded_status["input_source"] == original_status["input_source"]

        print("  ✅ ステータスファイルが正常に読み込まれました")
        self.test_results.append(("load_status", True))

    def test_update_step_status(self):
        """ステップステータスの更新テスト"""
        print("\n🧪 Test 3: ステップステータスの更新")

        # プロジェクトを作成
        project_dir = self.test_dir / "test_project_003"
        project_dir.mkdir(parents=True, exist_ok=True)

        self.manager.create_project_status(
            project_dir,
            "test.mp4",
            {}
        )

        # ステータスを更新
        self.manager.update_step_status(
            project_dir,
            ProcessStep.DOWNLOAD,
            StepStatus.IN_PROGRESS,
            progress=50,
            message="ダウンロード中..."
        )

        # 検証
        status = self.manager.load_status(project_dir)
        download_step = status["steps"][ProcessStep.DOWNLOAD.value]

        assert download_step["status"] == StepStatus.IN_PROGRESS.value
        assert download_step["progress"] == 50
        assert download_step["message"] == "ダウンロード中..."
        assert "started_at" in download_step

        # 完了状態に更新
        self.manager.update_step_status(
            project_dir,
            ProcessStep.DOWNLOAD,
            StepStatus.COMPLETED,
            progress=100,
            output_file="downloads/video.mp4"
        )

        # 再検証
        status = self.manager.load_status(project_dir)
        download_step = status["steps"][ProcessStep.DOWNLOAD.value]

        assert download_step["status"] == StepStatus.COMPLETED.value
        assert download_step["progress"] == 100
        assert download_step["output_file"] == "downloads/video.mp4"
        assert "completed_at" in download_step

        print("  ✅ ステップステータスが正常に更新されました")
        self.test_results.append(("update_step_status", True))

    def test_get_resumable_projects(self):
        """再開可能プロジェクトの取得テスト"""
        print("\n🧪 Test 4: 再開可能プロジェクトの取得")

        # この テスト用の独立ディレクトリを作成
        test_specific_dir = self.test_dir / "test4_resumable"
        test_specific_dir.mkdir(parents=True, exist_ok=True)
        test_manager = ResumeManager(test_specific_dir)

        # 複数のプロジェクトを作成
        projects_created = []

        # 未完了プロジェクト1
        project1_dir = test_specific_dir / "project_incomplete_1"
        project1_dir.mkdir(parents=True, exist_ok=True)
        status1 = test_manager.create_project_status(
            project1_dir,
            "video1.mp4",
            {}
        )
        projects_created.append(("project_incomplete_1", False))

        # 未完了プロジェクト2（エラー状態）
        project2_dir = test_specific_dir / "project_incomplete_2"
        project2_dir.mkdir(parents=True, exist_ok=True)
        test_manager.create_project_status(
            project2_dir,
            "video2.mp4",
            {}
        )
        test_manager.update_step_status(
            project2_dir,
            ProcessStep.TRANSCRIBE,
            StepStatus.ERROR,
            error_message="メモリ不足"
        )
        projects_created.append(("project_incomplete_2", False))

        # 完了プロジェクト（表示されないはず）
        project3_dir = test_specific_dir / "project_complete"
        project3_dir.mkdir(parents=True, exist_ok=True)
        test_manager.create_project_status(
            project3_dir,
            "video3.mp4",
            {}
        )
        test_manager.update_step_status(
            project3_dir,
            ProcessStep.COMPLETE,
            StepStatus.COMPLETED
        )
        projects_created.append(("project_complete", True))

        # 再開可能プロジェクトを取得
        resumable = test_manager.get_resumable_projects()

        # デバッグ情報を出力
        print(f"  見つかったプロジェクト数: {len(resumable)}")
        for proj_dir, status in resumable:
            print(f"    - {proj_dir.name}: {status['steps'][ProcessStep.COMPLETE.value]['status']}")

        # 検証
        assert len(resumable) == 2  # 未完了の2つのみ

        project_names = [p[0].name for p in resumable]
        assert "project_incomplete_1" in project_names
        assert "project_incomplete_2" in project_names
        assert "project_complete" not in project_names

        print(f"  ✅ {len(resumable)}個の再開可能プロジェクトが見つかりました")
        self.test_results.append(("get_resumable_projects", True))

    def test_progress_summary(self):
        """進捗サマリーの生成テスト"""
        print("\n🧪 Test 5: 進捗サマリーの生成")

        # プロジェクトを作成
        project_dir = self.test_dir / "test_project_summary"
        project_dir.mkdir(parents=True, exist_ok=True)

        self.manager.create_project_status(
            project_dir,
            "test.mp4",
            {}
        )

        # 各ステップのステータスを設定
        self.manager.update_step_status(
            project_dir,
            ProcessStep.DOWNLOAD,
            StepStatus.COMPLETED
        )

        self.manager.update_step_status(
            project_dir,
            ProcessStep.TRANSCRIBE,
            StepStatus.IN_PROGRESS,
            progress=75,
            segments_processed=90,
            total_segments=120
        )

        self.manager.update_step_status(
            project_dir,
            ProcessStep.ANALYZE,
            StepStatus.ERROR,
            error_message="API接続エラー"
        )

        # サマリーを生成
        summary = self.manager.get_progress_summary(project_dir)

        # 検証
        assert "📊 処理進捗:" in summary
        assert "✅ 初期化" in summary
        assert "✅ 動画ダウンロード" in summary
        assert "🔄 文字起こし (75%)" in summary
        assert "❌ AI分析 - API接続エラー" in summary

        print("  ✅ 進捗サマリーが正常に生成されました")
        print("\n生成されたサマリー:")
        print("  " + summary.replace("\n", "\n  "))
        self.test_results.append(("progress_summary", True))

    def test_error_recovery(self):
        """エラーからの復旧テスト"""
        print("\n🧪 Test 6: エラーからの復旧")

        # エラー状態のプロジェクトを作成
        project_dir = self.test_dir / "test_error_recovery"
        project_dir.mkdir(parents=True, exist_ok=True)

        self.manager.create_project_status(
            project_dir,
            "error_test.mp4",
            {}
        )

        # エラー状態を設定
        self.manager.update_step_status(
            project_dir,
            ProcessStep.ANALYZE,
            StepStatus.ERROR,
            error_message="初回実行でエラー"
        )

        # エラーステップを再実行（復旧）
        self.manager.update_step_status(
            project_dir,
            ProcessStep.ANALYZE,
            StepStatus.IN_PROGRESS,
            progress=0,
            message="再実行中..."
        )

        # 成功
        self.manager.update_step_status(
            project_dir,
            ProcessStep.ANALYZE,
            StepStatus.COMPLETED,
            progress=100,
            output_file="analysis.json"
        )

        # 検証
        status = self.manager.load_status(project_dir)
        analyze_step = status["steps"][ProcessStep.ANALYZE.value]

        assert analyze_step["status"] == StepStatus.COMPLETED.value
        assert analyze_step["output_file"] == "analysis.json"

        print("  ✅ エラーからの復旧が成功しました")
        self.test_results.append(("error_recovery", True))

    def run_all_tests(self):
        """すべてのテストを実行"""
        print("\n" + "="*70)
        print("🚀 レジューム機能テストを開始")
        print("="*70)

        try:
            self.setup()

            # 各テストを実行
            self.test_create_project_status()
            self.test_load_status()
            self.test_update_step_status()
            self.test_get_resumable_projects()
            self.test_progress_summary()
            self.test_error_recovery()

        except Exception as e:
            print(f"\n❌ テストでエラーが発生: {e}")
            import traceback
            traceback.print_exc()
            self.test_results.append(("unexpected_error", False))
        finally:
            self.teardown()

        # 結果サマリー
        print("\n" + "="*70)
        print("📊 テスト結果サマリー")
        print("="*70)

        passed = sum(1 for _, result in self.test_results if result)
        failed = len(self.test_results) - passed

        for test_name, result in self.test_results:
            status_icon = "✅" if result else "❌"
            print(f"{status_icon} {test_name}")

        print("\n" + "-"*70)
        print(f"合計: {len(self.test_results)} テスト")
        print(f"成功: {passed} テスト")
        print(f"失敗: {failed} テスト")

        if failed == 0:
            print("\n🎉 すべてのテストが成功しました！")
        else:
            print(f"\n⚠️  {failed}個のテストが失敗しました")

        return failed == 0


def main():
    """メインエントリーポイント"""
    tester = TestResumeManager()
    success = tester.run_all_tests()

    # 終了コード
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()