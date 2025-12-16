# Quick fix for Python 3.13 + RTX 5070 Ti
Write-Host "Installing PyTorch Nightly for RTX 5070 Ti..." -ForegroundColor Cyan

# Install torch and torchvision (without torchaudio)
pip install --pre torch torchvision --index-url https://download.pytorch.org/whl/nightly/cu124

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nSuccess! PyTorch installed." -ForegroundColor Green

    # Test GPU
    Write-Host "`nTesting GPU..." -ForegroundColor Yellow
    python -c @"
import torch
print(f'PyTorch: {torch.__version__}')
print(f'CUDA: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'GPU: {torch.cuda.get_device_name(0)}')
    print('GPU is ready!')
"@
} else {
    Write-Host "Installation failed." -ForegroundColor Red
}

Write-Host "`nNote: torchaudio is not required for Whisper." -ForegroundColor Cyan
Write-Host "Press Enter to continue..."
Read-Host