"""
ユーティリティ関数モジュール

共通で使用される機能を提供：
- ロギング設定
- 依存関係チェック
- ファイル操作ヘルパー
"""

import logging
import os
import sys
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
import platform
import requests


def setup_logging(config: Any) -> logging.Logger:
    """
    ロギング設定を初期化

    Args:
        config: ロギング設定辞書または名前（後方互換性のため）

    Returns:
        設定済みロガー
    """
    # 文字列が渡された場合はデフォルト設定を使用（後方互換性）
    if isinstance(config, str):
        config = {
            'level': 'INFO',
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        }

    # ログレベルの設定
    level = config.get('level', 'INFO')
    log_format = config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # ロガーの設定
    logger = logging.getLogger('VideoTranscriptAnalyzer')
    logger.setLevel(getattr(logging, level.upper()))

    # 既存のハンドラーをクリア
    logger.handlers.clear()

    # コンソールハンドラーの追加
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))
    console_formatter = logging.Formatter(log_format)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # ファイルハンドラーの追加（指定されている場合）
    if 'file' in config:
        log_file = Path(config['file'])
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(getattr(logging, level.upper()))
        file_formatter = logging.Formatter(log_format)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


def check_dependencies() -> None:
    """
    必要な依存関係をチェック

    Raises:
        RuntimeError: 必要な依存関係が不足している場合
    """
    missing_deps = []

    # Python パッケージのチェック
    # パッケージ名: インポート名のマッピング
    required_packages = {
        'yt_dlp': 'yt_dlp',
        'whisper': 'whisper',
        'openai': 'openai',
        'ffmpeg-python': 'ffmpeg',
        'Pillow': 'PIL',
        'requests': 'requests',
        'pyyaml': 'yaml',
        'python-dotenv': 'dotenv'
    }

    for package, import_name in required_packages.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_deps.append(f"Python package: {package}")

    # システムツールのチェック
    system_tools = ['ffmpeg']

    for tool in system_tools:
        if not shutil.which(tool):
            missing_deps.append(f"System tool: {tool}")

    # CUDA/GPU のチェック（オプション）
    try:
        import torch
        if torch.cuda.is_available():
            logging.getLogger('VideoTranscriptAnalyzer').info("✅ CUDA GPU が利用可能です")
        else:
            logging.getLogger('VideoTranscriptAnalyzer').info("ℹ️ CUDA GPU は利用できません（CPU使用）")
    except ImportError:
        logging.getLogger('VideoTranscriptAnalyzer').warning("⚠️ PyTorch がインストールされていません")

    if missing_deps:
        error_msg = "以下の依存関係が不足しています:\n" + "\n".join(f"  - {dep}" for dep in missing_deps)
        raise RuntimeError(error_msg)


def get_system_info() -> Dict[str, str]:
    """
    システム情報を取得

    Returns:
        システム情報の辞書
    """
    return {
        'platform': platform.platform(),
        'python_version': platform.python_version(),
        'architecture': platform.architecture()[0],
        'processor': platform.processor(),
        'machine': platform.machine()
    }


def ensure_directory(path: Path) -> Path:
    """
    ディレクトリの存在を確認し、なければ作成

    Args:
        path: ディレクトリパス

    Returns:
        作成されたディレクトリパス
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_filename(filename: str) -> str:
    """
    ファイル名を安全な形式に変換

    Args:
        filename: 元のファイル名

    Returns:
        安全なファイル名
    """
    # 危険な文字を置換
    unsafe_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    safe_name = filename

    for char in unsafe_chars:
        safe_name = safe_name.replace(char, '_')

    # 先頭末尾の空白とピリオドを除去
    safe_name = safe_name.strip(' .')

    # 長すぎる場合は切り詰め
    if len(safe_name) > 200:
        safe_name = safe_name[:200]

    return safe_name


def format_duration(seconds: float) -> str:
    """
    秒数を時間:分:秒の形式でフォーマット

    Args:
        seconds: 秒数

    Returns:
        フォーマット済み時間文字列
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"


def format_filesize(size_bytes: int) -> str:
    """
    バイト数を人間が読みやすい形式でフォーマット

    Args:
        size_bytes: バイト数

    Returns:
        フォーマット済みファイルサイズ文字列
    """
    if size_bytes == 0:
        return "0B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0

    while size_bytes >= 1024.0 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1

    return f"{size_bytes:.1f}{size_names[i]}"


