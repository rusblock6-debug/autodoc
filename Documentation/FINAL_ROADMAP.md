# ФИНАЛЬНАЯ ДОРОЖНАЯ КАРТА: Guidde-подобная архитектура

## ⚠️ ВАЖНЫЕ ИСПРАВЛЕНИЯ (обновлено)

### Исправление 1: MediaRecorder в popup.js, НЕ в background.js
**Проблема:** Service workers не имеют доступа к `navigator.mediaDevices`  
**Решение:** MediaRecorder работает в `popup.js`, где есть доступ к DOM

### Исправление 2: Один MediaRecorder вместо двух
**Проблема:** Два MediaRecorder создают проблемы синхронизации  
**Решение:** Один MediaRecorder с `mimeType: 'video/webm;codecs=vp9,opus'` (поддерживает аудио)

### Исправление 3: Настройка URL сервера
**Проблема:** Нет возможности работать с удаленным сервером  
**Решение:** UI для ввода URL + сохранение в `chrome.storage.local`

### Исправление 4: Обработка закрытия popup
**Проблема:** Если пользователь закроет popup - запись остановится  
**Решение:** 
- Добавить `beforeunload` обработчик с предупреждением
- Показать UI предупреждение "Не закрывайте окно"
- Опционально: Offscreen API для Chrome 109+ (версия 2.0)

---

## КРИТИЧЕСКИ ВАЖНО: Правильное понимание

### ❌ ЧТО МЫ НЕ ДЕЛАЕМ:
- Генерация видео из скриншотов через AI (Stable Video Diffusion)
- Требует A100 GPU, очень сложно, нестабильно

### ✅ ЧТО МЫ ДЕЛАЕМ (как Guidde):
1. **Расширение записывает video.webm** (MediaRecorder API)
2. **AI анализирует контент:**
   - Whisper транскрибирует речь → текст с таймкодами
   - LLM генерирует описания из речи
   - TTS создает озвучку из отредактированного текста
3. **FFmpeg обрабатывает видео:**
   - Нарезает video.webm по кликам
   - Добавляет маркеры на видео
   - Склеивает сегменты
   - Накладывает TTS аудио

### Разделение ответственности:
```
AI (понимание):          FFmpeg (обработка):
├─ Whisper (речь→текст)  ├─ Нарезка видео по таймкодам
├─ LLM (генерация)       ├─ Извлечение кадров
└─ TTS (озвучка)         ├─ Добавление маркеров
                         ├─ Склейка сегментов
                         └─ Конвертация форматов
```

---

## ТЕКУЩЕЕ СОСТОЯНИЕ

### Что РАБОТАЕТ:
- ✅ Расширение логирует клики + делает скриншоты
- ✅ Backend обрабатывает клики
- ✅ Пользователь редактирует текстовый гайд
- ✅ FFmpeg извлекает кадры

### Что НЕ РАБОТАЕТ:
- ❌ Расширение НЕ записывает видео (только скриншоты)
- ❌ Нет AI транскрибации речи
- ❌ Нет AI генерации описаний
- ❌ Shorts генерация сломана (пытается склеить скриншоты)

---

## ИТЕРАЦИЯ 1: Запись видео в расширении (3-4 часа)

### Цель
Добавить запись video.webm (с аудио) как в Loom/Guidde.

### Файлы для изменения
- `extension/popup.js` - добавить MediaRecorder API (НЕ background.js!)
- `extension/popup.html` - добавить настройку URL сервера
- `extension/background.js` - только хранение состояния и upload

### Задачи

**1.1. Добавить настройку URL сервера**

В `extension/popup.html` добавить:

```html
<!-- Настройки сервера -->
<div class="settings-section">
  <label for="serverUrl">URL сервера:</label>
  <input 
    type="text" 
    id="serverUrl" 
    placeholder="http://localhost:8888"
    value="http://localhost:8888"
  />
  <button id="saveSettings">Сохранить</button>
</div>
```

В `extension/popup.js` добавить:

```javascript
// Загрузка настроек при открытии popup
document.addEventListener('DOMContentLoaded', async () => {
  const settings = await chrome.storage.local.get(['serverUrl']);
  const serverUrl = settings.serverUrl || 'http://localhost:8888';
  document.getElementById('serverUrl').value = serverUrl;
});

// Сохранение настроек
document.getElementById('saveSettings').addEventListener('click', async () => {
  const serverUrl = document.getElementById('serverUrl').value;
  await chrome.storage.local.set({ serverUrl });
  alert('Настройки сохранены!');
});
```

**1.2. Добавить MediaRecorder API в popup.js**

⚠️ **ВАЖНО:** MediaRecorder должен быть в `popup.js`, НЕ в `background.js`!

Причины:
- `background.js` - service worker, может быть неактивен
- Service workers не имеют доступа к `navigator.mediaDevices`
- `popup.js` имеет доступ к DOM и user interaction

⚠️ **ПРОБЛЕМА:** Если пользователь закроет popup - запись остановится!

**Решение:** Использовать Chrome Offscreen API (Chrome 109+) или держать popup открытым.

В `extension/popup.js` добавить:

