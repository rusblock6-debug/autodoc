/**
 * AutoDoc AI - Editor Script
 * Visual Editor with Drag-and-Drop Markers
 * Notion-style adapted version
 */

document.addEventListener('DOMContentLoaded', () => {
    // API Configuration
    const API_BASE_URL = 'http://localhost:8000/api/v1';
    
    // DOM Elements
    const marker = document.getElementById('marker');
    const screenshotContainer = document.getElementById('screenshotContainer');
    const screenshotImg = document.getElementById('screenshotImg');
    const instructionText = document.getElementById('instructionText');
    const addStepBtn = document.getElementById('addStepBtn');
    const stepsList = document.getElementById('stepsList');
    const previewBtn = document.getElementById('previewBtn');
    const exportBtn = document.getElementById('exportBtn');
    const exportDropdown = document.getElementById('exportDropdown');
    const saveDraftBtn = document.getElementById('saveDraftBtn');
    const ttsBtn = document.getElementById('ttsBtn');
    const createShortsBtn = document.getElementById('createShortsBtn');
    const previewModal = document.getElementById('previewModal');
    const shortsModal = document.getElementById('shortsModal');
    const guideTitle = document.getElementById('guideTitle');

    // State
    let currentStep = 1;
    let totalSteps = 5;
    let isDragging = false;
    let hasChanges = false;

    // Initialize
    init();

    function init() {
        setupMarkerDrag();
        setupEventListeners();
        updateStepDisplay();
        setupStepClickHandlers();
    }

    // Marker Drag and Drop Functionality
    function setupMarkerDrag() {
        if (!marker || !screenshotContainer) return;

        marker.addEventListener('mousedown', startDrag);
        marker.addEventListener('touchstart', startDrag, { passive: false });

        document.addEventListener('mousemove', drag);
        document.addEventListener('touchmove', drag, { passive: false });
        document.addEventListener('mouseup', stopDrag);
        document.addEventListener('touchend', stopDrag);

        function startDrag(e) {
            if (e.type === 'touchstart') {
                e.preventDefault();
            }

            isDragging = true;
            marker.classList.add('dragging');

            // Bring marker to front
            marker.style.zIndex = '100';
        }

        function drag(e) {
            if (!isDragging) return;

            e.preventDefault();

            let clientX, clientY;

            if (e.type === 'touchmove') {
                clientX = e.touches[0].clientX;
                clientY = e.touches[0].clientY;
            } else {
                clientX = e.clientX;
                clientY = e.clientY;
            }

            const rect = screenshotContainer.getBoundingClientRect();

            // Calculate position relative to container
            let x = clientX - rect.left;
            let y = clientY - rect.top;

            // Constrain to container bounds
            const markerSize = 40;
            x = Math.max(markerSize / 2, Math.min(x, rect.width - markerSize / 2));
            y = Math.max(markerSize / 2, Math.min(y, rect.height - markerSize / 2));

            // Convert to percentage for responsive positioning
            const percentX = (x / rect.width) * 100;
            const percentY = (y / rect.height) * 100;

            marker.style.left = percentX + '%';
            marker.style.top = percentY + '%';

            // Mark as changed
            if (!hasChanges) {
                hasChanges = true;
                saveDraftBtn.classList.add('changed');
            }
        }

        function stopDrag() {
            if (isDragging) {
                isDragging = false;
                marker.classList.remove('dragging');
                marker.style.zIndex = '10';
            }
        }
    }

    // Setup event listeners
    function setupEventListeners() {
        // Instruction text changes
        if (instructionText) {
            instructionText.addEventListener('input', () => {
                hasChanges = true;
                saveDraftBtn.classList.add('changed');
            });
        }

        // Title changes
        if (guideTitle) {
            guideTitle.addEventListener('input', () => {
                hasChanges = true;
                saveDraftBtn.classList.add('changed');
            });
        }

        // Add step button
        if (addStepBtn) {
            addStepBtn.addEventListener('click', addNewStep);
        }

        // Preview button
        if (previewBtn) {
            previewBtn.addEventListener('click', openPreview);
        }

        // Export button
        if (exportBtn) {
            exportBtn.addEventListener('click', toggleExportDropdown);
        }

        // Save draft button
        if (saveDraftBtn) {
            saveDraftBtn.addEventListener('click', saveDraft);
        }

        // TTS button
        if (ttsBtn) {
            ttsBtn.addEventListener('click', runTTS);
        }

        // Create shorts button
        if (createShortsBtn) {
            createShortsBtn.addEventListener('click', openShortsModal);
        }

        // Close dropdowns when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.notion-dropdown')) {
                if (exportDropdown) exportDropdown.style.display = 'none';
            }
        });

        // Close modals when clicking outside
        document.addEventListener('click', (e) => {
            if (e.target === previewModal) closePreviewModal();
            if (e.target === shortsModal) closeShortsModal();
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                closePreviewModal();
                closeShortsModal();
                closeExportDropdown();
            }

            // Ctrl+S to save
            if (e.ctrlKey && e.key === 's') {
                e.preventDefault();
                saveDraft();
            }
        });

        // Tool buttons
        setupToolButtons();
    }

    // Setup tool buttons
    function setupToolButtons() {
        const zoomInBtn = document.getElementById('zoomInBtn');
        const zoomOutBtn = document.getElementById('zoomOutBtn');
        const blurBtn = document.getElementById('blurBtn');
        const arrowBtn = document.getElementById('arrowBtn');

        if (zoomInBtn) {
            zoomInBtn.addEventListener('click', () => {
                zoomScreenshot(1.1);
            });
        }

        if (zoomOutBtn) {
            zoomOutBtn.addEventListener('click', () => {
                zoomScreenshot(0.9);
            });
        }

        if (blurBtn) {
            blurBtn.addEventListener('click', () => {
                toggleTool('blur');
            });
        }

        if (arrowBtn) {
            arrowBtn.addEventListener('click', () => {
                toggleTool('arrow');
            });
        }
    }

    // Zoom screenshot
    let currentZoom = 1;

    function zoomScreenshot(factor) {
        currentZoom *= factor;
        currentZoom = Math.max(0.5, Math.min(currentZoom, 2));

        if (screenshotImg) {
            screenshotImg.style.transform = `scale(${currentZoom})`;
        }
    }

    // Toggle tool
    function toggleTool(tool) {
        const tools = ['blur', 'arrow'];
        tools.forEach(t => {
            const btn = document.getElementById(t + 'Btn');
            if (btn) {
                if (t === tool) {
                    btn.classList.toggle('active');
                } else {
                    btn.classList.remove('active');
                }
            }
        });

        // Show notification
        showNotification(`Инструмент "${tool}" выбран`);
    }

    // Add new step
    function addNewStep() {
        totalSteps++;
        const newStepNum = totalSteps;

        const stepHTML = `
            <div class="notion-step-item" data-step="${newStepNum}">
                <div class="notion-step-thumb">
                    <img src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 120 80'%3E%3Crect fill='%23FAFAF9' width='120' height='80'/%3E%3Crect x='8' y='8' width='104' height='12' rx='2' fill='%23E7E5E4'/%3E%3Crect x='8' y='28' width='80' height='50' rx='2' fill='%23F5F5F4'/%3E%3C/svg%3E" alt="Шаг ${newStepNum}">
                    <span class="step-num">${newStepNum}</span>
                </div>
                <div class="notion-step-content">
                    <p>Новый шаг ${newStepNum}</p>
                    <div class="notion-step-actions">
                        <button class="notion-btn-icon-sm" title="Редактировать">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="notion-btn-icon-sm" title="Дублировать">
                            <i class="fas fa-copy"></i>
                        </button>
                    </div>
                </div>
                <button class="notion-btn-icon-sm step-menu-toggle" onclick="toggleStepMenu(this)">
                    <i class="fas fa-ellipsis-h"></i>
                </button>
                <div class="notion-step-menu" style="display: none;">
                    <a href="#"><i class="fas fa-link"></i> Связать со следующим</a>
                    <a href="#" class="danger"><i class="fas fa-trash"></i> Удалить</a>
                </div>
            </div>
        `;

        if (stepsList) {
            stepsList.insertAdjacentHTML('beforeend', stepHTML);
        }

        // Update total steps display
        document.getElementById('totalSteps').textContent = totalSteps;

        // Switch to new step
        switchToStep(newStepNum);

        // Mark as changed
        hasChanges = true;
        saveDraftBtn.classList.add('changed');

        showNotification('Шаг добавлен');
    }

    // Switch to step
    function switchToStep(stepNum) {
        // Update active step
        document.querySelectorAll('.notion-step-item').forEach(item => {
            item.classList.remove('active');
        });

        const stepItem = document.querySelector(`.notion-step-item[data-step="${stepNum}"]`);
        if (stepItem) {
            stepItem.classList.add('active');
        }

        // Update marker number
        const markerNumber = marker.querySelector('.marker-number');
        if (markerNumber) {
            markerNumber.textContent = stepNum;
        }

        // Update step display
        currentStep = stepNum;
        updateStepDisplay();

        // Update instruction text (in real app, this would load from state)
        const instructions = {
            1: 'Нажмите на поле "Email" и введите ваш адрес электронной почты. Убедитесь, что формат email корректный.',
            2: 'Введите пароль от вашего аккаунта в соответствующее поле. Используйте надежный пароль.',
            3: 'Нажмите кнопку "Войти" для авторизации в системе. Вы будете перенаправлены на главную страницу.',
            4: 'Выберите способ оплаты и подтвердите заказ. Проверьте все данные перед оплатой.',
            5: 'Заказ успешно оформлен! Проверьте почту для подтверждения заказа.'
        };

        if (instructionText) {
            instructionText.value = instructions[stepNum] || `Инструкция для шага ${stepNum}`;
        }
    }

    // Update step display
    function updateStepDisplay() {
        const currentStepEl = document.getElementById('currentStepNum');
        const totalStepsEl = document.getElementById('totalSteps');

        if (currentStepEl) currentStepEl.textContent = currentStep;
        if (totalStepsEl) totalStepsEl.textContent = totalSteps;
    }

    // Toggle export dropdown
    function toggleExportDropdown() {
        if (exportDropdown) {
            const isHidden = exportDropdown.style.display === 'none' || exportDropdown.style.display === '';
            exportDropdown.style.display = isHidden ? 'block' : 'none';
        }
    }

    function closeExportDropdown() {
        if (exportDropdown) {
            exportDropdown.style.display = 'none';
        }
    }

    // Save draft
    function saveDraft() {
        // Simulate save
        saveDraftBtn.classList.add('saving');
        saveDraftBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>Сохранение...</span>';

        setTimeout(() => {
            saveDraftBtn.classList.remove('saving', 'changed');
            saveDraftBtn.innerHTML = '<i class="fas fa-save"></i><span>Сохранено</span>';
            hasChanges = false;
            showNotification('Черновик сохранен');
        }, 1000);
    }

    // Run TTS
    function runTTS() {
        const instruction = instructionText ? instructionText.value : '';
        if (!instruction) {
            showNotification('Нет текста для озвучивания');
            return;
        }

        // Show progress
        ttsBtn.classList.add('processing');
        const originalContent = ttsBtn.innerHTML;
        ttsBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>Озвучивание...</span>';

        // Simulate TTS generation
        setTimeout(() => {
            ttsBtn.classList.remove('processing');
            ttsBtn.innerHTML = originalContent;
            showNotification('Озвучивание завершено');
        }, 2000);
    }

    // Open preview modal
    function openPreview() {
        if (previewModal) {
            previewModal.style.display = 'flex';
        }
    }

    // Close preview modal
    function closePreviewModal() {
        if (previewModal) {
            previewModal.style.display = 'none';
        }
    }

    // Open shorts modal
    function openShortsModal() {
        if (shortsModal) {
            shortsModal.style.display = 'flex';
            startShortsProgress();
        }
    }

    // Close shorts modal
    function closeShortsModal() {
        if (shortsModal) {
            shortsModal.style.display = 'none';
        }
    }

    // Start shorts progress animation
    function startShortsProgress() {
        const progressFill = shortsModal.querySelector('.progress-fill');
        const progressText = shortsModal.querySelector('.notion-progress p');

        if (progressFill && progressText) {
            let progress = 0;
            const interval = setInterval(() => {
                progress += 5;
                if (progress > 100) {
                    progress = 100;
                    clearInterval(interval);
                }
                progressFill.style.width = progress + '%';
                progressText.textContent = `Генерация видео: ${progress}%`;
            }, 200);
        }
    }

    // Export guide
    window.exportGuide = function(format) {
        closeExportDropdown();

        showNotification(`Экспорт в формат ${format.toUpperCase()}`);

        // In real app, this would generate and download the file
        setTimeout(() => {
            openExportModal(1);
        }, 500);
    };

    // Open export modal (for dashboard compatibility)
    function openExportModal(guideId) {
        // This could be implemented to open a modal in the editor
        console.log('Export guide:', guideId);
    }

    // Show notification
    function showNotification(message) {
        const notification = document.createElement('div');
        notification.className = 'editor-notification';
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            bottom: 24px;
            left: 50%;
            transform: translateX(-50%);
            padding: 12px 24px;
            background: #37352F;
            color: white;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 500;
            z-index: 1001;
            animation: slideUp 0.3s ease;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        `;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.animation = 'fadeOut 0.3s ease forwards';
            setTimeout(() => notification.remove(), 300);
        }, 2000);
    }

    // Setup step click handlers
    function setupStepClickHandlers() {
        const stepItems = document.querySelectorAll('.notion-step-item');

        stepItems.forEach(item => {
            item.addEventListener('click', (e) => {
                // Don't switch if clicking on menu or action buttons
                if (e.target.closest('.notion-step-menu') || 
                    e.target.closest('.notion-step-actions') || 
                    e.target.closest('.step-menu-toggle')) {
                    return;
                }

                const stepNum = parseInt(item.dataset.step);
                if (item.classList.contains('active')) return;

                // Update active state
                stepItems.forEach(i => i.classList.remove('active'));
                item.classList.add('active');

                // Update marker
                const markerNumber = marker ? marker.querySelector('.marker-number') : null;

                if (markerNumber) {
                    markerNumber.textContent = stepNum;
                }

                // Update current step display
                const currentStepEl = document.getElementById('currentStepNum');
                if (currentStepEl) currentStepEl.textContent = stepNum;

                // Update instruction text
                const instructions = {
                    1: 'Нажмите на поле "Email" и введите ваш адрес электронной почты. Убедитесь, что формат email корректный.',
                    2: 'Введите пароль от вашего аккаунта в соответствующее поле. Используйте надежный пароль.',
                    3: 'Нажмите кнопку "Войти" для авторизации в системе. Вы будете перенаправлены на главную страницу.',
                    4: 'Выберите способ оплаты и подтвердите заказ. Проверьте все данные перед оплатой.',
                    5: 'Заказ успешно оформлен! Проверьте почту для подтверждения заказа.'
                };

                if (instructionText) {
                    instructionText.value = instructions[stepNum] || `Инструкция для шага ${stepNum}`;
                }
            });
        });
    }

    // Add animation styles
    const style = document.createElement('style');
    style.textContent = `
        @keyframes fadeOut {
            to { opacity: 0; transform: translateX(-50%) translateY(10px); }
        }
        @keyframes slideUp {
            from { opacity: 0; transform: translateX(-50%) translateY(10px); }
            to { opacity: 1; transform: translateX(-50%) translateY(0); }
        }
        .notion-btn.changed::after {
            content: '';
            position: absolute;
            top: 6px;
            right: 6px;
            width: 8px;
            height: 8px;
            background: #2383E2;
            border-radius: 50%;
        }
        .notion-btn.saving {
            opacity: 0.7;
        }
        .notion-btn {
            position: relative;
        }
        .notion-btn.processing {
            opacity: 0.7;
            cursor: wait;
        }
    `;
    document.head.appendChild(style);
});

// Global functions
window.toggleStepMenu = function(btn) {
    // Close all other menus
    document.querySelectorAll('.notion-step-menu').forEach(menu => {
        if (menu !== btn.nextElementSibling) {
            menu.style.display = 'none';
        }
    });

    const menu = btn.nextElementSibling;
    if (menu && menu.classList.contains('notion-step-menu')) {
        menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
    }
};

window.deleteStep = function(stepNum) {
    if (confirm(`Удалить шаг ${stepNum}?`)) {
        const stepItem = document.querySelector(`.notion-step-item[data-step="${stepNum}"]`);
        if (stepItem) {
            stepItem.remove();
            // Update total steps count
            const totalStepsEl = document.getElementById('totalSteps');
            if (totalStepsEl) {
                const currentTotal = parseInt(totalStepsEl.textContent);
                totalStepsEl.textContent = currentTotal - 1;
            }
        }
    }
};

window.closePreviewModal = function() {
    const modal = document.getElementById('previewModal');
    if (modal) modal.style.display = 'none';
};

window.closeShortsModal = function() {
    const modal = document.getElementById('shortsModal');
    if (modal) modal.style.display = 'none';
};

// Add click handler to close menus when clicking outside
document.addEventListener('click', (e) => {
    if (!e.target.closest('.notion-step-item') && !e.target.closest('.notion-step-menu')) {
        document.querySelectorAll('.notion-step-menu').forEach(menu => {
            menu.style.display = 'none';
        });
    }
});
