#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Whisper Transcript to Professional Report Processor
Based on CLAUDE.md specifications
"""

import os
import json
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from modules.gemini_ultimate_generator import GeminiUltimateGenerator
from modules.reporter import Reporter
from modules.keyword_analyzer import KeywordAnalyzer
from modules.utils import setup_logging, extract_video_frame

# Setup logging
logger = setup_logging(__name__)

class TranscriptReportGenerator:
    """CLAUDE.md仕様に基づくレポート生成器"""

    def __init__(self, gemini_api_key: str = None):
        """初期化"""
        self.gemini = GeminiUltimateGenerator(api_key=gemini_api_key)
        self.keyword_analyzer = KeywordAnalyzer()
        self.reporter = Reporter()

        # Screenshot trigger weights
        self.screenshot_triggers = {
            "speaker_introduction": 0.9,
            "shocking_statistic": 1.0,
            "visual_demonstration": 0.95,
            "graph_or_chart_mention": 1.0,
            "before_after_comparison": 0.95,
            "success_story_peak": 0.85,
            "key_formula_or_method": 1.0,
            "emotional_moment": 0.8,
            "final_summary": 0.9
        }

        # Topic patterns
        self.topic_patterns = {
            "revenue_model": ["収益", "マネタイズ", "売上", "収入", "利益"],
            "growth_strategy": ["成長", "フォロワー", "リーチ", "拡大", "伸び"],
            "content_creation": ["コンテンツ", "投稿", "リール", "動画", "作成"],
            "case_study": ["事例", "成功例", "実績", "結果", "実現"],
            "technical_tutorial": ["方法", "やり方", "ステップ", "手順", "テクニック"],
            "mindset": ["考え方", "マインド", "哲学", "意識", "姿勢"],
            "tools_resources": ["ツール", "リソース", "使い方", "活用", "機能"]
        }

    def load_transcript(self, transcript_path: str) -> Dict:
        """Whisper JSONトランスクリプトを読み込み"""
        logger.info(f"Loading transcript: {transcript_path}")
        with open(transcript_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def analyze_segments(self, segments: List[Dict]) -> Dict:
        """セグメントを分析してキーモーメントを特定"""
        logger.info("Analyzing segments for key moments...")

        analysis = {
            "topics": [],
            "key_moments": [],
            "statistics": [],
            "action_items": [],
            "case_studies": []
        }

        for i, segment in enumerate(segments):
            text = segment.get('text', '')
            timestamp = segment.get('start', 0)

            # Topic detection
            for topic, keywords in self.topic_patterns.items():
                if any(kw in text for kw in keywords):
                    analysis["topics"].append({
                        "topic": topic,
                        "text": text,
                        "timestamp": timestamp,
                        "index": i
                    })

            # Statistics detection
            import re
            numbers = re.findall(r'\d+[万億千百]?[円人個]', text)
            if numbers:
                analysis["statistics"].append({
                    "numbers": numbers,
                    "text": text,
                    "timestamp": timestamp,
                    "index": i
                })

            # Action items detection
            action_keywords = ["ステップ", "方法", "やり方", "まず", "次に", "最後に"]
            if any(kw in text for kw in action_keywords):
                analysis["action_items"].append({
                    "text": text,
                    "timestamp": timestamp,
                    "index": i
                })

        return analysis

    def select_screenshot_moments(self, analysis: Dict, max_screenshots: int = 10) -> List[Dict]:
        """スクリーンショット撮影タイミングを選定"""
        logger.info(f"Selecting top {max_screenshots} screenshot moments...")

        screenshot_moments = []

        # Opening scene (first meaningful segment)
        if analysis["topics"]:
            screenshot_moments.append({
                "name": "opening_scene",
                "timestamp": 5.0,  # 5 seconds in
                "weight": 0.9
            })

        # Key statistics
        for stat in analysis["statistics"][:3]:  # Top 3 statistics
            screenshot_moments.append({
                "name": f"statistic_{stat['index']}",
                "timestamp": stat["timestamp"],
                "weight": 1.0
            })

        # Important topics
        seen_topics = set()
        for topic_entry in analysis["topics"]:
            topic = topic_entry["topic"]
            if topic not in seen_topics and len(screenshot_moments) < max_screenshots:
                screenshot_moments.append({
                    "name": f"{topic}_{topic_entry['index']}",
                    "timestamp": topic_entry["timestamp"],
                    "weight": 0.85
                })
                seen_topics.add(topic)

        # Sort by timestamp and limit
        screenshot_moments.sort(key=lambda x: x["timestamp"])
        return screenshot_moments[:max_screenshots]

    def generate_markdown_report(self, transcript_data: Dict, analysis: Dict,
                                screenshots: List[Dict], output_path: str) -> str:
        """マークダウンレポートを生成"""
        logger.info("Generating markdown report...")

        # Use Gemini for high-quality summary
        all_text = " ".join([s.get('text', '') for s in transcript_data.get('segments', [])])

        # Generate comprehensive summary
        summary_prompt = f"""
        以下のトランスクリプトから、プロフェッショナルなレポートを作成してください：

        {all_text[:50000]}  # Limit for API

        以下の形式で出力してください：
        1. エグゼクティブサマリー（核心メッセージ）
        2. 主要ポイント（3-5個）
        3. 具体的な数値や実績
        4. アクションアイテム（初級・中級・上級別）
        5. まとめ
        """

        summary = self.gemini.generate(summary_prompt)

        # Build report structure
        report_lines = [
            f"# 📝 {Path(output_path).stem.replace('_', ' ').title()} 完全レポート",
            "",
            "## 🎯 エグゼクティブサマリー",
            "",
            summary.get("executive_summary", ""),
            "",
            "### 📌 最重要ポイント",
            f"> {summary.get('key_point', '')}",
            "",
            "---",
            ""
        ]

        # Add main content sections
        if analysis["statistics"]:
            report_lines.extend([
                "## 💰 重要な数値・実績",
                "",
            ])
            for stat in analysis["statistics"][:5]:
                report_lines.append(f"- {stat['text']}")
            report_lines.extend(["", "---", ""])

        # Add action items
        if analysis["action_items"]:
            report_lines.extend([
                "## ✅ 実践すべきアクション",
                "",
                "### 初心者向け",
            ])
            for item in analysis["action_items"][:3]:
                report_lines.append(f"1. {item['text'][:100]}...")
            report_lines.extend(["", "---", ""])

        # Add metadata
        report_lines.extend([
            "## 📚 参考情報",
            f"- **処理日時**: {datetime.now().strftime('%Y年%m月%d日 %H:%M')}",
            f"- **セグメント数**: {len(transcript_data.get('segments', []))}",
            f"- **総時間**: {transcript_data.get('segments', [{}])[-1].get('end', 0):.1f}秒",
            "",
            "---",
            "",
            "*このレポートはCLAUDE.md仕様に基づいて自動生成されました*"
        ])

        return "\n".join(report_lines)

    def process(self, transcript_path: str, output_dir: str,
                video_path: str = None, max_screenshots: int = 10):
        """完全な処理フロー"""
        logger.info("Starting transcript processing...")

        # Create output directories
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        screenshots_dir = output_dir / "screenshots"
        screenshots_dir.mkdir(exist_ok=True)

        # Load and analyze transcript
        transcript_data = self.load_transcript(transcript_path)
        segments = transcript_data.get('segments', [])

        analysis = self.analyze_segments(segments)

        # Select screenshot moments
        screenshot_moments = self.select_screenshot_moments(analysis, max_screenshots)

        # Extract screenshots if video provided
        if video_path and Path(video_path).exists():
            logger.info("Extracting screenshots...")
            for moment in screenshot_moments:
                screenshot_path = screenshots_dir / f"{moment['name']}.jpg"
                try:
                    extract_video_frame(
                        video_path,
                        moment['timestamp'],
                        str(screenshot_path)
                    )
                    logger.info(f"Extracted: {screenshot_path.name}")
                except Exception as e:
                    logger.warning(f"Failed to extract {moment['name']}: {e}")

        # Generate report
        report_path = output_dir / f"{Path(transcript_path).stem}_report.md"
        report_content = self.generate_markdown_report(
            transcript_data, analysis, screenshot_moments, str(report_path)
        )

        # Save report
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)

        logger.info(f"✅ Report generated: {report_path}")
        logger.info(f"📸 Screenshots: {len(screenshot_moments)} moments identified")

        return {
            "report_path": str(report_path),
            "screenshots": len(screenshot_moments),
            "topics": len(set([t["topic"] for t in analysis["topics"]])),
            "statistics": len(analysis["statistics"]),
            "action_items": len(analysis["action_items"])
        }


def main():
    """メイン実行関数"""
    parser = argparse.ArgumentParser(
        description="Whisper Transcript to Professional Report Generator"
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to Whisper JSON transcript file"
    )
    parser.add_argument(
        "--output", "-o",
        default="output/reports",
        help="Output directory for report and screenshots"
    )
    parser.add_argument(
        "--video", "-v",
        help="Path to video file for screenshot extraction"
    )
    parser.add_argument(
        "--screenshots", "-s",
        type=int,
        default=10,
        help="Maximum number of screenshots to extract"
    )
    parser.add_argument(
        "--gemini-api-key",
        help="Gemini API key (or set in config.yaml)"
    )

    args = parser.parse_args()

    # Initialize generator
    generator = TranscriptReportGenerator(
        gemini_api_key=args.gemini_api_key
    )

    # Process transcript
    result = generator.process(
        transcript_path=args.input,
        output_dir=args.output,
        video_path=args.video,
        max_screenshots=args.screenshots
    )

    # Print results
    print("\n" + "="*70)
    print("✅ TRANSCRIPT PROCESSING COMPLETE")
    print("="*70)
    print(f"📝 Report: {result['report_path']}")
    print(f"📸 Screenshots: {result['screenshots']}")
    print(f"📊 Topics: {result['topics']}")
    print(f"💰 Statistics: {result['statistics']}")
    print(f"✅ Action Items: {result['action_items']}")
    print("="*70)


if __name__ == "__main__":
    main()