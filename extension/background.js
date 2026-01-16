/**
 * НИР-Документ - Background Service Worker
 * Записывает клики и скриншоты на ВСЕХ вкладках
 * 
 * Лучшие практики от Loom/Scribe/Tango:
 * - Запись продолжается при переключении вкладок
 * - Скриншот делается для активной вкладки
 * - Content script инжектится во все вкладки
 */

// Состояние записи
let recordingState = {
  isRecording: false,
  startTime: null,
  sessionName: '',
  clickLog: [],
  screenshots: []
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
  console.log('[НИР-Документ] Message:', message.type);
  
  switch (message.type) {
    case 'START_RECORDING':
      handleStartRecording(message, sendResponse);
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
      
    default:
      sendResponse({ success: true });
      return false;
  }
});

// ============================================
// RECORDING FUNCTIONS
// ============================================

async function handleStartRecording(message, sendResponse) {
  if (recordingState.isRecording) {
    sendResponse({ error: 'Already recording' });
    return;
  }
  
  try {
    // Сброс состояния
    recordingState = {
      isRecording: true,
      startTime: Date.now(),
      sessionName: message.sessionName || 'Новый гайд',
      clickLog: [],
      screenshots: []
    };
    
    // Инжектим content script во ВСЕ открытые вкладки
    await injectContentScriptToAllTabs();
    
    showNotification('recording-started', 'НИР-Документ', 'Запись началась! Кликайте по элементам на любой вкладке.');
    
    sendResponse({ 
      success: true, 
      recordingId: recordingState.startTime 
    });
    
  } catch (error) {
    console.error('[НИР-Документ] Start error:', error);
    sendResponse({ error: error.message });
  }
}

async function handleStopRecording(message, sendResponse) {
  if (!recordingState.isRecording) {
    sendResponse({ error: 'Not recording' });
    return;
  }
  
  try {
    // Обновляем имя если передано
    if (message?.sessionName) {
      recordingState.sessionName = message.sessionName;
    }
    
    // Останавливаем запись во всех вкладках
    await stopRecordingInAllTabs();
    
    // Собираем данные
    const sessionData = {
      session_name: recordingState.sessionName,
      start_time: recordingState.startTime,
      end_time: Date.now(),
      duration_seconds: (Date.now() - recordingState.startTime) / 1000,
      clicks: recordingState.clickLog,
      click_count: recordingState.clickLog.length
    };
    
    console.log('[НИР-Документ] Session:', sessionData.click_count, 'clicks');
    
    // Отправляем на бэкенд
    const result = await uploadSession(sessionData);
    
    // Сохраняем количество кликов для уведомления
    const clickCount = recordingState.clickLog.length;
    
    // Сбрасываем состояние
    recordingState = {
      isRecording: false,
      startTime: null,
      sessionName: '',
      clickLog: [],
      screenshots: []
    };
    
    // Открываем результат
    if (result.success && result.guide_id) {
      showNotification('done', 'НИР-Документ', `Готово! ${clickCount} шагов`);
      chrome.tabs.create({ url: `${CONFIG.FRONTEND_URL}/guide/${result.guide_id}/edit` });
    } else {
      showNotification('done', 'НИР-Документ', result.error || 'Сохранено');
      chrome.tabs.create({ url: CONFIG.FRONTEND_URL });
    }
    
    sendResponse({ success: true, uploadResult: result });
    
  } catch (error) {
    console.error('[НИР-Документ] Stop error:', error);
    recordingState.isRecording = false;
    sendResponse({ error: error.message });
  }
}

// ============================================
// CLICK HANDLING
// ============================================

async function handleClickLog(data, sender) {
  if (!recordingState.isRecording) return;
  
  const clickIndex = recordingState.clickLog.length;
  const timestamp = (Date.now() - recordingState.startTime) / 1000;
  
  // Сохраняем клик
  const clickEntry = {
    timestamp,
    x: data.x,
    y: data.y,
    element: data.tagName || 'unknown',
    element_id: data.id || null,
    element_class: data.className || null,
    element_text: data.text || null,
    viewport_width: data.viewportWidth,
    viewport_height: data.viewportHeight,
    page_url: data.url || sender.tab?.url || null,
    screenshot_index: clickIndex
  };
  
  recordingState.clickLog.push(clickEntry);
  console.log(`[НИР-Документ] Click #${clickIndex + 1}: ${data.tagName} at ${data.x},${data.y}`);
  
  // Делаем скриншот активной вкладки
  try {
    const dataUrl = await chrome.tabs.captureVisibleTab(sender.tab?.windowId, {
      format: 'png',
      quality: 90
    });
    recordingState.screenshots[clickIndex] = dataUrl;
    console.log(`[НИР-Документ] Screenshot #${clickIndex + 1} OK`);
  } catch (e) {
    console.log(`[НИР-Документ] Screenshot #${clickIndex + 1} failed:`, e.message);
    recordingState.screenshots[clickIndex] = null;
  }
  
  // Обновляем popup
  chrome.runtime.sendMessage({
    type: 'CLICK_UPDATE',
    count: recordingState.clickLog.length
  }).catch(() => {});
}

