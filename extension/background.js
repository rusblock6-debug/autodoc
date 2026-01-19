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
  navigationLog: [],
  screenshots: [],
  activeTabId: null,
  recordingTabs: new Set()
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
  console.log('[НИР-Документ] Message:', message.type, sender.tab?.id);
  
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
          navigationCount: recordingState.navigationLog.length,
          sessionName: recordingState.sessionName,
          activeTabId: recordingState.activeTabId,
          recordingTabs: Array.from(recordingState.recordingTabs)
        }
      });
      return false;
      
    case 'CLICK_LOG':
      handleClickLog(message.data, sender);
      sendResponse({ success: true });
      return false;
      
    case 'NAVIGATION_LOG':
      handleNavigationLog(message.data, sender);
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
    // Получаем активную вкладку
    const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
    
    // Сброс состояния
    recordingState = {
      isRecording: true,
      startTime: Date.now(),
      sessionName: message.sessionName || 'Новый гайд',
      clickLog: [],
      navigationLog: [],
      screenshots: [],
      activeTabId: activeTab?.id || null,
      recordingTabs: new Set()
    };
    
    // Инжектим content script во ВСЕ открытые вкладки
    await injectContentScriptToAllTabs();
    
    // Логируем начальное состояние
    if (activeTab) {
      recordingState.navigationLog.push({
        timestamp: (Date.now() - recordingState.startTime) / 1000,
        navigationType: 'recording_started',
        url: activeTab.url,
        tabId: activeTab.id,
        isActiveTab: true
      });
    }
    
    showNotification('recording-started', 'НИР-Документ', 'Запись началась! Кликайте по элементам на любой вкладке.');
    
    sendResponse({ 
      success: true, 
      recordingId: recordingState.startTime,
      activeTabId: recordingState.activeTabId
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
      navigation: recordingState.navigationLog,
      click_count: recordingState.clickLog.length,
      navigation_count: recordingState.navigationLog.length,
      recording_tabs: Array.from(recordingState.recordingTabs)
    };
    
    console.log('[НИР-Документ] Session:', sessionData.click_count, 'clicks,', sessionData.navigation_count, 'navigations');
    
    // Отправляем на бэкенд
    const result = await uploadSession(sessionData);
    
    // Сохраняем количество событий для уведомления
    const eventCount = recordingState.clickLog.length + recordingState.navigationLog.length;
    
    // Сбрасываем состояние
    recordingState = {
      isRecording: false,
      startTime: null,
      sessionName: '',
      clickLog: [],
      navigationLog: [],
      screenshots: [],
      activeTabId: null,
      recordingTabs: new Set()
    };
    
    // Открываем результат
    if (result.success && result.guide_id) {
      showNotification('done', 'НИР-Документ', `Готово! ${eventCount} событий`);
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
// CLICK & NAVIGATION HANDLING
// ============================================

async function handleClickLog(data, sender) {
  if (!recordingState.isRecording) return;
  
  const clickIndex = recordingState.clickLog.length;
  const timestamp = (Date.now() - recordingState.startTime) / 1000;
  const tabId = sender.tab?.id;
  
  // Отмечаем вкладку как активную в записи
  if (tabId) {
    recordingState.recordingTabs.add(tabId);
  }
  
  // Сохраняем клик
  const clickEntry = {
    timestamp,
    x: data.x,
    y: data.y,
    element: data.tagName || 'unknown',
    element_id: data.id || null,
    element_class: data.className || null,
    element_text: data.text || null,
    href: data.href || null,
    is_link: data.isLink || false,
    viewport_width: data.viewportWidth,
    viewport_height: data.viewportHeight,
    page_url: data.url || sender.tab?.url || null,
    tab_id: tabId,
    screenshot_index: clickIndex
  };
  
  recordingState.clickLog.push(clickEntry);
  console.log(`[НИР-Документ] Click #${clickIndex + 1}: ${data.tagName} at ${data.x},${data.y} on tab ${tabId}`);
  
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
    count: recordingState.clickLog.length,
    navigationCount: recordingState.navigationLog.length
  }).catch(() => {});
}

async function handleNavigationLog(data, sender) {
  if (!recordingState.isRecording) return;
  
  const timestamp = (Date.now() - recordingState.startTime) / 1000;
  const tabId = sender.tab?.id;
  
  // Отмечаем вкладку как активную в записи
  if (tabId) {
    recordingState.recordingTabs.add(tabId);
  }
  
  const navigationEntry = {
    timestamp,
    navigation_type: data.navigationType,
    url: data.url,
    from_url: data.fromUrl || null,
    tab_id: tabId,
    load_time: data.loadTime || null,
    from_click: data.fromClick || false,
    click_index: data.clickIndex || null,
    state_data: data.state || null
  };
  
  recordingState.navigationLog.push(navigationEntry);
  console.log(`[НИР-Документ] Navigation #${recordingState.navigationLog.length}: ${data.navigationType} to ${data.url} on tab ${tabId}`);
  
  // Обновляем popup
  chrome.runtime.sendMessage({
    type: 'NAVIGATION_UPDATE',
    count: recordingState.navigationLog.length,
    clickCount: recordingState.clickLog.length
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
        await chrome.tabs.sendMessage(tab.id, { type: 'PING' });
        await chrome.tabs.sendMessage(tab.id, { type: 'START_RECORDING' });
        console.log(`[НИР-Документ] Tab ${tab.id} already has content script`);
      } catch {
        // Инжектим content script
        try {
          await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            files: ['content.js']
          });
          await new Promise(r => setTimeout(r, 100));
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
    // Проверяем, есть ли уже content script
    try {
      await chrome.tabs.sendMessage(tabId, { type: 'PING' });
      console.log(`[НИР-Документ] Tab ${tabId} already has content script after update`);
    } catch {
      // Инжектим content script
      await chrome.scripting.executeScript({
        target: { tabId },
        files: ['content.js']
      });
      await new Promise(r => setTimeout(r, 100));
    }
    
    await chrome.tabs.sendMessage(tabId, { type: 'START_RECORDING' });
    console.log(`[НИР-Документ] Injected/restarted recording in updated tab ${tabId}`);
    
    // Логируем навигацию
    if (recordingState.recordingTabs.has(tabId)) {
      recordingState.navigationLog.push({
        timestamp: (Date.now() - recordingState.startTime) / 1000,
        navigation_type: 'tab_updated',
        url: tab.url,
        tab_id: tabId,
        change_info: changeInfo
      });
    }
  } catch (e) {
    console.log(`[НИР-Документ] Failed to handle tab update ${tabId}:`, e.message);
  }
});

// Отслеживаем переключение вкладок
chrome.tabs.onActivated.addListener(async (activeInfo) => {
  if (!recordingState.isRecording) return;
  
  try {
    const tab = await chrome.tabs.get(activeInfo.tabId);
    recordingState.activeTabId = activeInfo.tabId;
    
    // Логируем переключение вкладки
    recordingState.navigationLog.push({
      timestamp: (Date.now() - recordingState.startTime) / 1000,
      navigation_type: 'tab_activated',
      url: tab.url,
      tab_id: activeInfo.tabId,
      from_tab_id: activeInfo.previousTabId || null
    });
    
    console.log(`[НИР-Документ] Tab activated: ${activeInfo.tabId} (${tab.url})`);
  } catch (e) {
    console.log(`[НИР-Документ] Failed to handle tab activation:`, e.message);
  }
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
