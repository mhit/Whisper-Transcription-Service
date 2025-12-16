#!/usr/bin/env python3
"""
既存のトランスクリプトファイルを使用して階層的要約を実行するスクリプト
seminar_transcript_synced.txt を読み込み、階層的要約を適用
"""

import sys
import re
import json
from pathlib import Path
from typing import List, Dict, Any
import logging

# プロジェクトディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from modules.hierarchical_analyzer import HierarchicalAnalyzer
from modules.utils import setup_logging


def parse_existing_transcript(file_path: str) -> Dict[str, Any]:
    """
    既存のトランスクリプトファイルをパースして、階層的要約用の形式に変換

    Args:
        file_path: トランスクリプトファイルのパス

    Returns:
        階層的要約に適した形式の辞書
    """
    print(f"📄 読み込み中: {file_path}")

    segments = []
    total_duration = 0

    # タイムスタンプのパターン: [XXX.XX分 - XXX.XX分] テキスト
    pattern = r'\[(\d+\.\d+)分 - (\d+\.\d+)分\] (.+)'

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    print(f"📝 {len(lines)}行を読み込みました")

    # メタ情報を探す
    for line in lines[:10]:
        if '総時間:' in line:
            match = re.search(r'(\d+\.\d+)分', line)
            if match:
                total_duration = float(match.group(1)) * 60  # 秒に変換
                print(f"⏱️ 総時間: {total_duration:.1f}秒 ({total_duration/60:.1f}分)")

    # セグメントをパース
    for line in lines:
        match = re.match(pattern, line.strip())
        if match:
            start_min = float(match.group(1))
            end_min = float(match.group(2))
            text = match.group(3)

            segment = {
                'start': start_min * 60,  # 秒に変換
                'end': end_min * 60,      # 秒に変換
                'text': text,
                'confidence': 0.95,  # 既存のトランスクリプトなので高信頼度
                'avg_logprob': -0.1,
                'compression_ratio': 1.2,
                'no_speech_prob': 0.01
            }
            segments.append(segment)

    print(f"✅ {len(segments)}個のセグメントを抽出しました")

    # 階層的要約用のデータ構造を作成
    transcript_data = {
        'segments': segments,
        'text': '\n'.join([seg['text'] for seg in segments]),
        'language': 'ja',
        'duration': total_duration if total_duration > 0 else segments[-1]['end'] if segments else 0
    }

    return transcript_data


