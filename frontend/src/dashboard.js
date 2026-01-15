/**
 * AutoDoc AI - Dashboard Script (Notion Style)
 * Main Page Functionality
 */

document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const searchInput = document.getElementById('searchInput');
    const newGuideBtn = document.getElementById('newGuideBtn');
    const guidesGrid = document.getElementById('guidesGrid');
    const exportModal = document.getElementById('exportModal');
    const viewBtns = document.querySelectorAll('.notion-view-btn');

    // Initialize
    init();

    function init() {
        setupEventListeners();
    }

    // Setup event listeners
    function setupEventListeners() {
        // Search functionality
        if (searchInput) {
            searchInput.addEventListener('input', debounce(handleSearch, 300));
        }

        // New guide button
        if (newGuideBtn) {
            newGuideBtn.addEventListener('click', () => {
                window.location.href = 'editor.html?new=true';
            });
        }

        // View toggle
        viewBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                viewBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const view = btn.dataset.view;
                toggleView(view);
            });
        });

        // Close modal when clicking outside
        document.addEventListener('click', (e) => {
            if (e.target === exportModal) {
                closeExportModal();
            }
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                closeExportModal();
                closeAllMenus();
            }
        });
    }

    // Handle search
    function handleSearch(e) {
        const query = e.target.value.toLowerCase().trim();
        const cards = document.querySelectorAll('.notion-card:not(.notion-card-new)');

        cards.forEach(card => {
            const title = card.querySelector('.notion-card-title').textContent.toLowerCase();
            const matches = title.includes(query);

            card.style.display = matches ? '' : 'none';
        });
    }

    // Toggle view (grid/list)
    function toggleView(view) {
        if (guidesGrid) {
            if (view === 'list') {
                guidesGrid.style.gridTemplateColumns = '1fr';
            } else {
                guidesGrid.style.gridTemplateColumns = '';
            }
        }
    }

    // Close all menus
    function closeAllMenus() {
        document.querySelectorAll('.notion-dropdown').forEach(menu => {
            menu.style.display = 'none';
        });
        document.querySelectorAll('.notion-step-menu').forEach(menu => {
            menu.style.display = 'none';
        });
    }
});

// Global functions
window.toggleMenu = function(btn) {
    // Close all other menus first
    document.querySelectorAll('.notion-dropdown').forEach(menu => {
        if (menu !== btn.nextElementSibling) {
            menu.style.display = 'none';
        }
    });

    const menu = btn.nextElementSibling;
    if (menu) {
        menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
    }
};

window.closeAllMenus = function() {
    document.querySelectorAll('.notion-dropdown').forEach(menu => {
        menu.style.display = 'none';
    });
    document.querySelectorAll('.notion-step-menu').forEach(menu => {
        menu.style.display = 'none';
    });
};

window.openExportModal = function(guideId) {
    const modal = document.getElementById('exportModal');
    if (modal) {
        modal.style.display = 'flex';
    }
};

window.closeExportModal = function() {
    const modal = document.getElementById('exportModal');
    if (modal) {
        modal.style.display = 'none';
    }
};

// Utility function: debounce
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Add event listener to close menus when clicking outside
document.addEventListener('click', (e) => {
    if (!e.target.closest('.notion-card-actions') && !e.target.closest('.notion-step-item')) {
        closeAllMenus();
    }
});

// Tab switching in export modal
document.addEventListener('DOMContentLoaded', () => {
    const tabBtns = document.querySelectorAll('.notion-tab');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // Remove active class from all tabs
            tabBtns.forEach(b => b.classList.remove('active'));
            // Add active class to clicked tab
            btn.classList.add('active');

            // Update preview based on tab
            const tab = btn.dataset.tab;
            updateExportPreview(tab);
        });
    });
});

function updateExportPreview(format) {
    const preview = document.getElementById('exportCode');

    const templates = {
        markdown: `# Как оформить заказ

## Шаг 1
Нажмите на поле «Email» и введите ваш адрес электронной почты.

![Шаг 1](screenshot_01.png)

## Шаг 2
Введите пароль от вашего аккаунта в соответствующее поле.

![Шаг 2](screenshot_02.png)

## Шаг 3
Нажмите кнопку «Войти» для авторизации в системе.

![Шаг 3](screenshot_03.png)`,

        html: `<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Как оформить заказ</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .step { margin-bottom: 40px; }
        .step h2 { color: #37352F; }
        .step img { max-width: 100%; border-radius: 8px; }
        .step p { font-size: 16px; line-height: 1.6; color: #37352F; }
    </style>
</head>
<body>
    <h1>Как оформить заказ</h1>

    <div class="step">
        <h2>Шаг 1</h2>
        <p>Нажмите на поле «Email» и введите ваш адрес электронной почты.</p>
        <img src="screenshot_01.png" alt="Шаг 1">
    </div>

    <div class="step">
        <h2>Шаг 2</h2>
        <p>Введите пароль от вашего аккаунта.</p>
        <img src="screenshot_02.png" alt="Шаг 2">
    </div>
</body>
</html>`,

        pdf: `PDF документ будет содержать:
- Титульную страницу с названием гайда
- Оглавление со всеми шагами
- Пошаговые инструкции со скриншотами
- Нумерацию страниц
- Верхний и нижний колонтитулы

Для скачивания нажмите кнопку «Скачать»`
    };

    if (preview && templates[format]) {
        preview.textContent = templates[format];
    }
}
