#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gemini API環境設定スクリプト
APIキーを安全に環境変数として設定
"""

import os
import sys
from pathlib import Path

def setup_gemini_env():
    """Gemini API環境変数の設定"""

    print("="*60)
    print("Gemini API 環境設定")
    print("="*60)

    # .envファイルのパス
    env_file = Path(".env")

    # 既存の.envファイルをチェック
    if env_file.exists():
        print("既存の.envファイルが見つかりました。")
        response = input("上書きしますか？ (y/n): ")
        if response.lower() != 'y':
            print("設定をキャンセルしました。")
            return

    # APIキーの入力（セキュリティのため表示されない）
    import getpass
    api_key = getpass.getpass("Gemini APIキーを入力してください: ")

    if not api_key:
        print("APIキーが入力されませんでした。")
        return

    # モデル選択
    print("\n使用するモデルを選択してください:")
    print("1. gemini-1.5-flash (高速・推奨)")
    print("2. gemini-1.5-pro (高品質)")
    print("3. gemini-pro (標準)")

    choice = input("選択 (1-3) [デフォルト: 1]: ").strip() or "1"

    models = {
        "1": "gemini-1.5-flash",
        "2": "gemini-1.5-pro",
        "3": "gemini-pro"
    }

    model = models.get(choice, "gemini-1.5-flash")

    # .envファイルの内容
    env_content = f"""# Gemini API Configuration
GEMINI_API_KEY={api_key}
GEMINI_MODEL={model}
GEMINI_TEMPERATURE=0.3
"""

    # .envファイルに書き込み
    with open(env_file, 'w') as f:
        f.write(env_content)

    print(f"\n✓ .envファイルを作成しました: {env_file.absolute()}")
    print(f"✓ 設定されたモデル: {model}")

    # .gitignoreに.envを追加
    gitignore = Path(".gitignore")
    if gitignore.exists():
        with open(gitignore, 'r') as f:
            content = f.read()

        if '.env' not in content:
            with open(gitignore, 'a') as f:
                f.write("\n# Environment variables\n.env\n")
            print("✓ .gitignoreに.envを追加しました")
    else:
        with open(gitignore, 'w') as f:
            f.write("# Environment variables\n.env\n")
        print("✓ .gitignoreファイルを作成しました")

    print("\n設定完了！")
    print("Gemini APIを使用する準備ができました。")

    # 警告
    print("\n" + "⚠️ "*10)
    print("重要：.envファイルは絶対にGitにコミットしないでください！")
    print("⚠️ "*10)

if __name__ == "__main__":
    setup_gemini_env()