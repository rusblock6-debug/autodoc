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
  
  // Основной обработчик кликов
  document.addEventListener('click', (event) => {
    if (!isRecording) return;
    
    const target = event.target;
    clickCount++;
    
    showClickMarker(event.clientX, event.clientY, clickCount);
    
    // Проверяем, является ли это ссылкой
    const isLink = target.tagName === 'A' || target.closest('a');
    const linkHref = isLink ? (target.href || target.closest('a')?.href) : null;
    
    const clickData = {
      x: event.clientX,
      y: event.clientY,
      pageX: event.pageX,
      pageY: event.pageY,
      tagName: target.tagName,
      className: target.className || '',
      id: target.id || '',
      text: getElementText(target),
      href: linkHref,
      isLink: !!isLink,
      viewportWidth: window.innerWidth,
      viewportHeight: window.innerHeight,
      scrollX: window.scrollX,
      scrollY: window.scrollY,
      url: window.location.href,
      timestamp: Date.now()
    };
    
    chrome.runtime.sendMessage({
      type: 'CLICK_LOG',
      data: clickData
    }).catch(() => {});
    
    console.log(`[НИР-Документ] Click #${clickCount}:`, target.tagName, linkHref ? `-> ${linkHref}` : '');
    
    // Если это ссылка, подготавливаемся к навигации
    if (isLink && linkHref) {
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