def run_command(command: List[str],
                cwd: Optional[Path] = None,
                timeout: Optional[int] = None,
                capture_output: bool = True) -> subprocess.CompletedProcess:
    """
    コマンドを安全に実行

    Args:
        command: 実行するコマンドのリスト
        cwd: 作業ディレクトリ
        timeout: タイムアウト（秒）
        capture_output: 出力をキャプチャするか

    Returns:
        実行結果

    Raises:
        subprocess.CalledProcessError: コマンド実行が失敗した場合
        subprocess.TimeoutExpired: タイムアウトした場合
    """
    logger = logging.getLogger('VideoTranscriptAnalyzer')

    logger.debug(f"実行コマンド: {' '.join(command)}")

    result = subprocess.run(
        command,
        cwd=cwd,
        timeout=timeout,
        capture_output=capture_output,
        text=True,
        check=False
    )

    if result.returncode != 0:
        error_msg = f"コマンド実行失敗: {' '.join(command)}\n"
        if result.stderr:
            error_msg += f"エラー出力: {result.stderr}"
        raise subprocess.CalledProcessError(result.returncode, command, error_msg)

    return result


def cleanup_temp_files(directory: Path, pattern: str = "*temp*") -> int:
    """
    一時ファイルをクリーンアップ

    Args:
        directory: クリーンアップ対象のディレクトリ
        pattern: 削除するファイルのパターン

    Returns:
        削除されたファイル数
    """
    logger = logging.getLogger('VideoTranscriptAnalyzer')

    if not directory.exists():
        return 0

    deleted_count = 0
    for temp_file in directory.glob(pattern):
        try:
            if temp_file.is_file():
                temp_file.unlink()
                deleted_count += 1
                logger.debug(f"一時ファイルを削除: {temp_file}")
            elif temp_file.is_dir():
                shutil.rmtree(temp_file)
                deleted_count += 1
                logger.debug(f"一時ディレクトリを削除: {temp_file}")
        except Exception as e:
            logger.warning(f"一時ファイル削除エラー {temp_file}: {e}")

    if deleted_count > 0:
        logger.info(f"一時ファイル {deleted_count} 個を削除しました")

    return deleted_count


def validate_url(url: str) -> bool:
    """
    URLの妥当性をチェック

    Args:
        url: チェックするURL

    Returns:
        URLが妥当かどうか
    """
    import re

    # 基本的なURL形式のチェック
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    return bool(url_pattern.match(url))


def get_available_space(path: Path) -> int:
    """
    指定パスの利用可能容量を取得（バイト）

    Args:
        path: チェックするパス

    Returns:
        利用可能容量（バイト）
    """
    try:
        stat = shutil.disk_usage(path)
        return stat.free
    except Exception:
        return 0


class ProgressTracker:
    """進行状況追跡用クラス"""

    def __init__(self, total_steps: int, logger: Optional[logging.Logger] = None):
        self.total_steps = total_steps
        self.current_step = 0
        self.logger = logger or logging.getLogger('VideoTranscriptAnalyzer')

    def update(self, step_name: str) -> None:
        """進行状況を更新"""
        self.current_step += 1
        progress = (self.current_step / self.total_steps) * 100
        self.logger.info(f"[{self.current_step}/{self.total_steps}] ({progress:.1f}%) {step_name}")

    def complete(self) -> None:
        """完了マーク"""
        self.logger.info(f"✅ 全 {self.total_steps} ステップが完了しました")


def check_ollama_installed() -> bool:
    """
    Ollamaがインストールされているかチェック

    Returns:
        インストールされている場合True
    """
    return shutil.which('ollama') is not None


def is_ollama_running() -> bool:
    """
    Ollamaサーバーが実行中かチェック

    Returns:
        実行中の場合True
    """
    try:
        response = requests.get('http://localhost:11434/api/version', timeout=2)
        return response.status_code == 200
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return False