// ============================================
// CONTENT SCRIPT INJECTION
// ============================================

async function injectContentScriptToAllTabs() {
  try {
    const tabs = await chrome.tabs.query({});
    
    for (const tab of tabs) {
      // Пропускаем системные страницы
      if (!tab.url || tab.url.startsWith('chrome://') || tab.url.startsWith('chrome-extension://')) {
        continue;
      }
      
      try {
        // Проверяем, есть ли уже content script
        await chrome.tabs.sendMessage(tab.id, { type: 'START_RECORDING' });
        console.log(`[НИР-Документ] Tab ${tab.id} already has content script`);
      } catch {
        // Инжектим content script
        try {
          await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            files: ['content.js']
          });
          await new Promise(r => setTimeout(r, 50));
          await chrome.tabs.sendMessage(tab.id, { type: 'START_RECORDING' });
          console.log(`[НИР-Документ] Injected into tab ${tab.id}`);
        } catch (e) {
          console.log(`[НИР-Документ] Cannot inject into tab ${tab.id}:`, e.message);
        }
      }
    }
  } catch (e) {
    console.error('[НИР-Документ] Injection error:', e);
  }
}

async function stopRecordingInAllTabs() {
  try {
    const tabs = await chrome.tabs.query({});
    for (const tab of tabs) {
      try {
        await chrome.tabs.sendMessage(tab.id, { type: 'STOP_RECORDING' });
      } catch {}
    }
  } catch {}
}

// Инжектим в новые вкладки во время записи
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (!recordingState.isRecording) return;
  if (changeInfo.status !== 'complete') return;
  if (!tab.url || tab.url.startsWith('chrome://')) return;
  
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ['content.js']
    });
    await new Promise(r => setTimeout(r, 50));
    await chrome.tabs.sendMessage(tabId, { type: 'START_RECORDING' });
    console.log(`[НИР-Документ] Injected into new tab ${tabId}`);
  } catch {}
});

// ============================================
// UPLOAD
// ============================================

async function uploadSession(sessionData) {
  try {
    const clicksJson = JSON.stringify({
      version: '1.0',
      session_name: sessionData.session_name,
      start_time: sessionData.start_time,
      end_time: sessionData.end_time,
      duration_seconds: sessionData.duration_seconds,
      clicks: sessionData.clicks.map((c, i) => ({
        ...c,
        has_screenshot: !!recordingState.screenshots[i]
      }))
    }, null, 2);
    
    const formData = new FormData();
    formData.append('clicks_log', new Blob([clicksJson], { type: 'application/json' }), 'clicks.json');
    formData.append('title', sessionData.session_name);
    formData.append('duration_seconds', String(sessionData.duration_seconds || 0));
    formData.append('click_count', String(sessionData.click_count || 0));
    
    // Добавляем скриншоты
    for (let i = 0; i < recordingState.screenshots.length; i++) {
      const screenshot = recordingState.screenshots[i];
      if (screenshot) {
        const response = await fetch(screenshot);
        const blob = await response.blob();
        formData.append('screenshots', blob, `screenshot_${i}.png`);
      }
    }
    
    const response = await fetch(CONFIG.API_BASE + CONFIG.UPLOAD_ENDPOINT, {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    const result = await response.json();
    return { success: true, session_id: result.session_id, guide_id: result.guide_id };
    
  } catch (error) {
    console.error('[НИР-Документ] Upload error:', error);
    return { success: false, error: error.message };
  }
}

// ============================================
// UTILITIES
// ============================================

function showNotification(id, title, message) {
  try {
    chrome.notifications?.create(id, {
      type: 'basic',
      iconUrl: 'icons/icon128.png',
      title,
      message
    });
  } catch {}
}

chrome.runtime.onInstalled.addListener(() => {
  console.log('[НИР-Документ] Installed');
});
