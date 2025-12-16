"""
レポート生成モジュール

スクリーンショット抽出とMarkdownレポート生成機能を提供：
- 動画からのスクリーンショット抽出
- 分析結果の統合
- Markdownレポート生成
- HTMLレポート生成（オプション）
"""

import logging
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import math

try:
    import ffmpeg
except ImportError:
    print("ffmpeg-python が見つかりません。以下のコマンドでインストールしてください:")
    print("pip install ffmpeg-python")
    ffmpeg = None

try:
    from PIL import Image
except ImportError:
    print("Pillow が見つかりません。以下のコマンドでインストールしてください:")
    print("pip install Pillow")
    Image = None

from .utils import format_duration, format_filesize, safe_filename


class ReportGenerator:
    """レポート生成クラス"""

    def __init__(self, config: Dict[str, Any]):
        """
        初期化

        Args:
            config: レポート生成設定
        """
        self.config = config
        self.logger = logging.getLogger('VideoTranscriptAnalyzer.reporter')

        # 設定値
        self.format = config.get('format', 'markdown')
        self.include_screenshots = config.get('include_screenshots', True)
        self.screenshot_count = config.get('screenshot_count', 10)
        self.screenshot_width = config.get('screenshot_width', 800)
        self.screenshot_quality = config.get('screenshot_quality', 85)

    def extract_screenshots(self,
                          video_path: Path,
                          analysis_data: Optional[Dict[str, Any]],
                          output_dir: Path) -> List[Dict[str, Any]]:
        """
        動画からスクリーンショットを抽出

        Args:
            video_path: 動画ファイルパス
            analysis_data: 分析データ（タイムスタンプ特定用）
            output_dir: 出力ディレクトリ

        Returns:
            スクリーンショット情報のリスト

        Raises:
            RuntimeError: スクリーンショット抽出失敗
        """
        if not self.include_screenshots or not ffmpeg:
            self.logger.info("スクリーンショット抽出をスキップ")
            return []

        if not video_path.exists():
            raise RuntimeError(f"動画ファイルが見つかりません: {video_path}")

        self.logger.info(f"スクリーンショット抽出開始: {video_path}")

        try:
            # 動画情報を取得
            probe = ffmpeg.probe(str(video_path))
            video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
            duration = float(probe['format']['duration'])

            self.logger.info(f"動画時間: {format_duration(duration)}")

            # スクリーンショット保存ディレクトリ
            screenshots_dir = output_dir / "screenshots"
            screenshots_dir.mkdir(exist_ok=True)

            # 抽出タイムスタンプを決定
            timestamps = self._determine_screenshot_timestamps(duration, analysis_data)

            screenshots = []
            for i, timestamp in enumerate(timestamps):
                screenshot_filename = f"screenshot_{i+1:02d}_{int(timestamp):04d}s.jpg"
                screenshot_path = screenshots_dir / screenshot_filename

                try:
                    # ffmpegでスクリーンショット抽出
                    (
                        ffmpeg
                        .input(str(video_path), ss=timestamp)
                        .output(
                            str(screenshot_path),
                            vframes=1,
                            format='image2',
                            vcodec='mjpeg',
                            **{'q:v': 2}  # 高品質
                        )
                        .overwrite_output()
                        .run(capture_stdout=True, capture_stderr=True, quiet=True)
                    )

                    # 画像リサイズ（オプション）
                    if Image and self.screenshot_width:
                        self._resize_image(screenshot_path, self.screenshot_width)

                    # スクリーンショット情報を記録
                    screenshot_info = {
                        'index': i + 1,
                        'timestamp': timestamp,
                        'timestamp_formatted': format_duration(timestamp),
                        'filename': screenshot_filename,
                        'path': str(screenshot_path),
                        'relative_path': f"screenshots/{screenshot_filename}",
                        'size': screenshot_path.stat().st_size if screenshot_path.exists() else 0
                    }

                    # 対応するテキストセグメントを取得
                    if analysis_data and 'segments' in analysis_data:
                        segment_text = self._find_segment_text(timestamp, analysis_data['segments'])
                        screenshot_info['segment_text'] = segment_text

                    screenshots.append(screenshot_info)
                    self.logger.debug(f"スクリーンショット生成: {screenshot_filename}")

                except Exception as e:
                    self.logger.warning(f"スクリーンショット抽出失敗 ({timestamp}s): {e}")

            self.logger.info(f"✅ {len(screenshots)} 枚のスクリーンショットを抽出")
            return screenshots

        except Exception as e:
            error_msg = f"スクリーンショット抽出エラー: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg)

    def generate_report(self,
                       transcript_data: Optional[Dict[str, Any]],
                       analysis_data: Optional[Dict[str, Any]],
                       screenshots: List[Dict[str, Any]],
                       output_dir: Path) -> Path:
        """
        統合レポートを生成

        Args:
            transcript_data: 文字起こしデータ
            analysis_data: 分析データ
            screenshots: スクリーンショット情報
            output_dir: 出力ディレクトリ

        Returns:
            生成されたレポートファイルのパス

        Raises:
            RuntimeError: レポート生成失敗
        """
        self.logger.info("レポート生成開始...")

        try:
            # Markdownレポート生成
            if self.format == 'markdown' or self.format == 'both':
                markdown_path = self._generate_markdown_report(
                    transcript_data, analysis_data, screenshots, output_dir
                )

            # HTMLレポート生成（オプション）
            if self.format == 'html' or self.format == 'both':
                html_path = self._generate_html_report(
                    transcript_data, analysis_data, screenshots, output_dir
                )

            # メインレポートファイルパスを決定
            if self.format == 'html':
                return html_path
            else:
                return markdown_path

        except Exception as e:
            error_msg = f"レポート生成エラー: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg)

    def _determine_screenshot_timestamps(self,
                                       duration: float,
                                       analysis_data: Optional[Dict[str, Any]]) -> List[float]:
        """
        スクリーンショット抽出タイムスタンプを決定

        Args:
            duration: 動画時間
            analysis_data: 分析データ

        Returns:
            タイムスタンプのリスト
        """
        timestamps = []

        if analysis_data and 'segments' in analysis_data:
            # 重要なセグメントから選択
            segments = analysis_data['segments']
            important_segments = []

            # セグメントの重要度を評価
            for segment in segments:
                # 長いセグメント、高信頼度セグメントを重要とみなす
                segment_length = segment.get('end', 0) - segment.get('start', 0)
                confidence = segment.get('confidence', 0.0)
                importance_score = segment_length * confidence

                important_segments.append({
                    'timestamp': segment.get('start', 0) + segment_length / 2,  # セグメント中央
                    'score': importance_score,
                    'start': segment.get('start', 0),
                    'end': segment.get('end', 0)
                })

            # 重要度順でソート
            important_segments.sort(key=lambda x: x['score'], reverse=True)

            # 上位セグメントから選択（重複を避ける）
            min_interval = duration / (self.screenshot_count * 2)  # 最小間隔
            for segment in important_segments:
                timestamp = segment['timestamp']

                # 既存のタイムスタンプと重複しないかチェック
                if not any(abs(timestamp - existing) < min_interval for existing in timestamps):
                    timestamps.append(timestamp)

                if len(timestamps) >= self.screenshot_count:
                    break

        # 不足分は等間隔で補完
        while len(timestamps) < self.screenshot_count:
            interval = duration / (self.screenshot_count + 1)
            for i in range(1, self.screenshot_count + 1):
                candidate = i * interval

                # 既存のタイムスタンプと重複しないかチェック
                if not any(abs(candidate - existing) < interval * 0.3 for existing in timestamps):
                    timestamps.append(candidate)

                if len(timestamps) >= self.screenshot_count:
                    break

        # ソートして返す
        return sorted(timestamps[:self.screenshot_count])

    def _find_segment_text(self, timestamp: float, segments: List[Dict[str, Any]]) -> str:
        """
        タイムスタンプに対応するセグメントテキストを取得

        Args:
            timestamp: タイムスタンプ
            segments: セグメントリスト

        Returns:
            対応するテキスト
        """
        for segment in segments:
            start = segment.get('start', 0)
            end = segment.get('end', 0)

            if start <= timestamp <= end:
                return segment.get('text', '').strip()

        # 最も近いセグメントを探す
        closest_segment = min(
            segments,
            key=lambda s: min(
                abs(timestamp - s.get('start', 0)),
                abs(timestamp - s.get('end', 0))
            )
        )
        return closest_segment.get('text', '').strip()

    def _resize_image(self, image_path: Path, max_width: int) -> None:
        """
        画像をリサイズ

        Args:
            image_path: 画像ファイルパス
            max_width: 最大幅
        """
        if not Image:
            return

        try:
            with Image.open(image_path) as img:
                # 現在のサイズ
                width, height = img.size

                # リサイズが必要か判定
                if width <= max_width:
                    return

                # アスペクト比を保持してリサイズ
                ratio = max_width / width
                new_width = max_width
                new_height = int(height * ratio)

                # リサイズ実行
                resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                resized_img.save(image_path, quality=self.screenshot_quality, optimize=True)

                self.logger.debug(f"画像リサイズ: {width}x{height} -> {new_width}x{new_height}")

        except Exception as e:
            self.logger.warning(f"画像リサイズ失敗 {image_path}: {e}")

    def _generate_markdown_report(self,
                                transcript_data: Optional[Dict[str, Any]],
                                analysis_data: Optional[Dict[str, Any]],
                                screenshots: List[Dict[str, Any]],
                                output_dir: Path) -> Path:
        """
        Markdownレポートを生成

        Args:
            transcript_data: 文字起こしデータ
            analysis_data: 分析データ
            screenshots: スクリーンショット情報
            output_dir: 出力ディレクトリ

        Returns:
            生成されたMarkdownファイルのパス
        """
        report_path = output_dir / "video_analysis_report.md"

        with open(report_path, 'w', encoding='utf-8') as f:
            # ヘッダー
            f.write("# 動画分析レポート\n\n")
            f.write(f"生成日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}\n\n")

            # 概要セクション
            f.write("## 📊 概要\n\n")
            if transcript_data:
                duration = transcript_data.get('duration', 0)
                segments_count = len(transcript_data.get('segments', []))
                f.write(f"- **動画時間**: {format_duration(duration)}\n")
                f.write(f"- **セグメント数**: {segments_count:,}個\n")
                f.write(f"- **検出言語**: {transcript_data.get('language', '不明')}\n")

            if analysis_data and analysis_data.get('metadata'):
                metadata = analysis_data['metadata']
                f.write(f"- **分析時間**: {metadata.get('analysis_time', 0):.1f}秒\n")
                f.write(f"- **使用モデル**: {metadata.get('model_used', '不明')}\n")

            f.write(f"- **スクリーンショット数**: {len(screenshots)}枚\n\n")

            # 階層的要約セクション（利用可能な場合）
            if analysis_data and analysis_data.get('hierarchical_summaries'):
                hierarchical = analysis_data['hierarchical_summaries']

                # Level 3 - 最終統合要約
                if hierarchical.get('level3'):
                    f.write("## 📝 統合要約\n\n")
                    f.write(f"{hierarchical['level3'].get('text', '')}\n\n")

                # Level 2 - 中間要約
                if hierarchical.get('level2'):
                    f.write("## 🎯 セクション要約\n\n")
                    for i, summary in enumerate(hierarchical['level2'][:5], 1):
                        f.write(f"### グループ {summary.get('group_id', i)}\n")
                        f.write(f"**時間範囲**: {format_duration(summary.get('start_time', 0))} - {format_duration(summary.get('end_time', 0))}\n\n")
                        f.write(f"{summary.get('text', '')}\n\n")

                # 重要な瞬間（階層的要約から）
                if analysis_data.get('key_moments'):
                    f.write("## 🌟 重要な瞬間\n\n")
                    for i, moment in enumerate(analysis_data['key_moments'][:10], 1):
                        importance = moment.get('importance_score', 0)
                        importance_icon = '🔴' if importance > 0.8 else '🟡' if importance > 0.5 else '🟢'
                        f.write(f"{i}. {importance_icon} **[{format_duration(moment.get('start_time', 0))}]** ")
                        f.write(f"(重要度: {importance:.1%})\n")
                        f.write(f"   - {moment.get('preview', '')}\n")
                        f.write(f"   - 理由: {moment.get('reason', '')}\n\n")

            # 通常の要約セクション（階層的要約がない場合）
            elif analysis_data and analysis_data.get('summary'):
                f.write("## 📝 要約\n\n")
                summary = analysis_data['summary'].get('main_summary', '')
                f.write(f"{summary}\n\n")

            # 重要ポイントセクション（階層的要約がない場合）
            if analysis_data and analysis_data.get('key_points') and not analysis_data.get('hierarchical_summaries'):
                f.write("## 🎯 重要ポイント\n\n")
                for i, point in enumerate(analysis_data['key_points'][:10], 1):
                    importance = point.get('importance', 'medium')
                    importance_icon = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(importance, '⚪')
                    f.write(f"{i}. {importance_icon} {point.get('point', '') if isinstance(point, dict) else point}\n")
                    if isinstance(point, dict) and point.get('category'):
                        f.write(f"   - カテゴリ: {point['category']}\n")
                f.write("\n")

            # トピックセクション
            if analysis_data and analysis_data.get('topics'):
                f.write("## 📚 主要トピック\n\n")
                for topic in analysis_data['topics'][:5]:
                    f.write(f"### {topic.get('topic', '')}\n")
                    f.write(f"{topic.get('description', '')}\n\n")

            # スクリーンショットセクション
            if screenshots:
                f.write("## 📸 スクリーンショット\n\n")
                for screenshot in screenshots:
                    f.write(f"### {screenshot['timestamp_formatted']}\n")
                    f.write(f"![Screenshot {screenshot['index']}]({screenshot['relative_path']})\n")
                    if screenshot.get('segment_text'):
                        f.write(f"\n**該当箇所のテキスト:**\n")
                        f.write(f"> {screenshot['segment_text']}\n")
                    f.write("\n")

            # キーワードセクション
            if analysis_data and analysis_data.get('keywords'):
                f.write("## 🏷️ キーワード\n\n")
                keywords = analysis_data['keywords'][:20]
                f.write(", ".join(f"`{kw}`" for kw in keywords))
                f.write("\n\n")

            # 感情分析セクション
            if analysis_data and analysis_data.get('sentiment'):
                sentiment = analysis_data['sentiment']
                f.write("## 😊 感情分析\n\n")
                f.write(f"- **全体的な感情**: {sentiment.get('overall', 'neutral')}\n")
                f.write(f"- **信頼度**: {sentiment.get('confidence', 0.0):.1%}\n")
                if sentiment.get('emotions'):
                    f.write(f"- **検出された感情**: {', '.join(sentiment['emotions'])}\n")
                f.write("\n")

            # 階層的分析メタデータ
            if analysis_data and analysis_data.get('metadata') and analysis_data.get('hierarchical_summaries'):
                metadata = analysis_data['metadata']
                f.write("## 📊 階層的分析統計\n\n")
                f.write(f"- **処理時間**: {metadata.get('processing_time', 0):.1f}秒\n")
                f.write(f"- **総セグメント数**: {metadata.get('total_segments', 0)}個\n")
                f.write(f"- **階層数**: {metadata.get('hierarchy_levels', 3)}層\n")
                f.write(f"- **圧縮達成率**: {metadata.get('reduction_achieved', 0):.1%}\n")
                if metadata.get('level_stats'):
                    f.write("- **各層の統計**:\n")
                    for level, stats in metadata.get('level_stats', {}).items():
                        f.write(f"  - {level}: {stats.get('count', 0)}個の要約\n")
                f.write("\n")

            # 品質メトリクス
            if analysis_data and analysis_data.get('quality_metrics'):
                metrics = analysis_data['quality_metrics']
                f.write("## 📈 品質メトリクス\n\n")
                f.write(f"- **平均信頼度**: {metrics.get('average_confidence', 0.0):.1%}\n")

                if 'confidence_distribution' in metrics:
                    dist = metrics['confidence_distribution']
                    f.write("- **信頼度分布**:\n")
                    f.write(f"  - 高 (80%以上): {dist.get('high', 0)}セグメント\n")
                    f.write(f"  - 中 (50-80%): {dist.get('medium', 0)}セグメント\n")
                    f.write(f"  - 低 (50%未満): {dist.get('low', 0)}セグメント\n")

                if 'text_metrics' in metrics:
                    text_metrics = metrics['text_metrics']
                    f.write(f"- **総単語数**: {text_metrics.get('total_words', 0):,}語\n")
                    f.write(f"- **総文字数**: {text_metrics.get('total_characters', 0):,}文字\n")

                f.write("\n")

            # 推奨事項セクション
            if analysis_data and analysis_data.get('recommendations'):
                f.write("## 💡 推奨事項\n\n")
                for i, rec in enumerate(analysis_data['recommendations'], 1):
                    f.write(f"{i}. {rec}\n")
                f.write("\n")

            # 完全な文字起こしセクション
            if transcript_data and transcript_data.get('text'):
                f.write("## 📄 完全な文字起こし\n\n")
                if transcript_data.get('segments'):
                    for segment in transcript_data['segments']:
                        start_time = format_duration(segment.get('start', 0))
                        end_time = format_duration(segment.get('end', 0))
                        text = segment.get('text', '').strip()
                        f.write(f"**[{start_time} - {end_time}]** {text}\n\n")
                else:
                    f.write(transcript_data['text'])
                    f.write("\n\n")

            # フッター
            f.write("---\n")
            f.write("*このレポートは VideoTranscriptAnalyzer により自動生成されました*\n")

        self.logger.info(f"Markdownレポート生成完了: {report_path}")
        return report_path

    def _generate_html_report(self,
                            transcript_data: Optional[Dict[str, Any]],
                            analysis_data: Optional[Dict[str, Any]],
                            screenshots: List[Dict[str, Any]],
                            output_dir: Path) -> Path:
        """
        HTMLレポートを生成

        Args:
            transcript_data: 文字起こしデータ
            analysis_data: 分析データ
            screenshots: スクリーンショット情報
            output_dir: 出力ディレクトリ

        Returns:
            生成されたHTMLファイルのパス
        """
        report_path = output_dir / "video_analysis_report.html"

        # 基本的なHTMLテンプレート
        html_content = f"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>動画分析レポート</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 40px; line-height: 1.6; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; }}
        .section {{ margin: 20px 0; padding: 15px; border-left: 4px solid #667eea; }}
        .screenshot {{ max-width: 100%; height: auto; border: 1px solid #ddd; border-radius: 5px; }}
        .timestamp {{ color: #666; font-weight: bold; }}
        .keyword {{ background: #f0f0f0; padding: 2px 6px; border-radius: 3px; margin: 2px; display: inline-block; }}
        .confidence-high {{ color: #28a745; }}
        .confidence-medium {{ color: #ffc107; }}
        .confidence-low {{ color: #dc3545; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📹 動画分析レポート</h1>
        <p>生成日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}</p>
    </div>
"""

        # 概要セクション
        if transcript_data or analysis_data:
            html_content += '<div class="section"><h2>📊 概要</h2><ul>'

            if transcript_data:
                duration = transcript_data.get('duration', 0)
                segments_count = len(transcript_data.get('segments', []))
                html_content += f'<li><strong>動画時間:</strong> {format_duration(duration)}</li>'
                html_content += f'<li><strong>セグメント数:</strong> {segments_count:,}個</li>'
                html_content += f'<li><strong>検出言語:</strong> {transcript_data.get("language", "不明")}</li>'

            html_content += f'<li><strong>スクリーンショット数:</strong> {len(screenshots)}枚</li>'
            html_content += '</ul></div>'

        # 階層的要約セクション（利用可能な場合）
        if analysis_data and analysis_data.get('hierarchical_summaries'):
            hierarchical = analysis_data['hierarchical_summaries']

            # Level 3 - 最終統合要約
            if hierarchical.get('level3'):
                html_content += f'<div class="section"><h2>📝 統合要約</h2><p>{hierarchical["level3"].get("text", "")}</p></div>'

            # Level 2 - 中間要約
            if hierarchical.get('level2'):
                html_content += '<div class="section"><h2>🎯 セクション要約</h2>'
                for summary in hierarchical['level2'][:5]:
                    html_content += f'<h3>グループ {summary.get("group_id", 0) + 1}</h3>'
                    html_content += f'<p class="timestamp">時間範囲: {format_duration(summary.get("start_time", 0))} - {format_duration(summary.get("end_time", 0))}</p>'
                    html_content += f'<p>{summary.get("text", "")}</p>'
                html_content += '</div>'

            # 重要な瞬間
            if analysis_data.get('key_moments'):
                html_content += '<div class="section"><h2>🌟 重要な瞬間</h2><ul>'
                for moment in analysis_data['key_moments'][:10]:
                    importance = moment.get('importance_score', 0)
                    importance_class = 'confidence-high' if importance > 0.8 else 'confidence-medium' if importance > 0.5 else 'confidence-low'
                    html_content += f'<li><span class="{importance_class}">[{format_duration(moment.get("start_time", 0))}] (重要度: {importance:.1%})</span><br>'
                    html_content += f'{moment.get("preview", "")}<br>'
                    html_content += f'<em>理由: {moment.get("reason", "")}</em></li>'
                html_content += '</ul></div>'

        # 通常の要約セクション（階層的要約がない場合）
        elif analysis_data and analysis_data.get('summary'):
            summary = analysis_data['summary'].get('main_summary', '')
            html_content += f'<div class="section"><h2>📝 要約</h2><p>{summary}</p></div>'

        # スクリーンショットセクション
        if screenshots:
            html_content += '<div class="section"><h2>📸 スクリーンショット</h2>'
            for screenshot in screenshots:
                html_content += f'<h3 class="timestamp">{screenshot["timestamp_formatted"]}</h3>'
                html_content += f'<img src="{screenshot["relative_path"]}" alt="Screenshot {screenshot["index"]}" class="screenshot"><br>'
                if screenshot.get('segment_text'):
                    html_content += f'<blockquote>{screenshot["segment_text"]}</blockquote>'
            html_content += '</div>'

        html_content += '</body></html>'

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        self.logger.info(f"HTMLレポート生成完了: {report_path}")
        return report_path