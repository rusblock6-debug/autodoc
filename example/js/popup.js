/**
 * AutoDoc AI - Popup Script (Notion Style)
 * Chrome Extension Popup Functionality
 */

document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const startRecordBtn = document.getElementById('startRecordBtn');
    const stopRecordBtn = document.getElementById('stopRecordBtn');
    const timerDisplay = document.getElementById('timerDisplay');
    const timerText = document.getElementById('timerText');
    const settingsModal = document.getElementById('settingsModal');

    // State
    let isRecording = false;
    let recordingTimer = null;
    let seconds = 0;

    // Initialize
    init();

    function init() {
        setupEventListeners();
    }

    // Setup event listeners
    function setupEventListeners() {
        if (startRecordBtn) {
            startRecordBtn.addEventListener('click', startRecording);
        }
        if (stopRecordBtn) {
            stopRecordBtn.addEventListener('click', stopRecording);
        }
        if (settingsModal) {
            settingsModal.addEventListener('click', (e) => {
                if (e.target === settingsModal) closeSettings();
            });
        }

        // Close dropdowns when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.notion-dropdown')) {
                const dropdown = document.querySelector('.notion-dropdown-menu');
                if (dropdown) dropdown.style.display = 'none';
            }
        });
    }

    // Start recording
    function startRecording() {
        isRecording = true;
        seconds = 0;

        // Update UI
        if (startRecordBtn) startRecordBtn.style.display = 'none';
        if (stopRecordBtn) stopRecordBtn.style.display = 'flex';
        if (timerDisplay) timerDisplay.style.display = 'flex';

        // Update status indicator
        const statusIndicator = document.querySelector('.status-indicator');
        const statusText = document.querySelector('.status-text');
        if (statusIndicator) statusIndicator.classList.add('recording');
        if (statusText) statusText.textContent = 'Запись... 00:00';

        // Start timer
        recordingTimer = setInterval(updateTimer, 1000);

        // Visual feedback
        document.body.classList.add('recording');

        // Show notification
        showNotification('Запись началась');
    }

    // Stop recording
    function stopRecording() {
        isRecording = false;

        // Clear timer
        if (recordingTimer) {
            clearInterval(recordingTimer);
            recordingTimer = null;
        }

        // Update UI
        if (startRecordBtn) startRecordBtn.style.display = 'flex';
        if (stopRecordBtn) stopRecordBtn.style.display = 'none';
        if (timerDisplay) timerDisplay.style.display = 'none';

        // Update status indicator
        const statusIndicator = document.querySelector('.status-indicator');
        const statusText = document.querySelector('.status-text');
        if (statusIndicator) statusIndicator.classList.remove('recording');
        if (statusText) statusText.textContent = 'Готов к записи';

        // Visual feedback
        document.body.classList.remove('recording');

        // Show notification
        showNotification('Запись остановлена');

        // Open editor with new guide
        setTimeout(() => {
            window.open('editor.html?new=true', '_blank');
        }, 500);
    }

    // Update timer display
    function updateTimer() {
        seconds++;
        const mins = Math.floor(seconds / 60).toString().padStart(2, '0');
        const secs = (seconds % 60).toString().padStart(2, '0');
        const timeString = `${mins}:${secs}`;

        if (timerText) timerText.textContent = timeString;

        const statusText = document.querySelector('.status-text');
        if (statusText) statusText.textContent = `Запись... ${timeString}`;
    }

    // Show notification
    function showNotification(message) {
        const notification = document.createElement('div');
        notification.className = 'notion-notification';
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            padding: 12px 24px;
            background: #37352F;
            color: white;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            z-index: 1001;
            animation: slideUp 0.3s ease;
        `;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.animation = 'fadeOut 0.3s ease forwards';
            setTimeout(() => notification.remove(), 300);
        }, 2000);
    }

    // Add animation styles
    const style = document.createElement('style');
    style.textContent = `
        @keyframes fadeOut {
            to { opacity: 0; transform: translateX(-50%) translateY(10px); }
        }
    `;
    document.head.appendChild(style);
});

// Global functions
window.openSettings = function() {
    const settingsModal = document.getElementById('settingsModal');
    if (settingsModal) settingsModal.style.display = 'flex';
};

window.closeSettings = function() {
    const settingsModal = document.getElementById('settingsModal');
    if (settingsModal) settingsModal.style.display = 'none';
};

window.startRecording = function() {
    const startRecordBtn = document.getElementById('startRecordBtn');
    if (startRecordBtn) startRecordBtn.click();
};
