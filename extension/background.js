// AutoDoc AI - Background Service Worker
// Управление записью экрана, аудио и отправкой данных на backend

const API_URL = 'http://localhost:8000/api/v1'

let recordingState = {
  isRecording: false,
  mediaRecorder: null,
  audioRecorder: null,
  videoChunks: [],
  audioChunks: [],
  clicksLog: [],
  sessionId: null,
  guideId: null,
  startTime: null,
  tabId: null
}

// Listen for messages from popup and content scripts
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'startRecording') {
    handleStartRecording(message, sendResponse)
    return true // Keep channel open for async response
  } else if (message.action === 'stopRecording') {
    handleStopRecording(message, sendResponse)
    return true
  } else if (message.action === 'recordClick') {
    handleRecordClick(message, sender)
  }
})

// Start recording
async function handleStartRecording(message, sendResponse) {
  try {
    console.log('Starting recording...', message)
    
    // Create guide on backend
    const guideResponse = await fetch(`${API_URL}/guides`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: message.sessionName,
        language: 'ru',
        status: 'draft'
      })
    })
    
    if (!guideResponse.ok) {
      throw new Error('Failed to create guide')
    }
    
    const guideData = await guideResponse.json()
    
    // Request screen capture
    const streamId = await new Promise((resolve, reject) => {
      chrome.tabCapture.getMediaStreamId({
        targetTabId: message.tabId
      }, (streamId) => {
        if (chrome.runtime.lastError) {
          reject(chrome.runtime.lastError)
        } else {
          resolve(streamId)
        }
      })
    })
    
    // Get screen stream
    const screenStream = await navigator.mediaDevices.getUserMedia({
      video: {
        mandatory: {
          chromeMediaSource: 'tab',
          chromeMediaSourceId: streamId
        }
      },
      audio: {
        mandatory: {
          chromeMediaSource: 'tab',
          chromeMediaSourceId: streamId
        }
      }
    })
    
    // Get microphone stream
    let micStream = null
    try {
      micStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 44100
        }
      })
    } catch (error) {
      console.warn('Microphone access denied:', error)
    }
    
    // Setup video recorder (screen + tab audio)
    recordingState.mediaRecorder = new MediaRecorder(screenStream, {
      mimeType: 'video/webm;codecs=vp9',
      videoBitsPerSecond: 2500000
    })
    
    recordingState.videoChunks = []
    recordingState.mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        recordingState.videoChunks.push(event.data)
      }
    }
    
    // Setup audio recorder (microphone)
    if (micStream) {
      recordingState.audioRecorder = new MediaRecorder(micStream, {
        mimeType: 'audio/webm;codecs=opus'
      })
      
      recordingState.audioChunks = []
      recordingState.audioRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          recordingState.audioChunks.push(event.data)
        }
      }
      
      recordingState.audioRecorder.start(1000) // Collect data every second
    }
    
    recordingState.mediaRecorder.start(1000)
    
    // Initialize state
    recordingState.isRecording = true
    recordingState.sessionId = `session_${Date.now()}`
    recordingState.guideId = guideData.id
    recordingState.startTime = Date.now()
    recordingState.clicksLog = []
    recordingState.tabId = message.tabId
    
    console.log('Recording started successfully')
    
    sendResponse({
      success: true,
      sessionId: recordingState.sessionId,
      guideId: recordingState.guideId
    })
    
  } catch (error) {
    console.error('Failed to start recording:', error)
    sendResponse({
      success: false,
      error: error.message
    })
  }
}

// Stop recording
async function handleStopRecording(message, sendResponse) {
  try {
    console.log('Stopping recording...')
    
    if (!recordingState.isRecording) {
      throw new Error('Not recording')
    }
    
    // Stop recorders
    if (recordingState.mediaRecorder) {
      recordingState.mediaRecorder.stop()
    }
    
    if (recordingState.audioRecorder) {
      recordingState.audioRecorder.stop()
    }
    
    // Wait for data to be collected
    await new Promise(resolve => setTimeout(resolve, 1000))
    
    // Create blobs
    const videoBlob = new Blob(recordingState.videoChunks, { type: 'video/webm' })
    const audioBlob = recordingState.audioChunks.length > 0 
      ? new Blob(recordingState.audioChunks, { type: 'audio/webm' })
      : null
    
    // Create clicks log
    const clicksData = {
      clicks: recordingState.clicksLog,
      duration: (Date.now() - recordingState.startTime) / 1000,
      clickCount: recordingState.clicksLog.length
    }
    
    console.log('Uploading session data...', {
      videoSize: videoBlob.size,
      audioSize: audioBlob?.size,
      clicks: clicksData.clickCount
    })
    
    // Upload to backend
    const formData = new FormData()
    formData.append('video', videoBlob, 'recording.webm')
    if (audioBlob) {
      formData.append('audio', audioBlob, 'audio.webm')
    }
    formData.append('clicks', JSON.stringify(clicksData))
    formData.append('guide_id', recordingState.guideId)
    
    const uploadResponse = await fetch(`${API_URL}/sessions/upload`, {
      method: 'POST',
      body: formData
    })
    
    if (!uploadResponse.ok) {
      throw new Error('Failed to upload session')
    }
    
    const uploadData = await uploadResponse.json()
    console.log('Upload successful:', uploadData)
    
    // Start processing
    await fetch(`${API_URL}/sessions/${uploadData.session_id}/process`, {
      method: 'POST'
    })
    
    // Reset state
    recordingState.isRecording = false
    recordingState.mediaRecorder = null
    recordingState.audioRecorder = null
    recordingState.videoChunks = []
    recordingState.audioChunks = []
    recordingState.clicksLog = []
    
    sendResponse({
      success: true,
      sessionId: uploadData.session_id
    })
    
  } catch (error) {
    console.error('Failed to stop recording:', error)
    sendResponse({
      success: false,
      error: error.message
    })
  }
}

// Record click event
function handleRecordClick(message, sender) {
  if (!recordingState.isRecording) return
  
  const timestamp = (Date.now() - recordingState.startTime) / 1000 // seconds
  
  recordingState.clicksLog.push({
    timestamp: timestamp,
    x: message.x,
    y: message.y,
    element: message.element,
    pageX: message.pageX,
    pageY: message.pageY,
    screenWidth: message.screenWidth,
    screenHeight: message.screenHeight
  })
  
  console.log('Click recorded:', {
    timestamp,
    x: message.x,
    y: message.y,
    total: recordingState.clicksLog.length
  })
}

// Handle extension icon click
chrome.action.onClicked.addListener((tab) => {
  // Open popup (default behavior)
})

console.log('AutoDoc AI Background Service Worker loaded')
