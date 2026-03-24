# Проблема закрытия popup во время записи

## 🚨 Критическая проблема

**Что происходит:**
Если пользователь закроет popup во время записи - MediaRecorder остановится и запись потеряется.

**Почему:**
- MediaRecorder работает в контексте popup
- Когда popup закрывается - весь JavaScript останавливается
- Записанные данные теряются

---

## ✅ Решения (3 варианта)

### Решение 1: Предупреждение (для MVP) ⭐ РЕКОМЕНДУЕТСЯ

**Сложность:** Низкая  
**Эффективность:** Средняя  
**Требования:** Нет

```javascript
// В popup.js

// 1. Обработчик закрытия окна
window.addEventListener('beforeunload', (event) => {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    event.preventDefault();
    event.returnValue = '';
    
    const confirmed = confirm(
      'Запись еще идет! Если закроете окно - запись остановится.\n\n' +
      'Остановить запись сейчас?'
    );
    
    if (confirmed) {
      stopVideoRecording();
    }
    
    return false;
  }
});

// 2. UI предупреждение
function showRecordingWarning() {
  const warning = document.createElement('div');
  warning.id = 'recording-warning';
  warning.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    background: #ff9800;
    color: white;
    padding: 10px;
    text-align: center;
    font-weight: bold;
    z-index: 9999;
  `;
  warning.innerHTML = `
    ⚠️ Не закрывайте это окно во время записи!
    <br>
    <small>Запись остановится если закроете popup</small>
  `;
  document.body.insertBefore(warning, document.body.firstChild);
}

// 3. Убрать предупреждение после остановки
function hideRecordingWarning() {
  const warning = document.getElementById('recording-warning');
  if (warning) {
    warning.remove();
  }
}

// Использование
startBtn.addEventListener('click', async () => {
  await startVideoRecording();
  showRecordingWarning();
});

stopBtn.addEventListener('click', async () => {
  await stopVideoRecording();
  hideRecordingWarning();
});
```

**Плюсы:**
- ✅ Просто реализовать
- ✅ Работает во всех версиях Chrome
- ✅ Не требует дополнительных разрешений

**Минусы:**
- ❌ Пользователь может проигнорировать предупреждение
- ❌ Запись все равно остановится если закрыть

---

### Решение 2: Offscreen API (для версии 2.0)

**Сложность:** Высокая  
**Эффективность:** Высокая  
**Требования:** Chrome 109+

```javascript
// В manifest.json
{
  "manifest_version": 3,
  "permissions": ["offscreen"],
  "minimum_chrome_version": "109"
}

// В background.js
async function startRecordingInOffscreen() {
  // Создаем offscreen document
  await chrome.offscreen.createDocument({
    url: 'offscreen.html',
    reasons: ['USER_MEDIA'],
    justification: 'Recording screen and audio for guide creation'
  });
  
  // Отправляем команду начать запись
  chrome.runtime.sendMessage({ 
    type: 'START_OFFSCREEN_RECORDING',
    sessionName: 'My Guide'
  });
}

async function stopRecordingInOffscreen() {
  // Отправляем команду остановить
  const result = await chrome.runtime.sendMessage({ 
    type: 'STOP_OFFSCREEN_RECORDING' 
  });
  
  // Получаем записанное видео
  const videoBlob = result.videoBlob;
  
  // Закрываем offscreen document
  await chrome.offscreen.closeDocument();
  
  return videoBlob;
}

// В offscreen.html
<!DOCTYPE html>
<html>
<head>
  <title>Recording Offscreen</title>
</head>
<body>
  <script src="offscreen.js"></script>
</body>
</html>

// В offscreen.js
let mediaRecorder = null;
let recordedChunks = [];

chrome.runtime.onMessage.addListener(async (message, sender, sendResponse) => {
  if (message.type === 'START_OFFSCREEN_RECORDING') {
    // MediaRecorder работает здесь, даже если popup закрыт!
    const displayStream = await navigator.mediaDevices.getDisplayMedia({
      video: true,
      audio: true
    });
    
    const micStream = await navigator.mediaDevices.getUserMedia({
      audio: true
    });
    
    const combinedStream = new MediaStream([
      ...displayStream.getVideoTracks(),
      ...displayStream.getAudioTracks(),
      ...micStream.getAudioTracks()
    ]);
    
    mediaRecorder = new MediaRecorder(combinedStream, {
      mimeType: 'video/webm;codecs=vp9,opus'
    });
    
    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        recordedChunks.push(event.data);
      }
    };
    
    mediaRecorder.start(1000);
    sendResponse({ success: true });
  }
  
  if (message.type === 'STOP_OFFSCREEN_RECORDING') {
    mediaRecorder.stop();
    
    mediaRecorder.onstop = () => {
      const videoBlob = new Blob(recordedChunks, { 
        type: 'video/webm;codecs=vp9,opus' 
      });
      
      // Отправляем blob обратно
      sendResponse({ videoBlob });
    };
  }
  
  return true; // Асинхронный ответ
});
```

**Плюсы:**
- ✅ Запись продолжается даже если popup закрыт
- ✅ Пользователь может свободно работать
- ✅ Надежно

**Минусы:**
- ❌ Требует Chrome 109+
- ❌ Сложнее реализовать
- ❌ Нужно передавать Blob между контекстами

---

### Решение 3: Минимизация popup

**Сложность:** Низкая  
**Эффективность:** Низкая  
**Требования:** Нет

```javascript
// В popup.js
function minimizePopup() {
  // Делаем popup маленьким
  window.resizeTo(300, 100);
  
  // Показываем только таймер
  document.body.innerHTML = `
    <div style="padding: 20px; text-align: center;">
      <div style="font-size: 24px; font-weight: bold;">
        🔴 <span id="timer">00:00</span>
      </div>
      <button id="stopBtn">Остановить</button>
    </div>
  `;
  
  // Обновляем таймер
  startTimer();
}

