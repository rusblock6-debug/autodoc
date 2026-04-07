/**
 * НИР-Документ - Popup UI
 * Version 2.2.1 - Removed pause indicator
 */

console.log('[НИР-Документ] Popup v2.2.1 loaded');

class Popup {
  constructor() {
    this.state = {
      isRecording: false,
      isPaused: false,
      startTime: null,
      pausedTime: 0,
      clickCount: 0,
      timerInterval: null
    };
    this.currentStream = null;
    this.init();
  }
  
  async init() {
    this.bindElements();
    this.bindEvents();
    await this.loadState();
    this.updateUI();
  }
  
  bindElements() {
    this.el = {
      startBtn: document.getElementById('startBtn'),
      stopBtn: document.getElementById('stopBtn'),
      pauseBtn: document.getElementById('pauseBtn'),
      cancelBtn: document.getElementById('cancelBtn'),
      undoBtn: document.getElementById('undoBtn'),
      status: document.getElementById('status'),
      duration: document.getElementById('duration'),
      clickCount: document.getElementById('clickCount'),
      sessionName: document.getElementById('sessionName'),
      viewGuidesBtn: document.getElementById('viewGuidesBtn'),
      toolbar: document.getElementById('toolbar')
    };
  }
  
  bindEvents() {
    this.el.startBtn.addEventListener('click', () => this.startRecording());
    this.el.stopBtn.addEventListener('click', () => this.stopRecording());
    this.el.pauseBtn.addEventListener('click', () => this.togglePause());
    this.el.cancelBtn.addEventListener('click', () => this.cancelRecording());
    this.el.undoBtn.addEventListener('click', () => this.undoLastClick());
    this.el.viewGuidesBtn.addEventListener('click', () => this.openDashboard());
  }
  
