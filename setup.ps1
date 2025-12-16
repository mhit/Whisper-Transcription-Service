# VideoTranscriptAnalyzer Setup Script
# Simple and reliable installation for Windows

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  VideoTranscriptAnalyzer Setup v2.1" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Phase 1: Check Python
Write-Host "[Phase 1] Checking Python..." -ForegroundColor Yellow

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "ERROR: Python not found." -ForegroundColor Red
    Write-Host "Please install Python 3.10+ from https://www.python.org/downloads/" -ForegroundColor Yellow
    pause
    exit 1
}

$pythonVersion = python --version 2>&1
Write-Host "OK: $pythonVersion" -ForegroundColor Green

# Phase 2: Check GPU
Write-Host ""
Write-Host "[Phase 2] Detecting GPU..." -ForegroundColor Yellow

$gpuInfo = ""
$isRTX5070Ti = $false
$hasCUDA = $false

# Detect NVIDIA GPU
$nvidiaGPU = Get-WmiObject Win32_VideoController | Where-Object {$_.Name -like "*NVIDIA*"}
if ($nvidiaGPU) {
    $gpuInfo = $nvidiaGPU.Name
    Write-Host "GPU Found: $gpuInfo" -ForegroundColor Green

    # Check for RTX 50 series
    if ($gpuInfo -match "RTX 50") {
        $isRTX5070Ti = $true
        Write-Host "INFO: RTX 50 series detected - Will install special version" -ForegroundColor Yellow
    }

    # Check CUDA
    $nvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
    if ($nvidiaSmi) {
        $hasCUDA = $true
        Write-Host "CUDA: Available" -ForegroundColor Green
    }
} else {
    Write-Host "No GPU detected - Will install CPU version" -ForegroundColor Cyan
}

# Phase 3: Setup virtual environment
Write-Host ""
Write-Host "[Phase 3] Setting up virtual environment..." -ForegroundColor Yellow

if (Test-Path "venv") {
    Write-Host "Using existing venv" -ForegroundColor Cyan
} else {
    Write-Host "Creating venv..." -ForegroundColor White
    python -m venv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to create venv" -ForegroundColor Red
        pause
        exit 1
    }
    Write-Host "OK: venv created" -ForegroundColor Green
}

# Activate venv
Write-Host "Activating venv..." -ForegroundColor White
& ".\venv\Scripts\Activate.ps1"
Write-Host "OK: venv activated" -ForegroundColor Green

# Upgrade pip
Write-Host "Upgrading pip..." -ForegroundColor White
python -m pip install --upgrade pip --quiet
Write-Host "OK: pip upgraded" -ForegroundColor Green

# Phase 4: Install PyTorch
Write-Host ""
Write-Host "[Phase 4] Installing PyTorch..." -ForegroundColor Yellow

if ($isRTX5070Ti) {
    Write-Host "Installing PyTorch Nightly for RTX 50 series..." -ForegroundColor Yellow
    # First uninstall existing PyTorch
    pip uninstall torch torchvision torchaudio -y 2>$null
    # Install PyTorch Nightly with CUDA 12.4 support
    # Note: torchaudio may not be available for Python 3.13 yet
    pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128

    # Try torchaudio separately (optional for Whisper)
    Write-Host "Attempting torchaudio installation (optional)..." -ForegroundColor White
    pip install --pre torchaudio --index-url https://download.pytorch.org/whl/nightly/cu124 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "NOTE: torchaudio not available for Python 3.13 (not required for Whisper)" -ForegroundColor Yellow
        $LASTEXITCODE = 0  # Reset error code since this is optional
    }
} elseif ($hasCUDA) {
    Write-Host "Installing PyTorch with CUDA support..." -ForegroundColor White
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
} else {
    Write-Host "Installing PyTorch CPU version..." -ForegroundColor White
    pip install torch torchvision torchaudio
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to install PyTorch" -ForegroundColor Red
    pause
    exit 1
}
Write-Host "OK: PyTorch installed" -ForegroundColor Green

# Phase 5: Install requirements
Write-Host ""
Write-Host "[Phase 5] Installing dependencies..." -ForegroundColor Yellow

pip install -r requirements.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to install dependencies" -ForegroundColor Red
    pause
    exit 1
}
Write-Host "OK: Dependencies installed" -ForegroundColor Green

# Phase 5.1: Install Hierarchical Summarization (LangChain + LlamaIndex)
Write-Host ""
Write-Host "[Phase 5.1] Installing Hierarchical Summarization..." -ForegroundColor Yellow
Write-Host "This enables advanced multi-level summarization for long videos" -ForegroundColor Cyan

# LangChain
Write-Host "Installing LangChain..." -ForegroundColor White
pip install langchain langchain-community langchain-core --quiet

