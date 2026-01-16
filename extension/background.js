/**
 * НИР-Документ - Background Service Worker
 * Управляет записью и передаёт данные на бэкенд
 */

// Состояние записи
let recordingState = {
  isRecording: false,
  startTime: null,
  sessionName: '',
  clickLog: [],
  screenshots: [],  // Массив скриншотов (base64)
  tabId: null
};

// Настройки
const CONFIG = {
  API_BASE: 'http://localhost:8000',
  FRONTEND_URL: 'http://localhost:3000',
  UPLOAD_ENDPOINT: '/api/v1/sessions/upload'
};

console.log('[НИР-Документ] Background script loaded');

// ============================================
// MESSAGE HANDLERS
// ============================================

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log('[НИР-Документ] Message received:', message.type);
  
  switch (message.type) {
    case 'START_RECORDING':
      handleStartRecording(message, sender, sendResponse);
      return true;
      
    case 'STOP_RECORDING':
      handleStopRecording(message, sendResponse);
      return true;
      
    case 'GET_STATE':
      sendResponse({ 
        state: {
          isRecording: recordingState.isRecording,
          startTime: recordingState.startTime,
          clickCount: recordingState.clickLog.length,
          sessionName: recordingState.sessionName
        }
      });
      return false;
      
    case 'CLICK_LOG':
      handleClickLog(message.data, sender);
      sendResponse({ success: true });
      return false;
      
    case 'KEY_LOG':
    case 'INPUT_LOG':
    case 'PAGE_INFO':
      sendResponse({ success: true });
      return false;
      
    default:
      sendResponse({ error: 'Unknown message type' });
      return false;
  }
});

// ============================================
// RECORDING FUNCTIONS
// ============================================

async function handleStartRecording(message, sender, sendResponse) {
  if (recordingState.isRecording) {
    sendResponse({ error: 'Already recording' });
    return;
  }
  
  try {
    recordingState.sessionName = message.sessionName || 'Новый гайд';
    recordingState.clickLog = [];
    recordingState.screenshots = [];
    recordingState.startTime = Date.now();
    recordingState.tabId = null;
    
    // Получаем активную вкладку
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    const tab = tabs[0];
    
    if (tab && tab.id) {
      recordingState.tabId = tab.id;
      
      // Отправляем сообщение content script о начале записи
      try {
        await chrome.tabs.sendMessage(tab.id, { type: 'START_RECORDING' });
        console.log('[НИР-Документ] Content script notified');
      } catch (e) {
        console.log('[НИР-Документ] Content script not ready, injecting...');
        try {
          await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            files: ['content.js']
          });
          // Даём время на загрузку
          await new Promise(r => setTimeout(r, 100));
          await chrome.tabs.sendMessage(tab.id, { type: 'START_RECORDING' });
        } catch (injectError) {
          console.log('[НИР-Документ] Could not inject content script:', injectError);
        }
      }
    }
    
    recordingState.isRecording = true;
    
    // Показываем уведомление
    showNotification('recording-started', 'НИР-Документ', 'Запись началась! Кликайте по элементам.');
    
    sendResponse({ 
      success: true, 
      recordingId: recordingState.startTime 
    });
    
  } catch (error) {
    console.error('[НИР-Документ] Start recording error:', error);
    sendResponse({ error: error.message });
  }
}

async function handleStopRecording(message, sendResponse) {
  if (!recordingState.isRecording) {
    sendResponse({ error: 'Not recording' });
    return;
  }
  
  try {
    // Обновляем имя если передано новое
    if (message && message.sessionName) {
      recordingState.sessionName = message.sessionName;
    }
    
    // Останавливаем запись в content script
    if (recordingState.tabId) {
      try {
        await chrome.tabs.sendMessage(recordingState.tabId, { type: 'STOP_RECORDING' });
      } catch (e) {
        console.log('[НИР-Документ] Could not stop content script:', e);
      }
    }
    
    // Собираем данные
    const sessionData = {
      session_name: recordingState.sessionName,
      start_time: recordingState.startTime,
      end_time: Date.now(),
      duration_seconds: (Date.now() - recordingState.startTime) / 1000,
      clicks: recordingState.clickLog,
      click_count: recordingState.clickLog.length
    };
    
    console.log('[НИР-Документ] Session data:', sessionData);
    
    // Отправляем на бэкенд
    const result = await uploadSession(sessionData);
    
    // Сбрасываем состояние
    const clickCount = recordingState.clickLog.length;
    recordingState.isRecording = false;
    recordingState.startTime = null;
    recordingState.clickLog = [];
    recordingState.screenshots = [];
    
    if (result.success && result.guide_id) {
      // Если гайд уже создан, открываем сразу редактор
      showNotification('recording-stopped', 'НИР-Документ', `Сохранено! Кликов: ${clickCount}`);
      const url = `${CONFIG.FRONTEND_URL}/guide/${result.guide_id}/edit`;
      console.log('[НИР-Документ] Opening guide editor:', url);
      chrome.tabs.create({ url });
    } else if (result.success && result.session_id) {
      // Иначе открываем страницу статуса сессии
      showNotification('recording-stopped', 'НИР-Документ', `Сохранено! Кликов: ${clickCount}`);
      const url = `${CONFIG.FRONTEND_URL}/session/${result.session_id}`;
      console.log('[НИР-Документ] Opening session status:', url);
      chrome.tabs.create({ url });
    } else if (result.success) {
      // Успех но нет session_id - открываем Dashboard
      showNotification('recording-stopped', 'НИР-Документ', `Сохранено! Кликов: ${clickCount}`);
      chrome.tabs.create({ url: CONFIG.FRONTEND_URL });
    } else {
      showNotification('upload-error', 'НИР-Документ - Ошибка', result.error || 'Не удалось сохранить');
      // Всё равно открываем Dashboard
      chrome.tabs.create({ url: CONFIG.FRONTEND_URL });
    }
    
    sendResponse({ 
      success: true, 
      sessionData,
      uploadResult: result
    });
    
  } catch (error) {
    console.error('[НИР-Документ] Stop recording error:', error);
    recordingState.isRecording = false;
    sendResponse({ error: error.message });
  }
}