```javascript
// Состояние записи видео
let mediaRecorder = null;
let recordedChunks = [];

async function startVideoRecording() {
  try {
    // Захват экрана + микрофон в ОДНОМ stream
    const displayStream = await navigator.mediaDevices.getDisplayMedia({
      video: {
        mediaSource: 'screen',
        width: { ideal: 1920 },
        height: { ideal: 1080 },
        frameRate: { ideal: 30 }
      },
      audio: true  // ← Захватываем аудио системы
    });
    
    // Захват микрофона
    const micStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        sampleRate: 44100
      }
    });
    
    // Объединяем видео + аудио системы + микрофон
    const combinedStream = new MediaStream([
      ...displayStream.getVideoTracks(),
      ...displayStream.getAudioTracks(),  // Аудио системы
      ...micStream.getAudioTracks()       // Микрофон
    ]);
    
    // ОДИН MediaRecorder для всего (видео + аудио)
    mediaRecorder = new MediaRecorder(combinedStream, {
      mimeType: 'video/webm;codecs=vp9,opus',  // ← Поддерживает audio!
      videoBitsPerSecond: 2500000
    });
    
    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        recordedChunks.push(event.data);
      }
    };
    
    // ⚠️ ВАЖНО: Обработка закрытия popup
    window.addEventListener('beforeunload', handlePopupClose);
    
    mediaRecorder.start(1000);  // Сохраняем каждую секунду
    
    console.log('[Video] Recording started');
    
    // Отправляем сообщение в background для начала логирования кликов
    chrome.runtime.sendMessage({
      type: 'START_RECORDING',
      sessionName: document.getElementById('sessionName').value
    });
    
    // Показываем предупреждение
    showWarning('⚠️ Не закрывайте это окно во время записи!');
    
  } catch (error) {
    console.error('[Video] Failed:', error);
    alert('Ошибка записи: ' + error.message);
    throw error;
  }
}

// ⚠️ КРИТИЧЕСКИ ВАЖНО: Обработка закрытия popup
function handlePopupClose(event) {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    // Пользователь пытается закрыть popup во время записи
    event.preventDefault();
    event.returnValue = '';
    
    // Показываем предупреждение
    const confirmed = confirm(
      'Запись еще идет! Если закроете окно - запись остановится.\n\n' +
      'Остановить запись сейчас?'
    );
    
    if (confirmed) {
      stopVideoRecording();
    }
    
    return false;
  }
}

async function stopVideoRecording() {
  return new Promise((resolve) => {
    if (!mediaRecorder) {
      resolve(null);
      return;
    }
    
    mediaRecorder.onstop = () => {
      // Создаем ОДИН blob с видео + аудио
      const videoBlob = new Blob(recordedChunks, { 
        type: 'video/webm;codecs=vp9,opus' 
      });
      recordedChunks = [];
      
      // Останавливаем все треки
      mediaRecorder.stream.getTracks().forEach(t => t.stop());
      
      // Убираем обработчик закрытия
      window.removeEventListener('beforeunload', handlePopupClose);
      
      resolve(videoBlob);
    };
    
    mediaRecorder.stop();
  });
}

function showWarning(message) {
  const warningDiv = document.createElement('div');
  warningDiv.style.cssText = `
    position: fixed;
    top: 10px;
    left: 10px;
    right: 10px;
    background: #ff9800;
    color: white;
    padding: 10px;
    border-radius: 5px;
    font-weight: bold;
    z-index: 9999;
  `;
  warningDiv.textContent = message;
  document.body.appendChild(warningDiv);
}
```

**Альтернативное решение (Chrome 109+): Offscreen API**

Если нужно чтобы запись продолжалась после закрытия popup, используйте Offscreen API:

```javascript
// В background.js
async function startRecordingInOffscreen() {
  // Создаем offscreen document для записи
  await chrome.offscreen.createDocument({
    url: 'offscreen.html',
    reasons: ['USER_MEDIA'],
    justification: 'Recording screen and audio'
  });
  
  // Отправляем команду начать запись
  chrome.runtime.sendMessage({ type: 'START_OFFSCREEN_RECORDING' });
}

// В offscreen.js (новый файл)
chrome.runtime.onMessage.addListener(async (message) => {
  if (message.type === 'START_OFFSCREEN_RECORDING') {
    // MediaRecorder работает здесь, даже если popup закрыт
    const stream = await navigator.mediaDevices.getDisplayMedia({...});
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.start();
  }
});
```

**Рекомендация:** Для MVP используйте первый вариант (с предупреждением). Offscreen API добавьте позже если нужно.

**1.3. Обновить UI в popup.js**

Добавить кнопки и статус:

```javascript
// UI элементы
const startBtn = document.getElementById('startRecording');
const stopBtn = document.getElementById('stopRecording');
const statusDiv = document.getElementById('status');

// Начать запись
startBtn.addEventListener('click', async () => {
  try {
    await startVideoRecording();
    
    startBtn.disabled = true;
    stopBtn.disabled = false;
    statusDiv.textContent = '🔴 Идет запись...';
    
  } catch (error) {
    statusDiv.textContent = '❌ Ошибка: ' + error.message;
  }
});

// Остановить запись
stopBtn.addEventListener('click', async () => {
  try {
    statusDiv.textContent = '⏳ Остановка записи...';
    
    // Останавливаем видео
    const videoBlob = await stopVideoRecording();
    
    // Останавливаем логирование кликов в background
    const response = await chrome.runtime.sendMessage({
      type: 'STOP_RECORDING',
      sessionName: document.getElementById('sessionName').value
    });
    
    // Получаем клики и скриншоты из background
    const { clickLog, screenshots } = response;
    
    // Загружаем на сервер
    statusDiv.textContent = '⏳ Загрузка на сервер...';
    await uploadToServer(videoBlob, clickLog, screenshots);
    
    statusDiv.textContent = '✅ Готово!';
    startBtn.disabled = false;
    stopBtn.disabled = true;
    
  } catch (error) {
    statusDiv.textContent = '❌ Ошибка: ' + error.message;
  }
});
```

