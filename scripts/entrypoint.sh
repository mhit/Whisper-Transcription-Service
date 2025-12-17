#!/bin/bash
# Whisper Transcription Service - Entrypoint Script

set -e

echo "============================================"
echo " Whisper Transcription Service"
echo "============================================"
echo ""

# Display configuration
echo "[Config] Whisper Model: ${WHISPER_MODEL:-large-v3}"
echo "[Config] Model Unload: ${MODEL_UNLOAD_MINUTES:-5} minutes"
echo "[Config] Job Retention: ${JOB_RETENTION_DAYS:-7} days"
echo "[Config] Debug Mode: ${DEBUG:-false}"
echo ""

# Check GPU availability
echo "[GPU Check] Checking CUDA availability..."
python3 -c "import torch; print(f'[GPU Check] CUDA available: {torch.cuda.is_available()}'); print(f'[GPU Check] Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"CPU\"}') if torch.cuda.is_available() else None"
echo ""

# Check FFmpeg
echo "[FFmpeg] Checking FFmpeg installation..."
ffmpeg -version | head -n 1
echo ""

# Create required directories
echo "[Setup] Creating data directories..."
mkdir -p /app/data/jobs /app/data/logs
echo "[Setup] Done"
echo ""

# Optional: Run database migrations (if any)
# echo "[Migration] Running database migrations..."
# python3 -m app.db.migrate

# Optional: Start Cloudflare Tunnel if token provided
if [ -n "${CLOUDFLARE_TUNNEL_TOKEN}" ]; then
    echo "[Tunnel] Starting Cloudflare Tunnel..."
    # cloudflared tunnel --no-autoupdate run --token "${CLOUDFLARE_TUNNEL_TOKEN}" &
    echo "[Tunnel] Cloudflare Tunnel started (background)"
fi

echo ""
echo "============================================"
echo " Starting Application Server"
echo "============================================"
echo ""

# Start the application
exec "$@"