function handleClickLog(data, sender) {
  if (!recordingState.isRecording) return;
  
  const timestamp = (Date.now() - recordingState.startTime) / 1000;
  const clickIndex = recordingState.clickLog.length;
  
  const clickEntry = {
    timestamp: timestamp,
    x: data.x,
    y: data.y,
    element: data.tagName || 'unknown',
    element_id: data.id || null,
    element_class: data.className || null,
    element_text: data.text || null,
    viewport_width: data.viewportWidth,
    viewport_height: data.viewportHeight,
    page_url: sender.tab?.url || null,
    screenshot_index: clickIndex  // Индекс скриншота
  };
  
  recordingState.clickLog.push(clickEntry);
  
  console.log(`[НИР-Документ] Click #${recordingState.clickLog.length}: ${clickEntry.x}, ${clickEntry.y}`);
  
  // Делаем скриншот
  captureScreenshot(clickIndex, sender.tab?.windowId);
  
  // Обновляем popup
  chrome.runtime.sendMessage({
    type: 'CLICK_UPDATE',
    count: recordingState.clickLog.length
  }).catch(() => {});
}

// Захват скриншота
async function captureScreenshot(clickIndex, windowId) {
  try {
    const dataUrl = await chrome.tabs.captureVisibleTab(windowId, {
      format: 'png',
      quality: 90
    });
    
    recordingState.screenshots[clickIndex] = dataUrl;
    console.log(`[НИР-Документ] Screenshot #${clickIndex + 1} captured (${Math.round(dataUrl.length / 1024)}KB)`);
    
  } catch (error) {
    console.error(`[НИР-Документ] Screenshot #${clickIndex + 1} failed:`, error);
    recordingState.screenshots[clickIndex] = null;
  }
}

// ============================================
// API FUNCTIONS
// ============================================

async function uploadSession(sessionData) {
  try {
    // Добавляем скриншоты к кликам
    const clicksWithScreenshots = sessionData.clicks.map((click, index) => ({
      ...click,
      has_screenshot: !!recordingState.screenshots[index]
    }));
    
    const clicksJson = JSON.stringify({
      version: '1.0',
      session_name: sessionData.session_name,
      start_time: sessionData.start_time,
      end_time: sessionData.end_time,
      duration_seconds: sessionData.duration_seconds,
      clicks: clicksWithScreenshots
    }, null, 2);
    
    console.log('[НИР-Документ] Clicks JSON:', clicksJson);
    
    const formData = new FormData();
    const clicksBlob = new Blob([clicksJson], { type: 'application/json' });
    formData.append('clicks_log', clicksBlob, 'clicks.json');
    formData.append('title', sessionData.session_name || 'Новый гайд');
    formData.append('duration_seconds', String(sessionData.duration_seconds || 0));
    formData.append('click_count', String(sessionData.click_count || 0));
    
    // Добавляем скриншоты
    for (let i = 0; i < recordingState.screenshots.length; i++) {
      const screenshot = recordingState.screenshots[i];
      if (screenshot) {
        // Конвертируем data URL в Blob
        const response = await fetch(screenshot);
        const blob = await response.blob();
        formData.append('screenshots', blob, `screenshot_${i}.png`);
        console.log(`[НИР-Документ] Added screenshot_${i}.png (${Math.round(blob.size / 1024)}KB)`);
      }
    }
    
    const url = CONFIG.API_BASE + CONFIG.UPLOAD_ENDPOINT;
    console.log('[НИР-Документ] Uploading to:', url);
    
    const response = await fetch(url, {
      method: 'POST',
      body: formData
    });
    
    console.log('[НИР-Документ] Response status:', response.status);
    
    const responseText = await response.text();
    console.log('[НИР-Документ] Response body:', responseText);
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${responseText}`);
    }
    
    let result;
    try {
      result = JSON.parse(responseText);
    } catch (e) {
      throw new Error('Invalid JSON response: ' + responseText);
    }
    
    console.log('[НИР-Документ] Upload success:', result);
    
    return {
      success: true,
      session_id: result.session_id,
      guide_id: result.guide_id
    };
    
  } catch (error) {
    console.error('[НИР-Документ] Upload error:', error);
    return {
      success: false,
      error: error.message
    };
  }
}

// ============================================
// UTILITIES
// ============================================

function showNotification(id, title, message) {
  try {
    if (chrome.notifications && chrome.notifications.create) {
      chrome.notifications.create(id, {
        type: 'basic',
        iconUrl: 'icons/icon128.png',
        title: title,
        message: message
      });
    }
  } catch (e) {
    console.log('[НИР-Документ] Notification error:', e);
  }
}

// Сброс при установке
chrome.runtime.onInstalled.addListener(() => {
  console.log('[НИР-Документ] Extension installed');
  recordingState = {
    isRecording: false,
    startTime: null,
    sessionName: '',
    clickLog: [],
    screenshots: [],
    tabId: null
  };
});

// Обработка закрытия вкладки
chrome.tabs.onRemoved.addListener((tabId) => {
  if (recordingState.tabId === tabId && recordingState.isRecording) {
    console.log('[НИР-Документ] Tab closed, stopping recording');
    handleStopRecording({}, () => {});
  }
});