**1.4. Добавить функцию загрузки на сервер**

В `extension/popup.js`:

```javascript
async function uploadToServer(videoBlob, clickLog, screenshots) {
  // Получаем URL сервера из настроек
  const settings = await chrome.storage.local.get(['serverUrl']);
  const serverUrl = settings.serverUrl || 'http://localhost:8888';
  
  const formData = new FormData();
  
  // Добавляем видео (ОДНО с аудио внутри)
  if (videoBlob) {
    formData.append('video', videoBlob, 'recording.webm');
  }
  
  // Добавляем клики
  const clicksJson = JSON.stringify({
    version: '1.0',
    session_name: document.getElementById('sessionName').value,
    clicks: clickLog
  });
  formData.append('clicks_log', new Blob([clicksJson], { type: 'application/json' }), 'clicks.json');
  
  // Добавляем скриншоты (для превью)
  for (let i = 0; i < screenshots.length; i++) {
    if (screenshots[i]) {
      const response = await fetch(screenshots[i]);
      const blob = await response.blob();
      formData.append('screenshots', blob, `screenshot_${i}.png`);
    }
  }
  
  // Отправляем на сервер
  const response = await fetch(`${serverUrl}/api/v1/sessions/upload`, {
    method: 'POST',
    body: formData
  });
  
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  
  const result = await response.json();
  
  // Открываем редактор
  if (result.guide_id) {
    chrome.tabs.create({ 
      url: `${serverUrl.replace(':8888', ':3000')}/guide/${result.guide_id}/edit` 
    });
  }
  
  return result;
}
```

**1.5. Обновить background.js (только хранение состояния)**

В `extension/background.js` изменить:

```javascript
// background.js теперь ТОЛЬКО хранит состояние и логирует клики
// MediaRecorder НЕ здесь!

let recordingState = {
  isRecording: false,
  startTime: null,
  sessionName: '',
  clickLog: [],
  screenshots: []
};

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  switch (message.type) {
    case 'START_RECORDING':
      recordingState.isRecording = true;
      recordingState.startTime = Date.now();
      recordingState.sessionName = message.sessionName;
      recordingState.clickLog = [];
      recordingState.screenshots = [];
      
      // Инжектим content script для логирования кликов
      injectContentScriptToAllTabs();
      
      sendResponse({ success: true });
      break;
      
    case 'STOP_RECORDING':
      recordingState.isRecording = false;
      
      // Останавливаем логирование кликов
      stopRecordingInAllTabs();
      
      // Возвращаем данные в popup
      sendResponse({
        clickLog: recordingState.clickLog,
        screenshots: recordingState.screenshots
      });
      break;
      
    case 'CLICK_LOG':
      // Логируем клик (как раньше)
      handleClickLog(message.data, sender);
      sendResponse({ success: true });
      break;
  }
  
  return true;
});

// ... остальные функции как раньше ...
```

### Критерии завершения
- ✅ Расширение записывает video.webm (с аудио внутри)
- ✅ MediaRecorder работает в popup.js (НЕ в background.js)
- ✅ Есть настройка URL сервера в UI
- ✅ URL сервера сохраняется в chrome.storage
- ✅ Видео загружается на настроенный сервер
- ✅ Клики и скриншоты работают как раньше
- ✅ Добавлен обработчик `beforeunload` для предупреждения
- ✅ Показывается UI предупреждение "Не закрывайте окно"

### Почему именно так:

**1. MediaRecorder в popup.js, а не в background.js:**
- `background.js` - service worker, может быть неактивен
- Service workers не имеют доступа к `navigator.mediaDevices`
- `popup.js` имеет доступ к DOM и user interaction

**2. Один MediaRecorder вместо двух:**
- Нет проблем синхронизации видео и аудио
- Проще код
- Меньше ошибок
- `mimeType: 'video/webm;codecs=vp9,opus'` поддерживает аудио

**3. Настройка URL сервера:**
- Пользователь может работать с удаленным сервером
- Сохраняется в `chrome.storage.local`
- Используется при загрузке

**4. Обработка закрытия popup:**
- `beforeunload` предупреждает пользователя
- UI предупреждение видно постоянно
- Для версии 2.0: Offscreen API (Chrome 109+)

---

## ИТЕРАЦИЯ 2: AI обработка (Whisper + LLM) (4-5 часов)

### Цель
Backend принимает видео, AI транскрибирует и генерирует описания.

### Файлы для изменения
- `app/api/sessions.py` - обновить upload endpoint
- `app/models.py` - добавить поля для видео
- `app/celery_tasks.py` - создать task обработки
- `app/services/ai_service.py` - улучшить AI

### Задачи

**2.1. Обновить API endpoint**

В `app/api/sessions.py` изменить `/upload`:

```python
@router.post("/upload")
async def upload_session(
    title: str = Form(...),
    clicks_log: UploadFile = File(...),
    video: UploadFile = File(None),  # ОДНО видео с аудио внутри
    screenshots: List[UploadFile] = File(None)
):
    """
    Принимает:
    - video: video.webm с аудио внутри (НЕ отдельный audio файл!)
    - clicks_log: JSON с кликами
    - screenshots: Превью для UI
    """
    
    # Сохраняем видео в MinIO
    video_key = None
    if video:
        video_key = await storage_service.upload_file(
            video.file,
            bucket="autodoc-videos",
            filename=f"session_{session_id}_video.webm"
        )
    
    # Создаем сессию
    session = Session(
        title=title,
        video_key=video_key,
        clicks_data=clicks_data,
        status="uploaded"
    )
    
    # Запускаем обработку
    process_session_task.delay(session.id)
    
    return {"session_id": session.id, "guide_id": guide.id}
```

