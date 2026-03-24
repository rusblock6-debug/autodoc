# УСТАРЕВШИЙ ДОКУМЕНТ

⚠️ **ЭТОТ ДОКУМЕНТ УСТАРЕЛ**

Пожалуйста, используйте актуальную дорожную карту:
👉 **[FINAL_ROADMAP.md](FINAL_ROADMAP.md)**

Этот документ содержит правильное понимание задачи, но финальная версия более детальная и структурированная.

---

# СТАРОЕ СОДЕРЖИМОЕ (СПРАВОЧНО)

# ПРАВИЛЬНЫЙ ПЛАН: Добавление записи видео + AI обработка

## Текущая ситуация

### Что ЕСТЬ сейчас:
- ✅ Расширение логирует клики
- ✅ Расширение делает скриншоты
- ✅ Backend обрабатывает клики
- ✅ FFmpeg извлекает кадры из скриншотов
- ❌ **НЕТ записи видео!**

### Что НУЖНО:
- ✅ Расширение записывает video.webm (экран + микрофон)
- ✅ AI транскрибирует речь (Whisper)
- ✅ AI генерирует описания (LLM)
- ✅ AI делает озвучку (TTS)
- ✅ FFmpeg нарезает видео по кликам
- ✅ Результат: готовый гайд с видео

---

## ИТЕРАЦИЯ 1: Добавить запись видео в расширение (3-4 часа)

### Цель
Расширение должно записывать video.webm + audio.wav как Loom/Guidde.

### Задачи

**1.1. Добавить MediaRecorder API**

Файл: `extension/background.js`

Добавить:
```javascript
let mediaRecorder = null;
let recordedChunks = [];
let audioRecorder = null;
let audioChunks = [];

async function startVideoRecording() {
  try {
    // Запрашиваем захват экрана
    const stream = await navigator.mediaDevices.getDisplayMedia({
      video: {
        mediaSource: 'screen',
        width: { ideal: 1920 },
        height: { ideal: 1080 },
        frameRate: { ideal: 30 }
      },
      audio: false  // Аудио отдельно
    });
    
    // Запрашиваем микрофон
    const audioStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        sampleRate: 44100
      }
    });
    
    // Создаем MediaRecorder для видео
    mediaRecorder = new MediaRecorder(stream, {
      mimeType: 'video/webm;codecs=vp9',
      videoBitsPerSecond: 2500000  // 2.5 Mbps
    });
    
    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        recordedChunks.push(event.data);
      }
    };
    
    // Создаем MediaRecorder для аудио
    audioRecorder = new MediaRecorder(audioStream, {
      mimeType: 'audio/webm;codecs=opus'
    });
    
    audioRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunks.push(event.data);
      }
    };
    
    // Запускаем запись
    mediaRecorder.start(1000);  // Сохраняем каждую секунду
    audioRecorder.start(1000);
    
    console.log('[Video] Recording started');
    
  } catch (error) {
    console.error('[Video] Failed to start:', error);
    throw error;
  }
}

async function stopVideoRecording() {
  return new Promise((resolve) => {
    if (!mediaRecorder || !audioRecorder) {
      resolve({ video: null, audio: null });
      return;
    }
    
    let videoBlob = null;
    let audioBlob = null;
    let completed = 0;
    
    mediaRecorder.onstop = () => {
      videoBlob = new Blob(recordedChunks, { type: 'video/webm' });
      recordedChunks = [];
      completed++;
      if (completed === 2) resolve({ video: videoBlob, audio: audioBlob });
    };
    
    audioRecorder.onstop = () => {
      audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
      audioChunks = [];
      completed++;
      if (completed === 2) resolve({ video: videoBlob, audio: audioBlob });
    };
    
    mediaRecorder.stop();
    audioRecorder.stop();
    
    // Останавливаем треки
    mediaRecorder.stream.getTracks().forEach(track => track.stop());
    audioRecorder.stream.getTracks().forEach(track => track.stop());
  });
}
```

**1.2. Интегрировать в существующий flow**