# LlamaIndex
Write-Host "Installing LlamaIndex..." -ForegroundColor White
pip install llama-index llama-index-core llama-index-llms-ollama llama-index-embeddings-ollama --quiet

# Vector stores
Write-Host "Installing vector stores..." -ForegroundColor White
pip install faiss-cpu chromadb --quiet

# Additional utilities
Write-Host "Installing utilities..." -ForegroundColor White
pip install tiktoken nest-asyncio --quiet

Write-Host "OK: Hierarchical Summarization installed" -ForegroundColor Green

# Phase 6: Verify installation
Write-Host ""
Write-Host "[Phase 6] Verifying installation..." -ForegroundColor Yellow

# Create verification script
$verifyScript = @"
import sys
try:
    import torch
    print(f'PyTorch: {torch.__version__}')

    if torch.cuda.is_available():
        print(f'GPU: {torch.cuda.get_device_name(0)}')
        print(f'CUDA: {torch.version.cuda}')
    else:
        print('Device: CPU mode')

    import whisper
    print('Whisper: OK')

    import langchain
    print('LangChain: OK')

    import llama_index
    print('LlamaIndex: OK')

    print('SUCCESS')
except Exception as e:
    print(f'ERROR: {e}')
    sys.exit(1)
"@

# Save and run verification
$verifyScript | Out-File -FilePath "temp_verify.py" -Encoding UTF8
python temp_verify.py
$verifyResult = $LASTEXITCODE
Remove-Item "temp_verify.py" -Force -ErrorAction SilentlyContinue

if ($verifyResult -eq 0) {
    Write-Host "OK: All components verified" -ForegroundColor Green
} else {
    Write-Host "WARNING: Some components may not be installed correctly" -ForegroundColor Yellow
}

# Phase 7: Check Ollama
Write-Host ""
Write-Host "[Phase 7] Checking Ollama..." -ForegroundColor Yellow

$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if ($ollama) {
    $ollamaVersion = ollama --version 2>&1
    Write-Host "Ollama: $ollamaVersion" -ForegroundColor Green

    # Check if Ollama server is running
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:11434/api/version" -Method Get -TimeoutSec 2 2>$null
        Write-Host "Ollama server: Running" -ForegroundColor Green
    } catch {
        Write-Host "Ollama server: Not running" -ForegroundColor Yellow
        Write-Host "Starting Ollama server..." -ForegroundColor White
        Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 3
    }

    # Check for models
    $models = ollama list 2>$null
    if ($models -match "gpt-oss:20b") {
        Write-Host "Model gpt-oss:20b: Available" -ForegroundColor Green
    } else {
        Write-Host "Model gpt-oss:20b: Not found" -ForegroundColor Yellow
        Write-Host "To install: ollama pull gpt-oss:20b" -ForegroundColor Cyan
    }
} else {
    Write-Host "Ollama: Not installed (optional)" -ForegroundColor Yellow
    Write-Host "Download from: https://ollama.ai/download/windows" -ForegroundColor Cyan
}

# Completion message
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "         Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

Write-Host "Installed Features:" -ForegroundColor Cyan
Write-Host "- Video download & extraction" -ForegroundColor White
Write-Host "- Whisper transcription (large-v3)" -ForegroundColor White
Write-Host "- Hierarchical summarization (LangChain + LlamaIndex)" -ForegroundColor White
Write-Host "- Ollama local LLM support" -ForegroundColor White
if ($isRTX5070Ti) {
    Write-Host "- RTX 50 series optimization" -ForegroundColor White
}
Write-Host ""

if ($isRTX5070Ti) {
    Write-Host "RTX 50 Series Information:" -ForegroundColor Yellow
    Write-Host "- PyTorch Nightly installed" -ForegroundColor White
    Write-Host "- GPU detection enabled with CPU fallback" -ForegroundColor White
    Write-Host ""
}

Write-Host "Usage Examples:" -ForegroundColor Cyan
Write-Host '1. Basic transcription:' -ForegroundColor Yellow
Write-Host '   python video_transcript_analyzer.py --input "video.mp4"' -ForegroundColor White
Write-Host ""
Write-Host '2. Test hierarchical summarization:' -ForegroundColor Yellow
Write-Host '   python test_hierarchical.py' -ForegroundColor White
Write-Host ""
Write-Host '3. With Ollama (local LLM):' -ForegroundColor Yellow
Write-Host '   python video_transcript_analyzer.py --input "video.mp4"' -ForegroundColor White
Write-Host '   (Ollama will be used automatically if configured)' -ForegroundColor Gray
Write-Host ""

# Check ffmpeg
$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
if (-not $ffmpeg) {
    Write-Host "WARNING: ffmpeg not installed" -ForegroundColor Yellow
    Write-Host "Download from: https://ffmpeg.org/download.html" -ForegroundColor Cyan
    Write-Host ""
}

Write-Host "Press Enter to exit..." -ForegroundColor Gray
Read-Host