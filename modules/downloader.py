"""
動画ダウンロードモジュール

yt-dlpを使用して動画をダウンロードする機能を提供：
- YouTube動画のダウンロード
- M3U8ストリームの処理
- 様々な動画サイト対応
"""

import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
import json

try:
    import yt_dlp
except ImportError:
    print("yt-dlp が見つかりません。以下のコマンドでインストールしてください:")
    print("pip install yt-dlp")
    sys.exit(1)

from .utils import safe_filename, format_filesize, get_available_space, validate_url


class VideoDownloader:
    """動画ダウンロードクラス"""

    def __init__(self, config: Dict[str, Any]):
        """
        初期化

        Args:
            config: ダウンローダー設定
        """
        self.config = config
        self.logger = logging.getLogger('VideoTranscriptAnalyzer.downloader')

        # デフォルト設定
        self.format_selector = config.get('format', 'best[height<=720]')
        self.timeout = config.get('timeout', 3600)
        self.retries = config.get('retries', 3)
        self.max_filesize = config.get('max_filesize_mb', 1000) * 1024 * 1024  # MB to bytes

    def download(self, url: str, output_dir: Path) -> Path:
        """
        動画をダウンロード

        Args:
            url: 動画URL
            output_dir: 出力ディレクトリ

        Returns:
            ダウンロードされた動画ファイルのパス

        Raises:
            ValueError: 無効なURL
            RuntimeError: ダウンロード失敗
            OSError: 容量不足
        """
        self.logger.info(f"動画ダウンロード開始: {url}")

        # URL妥当性チェック
        if not validate_url(url) and not url.endswith('.m3u8'):
            raise ValueError(f"無効なURL: {url}")

        # 容量チェック
        available_space = get_available_space(output_dir)
        if available_space < self.max_filesize:
            raise OSError(f"容量不足: 利用可能容量 {format_filesize(available_space)}")

        # 出力ディレクトリの作成
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 動画情報を取得
            info = self._get_video_info(url)
            self.logger.info(f"動画タイトル: {info.get('title', 'Unknown')}")
            self.logger.info(f"動画時間: {self._format_duration(info.get('duration', 0))}")

            # ファイル名を生成
            safe_title = safe_filename(info.get('title', 'video'))
            filename_template = output_dir / f"{safe_title}.%(ext)s"

            # ダウンロード設定
            ydl_opts = self._get_download_options(str(filename_template))

            # ダウンロード実行
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self.logger.info("ダウンロード開始...")
                ydl.download([url])

            # ダウンロード済みファイルを検索
            downloaded_file = self._find_downloaded_file(output_dir, safe_title)

            if downloaded_file and downloaded_file.exists():
                file_size = downloaded_file.stat().st_size
                self.logger.info(f"✅ ダウンロード完了: {downloaded_file}")
                self.logger.info(f"ファイルサイズ: {format_filesize(file_size)}")
                return downloaded_file
            else:
                raise RuntimeError("ダウンロードファイルが見つかりません")

        except yt_dlp.DownloadError as e:
            error_msg = f"yt-dlp ダウンロードエラー: {str(e)}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)

        except Exception as e:
            error_msg = f"予期しないダウンロードエラー: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg)

    def _get_video_info(self, url: str) -> Dict[str, Any]:
        """
        動画情報を取得

        Args:
            url: 動画URL

        Returns:
            動画情報辞書
        """
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return info
        except Exception as e:
            self.logger.warning(f"動画情報取得失敗: {e}")
            return {'title': 'unknown_video', 'duration': 0}

    def _get_download_options(self, output_template: str) -> Dict[str, Any]:
        """
        yt-dlpのダウンロードオプションを生成

        Args:
            output_template: 出力ファイル名テンプレート

        Returns:
            yt-dlpオプション辞書
        """
        return {
            'format': self.format_selector,
            'outtmpl': output_template,
            'writeinfojson': True,  # メタデータを保存
            'writethumbnail': True,  # サムネイルを保存
            'embedsubs': False,  # 字幕は埋め込まない
            'writesubtitles': False,  # 字幕ファイルも作成しない
            'retries': self.retries,
            'socket_timeout': self.timeout,
            'http_chunk_size': 1024 * 1024,  # 1MB chunks
            'concurrent_fragment_downloads': 4,
            'ignoreerrors': False,
            'no_warnings': False,
            'extractaudio': False,
            'audioformat': 'best',
            'prefer_free_formats': True,
            'postprocessors': [
                {
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }
            ],
            # プログレスフック
            'progress_hooks': [self._progress_hook],
        }

    def _progress_hook(self, d: Dict[str, Any]) -> None:
        """
        ダウンロード進行状況フック

        Args:
            d: 進行状況辞書
        """
        if d['status'] == 'downloading':
            if 'total_bytes' in d and d['total_bytes']:
                downloaded = d.get('downloaded_bytes', 0)
                total = d['total_bytes']
                percentage = (downloaded / total) * 100
                speed = d.get('speed', 0)

                if speed:
                    speed_str = f" | {format_filesize(int(speed))}/s"
                else:
                    speed_str = ""

                self.logger.info(
                    f"ダウンロード中: {percentage:.1f}% "
                    f"({format_filesize(downloaded)}/{format_filesize(total)}){speed_str}"
                )

        elif d['status'] == 'finished':
            self.logger.info("ダウンロード完了、後処理中...")

        elif d['status'] == 'error':
            self.logger.error(f"ダウンロードエラー: {d.get('error', 'Unknown error')}")

    def _find_downloaded_file(self, output_dir: Path, title_prefix: str) -> Optional[Path]:
        """
        ダウンロード済みファイルを検索

        Args:
            output_dir: 出力ディレクトリ
            title_prefix: ファイル名プレフィックス

        Returns:
            見つかったファイルパス、またはNone
        """
        # 動画ファイル拡張子
        video_extensions = ['.mp4', '.mkv', '.webm', '.avi', '.mov', '.flv']

        # プレフィックスでファイルを検索
        for ext in video_extensions:
            pattern = f"{title_prefix}*{ext}"
            files = list(output_dir.glob(pattern))
            if files:
                # 最大のファイル（本体と推定）を返す
                return max(files, key=lambda f: f.stat().st_size)

        # 見つからない場合は、出力ディレクトリ内の最大動画ファイルを返す
        all_video_files = []
        for ext in video_extensions:
            all_video_files.extend(output_dir.glob(f"*{ext}"))

        if all_video_files:
            return max(all_video_files, key=lambda f: f.stat().st_size)

        return None

    def _format_duration(self, duration: Optional[float]) -> str:
        """
        秒数を時間文字列に変換

        Args:
            duration: 秒数

        Returns:
            フォーマット済み時間文字列
        """
        if not duration:
            return "不明"

        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        seconds = int(duration % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"

    def get_supported_sites(self) -> List[str]:
        """
        サポートされているサイト一覧を取得

        Returns:
            サポートサイトのリスト
        """
        try:
            extractors = yt_dlp.extractor.gen_extractors()
            sites = []
            for extractor in extractors:
                if hasattr(extractor, 'IE_NAME') and extractor.IE_NAME:
                    sites.append(extractor.IE_NAME)
            return sorted(list(set(sites)))
        except Exception as e:
            self.logger.warning(f"サポートサイト一覧取得失敗: {e}")
            return ['youtube', 'generic']

    def validate_url_accessibility(self, url: str) -> bool:
        """
        URLアクセス可能性をチェック

        Args:
            url: チェックするURL

        Returns:
            アクセス可能かどうか
        """
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                ydl.extract_info(url, download=False)
                return True
        except Exception as e:
            self.logger.warning(f"URL アクセス不可: {url} - {e}")
            return False

    def estimate_download_size(self, url: str) -> Optional[int]:
        """
        ダウンロードサイズを推定

        Args:
            url: 動画URL

        Returns:
            推定サイズ（バイト）、または None
        """
        try:
            info = self._get_video_info(url)
            formats = info.get('formats', [])

            # 指定されたフォーマット選択基準に最も近いフォーマットを選択
            selected_format = None
            for fmt in formats:
                if fmt.get('height', 0) <= 720:  # 720p以下
                    selected_format = fmt
                    break

            if selected_format and 'filesize' in selected_format:
                return selected_format['filesize']

            # ファイルサイズが不明な場合は、ビットレートから推定
            if selected_format and 'tbr' in selected_format and 'duration' in info:
                bitrate = selected_format['tbr']  # kbps
                duration = info['duration']  # seconds
                estimated_size = (bitrate * 1000 * duration) // 8  # bytes
                return int(estimated_size)

        except Exception as e:
            self.logger.warning(f"サイズ推定失敗: {e}")

        return None