**2.2. Обновить модели БД**

В `app/models.py` добавить:

```python
class Session(Base):
    # ... существующие поля ...
    video_key = Column(String, nullable=True)  # Видео с аудио внутри
    transcription = Column(JSON, nullable=True)

class Step(Base):
    # ... существующие поля ...
    video_segment_key = Column(String, nullable=True)
    duration_seconds = Column(Float, default=3.0)
```

**Примечание:** Не нужно отдельное поле `audio_key`, так как аудио внутри видео!

**2.3. Создать Celery task**

В `app/celery_tasks.py` добавить:

```python
@celery_app.task
def process_session_task(session_id: int):
    """
    Полная обработка:
    1. FFmpeg извлекает аудио из видео
    2. Whisper транскрибирует аудио
    3. LLM генерирует описания
    4. FFmpeg нарезает видео
    5. Создает шаги в БД
    """
    session = get_session(session_id)
    
    # 1. Скачиваем видео из MinIO
    video_path = download_from_minio(session.video_key)
    
    # 2. FFmpeg: Извлекаем аудио из видео
    audio_path = extract_audio_from_video(video_path)
    # ffmpeg -i video.webm -vn -acodec copy audio.webm
    
    # 3. AI: Транскрибация (Whisper)
    transcription = whisper_service.transcribe(audio_path)
    # Результат: {"text": "...", "segments": [...], "words": [...]}
    
    # 4. Определение шагов (клики + речь)
    steps_data = step_detector.detect_steps(
        clicks=session.clicks_data,
        transcription=transcription
    )
    
    # 5. AI: Генерация описаний (LLM)
    for step in steps_data:
        step["description"] = llm_service.generate_description(
            raw_text=step["text"],
            context=get_previous_steps(steps_data, step)
        )
    
    # 6. FFmpeg: Нарезка видео
    for i, step in enumerate(steps_data):
        # Извлекаем сегмент (с аудио!)
        segment_path = ffmpeg_extract_segment(
            video_path,
            start_time=step["timestamp"],
            duration=step.get("duration", 3.0)
        )
        
        # Извлекаем скриншот
        screenshot_path = ffmpeg_extract_frame(
            video_path,
            timestamp=step["timestamp"]
        )
        
        # Сохраняем в MinIO
        step["video_segment_key"] = upload_to_minio(segment_path)
        step["screenshot_key"] = upload_to_minio(screenshot_path)
    
    # 7. Создаем гайд и шаги
    guide = create_guide(session, steps_data)
    
    # 8. Обновляем статус
    session.status = "processed"
    session.guide_id = guide.id
    
    return {"guide_id": guide.id}


def extract_audio_from_video(video_path: str) -> str:
    """Извлекает аудио из видео (FFmpeg)"""
    audio_path = video_path.replace('.webm', '_audio.webm')
    
    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vn",  # Без видео
        "-acodec", "copy",  # Копируем аудио без перекодирования
        audio_path
    ]
    
    subprocess.run(cmd, check=True)
    return audio_path
```

**2.4. Улучшить AI сервисы**

В `app/services/ai_service.py` улучшить:

```python
def transcribe_with_word_timestamps(audio_path: str) -> dict:
    """Whisper с word-level timestamps"""
    result = whisper_model.transcribe(
        audio_path,
        word_timestamps=True,  # Точная синхронизация
        language="ru",
        task="transcribe",
        vad_filter=True  # Фильтр тишины
    )
    
    # Фильтруем мусорные слова
    filtered_words = filter_filler_words(result["words"])
    
    return {
        "text": result["text"],
        "words": filtered_words,
        "segments": result["segments"]
    }

def generate_description(raw_text: str, context: List[str]) -> str:
    """LLM с контекстом предыдущих шагов"""
    context_text = "\n".join(context[-3:])
    
    prompt = f"""
Контекст предыдущих шагов:
{context_text}

Текущая речь: "{raw_text}"

Преобразуй в четкую инструкцию.
Убери "эм", "ну", слова-паразиты.
"""
    
    return llm.generate(prompt)
```

### Критерии завершения
- ✅ Backend принимает видео и аудио
- ✅ Whisper транскрибирует речь
- ✅ LLM генерирует описания
- ✅ FFmpeg нарезает видео по кликам
- ✅ Шаги создаются с видео-сегментами

---

## ИТЕРАЦИЯ 3: Генерация Shorts (AI + FFmpeg) (3-4 часа)

### Цель
Склеить сегменты в финальное видео с маркерами и TTS.

### Файлы для изменения
- `app/services/shorts_generator.py` - переделать под реальное видео
- `app/services/video_processor.py` - добавить функции
- `app/api/shorts.py` - обновить API

### Задачи

**3.1. Переделать Shorts Generator**

В `app/services/shorts_generator.py` изменить:

