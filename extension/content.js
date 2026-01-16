/**
 * AutoDoc AI Recorder - Content Script
 * Логирует клики и действия пользователя на странице
 * 
 * Этот скрипт внедряется в каждую страницу и отправляет
 * данные о кликах в background script
 */

(function() {
  'use strict';
  
  // Состояние
  let isRecording = false;
  let clickCount = 0;
  
  console.log('[AutoDoc Content] Script loaded on:', window.location.href);
  
  // ============================================
  // EVENT LISTENERS
  // ============================================
  
  // Клики
  document.addEventListener('click', handleClick, true);
  document.addEventListener('mousedown', handleMouseDown, true);
  
  // Клавиатура (опционально)
  document.addEventListener('keydown', handleKeyDown, true);
  
  // Ввод текста
  document.addEventListener('input', handleInput, true);
  
  // ============================================
  // HANDLERS
  // ============================================
  
  function handleClick(event) {
    if (!isRecording) return;
    
    const target = event.target;
    
    const clickData = {
      timestamp: Date.now(),
      x: event.clientX,
      y: event.clientY,
      pageX: event.pageX,
      pageY: event.pageY,
      tagName: target.tagName,
      className: target.className || '',
      id: target.id || '',
      text: getElementText(target),
      href: target.href || null,
      viewportWidth: window.innerWidth,
      viewportHeight: window.innerHeight,
      scrollX: window.scrollX,
      scrollY: window.scrollY,
      url: window.location.href
    };
    
    clickCount++;
    
    // Визуальная обратная связь
    showClickFeedback(event.clientX, event.clientY);
    
    // Отправляем в background
    chrome.runtime.sendMessage({
      type: 'CLICK_LOG',
      data: clickData
    }).catch(err => {
      console.log('[AutoDoc Content] Could not send click:', err);
    });
    
    console.log(`[AutoDoc Content] Click #${clickCount}:`, clickData.x, clickData.y, clickData.tagName);
  }
  
  function handleMouseDown(event) {
    // Можно использовать для более точного определения момента клика
  }
  
  function handleKeyDown(event) {
    if (!isRecording) return;
    
    // Логируем только важные клавиши
    const importantKeys = ['Enter', 'Tab', 'Escape', 'Backspace', 'Delete'];
    
    if (importantKeys.includes(event.key) || event.ctrlKey || event.metaKey) {
      chrome.runtime.sendMessage({
        type: 'KEY_LOG',
        data: {
          timestamp: Date.now(),
          key: event.key,
          code: event.code,
          ctrlKey: event.ctrlKey,
          shiftKey: event.shiftKey,
          altKey: event.altKey,
          metaKey: event.metaKey
        }
      }).catch(() => {});
    }
  }
  
  function handleInput(event) {
    if (!isRecording) return;
    
    const target = event.target;
    
    // Не логируем содержимое полей (приватность)
    chrome.runtime.sendMessage({
      type: 'INPUT_LOG',
      data: {
        timestamp: Date.now(),
        tagName: target.tagName,
        type: target.type || 'text',
        hasValue: !!target.value
      }
    }).catch(() => {});
  }
  
  // ============================================
  // UTILITIES
  // ============================================
  
  function getElementText(element) {
    // Получаем текст элемента (ограничиваем длину)
    let text = '';
    
    if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
      text = element.placeholder || element.name || '';
    } else if (element.tagName === 'IMG') {
      text = element.alt || element.title || '';
    } else {
      text = element.textContent || element.innerText || '';
    }
    
    // Очищаем и обрезаем
    text = text.trim().replace(/\s+/g, ' ');
    return text.substring(0, 100);
  }
  
  function showClickFeedback(x, y) {
    // Создаём визуальный маркер клика
    const marker = document.createElement('div');
    marker.className = 'autodoc-click-marker';
    marker.style.cssText = `
      position: fixed;
      left: ${x - 20}px;
      top: ${y - 20}px;
      width: 40px;
      height: 40px;
      border: 3px solid #FFD700;
      border-radius: 50%;
      pointer-events: none;
      z-index: 2147483647;
      animation: autodoc-pulse 0.6s ease-out forwards;
      box-shadow: 0 0 10px rgba(255, 215, 0, 0.5);
    `;
    
    // Добавляем стили анимации если ещё нет
    ensureStyles();
    
    document.body.appendChild(marker);
    
    // Удаляем через 600ms
    setTimeout(() => {
      marker.remove();
    }, 600);
  }
  
  function ensureStyles() {
    if (document.getElementById('autodoc-styles')) return;
    
    const style = document.createElement('style');
    style.id = 'autodoc-styles';
    style.textContent = `
      @keyframes autodoc-pulse {
        0% {
          transform: scale(0.5);
          opacity: 1;
        }
        100% {
          transform: scale(1.5);
          opacity: 0;
        }
      }
      
      .autodoc-click-marker {
        transition: none !important;
      }
    `;
    document.head.appendChild(style);
  }
  
  // ============================================
  // MESSAGE HANDLING
  // ============================================
  
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    console.log('[AutoDoc Content] Message:', message.type);
    
    switch (message.type) {
      case 'START_RECORDING':
        isRecording = true;
        clickCount = 0;
        console.log('[AutoDoc Content] Recording STARTED');
        sendResponse({ success: true });
        break;
        
      case 'STOP_RECORDING':
        isRecording = false;
        console.log('[AutoDoc Content] Recording STOPPED, clicks:', clickCount);
        sendResponse({ 
          success: true, 
          clickCount: clickCount 
        });
        break;
        
      case 'GET_STATUS':
        sendResponse({ 
          isRecording: isRecording,
          clickCount: clickCount,
          url: window.location.href
        });
        break;
        
      default:
        sendResponse({ error: 'Unknown message type' });
    }
    
    return true; // Async response
  });
  
  // ============================================
  // INITIALIZATION
  // ============================================
  
  // Сообщаем background что страница загружена
  chrome.runtime.sendMessage({
    type: 'PAGE_INFO',
    data: {
      url: window.location.href,
      title: document.title,
      width: window.innerWidth,
      height: window.innerHeight
    }
  }).catch(() => {
    // Background может быть не готов
  });
  
})();