Изменить `handleStartRecording()`:
```javascript
async function handleStartRecording(message, sendResponse) {
  // ... существующий код ...
  
  // ДОБАВИТЬ: Запуск записи видео
  try {
    await startVideoRecording();
    console.log('[НИР-Документ] Video recording started');
  } catch (error) {
    console.error('[НИР-Документ] Video recording failed:', error);
    // Продолжаем без видео (fallback)
  }
  
  // ... остальной код ...
}
```

Изменить `handleStopRecording()`:
```javascript
async function handleStopRecording(message, sendResponse) {
  // ... существующий код ...
  
  // ДОБАВИТЬ: Остановка записи видео
  const { video, audio } = await stopVideoRecording();
  
  // Собираем данные
  const sessionData = {
    // ... существующие поля ...
    has_video: !!video,
    has_audio: !!audio,
    video_size: video?.size || 0,
    audio_size: audio?.size || 0
  };
  
  // Отправляем на бэкенд (с видео и аудио)
  const result = await uploadSession(sessionData, video, audio);
  
  // ... остальной код ...
}
```

**1.3. Обновить upload функцию**

Изменить `uploadSession()`:
```javascript
async function uploadSession(sessionData, videoBlob, audioBlob) {
  try {
    const formData = new FormData();
    
    // Существующие поля
    formData.append('clicks_log', new Blob([clicksJson], { type: 'application/json' }), 'clicks.json');
    formData.append('title', sessionData.session_name);
    
    // ДОБАВИТЬ: Видео и аудио
    if (videoBlob) {
      formData.append('video', videoBlob, 'recording.webm');
    }
    if (audioBlob) {
      formData.append('audio', audioBlob, 'audio.webm');
    }
    
    // Скриншоты (оставляем для превью)
    for (let i = 0; i < recordingState.screenshots.length; i++) {
      // ... существующий код ...
    }
    
    // Отправляем
    const response = await fetch(CONFIG.API_BASE + CONFIG.UPLOAD_ENDPOINT, {
      method: 'POST',
      body: formData
    });
    
    // ... остальной код ...
  }
}
```

### Критерии завершения Итерации 1
✅ Расширение записывает video.webm
✅ Расширение записывает audio.webm
✅ Видео и аудио загружаются на backend
✅ Клики и скриншоты работают как раньше

---

## ИТЕРАЦИЯ 2: Backend обработка видео + AI (4-5 часов)

### Цель
Backend принимает видео, AI обрабатывает, FFmpeg нарезает.

### Задачи

**2.1. Обновить API endpoint**

Файл: `app/api/sessions.py`

Изменить `/upload`:
```python
@router.post("/upload")
async def upload_session(
    title: str = Form(...),
    clicks_log: UploadFile = File(...),
    video: UploadFile = File(None),  # НОВОЕ
    audio: UploadFile = File(None),  # НОВОЕ
    screenshots: List[UploadFile] = File(None)
):
    # Сохраняем видео в MinIO
    video_key = None
    if video:
        video_key = await storage_service.upload_file(
            video.file,
            bucket="autodoc-videos",
            filename=f"session_{session_id}_video.webm"
        )
    
    # Сохраняем аудио в MinIO
    audio_key = None
    if audio:
        audio_key = await storage_service.upload_file(
            audio.file,
            bucket="autodoc-audio",
            filename=f"session_{session_id}_audio.webm"
        )
    
    # Создаем сессию в БД
    session = Session(
        title=title,
        video_key=video_key,  # НОВОЕ
        audio_key=audio_key,  # НОВОЕ
        clicks_data=clicks_data,
        status="uploaded"
    )
    
    # Запускаем обработку
    process_session_task.delay(session.id)
    
    return {"session_id": session.id, "guide_id": guide.id}
```

**2.2. Создать Celery task для обработки**

Файл: `app/celery_tasks.py`