```python
class ShortsGenerator:
    """Генератор Shorts из реального видео"""
    
    async def generate_from_steps(
        self,
        steps: List[Dict[str, Any]],
        guide_uuid: str,
        use_tts: bool = True
    ) -> ShortsResult:
        """
        Генерация Shorts:
        1. Для каждого шага: берем video_segment
        2. Добавляем маркер клика (FFmpeg)
        3. Заменяем аудио на TTS (опционально)
        4. Склеиваем все сегменты
        """
        segments = []
        temp_files = []
        
        for i, step in enumerate(steps):
            # 1. Скачиваем сегмент из MinIO
            segment_path = download_from_minio(step["video_segment_key"])
            
            # 2. Добавляем маркер клика
            segment_with_marker = self.add_click_marker(
                segment_path,
                click_x=step["click_x"],
                click_y=step["click_y"]
            )
            
            # 3. Генерируем TTS
            if use_tts:
                text = step.get("edited_text") or step.get("normalized_text")
                tts_result = await tts_service.generate_audio(text)
                
                # Заменяем аудио
                segment_final = self.replace_audio(
                    segment_with_marker,
                    tts_result.audio_path
                )
            else:
                segment_final = segment_with_marker
            
            segments.append(segment_final)
            temp_files.append(segment_final)
        
        # 4. Склеиваем все сегменты
        output_path = self.output_dir / f"shorts_{guide_uuid}.mp4"
        self.concatenate_segments(segments, str(output_path))
        
        return ShortsResult(
            success=True,
            output_path=str(output_path),
            duration_seconds=self._get_duration(str(output_path)),
            segments_count=len(segments)
        )
    
    def add_click_marker(self, video_path: str, click_x: int, click_y: int) -> str:
        """Добавляет желтый маркер на видео (FFmpeg)"""
        output_path = f"{video_path}_marker.mp4"
        
        cmd = [
            "ffmpeg", "-i", video_path,
            "-vf", (
                f"drawbox=x={click_x-25}:y={click_y-25}:w=50:h=50:"
                f"color=yellow:t=5:round=25"
            ),
            output_path
        ]
        
        subprocess.run(cmd)
        return output_path
    
    def replace_audio(self, video_path: str, audio_path: str) -> str:
        """Заменяет аудио в видео (FFmpeg)"""
        output_path = f"{video_path}_tts.mp4"
        
        cmd = [
            "ffmpeg",
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "copy",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            output_path
        ]
        
        subprocess.run(cmd)
        return output_path
    
    def concatenate_segments(self, segments: List[str], output_path: str):
        """Склеивает сегменты (FFmpeg)"""
        concat_list = "concat_list.txt"
        with open(concat_list, "w") as f:
            for seg in segments:
                f.write(f"file '{seg}'\n")
        
        cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list,
            "-c", "copy",
            output_path
        ]
        
        subprocess.run(cmd)
```

**3.2. Добавить API endpoint**

В `app/api/shorts.py` обновить:

```python
@router.post("/guides/{guide_id}/shorts/generate")
async def generate_shorts(
    guide_id: int,
    use_tts: bool = True,
    add_markers: bool = True
):
    """Генерирует Shorts из реального видео"""
    
    # Запускаем задачу
    task = generate_shorts_task.delay(guide_id, use_tts, add_markers)
    
    return {
        "task_id": task.id,
        "status": "processing"
    }
```

### Критерии завершения
- ✅ Shorts генерируется из реального видео
- ✅ Маркеры кликов добавляются
- ✅ TTS заменяет оригинальное аудио
- ✅ Финальное видео доступно

---

## ИТЕРАЦИЯ 4: Frontend + тестирование (2-3 часа)

### Цель
Обновить UI и протестировать весь flow.

### Файлы для изменения
- `frontend/src/pages/StepEditor.jsx` - добавить видео плеер
- `frontend/src/pages/ShortsPreview.jsx` - обновить превью

### Задачи

**4.1. Обновить StepEditor**

В `frontend/src/pages/StepEditor.jsx`:

```jsx
function StepEditor({ guideId }) {
  const [steps, setSteps] = useState([]);
  const [currentStep, setCurrentStep] = useState(0);
  
  useEffect(() => {
    api.getGuideSteps(guideId).then(setSteps);
  }, [guideId]);
  
  return (
    <div>
      {/* Видео плеер для сегмента */}
      <video 
        src={steps[currentStep]?.video_segment_url}
        controls
        autoPlay
      />
      
      {/* Описание (редактируемое) */}
      <div 
        contentEditable
        onBlur={(e) => handleTextChange(e.target.innerText)}
      >
        {steps[currentStep]?.description}
      </div>
      
      {/* Навигация */}
      <button onClick={() => setCurrentStep(prev => prev - 1)}>
        ← Предыдущий
      </button>
      <button onClick={() => setCurrentStep(prev => prev + 1)}>
        Следующий →
      </button>
      
      {/* Генерация Shorts */}
      <button onClick={() => api.generateShorts(guideId)}>
        🎬 Сгенерировать Shorts
      </button>
    </div>
  );
}
```

**4.2. Комплексное тестирование**

- [ ] End-to-end: запись → обработка → редактирование → Shorts
- [ ] Тест с разными типами контента
- [ ] Тест с длинными видео (>5 минут)
- [ ] Тест без микрофона (только видео)
- [ ] Тест fallback (если AI не работает)

### Критерии завершения
- ✅ UI показывает видео-сегменты
- ✅ Можно редактировать описания
- ✅ Shorts генерируется корректно
- ✅ Все тесты проходят

---

## РЕЗЮМЕ

| Итерация | Время | Что делаем | Критичность |
|----------|-------|------------|-------------|
| 1. Запись видео | 3-4 ч | MediaRecorder в расширении | Высокая |
| 2. AI обработка | 4-5 ч | Whisper + LLM + FFmpeg нарезка | Высокая |
| 3. Shorts | 3-4 ч | Склейка + маркеры + TTS | Высокая |
| 4. Frontend | 2-3 ч | UI + тестирование | Средняя |
| **ИТОГО** | **12-16 ч** | **1.5-2 дня** | - |

