/**
 * AutoDoc AI Recorder - Background Service Worker
 * Управляет записью экрана, микрофона и передаёт данные на бэкенд
 */

// Состояние записи
let isRecording = false;
let mediaRecorder = null;
let audioRecorder = null;
let recordedChunks = [];
let audioChunks = [];
let clickLog = [];
let recordingStartTime = null;
let streamIds = {};

// Настройки
let settings = {
  captureAudio: true,
  captureMicrophone: true,
  apiEndpoint: "http://localhost:8000/api/v1/sessions/upload"
};

// Загружаем настройки
chrome.storage.local.get(["autodoc_settings"], (result) => {
  if (result.autodoc_settings) {
    settings = { ...settings, ...result.autodoc_settings };
  }
});

// Сообщения от popup и content scripts
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  switch (message.type) {
    case "START_RECORDING":
      startRecording(sendResponse);
      break;
      
    case "STOP_RECORDING":
      stopRecording(sendResponse);
      break;
      
    case "GET_STATUS":
      sendResponse({ isRecording });
      break;
      
    case "LOG_CLICK":
      logClick(message.data);
      sendResponse({ success: true });
      break;
      
    case "UPDATE_SETTINGS":
      updateSettings(message.settings);
      sendResponse({ success: true });
      break;
      
    default:
      sendResponse({ error: "Unknown message type" });
  }
  
  return true; // Асинхронный ответ
});

/**
 * Начать запись
 */
async function startRecording(sendResponse) {
  if (isRecording) {
    sendResponse({ error: "Already recording" });
    return;
  }
  
  try {
    clickLog = [];
    recordedChunks = [];
    audioChunks = [];
    recordingStartTime = Date.now();
    
    // Запрашиваем разрешения на захват
    const desktopStreamId = await chrome.desktopCapture.chooseDesktopMedia(
      ["screen", "window"],
      { tabs: true }  // Показываем только вкладки
    );
    
    if (!desktopStreamId || desktopStreamId === "") {
      throw new Error("User cancelled screen capture");
    }
    
    streamIds.desktop = desktopStreamId;
    
    // Создаём потоки
    const desktopStream = await navigator.mediaDevices.getUserMedia({
      video: {
        mandatory: {
          chromeMediaSource: "desktop",
          chromeMediaSourceId: desktopStreamId
        }
      },
      audio: settings.captureAudio ? {
        mandatory: {
          chromeMediaSource: "desktop"
        }
      } : false
    });
    
    // Захват микрофона если нужен
    let micStream = null;
    if (settings.captureMicrophone) {
      micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    }
    
    // Смешиваем аудио (десктоп + микрофон)
    let finalStream = desktopStream;
    
    if (micStream && settings.captureAudio) {
      const audioContext = new AudioContext();
      const dest = audioContext.createMediaStreamDestination();
      
      const desktopAudio = audioContext.createMediaStreamSource(desktopStream);
      const micAudio = audioContext.createMediaStreamSource(micStream);
      
      desktopAudio.connect(dest);
      micAudio.connect(dest);
      
      // Создаём новый поток с видео + миксаное аудио
      const videoTrack = desktopStream.getVideoTracks()[0];
      finalStream = new MediaStream([videoTrack, ...dest.stream.getAudioTracks()]);
    }
    
    // Настраиваем MediaRecorder для видео
    mediaRecorder = new MediaRecorder(finalStream, {
      mimeType: "video/webm;codecs=vp9"
    });
    
    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        recordedChunks.push(event.data);
      }
    };
    
    mediaRecorder.onstop = async () => {
      // Останавливаем все треки
      finalStream.getTracks().forEach(track => track.stop());
      if (micStream) micStream.getTracks().forEach(track => track.stop());
      
      // Генерируем файлы
      await finalizeRecording();
    };
    
    // Отдельный рекордер для аудио (если нужно)
    if (micStream && !settings.captureAudio) {
      // Записываем только микрофон отдельно
      audioRecorder = new MediaRecorder(micStream);
      
      audioRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunks.push(event.data);
        }
      };
      
      audioRecorder.start(1000); // Записываем по частям
    }
    
    // Начинаем запись
    mediaRecorder.start(1000);
    isRecording = true;
    
    // Отправляем уведомление
    chrome.notifications.create({
      type: "basic",
      iconUrl: "icons/icon128.png",
      title: "AutoDoc AI Recorder",
      message: "Запись началась. Кликайте по интерфейсу!"
    });
    
    sendResponse({ success: true, recordingId: Date.now() });
    
  } catch (error) {
    console.error("Recording failed:", error);
    sendResponse({ error: error.message });
  }
}

/**
 * Остановить запись
 */
async function stopRecording(sendResponse) {
  if (!isRecording) {
    sendResponse({ error: "Not recording" });
    return;
  }
  
  try {
    // Останавливаем рекордеры
    mediaRecorder.stop();
    
    if (audioRecorder) {
      audioRecorder.stop();
    }
    
    isRecording = false;
    
    // Ждём немного чтобы данные сохранились
    setTimeout(() => {
      finalizeRecording();
    }, 1000);
    
    sendResponse({ success: true });
    
  } catch (error) {
    console.error("Stop recording failed:", error);
    sendResponse({ error: error.message });
  }
}