Добавить:
```python
@celery_app.task
def process_session_task(session_id: int):
    """
    Полная обработка сессии:
    1. AI транскрибирует аудио (Whisper)
    2. AI генерирует описания (LLM)
    3. FFmpeg нарезает видео по кликам
    4. Создает шаги в БД
    """
    session = get_session(session_id)
    
    # 1. Скачиваем файлы из MinIO
    video_path = download_from_minio(session.video_key)
    audio_path = download_from_minio(session.audio_key)
    
    # 2. AI: Транскрибация
    transcription = whisper_service.transcribe(audio_path)
    # Результат: { "text": "...", "segments": [...], "words": [...] }
    
    # 3. AI: Определение шагов (клики + речь)
    steps_data = step_detector.detect_steps(
        clicks=session.clicks_data,
        transcription=transcription
    )
    # Результат: [{ "timestamp": 5.2, "click_x": 100, "text": "нажать кнопку" }, ...]
    
    # 4. AI: Генерация описаний
    for step in steps_data:
        step["description"] = llm_service.generate_description(
            raw_text=step["text"],
            context=get_previous_steps(steps_data, step)
        )
    
    # 5. FFmpeg: Нарезка видео по шагам
    for i, step in enumerate(steps_data):
        # Извлекаем сегмент видео
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
    
    # 6. Создаем гайд и шаги в БД
    guide = create_guide(session, steps_data)
    
    # 7. Обновляем статус
    session.status = "processed"
    session.guide_id = guide.id
    
    return {"guide_id": guide.id}
```

**2.3. Обновить модели БД**

Файл: `app/models.py`

Добавить поля:
```python
class Session(Base):
    # ... существующие поля ...
    video_key = Column(String, nullable=True)  # НОВОЕ
    audio_key = Column(String, nullable=True)  # НОВОЕ
    transcription = Column(JSON, nullable=True)  # НОВОЕ

class Step(Base):
    # ... существующие поля ...
    video_segment_key = Column(String, nullable=True)  # НОВОЕ
    audio_segment_key = Column(String, nullable=True)  # НОВОЕ
    duration_seconds = Column(Float, default=3.0)  # НОВОЕ
```

**2.4. Создать миграцию**

```bash
alembic revision -m "add_video_audio_fields"
```

### Критерии завершения Итерации 2
✅ Backend принимает видео и аудио
✅ Whisper транскрибирует речь
✅ LLM генерирует описания
✅ FFmpeg нарезает видео по кликам
✅ Шаги создаются в БД с видео-сегментами

---

## ИТЕРАЦИЯ 3: Генерация финального видео (3-4 часа)

### Цель
Склеить нарезанные сегменты в финальное видео с маркерами и озвучкой.

### Задачи

**3.1. Создать сервис для сборки видео**

Файл: `app/services/video_assembler.py` (новый)

```python
class VideoAssembler:
    """Сборка финального видео из сегментов"""
    
    def assemble_guide_video(
        self,
        guide_id: int,
        add_markers: bool = True,
        add_tts: bool = False
    ) -> str:
        """
        Собирает финальное видео:
        1. Берет сегменты из шагов
        2. Добавляет маркеры кликов
        3. Опционально: заменяет аудио на TTS
        4. Склеивает в одно видео
        """
        guide = get_guide(guide_id)
        steps = get_steps(guide_id)
        
        processed_segments = []
        
        for step in steps:
            # Скачиваем сегмент
            segment_path = download_from_minio(step.video_segment_key)
            
            # Добавляем маркер клика
            if add_markers:
                segment_with_marker = self.add_click_marker(
                    segment_path,
                    click_x=step.click_x,
                    click_y=step.click_y
                )
            else:
                segment_with_marker = segment_path
            
            # Заменяем аудио на TTS
            if add_tts:
                tts_audio = tts_service.generate(step.description)
                segment_final = self.replace_audio(
                    segment_with_marker,
                    tts_audio
                )
            else:
                segment_final = segment_with_marker
            
            processed_segments.append(segment_final)
        
        # Склеиваем все сегменты
        final_video = self.concatenate_segments(processed_segments)
        
        # Загружаем в MinIO
        final_key = upload_to_minio(final_video)
        
        # Обновляем гайд
        guide.final_video_key = final_key
        
        return final_key
    
    def add_click_marker(self, video_path: str, click_x: int, click_y: int) -> str:
        """Добавляет желтый маркер на видео"""
        output_path = f"{video_path}_marker.mp4"
        
        cmd = [
            "ffmpeg", "-i", video_path,
            "-vf", f"drawbox=x={click_x-25}:y={click_y-25}:w=50:h=50:color=yellow:t=5",
            output_path
        ]
        
        subprocess.run(cmd)
        return output_path
    
    def concatenate_segments(self, segments: List[str]) -> str:
        """Склеивает сегменты в одно видео"""
        concat_list = "concat_list.txt"
        with open(concat_list, "w") as f:
            for seg in segments:
                f.write(f"file '{seg}'\n")
        
        output_path = f"final_{uuid.uuid4()}.mp4"
        
        cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list,
            "-c", "copy",
            output_path
        ]
        
        subprocess.run(cmd)
        return output_path
```