---

## АРХИТЕКТУРА: AI vs FFmpeg

### AI делает (понимание):
- ✅ Whisper: речь → текст с таймкодами
- ✅ LLM: генерация описаний из речи
- ✅ TTS: текст → озвучка

### FFmpeg делает (обработка):
- ✅ Нарезка video.webm по таймкодам
- ✅ Извлечение кадров для скриншотов
- ✅ Добавление маркеров на видео
- ✅ Замена аудио дорожки
- ✅ Склейка сегментов
- ✅ Конвертация форматов

### Почему FFmpeg незаменим:
1. **Скорость**: Нарезка 10-минутного видео = 2 секунды
2. **Стабильность**: Работает одинаково всегда
3. **Качество**: Без потери качества
4. **Простота**: Одна команда = результат

### Почему AI не может заменить FFmpeg:
1. AI не умеет нарезать видео по таймкодам
2. AI не умеет склеивать видео
3. AI не умеет добавлять маркеры
4. Генерация видео из скриншотов = требует A100 GPU

---

## СЛЕДУЮЩИЕ ШАГИ

После завершения всех итераций:

1. **Бета-тестирование** с реальными пользователями
2. **Сбор feedback** и приоритизация
3. **Оптимизация** на основе данных
4. **Документация** для пользователей

---

## КОНТРОЛЬНЫЕ ТОЧКИ

После каждой итерации:
- ✅ Код ревью
- ✅ Тестирование
- ✅ Commit в git
- ✅ Проверка что ничего не сломалось

**Правило:** Если сломалось - откатываемся!


---

## ДЕТАЛЬНЫЕ ПРИМЕРЫ КОДА

### Пример 1: FFmpeg нарезка видео по таймкодам

```python
def extract_video_segment(
    video_path: str,
    start_time: float,
    duration: float,
    output_path: str
) -> bool:
    """
    Нарезает видео по таймкоду.
    Это делает FFmpeg, НЕ AI!
    """
    cmd = [
        "ffmpeg",
        "-ss", str(start_time),  # Начало
        "-t", str(duration),     # Длительность
        "-i", video_path,
        "-c", "copy",            # Без перекодирования (быстро!)
        "-y",
        output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, timeout=30)
    return result.returncode == 0
```

**Почему FFmpeg:**
- Нарезка 10-минутного видео = 2 секунды
- Без потери качества
- Стабильно работает

**Почему НЕ AI:**
- AI не умеет нарезать видео
- Генерация видео из скриншотов = требует A100 GPU
- Нестабильно, медленно, сложно

### Пример 2: Whisper транскрибация

```python
def transcribe_audio(audio_path: str) -> dict:
    """
    AI транскрибирует речь.
    Это делает Whisper, НЕ FFmpeg!
    """
    model = whisper.load_model("medium")
    result = model.transcribe(
        audio_path,
        word_timestamps=True,  # Точные таймкоды слов
        language="ru",
        vad_filter=True        # Фильтр тишины
    )
    
    return {
        "text": result["text"],
        "segments": result["segments"],
        "words": result["words"]
    }
```

**Почему Whisper:**
- Понимает речь
- Генерирует таймкоды
- Фильтрует тишину

**Почему НЕ FFmpeg:**
- FFmpeg не понимает речь
- FFmpeg только обрабатывает файлы

### Пример 3: Полный flow

```python
def process_recording(video_path: str, audio_path: str, clicks: List[dict]):
    """
    Полный flow обработки:
    1. AI понимает что говорит пользователь
    2. FFmpeg нарезает видео по кликам
    3. AI генерирует описания
    4. FFmpeg склеивает финальное видео
    """
    
    # 1. AI: Транскрибация (Whisper)
    transcription = whisper.transcribe(audio_path)
    # Результат: {"text": "нажмите кнопку войти", "segments": [...]}
    
    # 2. Определение шагов (клики + речь)
    steps = []
    for click in clicks:
        # Находим ближайший речевой сегмент
        speech = find_nearest_speech(click["timestamp"], transcription)
        
        steps.append({
            "timestamp": click["timestamp"],
            "click_x": click["x"],
            "click_y": click["y"],
            "raw_speech": speech["text"]
        })
    
    # 3. AI: Генерация описаний (LLM)
    for step in steps:
        step["description"] = llm.generate(
            f"Преобразуй в инструкцию: {step['raw_speech']}"
        )
    # Результат: "Нажмите кнопку 'Войти'"
    
    # 4. FFmpeg: Нарезка видео
    for i, step in enumerate(steps):
        # Извлекаем сегмент видео
        segment_path = f"segment_{i}.mp4"
        ffmpeg_extract_segment(
            video_path,
            start_time=step["timestamp"],
            duration=3.0,
            output_path=segment_path
        )
        
        # Добавляем маркер клика
        segment_with_marker = f"segment_{i}_marker.mp4"
        ffmpeg_add_marker(
            segment_path,
            click_x=step["click_x"],
            click_y=step["click_y"],
            output_path=segment_with_marker
        )
        
        step["video_segment"] = segment_with_marker
    
    # 5. AI: TTS озвучка (опционально)
    for step in steps:
        tts_audio = tts.generate(step["description"])
        
        # FFmpeg: Заменяем аудио
        ffmpeg_replace_audio(
            step["video_segment"],
            tts_audio,
            output_path=f"{step['video_segment']}_tts.mp4"
        )
    
    # 6. FFmpeg: Склейка финального видео
    final_video = ffmpeg_concatenate([s["video_segment"] for s in steps])
    
    return final_video
```

