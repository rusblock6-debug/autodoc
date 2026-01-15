/**
 * AutoDoc AI - Popup Script
 * Chrome Extension Popup Functionality
 */

document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const startRecordBtn = document.getElementById('startRecordBtn');
    const stopRecordBtn = document.getElementById('stopRecordBtn');
    const timerDisplay = document.getElementById('timerDisplay');
    const timerText = document.getElementById('timerText');
    const statusText = document.querySelector('.status-text');
    const statusIndicator = document.querySelector('.status-indicator');
    const settingsBtn = document.getElementById('settingsBtn');
    const settingsModal = document.getElementById('settingsModal');
    const closeSettings = document.getElementById('closeSettings');
    const recentGuidesList = document.getElementById('recentGuidesList');

    // State
    let isRecording = false;
    let recordingTimer = null;
    let seconds = 0;

    // Mock recent guides data
    const recentGuides = [
        { id: 1, title: 'Как оформить заказ v1.2', date: '25.10.2023' },
        { id: 2, title: 'Обновление профиля', date: '23.10.2023' },
        { id: 3, title: 'Настройка уведомлений', date: '20.10.2023' }
    ];

    // Initialize
    init();

    function init() {
        renderRecentGuides();
        setupEventListeners();
    }

    // Render recent guides list
    function renderRecentGuides() {
        recentGuidesList.innerHTML = recentGuides.map(guide => `
            <div class="mini-guide-card" onclick="window.open('editor.html?id=${guide.id}', '_blank')">
                <div class="mini-guide-preview">
                    <img src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 40 28'%3E%3Crect fill='%23E2E8F0' width='40' height='28'/%3E%3Crect x='4' y='4' width='32' height='8' rx='2' fill='%23CBD5E1'/%3E%3Crect x='4' y='16' width='20' height='6' rx='1' fill='%23CBD5E1'/%3E%3C/svg%3E" alt="Preview">
                </div>
                <div class="mini-guide-info">
                    <div class="mini-guide-title">${guide.title}</div>
                    <div class="mini-guide-date">${guide.date}</div>
                </div>
            </div>
        `).join('');
    }

    // Setup event listeners
    function setupEventListeners() {
        startRecordBtn.addEventListener('click', startRecording);
        stopRecordBtn.addEventListener('click', stopRecording);
        settingsBtn.addEventListener('click', openSettings);
        closeSettings.addEventListener('click', closeSettingsModal);
        settingsModal.addEventListener('click', (e) => {
            if (e.target === settingsModal) closeSettingsModal();
        });

        // Close dropdowns when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.export-dropdown')) {
                const dropdown = document.getElementById('exportDropdown');
                if (dropdown) dropdown.style.display = 'none';
            }
        });
    }

    // Start recording
    function startRecording() {
        isRecording = true;
        seconds = 0;

        // Update UI
        startRecordBtn.style.display = 'none';
        stopRecordBtn.style.display = 'flex';
        timerDisplay.style.display = 'flex';
        statusIndicator.classList.add('recording');
        statusText.textContent = 'Запись... 00:00';

        // Start timer
        recordingTimer = setInterval(updateTimer, 1000);

        // Visual feedback
        document.body.classList.add('recording');

        // In a real extension, this would communicate with the background script
        console.log('Recording started');

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
        startRecordBtn.style.display = 'flex';
        stopRecordBtn.style.display = 'none';
        timerDisplay.style.display = 'none';
        statusIndicator.classList.remove('recording');
        statusText.textContent = 'Не записывается';

        // Visual feedback
        document.body.classList.remove('recording');

        // In a real extension, this would communicate with the background script
        console.log('Recording stopped');

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

        timerText.textContent = timeString;
        statusText.textContent = `Запись... ${timeString}`;
    }

    // Open settings modal
    function openSettings() {
        settingsModal.style.display = 'flex';
    }

    // Close settings modal
    function closeSettingsModal() {
        settingsModal.style.display = 'none';
    }

    // Show notification
    function showNotification(message) {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = 'notification';
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            padding: 12px 24px;
            background: #1E293B;
            color: white;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            z-index: 1001;
            animation: slideUp 0.3s ease;
        `;

        document.body.appendChild(notification);

        // Remove after delay
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

// Make functions globally accessible
window.openSettings = function() {
    const settingsModal = document.getElementById('settingsModal');
    if (settingsModal) settingsModal.style.display = 'flex';
};
