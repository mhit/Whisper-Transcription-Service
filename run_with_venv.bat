@echo off
echo ========================================
echo VideoTranscriptAnalyzer 実行スクリプト
echo ========================================
echo.

REM 仮想環境をアクティベート
call venv\Scripts\activate.bat

REM Pythonバージョン確認
python --version

echo.
echo 開始中...
echo.

REM メインスクリプトを実行
python video_transcript_analyzer.py %*

echo.
echo 完了しました
pause