**3.2. Добавить API endpoint для генерации**

Файл: `app/api/guides.py`

```python
@router.post("/guides/{guide_id}/generate-video")
async def generate_guide_video(
    guide_id: int,
    add_markers: bool = True,
    use_tts: bool = False
):
    """Генерирует финальное видео гайда"""
    
    # Запускаем задачу
    task = assemble_video_task.delay(guide_id, add_markers, use_tts)
    
    return {
        "task_id": task.id,
        "status": "processing"
    }
```

### Критерии завершения Итерации 3
✅ Сегменты склеиваются в финальное видео
✅ Маркеры кликов добавляются
✅ Опционально: TTS заменяет оригинальное аудио
✅ Финальное видео доступно для скачивания

---

## ИТЕРАЦИЯ 4: Frontend интеграция (2-3 часа)

### Цель
Обновить UI для работы с видео.

### Задачи

**4.1. Обновить StepEditor**

Файл: `frontend/src/pages/StepEditor.jsx`

Добавить:
```jsx
function StepEditor({ guideId }) {
  const [steps, setSteps] = useState([]);
  const [currentStep, setCurrentStep] = useState(0);
  
  // Загружаем шаги
  useEffect(() => {
    api.getGuideSteps(guideId).then(setSteps);
  }, [guideId]);
  
  return (
    <div>
      {/* Видео плеер для текущего шага */}
      <video 
        src={steps[currentStep]?.video_segment_url}
        controls
        autoPlay
      />
      
      {/* Описание шага */}
      <div contentEditable>
        {steps[currentStep]?.description}
      </div>
      
      {/* Навигация */}
      <button onClick={() => setCurrentStep(prev => prev - 1)}>
        Предыдущий
      </button>
      <button onClick={() => setCurrentStep(prev => prev + 1)}>
        Следующий
      </button>
      
      {/* Генерация финального видео */}
      <button onClick={() => api.generateFinalVideo(guideId)}>
        Сгенерировать финальное видео
      </button>
    </div>
  );
}
```

### Критерии завершения Итерации 4
✅ UI показывает видео-сегменты
✅ Можно редактировать описания
✅ Можно сгенерировать финальное видео

---

## Резюме

| Итерация | Время | Что делаем |
|----------|-------|------------|
| 1. Запись видео | 3-4 ч | Добавляем MediaRecorder в расширение |
| 2. AI обработка | 4-5 ч | Whisper + LLM + FFmpeg нарезка |
| 3. Сборка видео | 3-4 ч | Склейка сегментов + маркеры |
| 4. Frontend | 2-3 ч | UI для работы с видео |
| **ИТОГО** | **12-16 ч** | **1.5-2 дня** |

---

## Зачем нужен FFmpeg?

**FFmpeg делает:**
- Нарезает видео по таймкодам (AI это не умеет)
- Извлекает кадры для скриншотов
- Добавляет маркеры/аннотации на видео
- Склеивает сегменты
- Меняет скорость/зум
- Конвертирует форматы

**AI делает:**
- Понимает что говорит пользователь (Whisper)
- Генерирует описания (LLM)
- Озвучивает текст (TTS)

**Вместе:** AI понимает контент, FFmpeg обрабатывает видео.

---

## Правильно ли я понял?

Если да - начинаем с Итерации 1 (добавление записи видео в расширение)?

