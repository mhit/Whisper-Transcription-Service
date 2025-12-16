"""
文字起こしモジュール

音声抽出とWhisperを使用した文字起こし機能を提供：
- ffmpegによる音声抽出
- OpenAI Whisperでの高精度文字起こし
- タイムスタンプ付きセグメント生成
"""

import logging
import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import time
import numpy as np

try:
    import whisper
    import torch
except ImportError:
    print("Whisper または PyTorch が見つかりません。以下のコマンドでインストールしてください:")
    print("pip install openai-whisper torch")
    sys.exit(1)

try:
    import ffmpeg
except ImportError:
    print("ffmpeg-python が見つかりません。以下のコマンドでインストールしてください:")
    print("pip install ffmpeg-python")
    sys.exit(1)

from .utils import format_duration, format_filesize, run_command, cleanup_temp_files


class AudioTranscriber:
    """音声文字起こしクラス"""

    def __init__(self, config: Dict[str, Any]):
        """
        初期化

        Args:
            config: 文字起こし設定
        """
        self.config = config
        self.logger = logging.getLogger('VideoTranscriptAnalyzer.transcriber')

        # 設定値
        self.model_name = config.get('model', 'large-v3')
        self.language = config.get('language', 'ja')
        self.device = config.get('device', 'auto')
        self.chunk_length = config.get('chunk_length_seconds', 30)
        self.temperature = config.get('temperature', 0.0)

        # デバイス設定
        self.device = self._setup_device()
        self.logger.info(f"使用デバイス: {self.device}")

        # Whisperモデルの初期化
        self.model = None
        self._load_model()

    def _setup_device(self) -> str:
        """
        使用デバイスを設定

        Returns:
            デバイス名
        """
        if self.device == 'auto':
            if torch.cuda.is_available():
                try:
                    gpu_info = torch.cuda.get_device_name(0)
                    self.logger.info(f"GPU detected: {gpu_info}")

                    # GPU compute capability check
                    capability = torch.cuda.get_device_capability(0)
                    self.logger.info(f"GPU compute capability: {capability[0]}.{capability[1]}")

                    # Check PyTorch CUDA support
                    if "RTX 50" in gpu_info or "RTX 5070" in gpu_info or "RTX 5080" in gpu_info or "RTX 5090" in gpu_info:
                        # RTX 50 series detected - check if PyTorch supports it
                        if capability[0] == 12:  # sm_120 (Blackwell)
                            self.logger.info("RTX 50 series (Blackwell) detected - checking PyTorch compatibility")
                            try:
                                # Test if CUDA operations work
                                test_tensor = torch.tensor([1.0]).cuda()
                                _ = test_tensor * 2
                                self.logger.info("✅ RTX 50 series GPU is compatible with current PyTorch")
                                return 'cuda'
                            except Exception as e:
                                self.logger.warning(f"RTX 50 series GPU not fully compatible: {e}")
                                self.logger.warning("Falling back to CPU mode. Install PyTorch Nightly for GPU support.")
                                return 'cpu'

                    # For other GPUs, use CUDA directly
                    return 'cuda'

                except Exception as e:
                    self.logger.warning(f"GPU detection error: {e}")
                    return 'cuda'  # Try CUDA anyway

            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                return 'mps'
            else:
                return 'cpu'
        return self.device

    def _load_model(self) -> None:
        """Whisperモデルを読み込み"""
        try:
            self.logger.info(f"Whisperモデル ({self.model_name}) を読み込み中...")
            start_time = time.time()

            self.model = whisper.load_model(
                name=self.model_name,
                device=self.device
            )

            load_time = time.time() - start_time
            self.logger.info(f"✅ モデル読み込み完了 ({load_time:.1f}秒)")

        except Exception as e:
            error_msg = f"Whisperモデル読み込み失敗: {e}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)

    def extract_audio(self, video_path: Path, output_dir: Path) -> Path:
        """
        動画から音声を抽出

        Args:
            video_path: 動画ファイルパス
            output_dir: 出力ディレクトリ

        Returns:
            抽出された音声ファイルのパス

        Raises:
            FileNotFoundError: 動画ファイルが見つからない
            RuntimeError: 音声抽出失敗
        """
        if not video_path.exists():
            raise FileNotFoundError(f"動画ファイルが見つかりません: {video_path}")

        # 出力音声ファイルパス
        audio_filename = video_path.stem + "_audio.wav"
        audio_path = output_dir / audio_filename

        self.logger.info(f"音声抽出開始: {video_path} -> {audio_path}")

        try:
            # ffmpegで音声抽出
            start_time = time.time()

            (
                ffmpeg
                .input(str(video_path))
                .output(
                    str(audio_path),
                    acodec='pcm_s16le',  # 16-bit PCM
                    ac=1,  # モノラル
                    ar=16000,  # 16kHz サンプリングレート（Whisper推奨）
                    loglevel='error'
                )
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )

            extract_time = time.time() - start_time
            file_size = audio_path.stat().st_size

            self.logger.info(f"✅ 音声抽出完了 ({extract_time:.1f}秒)")
            self.logger.info(f"音声ファイル: {audio_path}")
            self.logger.info(f"ファイルサイズ: {format_filesize(file_size)}")

            return audio_path

        except ffmpeg.Error as e:
            error_msg = f"FFmpeg音声抽出エラー: {e.stderr.decode() if e.stderr else str(e)}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)

        except Exception as e:
            error_msg = f"予期しない音声抽出エラー: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg)

    def transcribe(self, audio_path: Path, output_dir: Path) -> Dict[str, Any]:
        """
        音声ファイルを文字起こし

        Args:
            audio_path: 音声ファイルパス
            output_dir: 出力ディレクトリ

        Returns:
            文字起こし結果（segments, text, language等を含む辞書）

        Raises:
            FileNotFoundError: 音声ファイルが見つからない
            RuntimeError: 文字起こし失敗
        """
        if not audio_path.exists():
            raise FileNotFoundError(f"音声ファイルが見つかりません: {audio_path}")

        if not self.model:
            raise RuntimeError("Whisperモデルが読み込まれていません")

        self.logger.info(f"文字起こし開始: {audio_path}")
        start_time = time.time()

        try:
            # 言語に応じた初期プロンプトを設定
            initial_prompts = {
                'ja': "これは日本語のセミナーの音声です。",
                'en': "This is an audio recording from a seminar.",
                'auto': None
            }
            initial_prompt = initial_prompts.get(self.language, None)

            # Whisperで文字起こし実行 - 改良されたパラメータを使用
            result = self.model.transcribe(
                str(audio_path),
                # language=self.language if self.language != 'auto' else None,
                # task="transcribe",  # 文字起こし（翻訳ではない）
                # temperature=self.temperature,
                # best_of=5,  # 複数候補から最良を選択
                # beam_size=5,  # ビームサーチ
                # patience=1.0,  # デコーディング忍耐度
                # suppress_tokens=[-1],  # トークン抑制
                # initial_prompt=initial_prompt,  # 言語別初期プロンプト
                # condition_on_previous_text=True,  # 前のテキストを条件付け
                # compression_ratio_threshold=2.4,  # 圧縮率閾値
                # logprob_threshold=-1.0,  # ログ確率閾値
                # no_speech_threshold=0.6,  # 無音判定閾値
                # verbose=False,
                # word_timestamps=False  # 単語レベルのタイムスタンプは一旦無効化（精度優先）
                language="ja",
                task="transcribe",
                verbose=True,
                temperature=0.0,
                beam_size=5,
                best_of=5,
                patience=1.0,
                condition_on_previous_text=False,  # 幻覚防止
                compression_ratio_threshold=2.4,
                logprob_threshold=-1.0,
                no_speech_threshold=0.6,
                word_timestamps=False,
                initial_prompt=None,  # 初期プロンプトなし
                suppress_tokens=[-1],  # トークン抑制なし
                without_timestamps=False
            )

            transcribe_time = time.time() - start_time

            # 結果の処理
            processed_result = self._process_transcription_result(result)

            # 統計情報の追加
            processed_result['metadata'] = {
                'audio_file': str(audio_path),
                'model': self.model_name,
                'language': result.get('language', self.language),
                'duration': result.get('duration', 0),
                'transcription_time': transcribe_time,
                'device': self.device,
                'segments_count': len(processed_result.get('segments', [])),
                'word_count': len(processed_result.get('text', '').split()),
                'processing_speed': result.get('duration', 0) / transcribe_time if transcribe_time > 0 else 0
            }

            # テキストファイルとして保存
            self._save_text_outputs(processed_result, output_dir)

            self.logger.info(f"✅ 文字起こし完了 ({transcribe_time:.1f}秒)")
            self.logger.info(f"検出言語: {result.get('language', 'unknown')}")
            self.logger.info(f"セグメント数: {len(processed_result.get('segments', []))}")
            self.logger.info(f"総文字数: {len(processed_result.get('text', ''))}")
            self.logger.info(f"処理速度: {processed_result['metadata']['processing_speed']:.1f}x realtime")

            return processed_result

        except Exception as e:
            error_msg = f"文字起こしエラー: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg)

    def _process_transcription_result(self, raw_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Whisperの生結果を処理

        Args:
            raw_result: Whisperの生結果

        Returns:
            処理済み結果
        """
        processed_segments = []

        for segment in raw_result.get('segments', []):
            processed_segment = {
                'id': segment.get('id'),
                'start': segment.get('start', 0.0),
                'end': segment.get('end', 0.0),
                'text': segment.get('text', '').strip(),
                'words': []
            }

            # 単語レベル情報を処理（存在する場合のみ）
            if 'words' in segment and segment['words']:
                for word in segment['words']:
                    processed_word = {
                        'word': word.get('word', '').strip(),
                        'start': word.get('start', 0.0),
                        'end': word.get('end', 0.0),
                        'probability': word.get('probability', 0.0)
                    }
                    processed_segment['words'].append(processed_word)

            # セグメントの信頼度を計算（単語の平均確率、または全体の確率）
            if processed_segment['words']:
                avg_probability = sum(w['probability'] for w in processed_segment['words']) / len(processed_segment['words'])
                processed_segment['confidence'] = avg_probability
            elif 'avg_logprob' in segment:
                # 単語情報がない場合はセグメント全体の確率を使用
                processed_segment['confidence'] = np.exp(segment['avg_logprob'])
            else:
                processed_segment['confidence'] = 1.0  # デフォルト値

            processed_segments.append(processed_segment)

        return {
            'text': raw_result.get('text', ''),
            'segments': processed_segments,
            'language': raw_result.get('language'),
            'duration': raw_result.get('duration', 0)
        }

    def _save_text_outputs(self, result: Dict[str, Any], output_dir: Path) -> None:
        """
        文字起こし結果をテキストファイルとして保存

        Args:
            result: 文字起こし結果
            output_dir: 出力ディレクトリ
        """
        # プレーンテキスト保存
        text_file = output_dir / "transcript.txt"
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(result.get('text', ''))

        # タイムスタンプ付きテキスト保存
        timestamped_file = output_dir / "transcript_timestamped.txt"
        with open(timestamped_file, 'w', encoding='utf-8') as f:
            for segment in result.get('segments', []):
                start_time = format_duration(segment['start'])
                end_time = format_duration(segment['end'])
                f.write(f"[{start_time} - {end_time}] {segment['text']}\n")

        # SRT字幕ファイル保存
        srt_file = output_dir / "transcript.srt"
        self._save_srt_file(result.get('segments', []), srt_file)

        # VTT字幕ファイル保存
        vtt_file = output_dir / "transcript.vtt"
        self._save_vtt_file(result.get('segments', []), vtt_file)

        self.logger.info(f"テキストファイル保存: {text_file}")
        self.logger.info(f"タイムスタンプ付きテキスト保存: {timestamped_file}")
        self.logger.info(f"SRT字幕ファイル保存: {srt_file}")
        self.logger.info(f"VTT字幕ファイル保存: {vtt_file}")

    def _save_srt_file(self, segments: List[Dict[str, Any]], srt_path: Path) -> None:
        """
        SRT字幕ファイルを保存

        Args:
            segments: セグメントリスト
            srt_path: SRTファイルパス
        """
        with open(srt_path, 'w', encoding='utf-8') as f:
            for i, segment in enumerate(segments, 1):
                start_time = self._seconds_to_srt_time(segment['start'])
                end_time = self._seconds_to_srt_time(segment['end'])

                f.write(f"{i}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{segment['text'].strip()}\n\n")

    def _save_vtt_file(self, segments: List[Dict[str, Any]], vtt_path: Path) -> None:
        """
        VTT字幕ファイルを保存

        Args:
            segments: セグメントリスト
            vtt_path: VTTファイルパス
        """
        with open(vtt_path, 'w', encoding='utf-8') as f:
            f.write("WEBVTT\n\n")

            for segment in segments:
                start_time = self._seconds_to_vtt_time(segment['start'])
                end_time = self._seconds_to_vtt_time(segment['end'])

                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{segment['text'].strip()}\n\n")

    def _seconds_to_srt_time(self, seconds: float) -> str:
        """
        秒数をSRT時間形式に変換

        Args:
            seconds: 秒数

        Returns:
            SRT時間文字列 (HH:MM:SS,mmm)
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)

        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"

    def _seconds_to_vtt_time(self, seconds: float) -> str:
        """
        秒数をVTT時間形式に変換

        Args:
            seconds: 秒数

        Returns:
            VTT時間文字列 (HH:MM:SS.mmm)
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)

        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"

    def get_model_info(self) -> Dict[str, Any]:
        """
        現在のモデル情報を取得

        Returns:
            モデル情報辞書
        """
        return {
            'model_name': self.model_name,
            'language': self.language,
            'device': self.device,
            'is_multilingual': self.model_name.endswith('.en') if self.model else False,
            'available_models': whisper.available_models()
        }

    def estimate_processing_time(self, audio_duration: float) -> float:
        """
        処理時間を推定

        Args:
            audio_duration: 音声時間（秒）

        Returns:
            推定処理時間（秒）
        """
        # デバイス別の大まかな処理速度倍率
        speed_multipliers = {
            'cuda': 0.1,    # GPU: 10x realtime
            'mps': 0.2,     # Apple Silicon: 5x realtime
            'cpu': 0.5      # CPU: 2x realtime
        }

        multiplier = speed_multipliers.get(self.device, 0.5)
        return audio_duration * multiplier

    def cleanup_temp_files(self, output_dir: Path) -> None:
        """
        一時ファイルをクリーンアップ

        Args:
            output_dir: クリーンアップ対象ディレクトリ
        """
        cleanup_count = cleanup_temp_files(output_dir, "*temp*")
        if cleanup_count > 0:
            self.logger.info(f"一時ファイル {cleanup_count} 個をクリーンアップしました")