/**
 * Финализация записи - создание файлов и отправка на бэкенд
 */
async function finalizeRecording() {
  try {
    // Создаём blob для видео
    const videoBlob = new Blob(recordedChunks, { type: "video/webm" });
    
    // Создаём blob для аудио (если записывался отдельно)
    let audioBlob = null;
    if (audioChunks.length > 0) {
      audioBlob = new Blob(audioChunks, { type: "audio/wav" });
    } else {
      // Если аудио было в видео, извлекаем из видео
      audioBlob = await extractAudioFromVideo(videoBlob);
    }
    
    // Создаём JSON лог кликов
    const clicksLog = {
      version: "1.0",
      start_time: recordingStartTime,
      end_time: Date.now(),
      clicks: clickLog
    };
    
    const clicksBlob = new Blob([JSON.stringify(clicksLog, null, 2)], { 
      type: "application/json" 
    });
    
    // Отправляем на бэкенд
    await uploadToBackend(videoBlob, audioBlob, clicksBlob);
    
    // Очищаем память
    recordedChunks = [];
    audioChunks = [];
    clickLog = [];
    
  } catch (error) {
    console.error("Finalization failed:", error);
  }
}

/**
 * Извлечь аудио из видео (если оно было внутри)
 */
async function extractAudioFromVideo(videoBlob) {
  // Создаём URL для видео
  const videoUrl = URL.createObjectURL(videoBlob);
  
  // Используем AudioContext для извлечения
  const audioContext = new AudioContext();
  const response = await fetch(videoUrl);
  const arrayBuffer = await response.arrayBuffer();
  const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
  
  // Конвертируем в WAV
  const wavBlob = audioBufferToWav(audioBuffer);
  
  URL.revokeObjectURL(videoUrl);
  
  return wavBlob;
}

/**
 * Конвертация AudioBuffer в WAV
 */
function audioBufferToWav(buffer) {
  const numChannels = buffer.numberOfChannels;
  const sampleRate = buffer.sampleRate;
  const format = 1; // PCM
  const bitDepth = 16;
  
  const bytesPerSample = bitDepth / 8;
  const blockAlign = numChannels * bytesPerSample;
  
  const dataLength = buffer.length * blockAlign;
  const bufferLength = 44 + dataLength;
  
  const arrayBuffer = new ArrayBuffer(bufferLength);
  const view = new DataView(arrayBuffer);
  
  // WAV заголовок
  writeString(view, 0, "RIFF");
  view.setUint32(4, 36 + dataLength, true);
  writeString(view, 8, "WAVE");
  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, format, true);
  view.setUint16(22, numChannels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * blockAlign, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, bitDepth, true);
  writeString(view, 36, "data");
  view.setUint32(40, dataLength, true);
  
  // Данные
  const channels = [];
  for (let i = 0; i < numChannels; i++) {
    channels.push(buffer.getChannelData(i));
  }
  
  let offset = 44;
  for (let i = 0; i < buffer.length; i++) {
    for (let channel = 0; channel < numChannels; channel++) {
      const sample = Math.max(-1, Math.min(1, channels[channel][i]));
      view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7FFF, true);
      offset += 2;
    }
  }
  
  return new Blob([arrayBuffer], { type: "audio/wav" });
}

function writeString(view, offset, string) {
  for (let i = 0; i < string.length; i++) {
    view.setUint8(offset + i, string.charCodeAt(i));
  }
}

/**
 * Логирование клика
 */
function logClick(data) {
  const timestamp = (Date.now() - recordingStartTime) / 1000;
  
  clickLog.push({
    timestamp: timestamp,
    x: data.x,
    y: data.y,
    element: data.element || null,
    page_url: data.url
  });
}

/**
 * Отправка файлов на бэкенд
 */
async function uploadToBackend(videoBlob, audioBlob, clicksBlob) {
  try {
    const formData = new FormData();
    formData.append("video", videoBlob, "recording.webm");
    formData.append("audio", audioBlob, "audio.wav");
    formData.append("clicks_log", clicksBlob, "clicks.json");
    
    const response = await fetch(settings.apiEndpoint, {
      method: "POST",
      body: formData
    });
    
    if (response.ok) {
      const result = await response.json();
      
      chrome.notifications.create({
        type: "basic",
        iconUrl: "icons/icon128.png",
        title: "AutoDoc AI",
        message: `Гайд создан! ID: ${result.session_id}`
      });
      
      // Открываем страницу редактирования
      chrome.tabs.create({
        url: `http://localhost:8000/guides/${result.session_id}`
      });
    } else {
      throw new Error(`Upload failed: ${response.status}`);
    }
    
  } catch (error) {
    console.error("Upload failed:", error);
    
    chrome.notifications.create({
      type: "basic",
      iconUrl: "icons/icon128.png",
      title: "AutoDoc AI - Ошибка",
      message: "Не удалось загрузить запись: " + error.message
    });
  }
}

/**
 * Обновление настроек
 */
function updateSettings(newSettings) {
  settings = { ...settings, ...newSettings };
  chrome.storage.local.set({ autodoc_settings: settings });
}
