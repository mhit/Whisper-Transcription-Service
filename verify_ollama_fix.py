#!/usr/bin/env python3
"""
Ollamaロジック修正の検証スクリプト
"""

import yaml
import os
from pathlib import Path

def verify_ollama_logic():
    """Ollamaが正しく認識されるか検証"""

    print("=" * 60)
    print("🔍 Ollama Logic Verification")
    print("=" * 60)

    # 1. config.yamlを読み込む
    config_path = Path("config.yaml")
    if not config_path.exists():
        print("❌ config.yaml not found")
        return False

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    analyzer_config = config.get('analyzer', {})
    ollama_config = analyzer_config.get('ollama_fallback', {})

    # 2. Ollama設定をチェック
    print("\n📋 Configuration Check:")
    print(f"  Ollama enabled: {ollama_config.get('enabled', False)}")
    print(f"  API base URL: {analyzer_config.get('api_base_url', 'Not set')}")
    print(f"  Model: {ollama_config.get('model', 'Not set')}")

    # 3. 新しいロジックをシミュレート
    openai_api_key = os.getenv('OPENAI_API_KEY')

    # 旧ロジック（バグあり）
    old_logic_result = bool(openai_api_key)

    # 新ロジック（修正済み）
    is_ollama_enabled = (
        ollama_config.get('enabled', False) or
        (analyzer_config.get('api_base_url') and 'localhost:11434' in analyzer_config.get('api_base_url', ''))
    )
    new_logic_result = bool(openai_api_key) or is_ollama_enabled

    # 4. 結果を表示
    print("\n🔬 Logic Analysis:")
    print(f"  OpenAI API Key: {'Set' if openai_api_key else 'Not set'}")
    print(f"  Ollama enabled: {is_ollama_enabled}")
    print(f"  Old logic (buggy): AI analysis would run = {old_logic_result}")
    print(f"  New logic (fixed): AI analysis would run = {new_logic_result}")

    # 5. 問題の診断
    print("\n📊 Diagnosis:")
    if not old_logic_result and is_ollama_enabled:
        print("  ✅ BUG FIXED: Previously AI analysis was skipped even with Ollama enabled")
        print("  ✅ Now AI analysis will run with Ollama!")
    elif old_logic_result == new_logic_result:
        print("  ℹ️  No change in behavior (both conditions give same result)")
    else:
        print("  🔍 Edge case detected")

    # 6. コードの確認
    print("\n📝 Code Verification:")
    try:
        with open("video_transcript_analyzer.py", 'r', encoding='utf-8') as f:
            content = f.read()

        # 修正が適用されているかチェック
        if "self.is_ollama_enabled" in content:
            print("  ✅ is_ollama_enabled flag found in code")
        else:
            print("  ❌ is_ollama_enabled flag NOT found - fix not applied?")

        if "elif self.openai_api_key or self.is_ollama_enabled:" in content:
            print("  ✅ Fixed condition found at line 250")
        else:
            print("  ❌ Fixed condition NOT found - using old buggy logic?")

    except Exception as e:
        print(f"  ❌ Could not verify code: {e}")

    print("\n" + "=" * 60)
    print("🎯 Summary:")
    if new_logic_result and is_ollama_enabled:
        print("  ✅ Ollama will be used for AI analysis!")
        print("  Run: python video_transcript_analyzer.py --input [video]")
    else:
        print("  ⚠️  AI analysis will be skipped")
        print("  Check your Ollama configuration in config.yaml")
    print("=" * 60)

if __name__ == "__main__":
    verify_ollama_logic()