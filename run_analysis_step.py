#!/usr/bin/env python3
"""
分析ステップを実行するスクリプト
既存のプロジェクトに対してシンプル要約を適用
"""

import sys
from pathlib import Path
from video_transcript_analyzer import VideoTranscriptAnalyzer
from modules.resume_manager import ProcessStep

def main():
    print("=" * 60)
    print("分析ステップ実行")
    print("=" * 60)

    # プロジェクトディレクトリ
    project_dir = Path("output/project_20250922_144453")

    if not project_dir.exists():
        print(f"エラー: プロジェクトが見つかりません: {project_dir}")
        return 1

    print(f"\nプロジェクト: {project_dir}")

    # VideoTranscriptAnalyzerを初期化
    analyzer = VideoTranscriptAnalyzer()

    # レジュームマネージャーを使用
    from modules.resume_manager import ResumeManager
    resume_manager = ResumeManager()

    print("\n現在のステータス確認...")
    status = resume_manager.load_status(project_dir)

    if status:
        print("各ステップの状態:")
        for step, info in status['steps'].items():
            status_text = info.get('status', 'unknown')
            print(f"  - {step}: {status_text}")

        # 分析ステップを強制的に再実行
        print("\n分析ステップを再実行します...")
        print("(パラメータ変更後の再処理をシミュレート)")

        # 以前のデータをクリーンアップ
        print("\n1. 以前の分析データをクリーンアップ...")
        resume_manager.clean_subsequent_steps(project_dir, ProcessStep.ANALYZE)

        # 分析を実行
        print("\n2. SimpleSummarizerで分析実行...")
        try:
            # トランスクリプトを読み込み
            transcript_file = project_dir / "transcript.json"
            if transcript_file.exists():
                import json
                with open(transcript_file, 'r', encoding='utf-8') as f:
                    transcript = json.load(f)

                # SimpleSummarizerを使って処理
                if analyzer.simple_summarizer:
                    print("   SimpleSummarizerで処理中...")

                    # セグメントをまとめる（最初の100セグメントでテスト）
                    segments = transcript.get('segments', [])[:100]
                    text = ' '.join([s.get('text', '') for s in segments])

                    print(f"   処理対象: {len(segments)}セグメント")
                    print(f"   テキスト長: {len(text)}文字")

                    # 要約生成
                    from modules.simple_summarizer import SimpleSummarizer

                    result = analyzer.simple_summarizer.summarize_segments([{
                        'start_time': 0,
                        'end_time': 600,
                        'text': text,
                        'segments': segments
                    }])

                    if result and len(result) > 0:
                        summary = result[0]
                        print(f"\n   要約生成成功:")
                        print(f"   - 基本要約: {summary.get('summary', '')[:100]}...")
                        print(f"   - キーポイント数: {len(summary.get('key_points', []))}")
                        print(f"   - 重要度スコア: {summary.get('importance_score', 0):.2f}")

                        # 結果を保存
                        output_file = project_dir / "simple_analysis.json"
                        import json
                        with open(output_file, 'w', encoding='utf-8') as f:
                            json.dump(result, f, ensure_ascii=False, indent=2)
                        print(f"\n   結果保存: {output_file}")

                        # ステータス更新
                        resume_manager.update_status(
                            project_dir,
                            ProcessStep.ANALYZE,
                            'completed',
                            progress=100,
                            output_file=str(output_file),
                            message="シンプル要約完了"
                        )
                        print("\n   ステータス更新完了")

                    else:
                        print("   要約生成失敗")
                else:
                    print("   SimpleSummarizerが初期化されていません")
            else:
                print(f"   トランスクリプトファイルが見つかりません: {transcript_file}")

        except Exception as e:
            print(f"\n   エラー: {e}")
            import traceback
            traceback.print_exc()

    else:
        print("ステータスファイルが見つかりません")

    print("\n" + "=" * 60)
    print("完了")
    print("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())