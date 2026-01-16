/**
 * НИР-Документ - Popup UI
 */

class Popup {
  constructor() {
    this.state = {
      isRecording: false,
      startTime: null,
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
      status: document.getElementById('status'),
      duration: document.getElementById('duration'),
      clickCount: document.getElementById('clickCount'),
      sessionName: document.getElementById('sessionName'),
      viewGuidesBtn: document.getElementById('viewGuidesBtn')
    };
  }
  
  bindEvents() {
    this.el.startBtn.addEventListener('click', () => this.startRecording());
    this.el.stopBtn.addEventListener('click', () => this.stopRecording());
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
          this.state.startTime = response.state.startTime;
          this.state.clickCount = response.state.clickCount || 0;
          // Восстанавливаем имя сессии
          if (response.state.sessionName) {
            this.el.sessionName.value = response.state.sessionName;
          }
          if (this.state.isRecording && this.state.startTime) {
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
    
    // Получаем текущее имя перед остановкой
    const currentName = this.el.sessionName.value.trim() || 'Новый гайд';
    
    this.el.stopBtn.disabled = true;
    this.el.stopBtn.textContent = 'Сохранение...';
    
    this.stopStream();
    
    chrome.runtime.sendMessage({ 
      type: 'STOP_RECORDING',
      sessionName: currentName  // Передаём актуальное имя
    }, (response) => {
      if (chrome.runtime.lastError) {
        console.error('Stop error:', chrome.runtime.lastError);
      }
      
      this.state.isRecording = false;
      this.stopTimer();
      this.updateUI();
      
      if (response?.success) {
        const clicks = response.sessionData?.click_count || 0;
        this.el.status.textContent = `✓ Сохранено (${clicks} кликов)`;
      } else {
        this.el.status.textContent = 'Ошибка сохранения';
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
      if (this.state.startTime) {
        const elapsed = Date.now() - this.state.startTime;
        this.el.duration.textContent = this.formatTime(elapsed);
      }
    }, 1000);
    
    if (this.state.startTime) {
      this.el.duration.textContent = this.formatTime(Date.now() - this.state.startTime);
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
    const { isRecording, clickCount } = this.state;
    
    this.el.startBtn.disabled = isRecording;
    this.el.stopBtn.disabled = !isRecording;
    
    if (isRecording) {
      this.el.status.textContent = '🔴 Запись...';
      this.el.status.classList.add('recording');
      this.el.startBtn.textContent = 'Идёт запись';
      this.el.stopBtn.textContent = 'Остановить';
    } else {
      this.el.status.classList.remove('recording');
      this.el.startBtn.textContent = 'Начать запись';
      this.el.stopBtn.textContent = 'Стоп';
    }
    
    this.el.clickCount.textContent = clickCount;
    // Имя можно менять всегда!
    // this.el.sessionName.disabled = isRecording;
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
  }
});