  async loadState() {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ type: 'GET_STATE' }, (response) => {
        if (chrome.runtime.lastError) {
          console.log('Could not get state:', chrome.runtime.lastError);
          resolve();
          return;
        }
        if (response?.state) {
          this.state.isRecording = response.state.isRecording;
          this.state.isPaused = response.state.isPaused || false;
          this.state.startTime = response.state.startTime;
          this.state.pausedTime = response.state.pausedTime || 0;
          this.state.clickCount = response.state.clickCount || 0;
          if (response.state.sessionName) {
            this.el.sessionName.value = response.state.sessionName;
          }
          if (this.state.isRecording && this.state.startTime && !this.state.isPaused) {
            this.startTimer();
          }
        }
        resolve();
      });
    });
  }
  
  async startRecording() {
    const sessionName = this.el.sessionName.value.trim() || 'Новый гайд';
    
    this.el.startBtn.disabled = true;
    this.el.startBtn.textContent = 'Запуск...';
    
    try {
      // Запрашиваем захват экрана
      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: {
          displaySurface: 'browser',
          width: { ideal: 1920 },
          height: { ideal: 1080 }
        },
        audio: false
      });
      
      this.currentStream = stream;
      
      // Слушаем остановку захвата
      stream.getVideoTracks()[0].onended = () => {
        console.log('Stream ended by user');
        this.stopRecording();
      };
      
      // Отправляем в background
      chrome.runtime.sendMessage({
        type: 'START_RECORDING',
        sessionName: sessionName
      }, (response) => {
        if (chrome.runtime.lastError) {
          console.error('Error:', chrome.runtime.lastError);
          alert('Ошибка: ' + chrome.runtime.lastError.message);
          this.stopStream();
          this.resetUI();
          return;
        }
        
        if (response?.success) {
          this.state.isRecording = true;
          this.state.startTime = Date.now();
          this.state.clickCount = 0;
          this.startTimer();
          this.updateUI();
        } else {
          alert('Не удалось начать запись: ' + (response?.error || 'Неизвестная ошибка'));
          this.stopStream();
          this.resetUI();
        }
      });
      
    } catch (error) {
      console.error('Screen capture error:', error);
      this.resetUI();
      
      if (error.name === 'NotAllowedError') {
        // Пользователь отменил - это нормально
      } else {
        alert('Ошибка: ' + error.message);
      }
    }
  }
  
  stopRecording() {
    if (!this.state.isRecording) return;
    
    const currentName = this.el.sessionName.value.trim() || 'Новый гайд';
    
    console.log('[Popup] Stopping recording with name:', currentName);
    
    this.el.stopBtn.disabled = true;
    this.el.stopBtn.textContent = '⏳ Сохранение...';
    
    this.stopStream();
    
    chrome.runtime.sendMessage({ 
      type: 'STOP_RECORDING',
      sessionName: currentName
    }, (response) => {
      if (chrome.runtime.lastError) {
        console.error('Stop error:', chrome.runtime.lastError);
      }
      
      this.state.isRecording = false;
      this.state.isPaused = false;
      this.state.pausedTime = 0;
      this.stopTimer();
      this.updateUI();
      
      if (response?.success) {
        const clicks = response.sessionData?.click_count || 0;
        this.el.status.textContent = `✓ Сохранено (${clicks})`;
      } else {
        this.el.status.textContent = 'Ошибка';
      }
    });
  }
  
  togglePause() {
    if (!this.state.isRecording) return;
    
    this.state.isPaused = !this.state.isPaused;
    
    chrome.runtime.sendMessage({ 
      type: this.state.isPaused ? 'PAUSE_RECORDING' : 'RESUME_RECORDING'
    }, (response) => {
      if (chrome.runtime.lastError) {
        console.error('Pause/Resume error:', chrome.runtime.lastError);
        return;
      }
      
      if (this.state.isPaused) {
        this.stopTimer();
        this.el.pauseBtn.textContent = '▶';
        this.el.pauseBtn.title = 'Продолжить';
        this.el.status.textContent = 'Пауза';
      } else {
        this.startTimer();
        this.el.pauseBtn.textContent = '⏸';
        this.el.pauseBtn.title = 'Пауза';
        this.el.status.textContent = 'Запись';
      }
      
      this.updateUI();
    });
  }
  
  cancelRecording() {
    if (!this.state.isRecording) return;
    
    if (!confirm('Отменить запись и начать заново? Все данные будут потеряны.')) {
      return;
    }
    
    this.stopStream();
    
    chrome.runtime.sendMessage({ type: 'CANCEL_RECORDING' }, (response) => {
      if (chrome.runtime.lastError) {
        console.error('Cancel error:', chrome.runtime.lastError);
      }
      
      this.state.isRecording = false;
      this.state.isPaused = false;
      this.state.pausedTime = 0;
      this.state.clickCount = 0;
      this.stopTimer();
      this.el.duration.textContent = '00:00';
      this.el.clickCount.textContent = '0';
      this.el.status.textContent = 'Готов';
      this.updateUI();
    });
  }
  
  undoLastClick() {
    if (!this.state.isRecording || this.state.clickCount === 0) return;
    
    chrome.runtime.sendMessage({ type: 'UNDO_LAST_CLICK' }, (response) => {
      if (chrome.runtime.lastError) {
        console.error('Undo error:', chrome.runtime.lastError);
        return;
      }
      
      if (response?.success) {
        this.state.clickCount = response.clickCount;
        this.el.clickCount.textContent = this.state.clickCount;
        this.updateUI();
      }
    });
  }
  
  stopStream() {
    if (this.currentStream) {
      this.currentStream.getTracks().forEach(track => track.stop());
      this.currentStream = null;
    }
  }
  
  resetUI() {
    this.el.startBtn.disabled = false;
    this.el.startBtn.textContent = 'Начать запись';
  }
  
  startTimer() {
    this.stopTimer();
    this.state.timerInterval = setInterval(() => {
      if (this.state.startTime && !this.state.isPaused) {
        const elapsed = Date.now() - this.state.startTime - this.state.pausedTime;
        this.el.duration.textContent = this.formatTime(elapsed);
      }
    }, 1000);
    
    if (this.state.startTime) {
      const elapsed = Date.now() - this.state.startTime - this.state.pausedTime;
      this.el.duration.textContent = this.formatTime(elapsed);
    }
  }
  
  stopTimer() {
    if (this.state.timerInterval) {
      clearInterval(this.state.timerInterval);
      this.state.timerInterval = null;
    }
  }
  
  formatTime(ms) {
    const s = Math.floor(ms / 1000);
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`;
  }
  
  updateUI() {
    const { isRecording, isPaused, clickCount } = this.state;
    
    this.el.startBtn.style.display = isRecording ? 'none' : 'block';
    this.el.toolbar.classList.toggle('hidden', !isRecording);
    
    if (isRecording) {
      if (isPaused) {
        this.el.status.textContent = 'Пауза';
        this.el.status.classList.remove('recording');
        this.el.pauseBtn.textContent = '▶';
        this.el.pauseBtn.title = 'Продолжить';
      } else {
        this.el.status.textContent = 'Запись';
        this.el.status.classList.add('recording');
        this.el.pauseBtn.textContent = '⏸';
        this.el.pauseBtn.title = 'Пауза';
      }
      this.el.undoBtn.disabled = clickCount === 0;
      // Блокируем кнопку Stop если нет кликов
      this.el.stopBtn.disabled = clickCount === 0;
    } else {
      this.el.status.classList.remove('recording');
      this.el.status.textContent = 'Готов';
    }
    
    this.el.clickCount.textContent = clickCount;
  }
  
  openDashboard() {
    chrome.tabs.create({ url: 'http://localhost:3000' });
  }
}

// Init
document.addEventListener('DOMContentLoaded', () => {
  window.popup = new Popup();
});

// Listen for click updates
chrome.runtime.onMessage.addListener((message) => {
  if (message.type === 'CLICK_UPDATE' && window.popup) {
    window.popup.state.clickCount = message.count;
    window.popup.el.clickCount.textContent = message.count;
    window.popup.updateUI();
  }
  
  if (message.type === 'PAUSED_TIME_UPDATE' && window.popup) {
    window.popup.state.pausedTime = message.pausedTime;
  }
});
