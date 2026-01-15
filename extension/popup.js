// extension/popup.js - UI logic for the Chrome Extension popup
// Handles recording controls and communication with background script

class AutoDocPopup {
    constructor() {
        this.recordingState = {
            isRecording: false,
            startTime: null,
            timerInterval: null,
            clickCount: 0,
            micEnabled: false
        };
        
        this.init();
    }
    
    init() {
        this.bindElements();
        this.bindEvents();
        this.loadState();
    }
    
    bindElements() {
        this.elements = {
            startBtn: document.getElementById('startBtn'),
            stopBtn: document.getElementById('stopBtn'),
            status: document.getElementById('status'),
            duration: document.getElementById('duration'),
            clickCount: document.getElementById('clickCount'),
            micStatus: document.getElementById('micStatus'),
            sessionName: document.getElementById('sessionName'),
            viewGuidesBtn: document.getElementById('viewGuidesBtn'),
            openEditorBtn: document.getElementById('openEditorBtn'),
            settingsLink: document.getElementById('settingsLink')
        };
    }
    
    bindEvents() {
        this.elements.startBtn.addEventListener('click', () => this.startRecording());
        this.elements.stopBtn.addEventListener('click', () => this.stopRecording());
        this.elements.viewGuidesBtn.addEventListener('click', () => this.openGuidesPage());
        this.elements.openEditorBtn.addEventListener('click', () => this.openEditor());
        this.elements.settingsLink.addEventListener('click', (e) => {
            e.preventDefault();
            chrome.runtime.openOptionsPage?.() || alert('Settings page not configured');
        });
    }
    
    loadState() {
        // Get current state from background script
        chrome.runtime.sendMessage({ type: 'GET_STATE' }, (response) => {
            if (response && response.state) {
                this.recordingState = { ...this.recordingState, ...response.state };
                this.updateUI();
            }
        });
    }
    
    async startRecording() {
        const sessionName = this.elements.sessionName.value.trim() || 'Untitled Session';
        
        try {
            // Request media stream
            const stream = await navigator.mediaDevices.getDisplayMedia({
                video: {
                    displaySurface: 'browser',
                    width: { ideal: 1920 },
                    height: { ideal: 1080 },
                    frameRate: { ideal: 30 }
                },
                audio: true
            });
            
            // Check if user wants microphone audio
            const audioTrack = stream.getAudioTracks()[0];
            if (audioTrack) {
                // Try to get microphone as well
                try {
                    const micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    this.recordingState.micEnabled = true;
                    
                    // Combine audio tracks
                    const audioContext = new AudioContext();
                    const dest = audioContext.createMediaStreamDestination();
                    
                    audioTrack.clone().connect(dest);
                    micStream.getAudioTracks()[0].connect(dest);
                    
                    // Replace audio track with combined audio
                    const newStream = new MediaStream([
                        ...stream.getVideoTracks(),
                        ...dest.stream.getAudioTracks()
                    ]);
                    
                    this.currentStream = newStream;
                } catch (micError) {
                    console.log('Microphone access denied, using system audio only');
                    this.currentStream = stream;
                }
            } else {
                this.currentStream = stream;
            }
            
            // Start recording in background
            chrome.runtime.sendMessage({
                type: 'START_RECORDING',
                sessionName: sessionName,
                streamId: stream.id
            });
            
            // Update state
            this.recordingState.isRecording = true;
            this.recordingState.startTime = Date.now();
            this.recordingState.clickCount = 0;
            
            // Start timer
            this.startTimer();
            
            // Listen for stream end
            stream.getVideoTracks()[0].onended = () => {
                this.stopRecording();
            };
            
            this.updateUI();
            
        } catch (error) {
            console.error('Failed to start recording:', error);
            alert('Failed to start recording. Please ensure you have granted the necessary permissions.');
        }
    
    }
    
    stopRecording() {
        if (!this.recordingState.isRecording) return;
        
        chrome.runtime.sendMessage({
            type: 'STOP_RECORDING',
            sessionName: this.elements.sessionName.value.trim()
        });
        
        // Stop all tracks
        if (this.currentStream) {
            this.currentStream.getTracks().forEach(track => track.stop());
        }
        
        // Update state
        this.recordingState.isRecording = false;
        this.recordingState.startTime = null;
        
        // Stop timer
        this.stopTimer();
        
        // Enable editor button
        this.elements.openEditorBtn.disabled = false;
        
        this.updateUI();
    }
    
    startTimer() {
        this.recordingState.timerInterval = setInterval(() => {
            const elapsed = Date.now() - this.recordingState.startTime;
            this.elements.duration.textContent = this.formatDuration(elapsed);
        }, 1000);
    }
    
    stopTimer() {
        if (this.recordingState.timerInterval) {
            clearInterval(this.recordingState.timerInterval);
            this.recordingState.timerInterval = null;
        }
    }
    
    formatDuration(ms) {
        const seconds = Math.floor(ms / 1000);
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;
        
        if (hours > 0) {
            return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
        return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    
    updateUI() {
        const { isRecording, clickCount, micEnabled } = this.recordingState;
        
        // Update buttons
        this.elements.startBtn.disabled = isRecording;
        this.elements.stopBtn.disabled = !isRecording;
        
        // Update status
        if (isRecording) {
            this.elements.status.textContent = 'Recording';
            this.elements.status.classList.add('recording');
            this.elements.startBtn.textContent = 'Recording...';
        } else {
            this.elements.status.textContent = 'Ready';
            this.elements.status.classList.remove('recording');
            this.elements.startBtn.textContent = 'Start Recording';
        }
        
        // Update click count
        this.elements.clickCount.textContent = clickCount;
        
        // Update mic status
        this.elements.micStatus.textContent = micEnabled ? 'On' : 'Off';
        this.elements.micStatus.style.color = micEnabled ? '#4CAF50' : '#FF4444';
        
        // Update session name input
        this.elements.sessionName.disabled = isRecording;
    }
    
    openGuidesPage() {
        // Open the web editor in a new tab
        chrome.tabs.create({ url: 'http://localhost:8000/guides' });
    }
    
    openEditor() {
        // Open the editor for the last session
        chrome.tabs.create({ url: 'http://localhost:8000/editor' });
    }
}

// Initialize popup
document.addEventListener('DOMContentLoaded', () => {
    new AutoDocPopup();
});

// Listen for updates from background script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'CLICK_UPDATE') {
        const popup = AutoDocPopup.instance;
        if (popup) {
            popup.recordingState.clickCount = message.count;
            popup.elements.clickCount.textContent = message.count;
        }
    }
    return false;
});