def run_hierarchical_analysis(transcript_data: Dict[str, Any], output_dir: Path):
    """
    階層的要約を実行

    Args:
        transcript_data: トランスクリプトデータ
        output_dir: 出力ディレクトリ
    """
    print("\n" + "="*60)
    print("🎯 階層的要約実行 (LangChain + LlamaIndex)")
    print("="*60)

    # 設定（config.yamlから読み込むか、デフォルト値を使用）
    config_file = Path('config.yaml')
    if config_file.exists():
        import yaml
        with open(config_file, 'r', encoding='utf-8') as f:
            full_config = yaml.safe_load(f)
            # hierarchical_summarization設定を取得
            config = full_config.get('hierarchical_summarization', {})
            # analyzer設定からapi_base_urlを取得
            analyzer_config = full_config.get('analyzer', {})
            if 'api_base_url' in analyzer_config:
                config['api_base_url'] = analyzer_config['api_base_url']
    else:
        # デフォルト設定
        config = {
            'levels': 3,
            'segment_duration': 600,  # 10分
            'reduction_ratio': 0.4,
            'model': 'gpt-oss:20b',  # Ollamaモデル
            'temperature': 0.3,
            'max_tokens': 2000,
            'api_base_url': 'http://localhost:11434/v1',  # OpenAI互換エンドポイント
            'cache_dir': './cache',
            'parallel_processing': True,
            'max_workers': 4
        }

    # HierarchicalAnalyzerの初期化
    print("\n🚀 階層的要約システムを初期化中...")
    analyzer = HierarchicalAnalyzer(config)

    # 階層的要約の実行
    print("\n📊 階層的要約処理中...")
    print("   これには数分かかる可能性があります...")

    try:
        result = analyzer.analyze(transcript_data, output_dir)

        print("\n" + "="*60)
        print("📈 結果")
        print("="*60)

        # Level 1の結果
        print(f"\n📍 Level 1 (詳細要約)")
        print(f"   セグメント数: {len(result.level1_summaries)}")
        if result.level1_summaries:
            first = result.level1_summaries[0]
            print(f"   サンプル: [{first['start_time']:.1f}秒-{first['end_time']:.1f}秒]")
            print(f"   内容: {first['text'][:200]}...")

        # Level 2の結果
        print(f"\n📍 Level 2 (中間要約)")
        print(f"   グループ数: {len(result.level2_summaries)}")
        if result.level2_summaries:
            first = result.level2_summaries[0]
            print(f"   グループ {first['group_id']+1}:")
            print(f"   内容: {first['text'][:200]}...")

        # Level 3の結果
        print(f"\n📍 Level 3 (最終統合要約)")
        if result.level3_summary:
            print("="*60)
            print(result.level3_summary['text'])
            print("="*60)

        # 重要な瞬間
        print(f"\n🌟 重要な瞬間 ({len(result.key_moments)}個)")
        for i, moment in enumerate(result.key_moments[:5], 1):
            print(f"\n{i}. [{moment['start_time']/60:.1f}分] (重要度: {moment['importance_score']:.2f})")
            print(f"   理由: {moment['reason']}")
            print(f"   内容: {moment['preview'][:100]}...")

        # メタデータ
        print(f"\n📊 統計")
        print(f"   処理時間: {result.metadata['processing_time']:.1f}秒")
        print(f"   総セグメント数: {result.metadata['total_segments']}")
        print(f"   圧縮達成率: {result.metadata['reduction_achieved']:.1%}")

        # 結果をファイルに保存
        print(f"\n💾 結果を保存中...")

        # JSONとして保存
        output_file = output_dir / "hierarchical_summary_from_existing.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'level1': result.level1_summaries,
                'level2': result.level2_summaries,
                'level3': result.level3_summary,
                'key_moments': result.key_moments,
                'metadata': result.metadata
            }, f, ensure_ascii=False, indent=2)

        print(f"✅ 結果を保存しました: {output_file}")

        # Markdownレポートとして保存
        report_file = output_dir / "hierarchical_summary_report.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("# 階層的要約レポート\n\n")
            f.write(f"生成日時: {result.metadata.get('timestamp', '')}\n\n")

            f.write("## 📝 統合要約 (Level 3)\n\n")
            f.write(result.level3_summary['text'])
            f.write("\n\n")

            f.write("## 🎯 セクション要約 (Level 2)\n\n")
            for summary in result.level2_summaries:
                f.write(f"### グループ {summary['group_id']+1}\n")
                f.write(f"**時間範囲**: {summary['start_time']/60:.1f}分 - {summary['end_time']/60:.1f}分\n\n")
                f.write(summary['text'])
                f.write("\n\n")

            f.write("## 🌟 重要な瞬間\n\n")
            for i, moment in enumerate(result.key_moments[:10], 1):
                f.write(f"{i}. **[{moment['start_time']/60:.1f}分]** (重要度: {moment['importance_score']:.1%})\n")
                f.write(f"   - {moment['preview']}\n")
                f.write(f"   - 理由: {moment['reason']}\n\n")

            f.write("## 📊 統計\n\n")
            f.write(f"- 処理時間: {result.metadata['processing_time']:.1f}秒\n")
            f.write(f"- 総セグメント数: {result.metadata['total_segments']}\n")
            f.write(f"- 圧縮達成率: {result.metadata['reduction_achieved']:.1%}\n")

        print(f"✅ レポートを保存しました: {report_file}")

    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


def main():
    """メイン処理"""
    # UTF-8エンコーディングを設定
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    print("="*60)
    print("🔬 既存トランスクリプトで階層的要約テスト")
    print("="*60)

    # ロギング設定
    logger = setup_logging({'level': 'INFO'})

    # トランスクリプトファイルのパス
    transcript_file = Path(r"C:\Users\mhit\Downloads\セミナー文字起こし\seminar_transcript_synced.txt")

    if not transcript_file.exists():
        print(f"❌ トランスクリプトファイルが見つかりません: {transcript_file}")
        return

    # 出力ディレクトリ
    output_dir = Path("output_existing_transcript")
    output_dir.mkdir(exist_ok=True)

    # 1. 既存のトランスクリプトをパース
    print("\n📄 ステップ1: トランスクリプトファイルをパース中...")
    transcript_data = parse_existing_transcript(str(transcript_file))

    print(f"   - セグメント数: {len(transcript_data['segments'])}")
    print(f"   - 総時間: {transcript_data['duration']/60:.1f}分")
    print(f"   - 言語: {transcript_data['language']}")

    # 2. 階層的要約を実行
    print("\n🎯 ステップ2: 階層的要約を実行中...")
    run_hierarchical_analysis(transcript_data, output_dir)

    print("\n" + "="*60)
    print("✅ 処理完了！")
    print("="*60)
    print(f"\n結果は以下に保存されています:")
    print(f"  📁 {output_dir.absolute()}")
    print(f"     - hierarchical_summary_from_existing.json")
    print(f"     - hierarchical_summary_report.md")


if __name__ == "__main__":
    main()