/**
 * Whisper Transcription Service - Frontend JavaScript
 */

// API Base URL
const API_BASE = '/api';

// Status polling interval (ms)
const POLL_INTERVAL = 2000;

// Current polling timer
let pollTimer = null;

/**
 * Show toast notification
 */
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 3000);
}

/**
 * Format file size
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Get status display info
 */
function getStatusInfo(status) {
    const statusMap = {
        'queued': { icon: '⏳', text: '待機中', message: 'ジョブはキューに追加されました' },
        'downloading': { icon: '📥', text: 'ダウンロード中', message: '動画をダウンロードしています...' },
        'extracting': { icon: '🎵', text: '音声抽出中', message: '音声を抽出しています...' },
        'transcribing': { icon: '🎤', text: '文字起こし中', message: 'Whisperで文字起こし中...' },
        'formatting': { icon: '📝', text: 'フォーマット中', message: '出力ファイルを生成中...' },
        'completed': { icon: '✅', text: '完了', message: '文字起こしが完了しました！' },
        'failed': { icon: '❌', text: 'エラー', message: 'エラーが発生しました' }
    };
    return statusMap[status] || { icon: '❓', text: status, message: '' };
}

/**
 * File upload handling
 */
function initFileUpload() {
    const fileUpload = document.getElementById('file-upload');
    const fileInput = document.getElementById('file-input');
    const fileName = document.getElementById('file-name');

    if (!fileUpload || !fileInput) return;

    // Click to select
    fileUpload.addEventListener('click', () => {
        fileInput.click();
    });

    // File selected
    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            fileName.textContent = `${file.name} (${formatFileSize(file.size)})`;
            fileName.style.display = 'block';
        }
    });

    // Drag and drop
    fileUpload.addEventListener('dragover', (e) => {
        e.preventDefault();
        fileUpload.classList.add('dragover');
    });

    fileUpload.addEventListener('dragleave', () => {
        fileUpload.classList.remove('dragover');
    });

    fileUpload.addEventListener('drop', (e) => {
        e.preventDefault();
        fileUpload.classList.remove('dragover');

        const file = e.dataTransfer.files[0];
        if (file) {
            fileInput.files = e.dataTransfer.files;
            fileName.textContent = `${file.name} (${formatFileSize(file.size)})`;
            fileName.style.display = 'block';
        }
    });
}

/**
 * Submit job form
 */
async function submitJob(e) {
    e.preventDefault();

    const form = e.target;
    const submitBtn = form.querySelector('button[type="submit"]');
    const urlInput = document.getElementById('url-input');
    const fileInput = document.getElementById('file-input');
    const webhookInput = document.getElementById('webhook-input');

    // Validate
    const url = urlInput?.value?.trim();
    const file = fileInput?.files?.[0];

    if (!url && !file) {
        showToast('URLまたはファイルを指定してください', 'error');
        return;
    }

    // Disable submit
    submitBtn.disabled = true;
    submitBtn.textContent = '送信中...';

    try {
        const formData = new FormData();

        if (url) {
            formData.append('url', url);
        }
        if (file) {
            formData.append('file', file);
        }
        if (webhookInput?.value) {
            formData.append('webhook_url', webhookInput.value);
        }

        const response = await fetch(`${API_BASE}/jobs`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'ジョブの作成に失敗しました');
        }

        // Redirect to status page
        window.location.href = `/job/${data.job_id}`;

    } catch (error) {
        showToast(error.message, 'error');
        submitBtn.disabled = false;
        submitBtn.textContent = '文字起こしを開始';
    }
}

/**
 * Poll job status
 */
async function pollJobStatus(jobId) {
    try {
        const response = await fetch(`${API_BASE}/jobs/${jobId}`);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'ジョブの取得に失敗しました');
        }

        updateJobDisplay(data);

        // Continue polling if not finished
        if (data.status !== 'completed' && data.status !== 'failed') {
            pollTimer = setTimeout(() => pollJobStatus(jobId), POLL_INTERVAL);
        }

    } catch (error) {
        console.error('Poll error:', error);
        // Retry on error
        pollTimer = setTimeout(() => pollJobStatus(jobId), POLL_INTERVAL * 2);
    }
}

/**
 * Update job display
 */
function updateJobDisplay(job) {
    const statusInfo = getStatusInfo(job.status);

    // Update status icon and text
    const statusIcon = document.getElementById('status-icon');
    const statusText = document.getElementById('status-text');
    const statusMessage = document.getElementById('status-message');

    if (statusIcon) statusIcon.textContent = statusInfo.icon;
    if (statusText) {
        statusText.textContent = statusInfo.text;
        statusText.className = `status-text status-${job.status}`;
    }
    if (statusMessage) statusMessage.textContent = statusInfo.message;

    // Update progress bar
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');

    if (progressFill) {
        progressFill.style.width = `${job.progress || 0}%`;
    }
    if (progressText) {
        progressText.textContent = `${job.progress || 0}%`;
    }

    // Show/hide download links
    const downloadSection = document.getElementById('download-section');
    if (downloadSection) {
        if (job.status === 'completed') {
            downloadSection.style.display = 'block';
            updateDownloadLinks(job);
        } else {
            downloadSection.style.display = 'none';
        }
    }

    // Show error if failed
    const errorSection = document.getElementById('error-section');
    if (errorSection) {
        if (job.status === 'failed' && job.error) {
            errorSection.style.display = 'block';
            const errorMessage = document.getElementById('error-message');
            if (errorMessage) {
                errorMessage.textContent = job.error.message || 'Unknown error';
            }
        } else {
            errorSection.style.display = 'none';
        }
    }

    // Update job info
    updateJobInfo(job);
}

/**
 * Update download links
 */
function updateDownloadLinks(job) {
    const links = document.querySelectorAll('.download-link');
    links.forEach(link => {
        const format = link.dataset.format;
        if (job.download_urls && job.download_urls[format]) {
            link.href = job.download_urls[format];
        }
    });
}

/**
 * Update job info display
 */
function updateJobInfo(job) {
    const jobId = document.getElementById('info-job-id');
    const createdAt = document.getElementById('info-created-at');
    const stage = document.getElementById('info-stage');

    if (jobId) jobId.textContent = job.job_id;
    if (createdAt && job.created_at) {
        const date = new Date(job.created_at);
        createdAt.textContent = date.toLocaleString('ja-JP');
    }
    if (stage) stage.textContent = job.stage || job.status;
}

/**
 * Delete job
 */
async function deleteJob(jobId) {
    if (!confirm('このジョブを削除しますか？')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/jobs/${jobId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail || 'ジョブの削除に失敗しました');
        }

        showToast('ジョブを削除しました', 'success');
        window.location.href = '/';

    } catch (error) {
        showToast(error.message, 'error');
    }
}

/**
 * Copy job ID to clipboard
 */
function copyJobId(jobId) {
    navigator.clipboard.writeText(jobId).then(() => {
        showToast('ジョブIDをコピーしました', 'success');
    }).catch(() => {
        showToast('コピーに失敗しました', 'error');
    });
}

/**
 * Initialize page
 */
document.addEventListener('DOMContentLoaded', () => {
    // Initialize file upload
    initFileUpload();

    // Form submission
    const jobForm = document.getElementById('job-form');
    if (jobForm) {
        jobForm.addEventListener('submit', submitJob);
    }

    // Start polling if on job page
    const jobIdElement = document.getElementById('current-job-id');
    if (jobIdElement) {
        const jobId = jobIdElement.value;
        if (jobId) {
            pollJobStatus(jobId);
        }
    }
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (pollTimer) {
        clearTimeout(pollTimer);
    }
});