function startTimer() {
  const startTime = Date.now();
  
  setInterval(() => {
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    const minutes = Math.floor(elapsed / 60);
    const seconds = elapsed % 60;
    
    document.getElementById('timer').textContent = 
      `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  }, 1000);
}

// Использование
startBtn.addEventListener('click', async () => {
  await startVideoRecording();
  minimizePopup();
});
```

**Плюсы:**
- ✅ Просто реализовать
- ✅ Пользователь видит что идет запись
- ✅ Меньше шансов случайно закрыть

**Минусы:**
- ❌ Окно все равно можно закрыть
- ❌ Занимает место на экране

---

## 📊 Сравнение решений

| Критерий | Решение 1 (Предупреждение) | Решение 2 (Offscreen) | Решение 3 (Минимизация) |
|----------|---------------------------|----------------------|------------------------|
| Сложность | ⭐ Низкая | ⭐⭐⭐ Высокая | ⭐ Низкая |
| Эффективность | ⭐⭐ Средняя | ⭐⭐⭐ Высокая | ⭐ Низкая |
| Требования | Нет | Chrome 109+ | Нет |
| Надежность | ⭐⭐ Средняя | ⭐⭐⭐ Высокая | ⭐ Низкая |
| Время реализации | 30 минут | 3-4 часа | 1 час |

---

## 🎯 Рекомендация

### Для MVP (версия 1.0):
**Используйте Решение 1 (Предупреждение)**

Причины:
- Быстро реализовать
- Работает везде
- Достаточно для начала

### Для версии 2.0:
**Добавьте Решение 2 (Offscreen API)**

Причины:
- Профессиональное решение
- Как в Loom/Guidde
- Лучший UX

### Комбинированный подход:
```javascript
// Проверяем поддержку Offscreen API
if (chrome.offscreen) {
  // Chrome 109+ - используем Offscreen
  await startRecordingInOffscreen();
} else {
  // Старые версии - используем popup с предупреждением
  await startVideoRecording();
  showRecordingWarning();
}
```

---

## 📝 Чеклист реализации

### Для MVP (Решение 1):
- [ ] Добавить `beforeunload` обработчик
- [ ] Создать UI предупреждение
- [ ] Показать предупреждение при старте записи
- [ ] Убрать предупреждение при остановке
- [ ] Протестировать закрытие popup
- [ ] Протестировать confirm dialog

### Для версии 2.0 (Решение 2):
- [ ] Добавить `offscreen` permission в manifest
- [ ] Создать `offscreen.html`
- [ ] Создать `offscreen.js`
- [ ] Реализовать передачу Blob
- [ ] Добавить fallback для старых версий
- [ ] Протестировать на Chrome 109+
- [ ] Протестировать на Chrome 108 и ниже

---

## 🧪 Тестирование

### Тест 1: Предупреждение работает
```javascript
// 1. Начать запись
// 2. Попытаться закрыть popup
// 3. Должен появиться confirm dialog
// 4. Нажать "Отмена"
// 5. Popup не закрывается
```

### Тест 2: Остановка через confirm
```javascript
// 1. Начать запись
// 2. Попытаться закрыть popup
// 3. Нажать "OK" в confirm
// 4. Запись останавливается
// 5. Видео загружается на сервер
```

### Тест 3: UI предупреждение видно
```javascript
// 1. Начать запись
// 2. Проверить что оранжевое предупреждение видно
// 3. Остановить запись
// 4. Предупреждение исчезает
```

---

## 💡 Дополнительные улучшения

### 1. Иконка в системном трее (будущее)
```javascript
// Chrome не поддерживает, но можно показать notification
chrome.notifications.create({
  type: 'basic',
  iconUrl: 'icon.png',
  title: 'Идет запись',
  message: 'Не закрывайте расширение',
  requireInteraction: true
});
```

### 2. Сохранение в IndexedDB при закрытии
```javascript
// Сохранить chunks перед закрытием
window.addEventListener('beforeunload', async () => {
  if (recordedChunks.length > 0) {
    await saveToIndexedDB(recordedChunks);
  }
});

// Восстановить при следующем открытии
window.addEventListener('load', async () => {
  const saved = await loadFromIndexedDB();
  if (saved) {
    // Предложить продолжить загрузку
  }
});
```

### 3. Периодическая загрузка chunks
```javascript
// Загружать chunks каждые 10 секунд
setInterval(async () => {
  if (recordedChunks.length > 0) {
    await uploadChunks(recordedChunks);
    recordedChunks = [];
  }
}, 10000);
```

---

## 📚 Ссылки

- [Chrome Offscreen API](https://developer.chrome.com/docs/extensions/reference/offscreen/)
- [MediaRecorder API](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder)
- [beforeunload event](https://developer.mozilla.org/en-US/docs/Web/API/Window/beforeunload_event)
- [Loom Extension Architecture](https://www.loom.com/blog/how-loom-works)