def start_ollama_server() -> bool:
    """
    Ollamaサーバーを起動

    Returns:
        起動成功した場合True
    """
    logger = logging.getLogger('VideoTranscriptAnalyzer')

    if is_ollama_running():
        logger.info("Ollamaサーバーは既に実行中です")
        return True

    if not check_ollama_installed():
        logger.warning("Ollamaがインストールされていません")
        return False

    try:
        # Ollamaサーバーをバックグラウンドで起動
        subprocess.Popen(['ollama', 'serve'],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)

        # サーバー起動を待機（最大30秒）
        for _ in range(30):
            time.sleep(1)
            if is_ollama_running():
                logger.info("✅ Ollamaサーバーを起動しました")
                return True

        logger.warning("Ollamaサーバーの起動がタイムアウトしました")
        return False

    except Exception as e:
        logger.error(f"Ollamaサーバー起動エラー: {e}")
        return False


def pull_ollama_model(model_name: str, timeout: int = 600) -> bool:
    """
    Ollamaモデルをダウンロード

    Args:
        model_name: ダウンロードするモデル名 (例: "qwen2.5:32b", "llama2:7b")
        timeout: タイムアウト秒数（デフォルト10分）

    Returns:
        ダウンロード成功した場合True
    """
    logger = logging.getLogger('VideoTranscriptAnalyzer')

    if not check_ollama_installed():
        logger.warning("Ollamaがインストールされていません")
        return False

    try:
        # モデルが既に存在するかチェック
        result = subprocess.run(['ollama', 'list'],
                              capture_output=True,
                              text=True,
                              timeout=10)

        if model_name in result.stdout:
            logger.info(f"モデル {model_name} は既にダウンロード済みです")
            return True

        # モデルをダウンロード
        logger.info(f"モデル {model_name} をダウンロード中...")
        result = subprocess.run(['ollama', 'pull', model_name],
                              capture_output=True,
                              text=True,
                              timeout=timeout)

        if result.returncode == 0:
            logger.info(f"✅ モデル {model_name} のダウンロードが完了しました")
            return True
        else:
            logger.error(f"モデルダウンロードエラー: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error(f"モデルダウンロードがタイムアウトしました（{timeout}秒）")
        return False
    except Exception as e:
        logger.error(f"モデルダウンロードエラー: {e}")
        return False


def get_ollama_models() -> List[str]:
    """
    利用可能なOllamaモデルのリストを取得

    Returns:
        モデル名のリスト
    """
    if not check_ollama_installed():
        return []

    try:
        result = subprocess.run(['ollama', 'list'],
                              capture_output=True,
                              text=True,
                              timeout=10)

        if result.returncode == 0:
            # 出力をパースしてモデル名を抽出
            models = []
            lines = result.stdout.strip().split('\n')[1:]  # ヘッダー行をスキップ
            for line in lines:
                if line.strip():
                    model_name = line.split()[0]
                    models.append(model_name)
            return models

    except Exception:
        pass

    return []


def unload_ollama_model(model_name: Optional[str] = None) -> bool:
    """
    OllamaモデルをGPUメモリからアンロード

    Args:
        model_name: アンロードするモデル名（Noneの場合は全モデル）

    Returns:
        アンロード成功した場合True
    """
    logger = logging.getLogger('VideoTranscriptAnalyzer')

    if not is_ollama_running():
        logger.debug("Ollamaサーバーが実行されていません")
        return True  # サーバーが動いてないなら成功扱い

    try:
        # Ollama APIを使用してモデルをアンロード
        # /api/generate エンドポイントにkeep_alive=0を送信
        if model_name:
            payload = {
                "model": model_name,
                "keep_alive": 0  # 0秒でモデルをアンロード
            }
        else:
            # 全モデルをアンロードする場合は、リストを取得して順次アンロード
            models = get_ollama_models()
            for model in models:
                payload = {
                    "model": model,
                    "keep_alive": 0
                }
                requests.post('http://localhost:11434/api/generate',
                            json=payload,
                            timeout=5)
            logger.info("✅ 全Ollamaモデルをメモリからアンロードしました")
            return True

        response = requests.post('http://localhost:11434/api/generate',
                               json=payload,
                               timeout=5)

        if response.status_code in [200, 204]:
            logger.info(f"✅ モデル {model_name} をメモリからアンロードしました")
            return True
        else:
            logger.warning(f"モデルアンロード失敗: {response.status_code}")
            return False

    except requests.exceptions.Timeout:
        logger.warning("モデルアンロードがタイムアウトしました")
        return False
    except Exception as e:
        logger.error(f"モデルアンロードエラー: {e}")
        return False