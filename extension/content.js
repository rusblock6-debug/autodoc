// extension/content.js - Captures click events and logs them for the MVP workflow
// This script runs in the context of the captured tab

// State management
let isRecording = false;
let clickLog = [];
let lastClickTime = 0;

// Click event listener
document.addEventListener('click', (event) => {
    if (!isRecording) return;
    
    const clickData = {
        timestamp: Date.now(),
        x: event.clientX,
        y: event.clientY,
        tagName: event.target.tagName,
        className: event.target.className || '',
        id: event.target.id || '',
        text: (event.target.textContent || '').substring(0, 100),
        viewportWidth: window.innerWidth,
        viewportHeight: window.innerHeight
    };
    
    clickLog.push(clickData);
    lastClickTime = clickData.timestamp;
    
    // Visual feedback - brief highlight
    highlightClick(event.clientX, event.clientY);
    
    // Send to background script
    chrome.runtime.sendMessage({
        type: 'CLICK_LOG',
        data: clickData
    });
});

// Keyboard event listener (optional - for tracking interactions)
document.addEventListener('keydown', (event) => {
    if (!isRecording) return;
    
    const keyData = {
        timestamp: Date.now(),
        key: event.key,
        code: event.code,
        tagName: event.target.tagName,
        keyType: 'keyboard'
    };
    
    chrome.runtime.sendMessage({
        type: 'KEY_LOG',
        data: keyData
    });
});

// Input field tracking
document.addEventListener('input', (event) => {
    if (!isRecording) return;
    
    const inputData = {
        timestamp: Date.now(),
        tagName: event.target.tagName,
        type: event.target.type || 'text',
        valueLength: event.target.value ? event.target.value.length : 0,
        keyType: 'input'
    };
    
    chrome.runtime.sendMessage({
        type: 'INPUT_LOG',
        data: inputData
    });
});

// Visual feedback for clicks
function highlightClick(x, y) {
    const circle = document.createElement('div');
    circle.style.cssText = `
        position: fixed;
        left: ${x - 15}px;
        top: ${y - 15}px;
        width: 30px;
        height: 30px;
        border: 3px solid #FFD700;
        border-radius: 50%;
        pointer-events: none;
        z-index: 999999;
        animation: clickPulse 0.5s ease-out forwards;
    `;
    
    // Add animation if not exists
    if (!document.getElementById('clickAnimationStyle')) {
        const style = document.createElement('style');
        style.id = 'clickAnimationStyle';
        style.textContent = `
            @keyframes clickPulse {
                0% { transform: scale(0.5); opacity: 1; }
                100% { transform: scale(2); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    }
    
    document.body.appendChild(circle);
    setTimeout(() => circle.remove(), 500);
}

// Listen for messages from background script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    switch (message.type) {
        case 'START_RECORDING':
            isRecording = true;
            clickLog = [];
            lastClickTime = Date.now();
            console.log('[AutoDoc] Recording started');
            sendResponse({ success: true });
            break;
            
        case 'STOP_RECORDING':
            isRecording = false;
            console.log('[AutoDoc] Recording stopped, clicks:', clickLog.length);
            sendResponse({ 
                success: true, 
                clickCount: clickLog.length,
                duration: lastClickTime - (clickLog[0]?.timestamp || Date.now())
            });
            break;
            
        case 'GET_CLICK_LOG':
            sendResponse({ 
                success: true, 
                clicks: clickLog,
                lastClickTime: lastClickTime
            });
            break;
            
        case 'CLEAR_LOG':
            clickLog = [];
            sendResponse({ success: true });
            break;
    }
    return true;
});

// Report page info on load
window.addEventListener('load', () => {
    chrome.runtime.sendMessage({
        type: 'PAGE_INFO',
        data: {
            url: window.location.href,
            title: document.title,
            width: window.innerWidth,
            height: window.innerHeight
        }
    });
});
