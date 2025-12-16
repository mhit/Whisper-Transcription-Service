# Ollamaモデル修正スクリプト

Write-Host "="*60 -ForegroundColor Cyan
Write-Host "🔧 Ollamaモデル設定修正" -ForegroundColor Cyan
Write-Host "="*60 -ForegroundColor Cyan

# 1. インストール済みモデルを確認
Write-Host "`n📦 インストール済みモデル確認中..." -ForegroundColor Yellow
$models = ollama list 2>$null

if ($models) {
    Write-Host "利用可能なモデル:" -ForegroundColor Green
    Write-Host $models

    # モデル名を抽出
    $modelList = $models -split "`n" | Select-Object -Skip 1 | ForEach-Object {
        if ($_ -match '^(\S+)\s+') {
            $matches[1]
        }
    }

    if ($modelList) {
        $firstModel = $modelList[0]
        Write-Host "`n✅ 利用可能なモデル: $firstModel" -ForegroundColor Green

        # config.yamlを更新する提案
        Write-Host "`n💡 推奨事項:" -ForegroundColor Yellow
        Write-Host "config.yamlのモデル設定を以下に変更してください:" -ForegroundColor White
        Write-Host "  analyzer:" -ForegroundColor Gray
        Write-Host "    ollama_fallback:" -ForegroundColor Gray
        Write-Host "      model: $firstModel" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "  hierarchical_summarization:" -ForegroundColor Gray
        Write-Host "    model: $firstModel" -ForegroundColor Cyan
    }
} else {
    Write-Host "❌ インストール済みモデルが見つかりません" -ForegroundColor Red
}

# 2. 推奨モデルのインストール
Write-Host "`n📥 推奨モデルのインストール" -ForegroundColor Yellow
Write-Host "以下から選択してください:" -ForegroundColor White
Write-Host ""
Write-Host "1. llama3.2:3b  (軽量・高速 - 2GB)" -ForegroundColor Green
Write-Host "2. llama2:7b    (バランス型 - 4GB)" -ForegroundColor Yellow
Write-Host "3. qwen2.5:14b  (高精度 - 8GB)" -ForegroundColor Cyan
Write-Host "4. gpt-oss:20b  (最高精度 - 12GB) ※要高性能GPU" -ForegroundColor Red
Write-Host ""

$choice = Read-Host "番号を選択 (1-4)"

switch ($choice) {
    "1" {
        $model = "llama3.2:3b"
        Write-Host "`n📥 $model をインストール中..." -ForegroundColor Green
        ollama pull $model
    }
    "2" {
        $model = "llama2:7b"
        Write-Host "`n📥 $model をインストール中..." -ForegroundColor Yellow
        ollama pull $model
    }
    "3" {
        $model = "qwen2.5:14b"
        Write-Host "`n📥 $model をインストール中..." -ForegroundColor Cyan
        ollama pull $model
    }
    "4" {
        $model = "gpt-oss:20b"
        Write-Host "`n📥 $model をインストール中..." -ForegroundColor Red
        Write-Host "⚠️  このモデルは12GB以上のVRAMが必要です" -ForegroundColor Yellow
        ollama pull $model
    }
    default {
        Write-Host "キャンセルされました" -ForegroundColor Gray
        exit
    }
}

Write-Host "`n✅ インストール完了！" -ForegroundColor Green

# 3. 設定ファイルの自動更新
Write-Host "`n📝 設定ファイルを更新しますか？" -ForegroundColor Yellow
$update = Read-Host "config.yamlを自動更新する？ (y/n)"

if ($update -eq "y") {
    $configPath = "config.yaml"
    if (Test-Path $configPath) {
        $config = Get-Content $configPath -Raw

        # モデル名を更新
        $config = $config -replace 'model:\s*gpt-oss:20b', "model: $model"
        $config = $config -replace 'model:\s*"[^"]*"', "model: $model"

        # バックアップを作成
        Copy-Item $configPath "$configPath.backup" -Force

        # 更新を保存
        $config | Out-File $configPath -Encoding UTF8

        Write-Host "✅ config.yaml を更新しました" -ForegroundColor Green
        Write-Host "   バックアップ: config.yaml.backup" -ForegroundColor Gray
    }
}

Write-Host "`n" + "="*60 -ForegroundColor Cyan
Write-Host "🚀 次のステップ:" -ForegroundColor Green
Write-Host "1. python simple_test_hierarchical.py  (動作確認)" -ForegroundColor White
Write-Host "2. python run_hierarchical_on_existing.py  (本番実行)" -ForegroundColor White
Write-Host "="*60 -ForegroundColor Cyan