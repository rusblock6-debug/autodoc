/**
 * НИР-Документ - Content Script
 * Логирует клики на странице
 */

(function() {
  'use strict';
  
  let isRecording = false;
  let clickCount = 0;
  
  console.log('[НИР-Документ] Content script loaded:', window.location.href);
  
  document.addEventListener('click', (event) => {
    if (!isRecording) return;
    
    const target = event.target;
    clickCount++;
    
    showClickMarker(event.clientX, event.clientY, clickCount);
    
    chrome.runtime.sendMessage({
      type: 'CLICK_LOG',
      data: {
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
      }
    }).catch(() => {});
    
    console.log(`[НИР-Документ] Click #${clickCount}:`, target.tagName);
  }, true);
  
  function getElementText(el) {
    let text = '';
    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
      text = el.placeholder || el.name || '';
    } else if (el.tagName === 'IMG') {
      text = el.alt || el.title || '';
    } else {
      text = el.textContent || '';
    }
    return text.trim().replace(/\s+/g, ' ').substring(0, 100);
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
      console.log('[НИР-Документ] Recording STARTED');
      sendResponse({ success: true });
    } else if (message.type === 'STOP_RECORDING') {
      isRecording = false;
      console.log('[НИР-Документ] Recording STOPPED, clicks:', clickCount);
      sendResponse({ success: true, clickCount });
    } else if (message.type === 'GET_STATUS') {
      sendResponse({ isRecording, clickCount, url: window.location.href });
    }
    return true;
  });
})();