---

## МИГРАЦИЯ БАЗЫ ДАННЫХ

### Создать миграцию Alembic

```bash
# Создать миграцию
alembic revision -m "add_video_audio_fields"
```

### Содержимое миграции

```python
# alembic/versions/xxx_add_video_fields.py

def upgrade():
    # Добавляем поля в Session
    op.add_column('sessions', sa.Column('video_key', sa.String(), nullable=True))
    op.add_column('sessions', sa.Column('transcription', sa.JSON(), nullable=True))
    
    # Добавляем поля в Step
    op.add_column('steps', sa.Column('video_segment_key', sa.String(), nullable=True))
    op.add_column('steps', sa.Column('duration_seconds', sa.Float(), nullable=True))

def downgrade():
    # Откат изменений
    op.drop_column('sessions', 'video_key')
    op.drop_column('sessions', 'transcription')
    op.drop_column('steps', 'video_segment_key')
    op.drop_column('steps', 'duration_seconds')
```

**Примечание:** Не нужны поля `audio_key` и `audio_segment_key`, так как аудио внутри видео!

### Применить миграцию

```bash
# Применить
alembic upgrade head

# Откатить (если нужно)
alembic downgrade -1
```

---

## ТЕСТИРОВАНИЕ

### Тест 1: Запись видео

```javascript
// Тест расширения
async function testVideoRecording() {
  // 1. Начать запись
  await chrome.runtime.sendMessage({ type: 'START_RECORDING', sessionName: 'Test' });
  
  // 2. Подождать 5 секунд
  await sleep(5000);
  
  // 3. Сделать клик
  document.querySelector('button').click();
  
  // 4. Остановить запись
  const result = await chrome.runtime.sendMessage({ type: 'STOP_RECORDING' });
  
  // 5. Проверить результат
  console.assert(result.success, 'Recording failed');
  console.assert(result.uploadResult.guide_id, 'No guide created');
}
```

### Тест 2: AI обработка

```python
# Тест backend
def test_ai_processing():
    # 1. Создать тестовую сессию
    session = Session(
        title="Test",
        video_key="test_video.webm",
        audio_key="test_audio.webm",
        clicks_data=[{"timestamp": 5.0, "x": 100, "y": 200}]
    )
    db.add(session)
    db.commit()
    
    # 2. Запустить обработку
    result = process_session_task(session.id)
    
    # 3. Проверить результат
    assert result["guide_id"] is not None
    
    guide = db.query(Guide).get(result["guide_id"])
    assert len(guide.steps) > 0
    assert guide.steps[0].video_segment_key is not None
```

### Тест 3: Shorts генерация

```python
# Тест Shorts
def test_shorts_generation():
    # 1. Создать тестовый гайд с шагами
    guide = create_test_guide_with_steps()
    
    # 2. Сгенерировать Shorts
    result = shorts_generator.generate_from_steps(
        steps=guide.steps,
        guide_uuid=guide.uuid,
        use_tts=True
    )
    
    # 3. Проверить результат
    assert result.success
    assert os.path.exists(result.output_path)
    assert result.duration_seconds > 0
```

---

## TROUBLESHOOTING

### Проблема 1: Расширение не записывает видео

**Симптомы:**
- Ошибка "getDisplayMedia is not defined"
- Видео не загружается на backend

**Решение:**
```javascript
// 1. Проверить что MediaRecorder в popup.js, НЕ в background.js
// background.js - service worker, не имеет доступа к navigator.mediaDevices

// 2. Проверить что используется HTTPS или localhost
if (location.protocol !== 'https:' && location.hostname !== 'localhost') {
  console.error('MediaRecorder requires HTTPS or localhost');
}

// 3. Проверить разрешения
const permissions = await navigator.permissions.query({ name: 'camera' });
console.log('Camera permission:', permissions.state);

// 4. Проверить что popup открыт при записи
// Если popup закрыт - MediaRecorder останавливается!
```

**Важно:** Popup должен оставаться открытым во время записи, или нужно переместить логику в offscreen document (Chrome 109+).

### Проблема 1.1: Пользователь случайно закрыл popup

**Симптомы:**
- Запись остановилась преждевременно
- Видео неполное

**Решение 1 (простой):** Добавить предупреждение
```javascript
window.addEventListener('beforeunload', (event) => {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    event.preventDefault();
    event.returnValue = '';
    return 'Запись еще идет! Остановить?';
  }
});
```

**Решение 2 (продвинутый):** Использовать Offscreen API
```javascript
// В manifest.json добавить
{
  "permissions": ["offscreen"],
  "minimum_chrome_version": "109"
}

// В background.js
await chrome.offscreen.createDocument({
  url: 'offscreen.html',
  reasons: ['USER_MEDIA'],
  justification: 'Recording screen'
});

// Теперь запись продолжается даже если popup закрыт
```

**Решение 3 (UI):** Показать предупреждение в popup
```javascript
function showWarning() {
  const warning = document.createElement('div');
  warning.style.cssText = 'background: #ff9800; padding: 10px; color: white;';
  warning.textContent = '⚠️ Не закрывайте это окно во время записи!';
  document.body.insertBefore(warning, document.body.firstChild);
}
```

### Проблема 2: Whisper не транскрибирует

**Симптомы:**
- Ошибка "CUDA out of memory"
- Транскрибация очень медленная

