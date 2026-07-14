/**
 * НИР-Документ - Content Script
 * Отслеживает все действия пользователя: клики, навигацию, переходы
 */

(function() {
  'use strict';
  
  let isRecording = false;
  let clickCount = 0;
  let currentUrl = window.location.href;
  let navigationStartTime = Date.now();
  
  console.log('[НИР-Документ] Content script loaded:', currentUrl);
  
  // Отслеживаем изменения URL (SPA навигация)
  let lastUrl = currentUrl;
  const urlCheckInterval = setInterval(() => {
    if (window.location.href !== lastUrl) {
      lastUrl = window.location.href;
      handleNavigation('spa_navigation', lastUrl);
    }
  }, 500);
  
  // Отслеживаем события браузера
  window.addEventListener('beforeunload', () => {
    if (isRecording) {
      logNavigationEvent('page_unload', window.location.href);
    }
  });
  
  window.addEventListener('load', () => {
    if (isRecording) {
      logNavigationEvent('page_load', window.location.href);
    }
  });
  
  // Отслеживаем popstate (back/forward)
  window.addEventListener('popstate', (event) => {
    if (isRecording) {
      handleNavigation('browser_navigation', window.location.href, event.state);
    }
  });
  
  // Отслеживаем pushState/replaceState
  const originalPushState = history.pushState;
  const originalReplaceState = history.replaceState;
  
  history.pushState = function(...args) {
    originalPushState.apply(this, args);
    if (isRecording) {
      handleNavigation('push_state', window.location.href);
    }
  };
  
  history.replaceState = function(...args) {
    originalReplaceState.apply(this, args);
    if (isRecording) {
      handleNavigation('replace_state', window.location.href);
    }
  };
  
  // === Захват действий: click / select / drag / input ===
  // Тип действия определяется парой mousedown/mouseup:
  //   - жестом создано непустое выделение -> select (пишем выделенный текст);
  //   - мышь ушла дальше порога без выделения -> drag (from -> to);
  //   - иначе обычный click (его логирует штатное событие click ниже).
  // Без этого ЛЮБОЕ действие записывалось как клик, и генератор текстов
  // не мог написать «Выделите…»/«Перетащите…» — тип терялся ещё на записи.
  const DRAG_THRESHOLD_PX = 12;
  let gestureStart = null;
  let suppressNextClick = false;

  const buildEventData = (action, x, y, target, extra = {}) => {
    const isLink = target && (target.tagName === 'A' || target.closest?.('a'));
    const linkHref = isLink ? (target.href || target.closest('a')?.href) : null;
    return {
      action,
      x, y,
      pageX: x + window.scrollX,
      pageY: y + window.scrollY,
      tagName: (target && target.tagName) || 'UNKNOWN',
      className: (target && target.className) || '',
      id: (target && target.id) || '',
      text: target ? getElementText(target) : '',
      href: linkHref,
      isLink: !!isLink,
      viewportWidth: window.innerWidth,
      viewportHeight: window.innerHeight,
      scrollX: window.scrollX,
      scrollY: window.scrollY,
      url: window.location.href,
      timestamp: Date.now(),
      ...extra
    };
  };

  const logEvent = (data) => {
    clickCount++;
    chrome.runtime.sendMessage({ type: 'CLICK_LOG', data }).catch(() => {});
    console.log(`[НИР-Документ] ${data.action} #${clickCount}:`, data.tagName, data.href ? `-> ${data.href}` : '');
  };

  document.addEventListener('mousedown', (event) => {
    if (!isRecording) return;
    gestureStart = {
      x: event.clientX,
      y: event.clientY,
      target: event.target,
      // Запоминаем выделение ДО жеста: клик при уже существующем выделении —
      // это не «Выделите…», а обычный клик
      selection: (window.getSelection()?.toString() || '').trim()
    };
  }, true);

  document.addEventListener('mouseup', (event) => {
    if (!isRecording || !gestureStart) return;
    const start = gestureStart;
    gestureStart = null;

    const dist = Math.hypot(event.clientX - start.x, event.clientY - start.y);
    const selection = (window.getSelection()?.toString() || '').trim();

    if (selection && selection !== start.selection) {
      logEvent(buildEventData('select', event.clientX, event.clientY, event.target, {
        selectedText: selection.slice(0, 300)
      }));
      suppressNextClick = true;
    } else if (dist > DRAG_THRESHOLD_PX) {
      // Координаты и элемент — точка захвата; куда отпустили — toX/toY
      logEvent(buildEventData('drag', start.x, start.y, start.target, {
        toX: event.clientX,
        toY: event.clientY
      }));
      suppressNextClick = true;
    }
    // Клик после select/drag браузер может и не прислать (mouseup на другом
    // элементе) — не оставляем флаг висеть
    if (suppressNextClick) {
      setTimeout(() => { suppressNextClick = false; }, 150);
    }
  }, true);

  // Нативный HTML5 drag-and-drop: во время него mouseup не срабатывает
  let dndSource = null;
  document.addEventListener('dragstart', (event) => {
    if (!isRecording) return;
    dndSource = { x: event.clientX, y: event.clientY, target: event.target };
  }, true);

  document.addEventListener('dragend', (event) => {
    if (!isRecording || !dndSource) return;
    logEvent(buildEventData('drag', dndSource.x, dndSource.y, dndSource.target, {
      toX: event.clientX,
      toY: event.clientY
    }));
    dndSource = null;
    gestureStart = null;
  }, true);

  // Ввод в поля: change срабатывает при уходе из поля / выборе в селекте.
  // Чекбоксы/радио и пр. пропускаем — их полноценно описывает сам клик.
  document.addEventListener('change', (event) => {
    if (!isRecording) return;
    const t = event.target;
    const tag = t && t.tagName ? t.tagName.toUpperCase() : '';
    if (!['INPUT', 'TEXTAREA', 'SELECT'].includes(tag)) return;

    const type = (t.type || 'text').toLowerCase();
    if (tag === 'INPUT' && ['checkbox', 'radio', 'button', 'submit', 'reset', 'file', 'image', 'range', 'color'].includes(type)) return;

    const rect = t.getBoundingClientRect();
    const label = (t.labels && t.labels[0] && t.labels[0].textContent) ||
      t.placeholder || t.getAttribute('aria-label') || t.name || '';
    // Пароли не логируем никогда
    const secret = type === 'password';
    const value = secret ? '' :
      (tag === 'SELECT' ? (t.selectedOptions?.[0]?.textContent || t.value) : String(t.value || ''));

    logEvent(buildEventData('input',
      Math.round(rect.left + rect.width / 2),
      Math.round(rect.top + rect.height / 2),
      t,
      {
        fieldLabel: String(label).trim().slice(0, 120),
        value: String(value).trim().slice(0, 120)
      }
    ));
  }, true);

  // Основной обработчик кликов
  document.addEventListener('click', (event) => {
    if (!isRecording) return;

    // Этот click — хвост уже залогированного select/drag
    if (suppressNextClick) {
      suppressNextClick = false;
      return;
    }

    const target = event.target;

    // НЕ показываем маркер во время записи - он будет в редакторе
    // showClickMarker(event.clientX, event.clientY, clickCount);

    const linkHref = (target.tagName === 'A' || target.closest('a'))
      ? (target.href || target.closest('a')?.href) : null;

    logEvent(buildEventData('click', event.clientX, event.clientY, target));
    
    // Если это ссылка, подготавливаемся к навигации
    if (linkHref) {
      setTimeout(() => {
        // Проверяем, изменился ли URL через небольшое время
        if (window.location.href !== currentUrl) {
          handleNavigation('link_click', window.location.href, { fromClick: true, clickIndex: clickCount - 1 });
        }
      }, 100);
    }
  }, true);
  
  
  // Обработка навигации
  function handleNavigation(type, newUrl, data = {}) {
    if (!isRecording) return;
    
    const oldUrl = currentUrl;
    currentUrl = newUrl;
    
    console.log(`[НИР-Документ] Navigation (${type}):`, oldUrl, '->', newUrl);
    
    logNavigationEvent(type, newUrl, { 
      fromUrl: oldUrl, 
      ...data,
      loadTime: Date.now() - navigationStartTime
    });
    
    navigationStartTime = Date.now();
  }
  
  function logNavigationEvent(type, url, data = {}) {
    chrome.runtime.sendMessage({
      type: 'NAVIGATION_LOG',
      data: {
        navigationType: type,
        url: url,
        timestamp: Date.now(),
        ...data
      }
    }).catch(() => {});
  }
  
  function getElementText(el) {
    let text = '';
    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
      text = el.placeholder || el.name || el.value || '';
    } else if (el.tagName === 'IMG') {
      text = el.alt || el.title || '';
    } else if (el.tagName === 'A') {
      text = el.textContent || el.title || el.href || '';
    } else {
      text = el.textContent || el.title || '';
    }
    return text.trim().replace(/\s+/g, ' ').substring(0, 200);
  }
  
  function showClickMarker(x, y, num) {
    if (!document.getElementById('nir-doc-styles')) {
      const style = document.createElement('style');
      style.id = 'nir-doc-styles';
      style.textContent = `
        @keyframes nir-pulse {
          0% { transform: scale(0.5); opacity: 1; }
          100% { transform: scale(1.5); opacity: 0; }
        }
        .nir-click-marker {
          position: fixed;
          width: 50px;
          height: 50px;
          margin-left: -25px;
          margin-top: -25px;
          border: 3px solid #ed8d48;
          border-radius: 50%;
          pointer-events: none;
          z-index: 2147483647;
          animation: nir-pulse 0.5s ease-out forwards;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .nir-click-number {
          background: #ed8d48;
          color: white;
          font-size: 14px;
          font-weight: bold;
          width: 24px;
          height: 24px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        }
      `;
      document.head.appendChild(style);
    }
    
    const marker = document.createElement('div');
    marker.className = 'nir-click-marker';
    marker.style.left = x + 'px';
    marker.style.top = y + 'px';
    marker.innerHTML = `<span class="nir-click-number">${num}</span>`;
    
    document.body.appendChild(marker);
    setTimeout(() => marker.remove(), 500);
  }
  
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'START_RECORDING') {
      isRecording = true;
      clickCount = 0;
      currentUrl = window.location.href;
      navigationStartTime = Date.now();
      
      // Логируем начало записи на этой странице
      logNavigationEvent('recording_started', currentUrl);
      
      console.log('[НИР-Документ] Recording STARTED on:', currentUrl);
      sendResponse({ success: true, url: currentUrl });
    } else if (message.type === 'STOP_RECORDING') {
      isRecording = false;
      
      // Логируем окончание записи
      logNavigationEvent('recording_stopped', currentUrl);
      
      console.log('[НИР-Документ] Recording STOPPED, clicks:', clickCount);
      sendResponse({ success: true, clickCount, url: currentUrl });
    } else if (message.type === 'GET_STATUS') {
      sendResponse({ 
        isRecording, 
        clickCount, 
        url: currentUrl,
        tabId: sender?.tab?.id 
      });
    } else if (message.type === 'PING') {
      sendResponse({ success: true, url: currentUrl });
    }
    return true;
  });
  
  // Очистка при выгрузке страницы
  window.addEventListener('beforeunload', () => {
    clearInterval(urlCheckInterval);
  });
})();
