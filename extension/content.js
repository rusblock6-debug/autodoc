// AutoDoc AI - Content Script
// Отслеживание кликов пользователя на странице

console.log('AutoDoc AI Content Script loaded')

let isTracking = false
let clickMarker = null

// Start tracking clicks
function startTracking() {
  if (isTracking) return
  
  isTracking = true
  document.addEventListener('click', handleClick, true)
  console.log('Click tracking started')
}

// Stop tracking clicks
function stopTracking() {
  if (!isTracking) return
  
  isTracking = false
  document.removeEventListener('click', handleClick, true)
  removeMarker()
  console.log('Click tracking stopped')
}

// Handle click event
function handleClick(event) {
  if (!isTracking) return
  
  const x = event.clientX
  const y = event.clientY
  const pageX = event.pageX
  const pageY = event.pageY
  
  // Get element info
  const element = event.target
  const elementInfo = {
    tagName: element.tagName,
    id: element.id || null,
    className: element.className || null,
    text: element.textContent?.substring(0, 50) || null
  }
  
  // Show visual marker
  showClickMarker(x, y)
  
  // Send to background script
  chrome.runtime.sendMessage({
    action: 'recordClick',
    x: x,
    y: y,
    pageX: pageX,
    pageY: pageY,
    screenWidth: window.innerWidth,
    screenHeight: window.innerHeight,
    element: elementInfo
  })
  
  // Notify popup
  chrome.runtime.sendMessage({
    action: 'clickRecorded'
  })
  
  console.log('Click recorded:', { x, y, element: elementInfo })
}

// Show visual marker at click position
function showClickMarker(x, y) {
  // Remove previous marker
  removeMarker()
  
  // Create marker element
  clickMarker = document.createElement('div')
  clickMarker.id = 'autodoc-click-marker'
  clickMarker.style.cssText = `
    position: fixed;
    left: ${x}px;
    top: ${y}px;
    width: 40px;
    height: 40px;
    margin-left: -20px;
    margin-top: -20px;
    border-radius: 50%;
    background: rgba(255, 215, 0, 0.3);
    border: 3px solid #FFD700;
    pointer-events: none;
    z-index: 999999;
    animation: autodoc-pulse 0.6s ease-out;
  `
  
  // Add animation
  const style = document.createElement('style')
  style.textContent = `
    @keyframes autodoc-pulse {
      0% {
        transform: scale(0.5);
        opacity: 1;
      }
      100% {
        transform: scale(1.5);
        opacity: 0;
      }
    }
  `
  document.head.appendChild(style)
  
  document.body.appendChild(clickMarker)
  
  // Remove after animation
  setTimeout(() => {
    removeMarker()
  }, 600)
}

// Remove marker
function removeMarker() {
  if (clickMarker && clickMarker.parentNode) {
    clickMarker.parentNode.removeChild(clickMarker)
    clickMarker = null
  }
}

// Listen for messages from background script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'startTracking') {
    startTracking()
    sendResponse({ success: true })
  } else if (message.action === 'stopTracking') {
    stopTracking()
    sendResponse({ success: true })
  }
})

// Auto-start tracking if recording is active
chrome.storage.local.get(['recordingState'], (result) => {
  if (result.recordingState && result.recordingState.isRecording) {
    startTracking()
  }
})

// Start tracking immediately (will be active during recording)
startTracking()