**Решение:**
```python
# Использовать меньшую модель
model = whisper.load_model("base")  # Вместо "medium"

# Или использовать CPU
model = whisper.load_model("medium", device="cpu")

# Или использовать OpenRouter API
transcription = openrouter_whisper(audio_path)
```

### Проблема 3: Не работает загрузка на удаленный сервер

**Симптомы:**
- Ошибка "Failed to fetch"
- CORS ошибки

**Решение:**
```javascript
// 1. Проверить что URL сервера правильный
const settings = await chrome.storage.local.get(['serverUrl']);
console.log('Server URL:', settings.serverUrl);

// 2. Проверить CORS на сервере
// В app/main.py должно быть:
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Или конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

// 3. Проверить что сервер доступен
fetch(`${serverUrl}/health`)
  .then(r => console.log('Server OK'))
  .catch(e => console.error('Server not accessible:', e));
```

### Проблема 4: FFmpeg не нарезает видео

**Симптомы:**
- Ошибка "Invalid data found when processing input"
- Сегменты пустые

**Решение:**
```python
# Проверить формат видео
info = ffprobe(video_path)
print(info["format"]["format_name"])  # Должно быть "webm" или "matroska"

# Конвертировать если нужно
if info["format"]["format_name"] != "webm":
    converted = convert_to_webm(video_path)
    video_path = converted
```

### Проблема 4: FFmpeg не нарезает видео

**Симптомы:**
- Ошибка "Invalid data found when processing input"
- Сегменты пустые

**Решение:**
```python
# Проверить формат видео
info = ffprobe(video_path)
print(info["format"]["format_name"])  # Должно быть "webm" или "matroska"

# Конвертировать если нужно
if info["format"]["format_name"] != "webm":
    converted = convert_to_webm(video_path)
    video_path = converted

# Проверить что аудио внутри видео
streams = info["streams"]
has_video = any(s["codec_type"] == "video" for s in streams)
has_audio = any(s["codec_type"] == "audio" for s in streams)
print(f"Video: {has_video}, Audio: {has_audio}")
```

### Проблема 5: Shorts не генерируется

**Симптомы:**
- Ошибка "No such file or directory"
- Финальное видео пустое

**Решение:**
```python
# Проверить что все сегменты существуют
for step in steps:
    segment_path = download_from_minio(step.video_segment_key)
    assert os.path.exists(segment_path), f"Missing segment: {segment_path}"

# Проверить concat list
with open("concat_list.txt", "r") as f:
    print(f.read())  # Все пути должны существовать
```

---

## FAQ

### Q: Что если пользователь закроет popup во время записи?

**A:** Есть 3 решения:

**1. Простое (для MVP):** Предупреждение
```javascript
window.addEventListener('beforeunload', (event) => {
  if (isRecording) {
    event.preventDefault();
    return 'Запись еще идет!';
  }
});
```
Плюсы: Просто реализовать  
Минусы: Пользователь может случайно закрыть

**2. Продвинутое (Chrome 109+):** Offscreen API
```javascript
// Запись продолжается в offscreen document
await chrome.offscreen.createDocument({
  url: 'offscreen.html',
  reasons: ['USER_MEDIA']
});
```
Плюсы: Запись не прерывается  
Минусы: Требует Chrome 109+, сложнее

**3. UI решение:** Минимизировать popup
```javascript
// Показать маленькое окно с таймером
window.resizeTo(300, 100);
```
Плюсы: Пользователь видит что идет запись  
Минусы: Окно все равно можно закрыть

**Рекомендация:** Для MVP используйте решение 1 + UI предупреждение. Offscreen API добавьте в версии 2.0.

### Q: Зачем нужен FFmpeg если есть AI?

**A:** AI и FFmpeg решают разные задачи:
- **AI понимает** контент (речь, текст, смысл)
- **FFmpeg обрабатывает** файлы (нарезка, склейка, конвертация)

AI не может нарезать видео по таймкодам. Это делает FFmpeg за 2 секунды.

### Q: Можно ли использовать только AI без FFmpeg?

**A:** Нет. Генерация видео из скриншотов через AI:
- Требует A100 GPU (очень дорого)
- Нестабильно (качество плавает)
- Медленно (10 минут на 1 минуту видео)
- Сложно (нужна оркестрация моделей)

FFmpeg делает это за 2 секунды стабильно.

### Q: Что если у пользователя нет GPU?

**A:** Есть fallback:
1. Whisper → OpenRouter API (бесплатно)
2. LLM → OpenRouter API (бесплатно)
3. TTS → Edge TTS (бесплатно)
4. FFmpeg → работает на CPU

Все будет работать, просто медленнее.

### Q: Сколько места занимает видео?

**A:** Примерно:
- 1 минута video.webm = 10-20 MB
- 1 минута audio.webm = 1-2 MB
- 1 скриншот = 100-200 KB

10-минутная запись = ~200 MB

### Q: Можно ли удалить старые записи?

**A:** Да, добавить endpoint:
```python
@router.delete("/sessions/{session_id}")
async def delete_session(session_id: int):
    session = get_session(session_id)
    
    # Удалить из MinIO
    storage.delete(session.video_key)
    storage.delete(session.audio_key)
    
    # Удалить из БД
    db.delete(session)
    db.commit()
```

---

## ГОТОВО К СТАРТУ?

Если все понятно - начинаем с **Итерации 1** (добавление записи видео в расширение).

Время: 3-4 часа
Сложность: Средняя
Критичность: Высокая

**Следующий шаг:** Открыть `extension/background.js` и добавить MediaRecorder API.
