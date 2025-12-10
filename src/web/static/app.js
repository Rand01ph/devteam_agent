/**
 * DevTeam Agent Web UI - Frontend JavaScript
 */

// DOM Elements
const messagesEl = document.getElementById('messages');
const messageInput = document.getElementById('message-input');
const btnSend = document.getElementById('btn-send');
const btnInterrupt = document.getElementById('btn-interrupt');
const btnNewSession = document.getElementById('btn-new-session');
const btnBackChat = document.getElementById('btn-back-chat');
const btnCloseReport = document.getElementById('btn-close-report');
const statusBar = document.getElementById('status-bar');
const statusText = document.getElementById('status-text');
const reportList = document.getElementById('report-list');
const chatView = document.getElementById('chat-view');
const reportView = document.getElementById('report-view');
const reportTitle = document.getElementById('report-title');
const reportContent = document.getElementById('report-content');

// State
let ws = null;
let isProcessing = false;
let currentAssistantMessage = null;
let typewriterQueue = [];
let isTyping = false;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    connectWebSocket();
    loadReportList();
    setupEventListeners();
});

// WebSocket Connection
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws/chat`);

    ws.onopen = () => {
        console.log('WebSocket connected');
        showStatus('已连接', 'text-green-600');
        setTimeout(() => hideStatus(), 2000);
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleMessage(data);
    };

    ws.onclose = () => {
        console.log('WebSocket disconnected');
        showStatus('连接断开，正在重连...', 'text-red-600');
        setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        showStatus('连接错误', 'text-red-600');
    };
}

// Handle incoming messages
function handleMessage(data) {
    switch (data.type) {
        case 'text':
            queueTypewriter(data.content);
            break;
        case 'tool_call':
            showStatus(`🔧 调用工具: ${data.name}`, 'status-tool');
            break;
        case 'thinking':
            showStatus('🤔 思考中...', 'status-thinking');
            break;
        case 'done':
            finishAssistantMessage(data.duration_ms);
            break;
        case 'interrupted':
            showStatus('⚠️ 已中断', 'text-orange-600');
            setProcessing(false);
            break;
        case 'session_reset':
            clearMessages();
            showStatus('✓ 已开始新对话', 'text-green-600');
            setTimeout(() => hideStatus(), 2000);
            break;
        case 'error':
            showStatus(`❌ 错误: ${data.message}`, 'status-error');
            setProcessing(false);
            break;
    }
}

// Send message
function sendMessage() {
    const content = messageInput.value.trim();
    if (!content || isProcessing) return;

    // Add user message
    addMessage(content, 'user');
    messageInput.value = '';

    // Send to server
    ws.send(JSON.stringify({ type: 'message', content }));

    // Start processing state
    setProcessing(true);
    showStatus('⏳ 正在处理...', 'text-gray-500');

    // Prepare for assistant response
    currentAssistantMessage = null;
    typewriterQueue = [];
    isTyping = false;
}

// Add message to chat
function addMessage(content, role) {
    // Remove welcome message if present
    const welcome = messagesEl.querySelector('.text-center');
    if (welcome) welcome.remove();

    const div = document.createElement('div');
    div.className = `message message-${role} px-4 py-3`;

    if (role === 'user') {
        div.textContent = content;
    } else {
        div.innerHTML = `<div class="prose prose-sm"></div>`;
        div._content = '';
    }

    messagesEl.appendChild(div);
    scrollToBottom();

    return div;
}

// Queue text for typewriter effect
function queueTypewriter(text) {
    typewriterQueue.push(text);
    if (!isTyping) {
        processTypewriterQueue();
    }
}

// Process typewriter queue
async function processTypewriterQueue() {
    if (typewriterQueue.length === 0) {
        isTyping = false;
        return;
    }

    isTyping = true;
    const text = typewriterQueue.shift();

    if (!currentAssistantMessage) {
        currentAssistantMessage = addMessage('', 'assistant');
    }

    // Typewriter effect - character by character
    const proseEl = currentAssistantMessage.querySelector('.prose');
    for (let i = 0; i < text.length; i++) {
        currentAssistantMessage._content += text[i];
        proseEl.innerHTML = marked.parse(currentAssistantMessage._content);
        scrollToBottom();
        // Adjust speed based on character
        const char = text[i];
        if (char === '\n') {
            await sleep(20);
        } else if (/[，。！？、；：]/.test(char)) {
            await sleep(30);
        } else {
            await sleep(5);
        }
    }

    // Process next in queue
    processTypewriterQueue();
}

// Sleep helper
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Finish assistant message
function finishAssistantMessage(durationMs) {
    // Wait for typewriter to complete
    const checkTyping = setInterval(() => {
        if (!isTyping && typewriterQueue.length === 0) {
            clearInterval(checkTyping);
            const seconds = (durationMs / 1000).toFixed(1);
            showStatus(`✅ 完成 (${seconds}s)`, 'text-green-600');
            setTimeout(() => hideStatus(), 3000);
            setProcessing(false);
            currentAssistantMessage = null;

            // Refresh report list in case new reports were created
            loadReportList();
        }
    }, 100);
}

// Set processing state
function setProcessing(processing) {
    isProcessing = processing;
    btnSend.disabled = processing;
    btnInterrupt.classList.toggle('hidden', !processing);
    messageInput.disabled = processing;

    if (processing) {
        btnSend.classList.add('opacity-50', 'cursor-not-allowed');
    } else {
        btnSend.classList.remove('opacity-50', 'cursor-not-allowed');
    }
}

// Clear messages
function clearMessages() {
    messagesEl.innerHTML = `
        <div class="text-center text-gray-500 py-8">
            <p class="text-lg">欢迎使用 DevTeam Agent</p>
            <p class="text-sm mt-2">输入消息开始对话，或点击左侧查看周报</p>
        </div>
    `;
    currentAssistantMessage = null;
    typewriterQueue = [];
    isTyping = false;
}

// Show/hide status
function showStatus(text, className = '') {
    statusText.textContent = text;
    statusText.className = className;
    statusBar.classList.remove('hidden');
}

function hideStatus() {
    statusBar.classList.add('hidden');
}

// Scroll to bottom
function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

// Load report list
async function loadReportList() {
    try {
        const response = await fetch('/api/reports');
        const data = await response.json();

        reportList.innerHTML = '';

        if (data.reports && data.reports.length > 0) {
            data.reports.forEach(report => {
                const div = document.createElement('div');
                div.className = 'report-item';
                div.textContent = report.name.replace('.md', '');
                div.dataset.name = report.name;
                div.addEventListener('click', () => loadReport(report.name));
                reportList.appendChild(div);
            });
        } else {
            reportList.innerHTML = '<div class="p-3 text-gray-500 text-sm">暂无周报</div>';
        }
    } catch (error) {
        console.error('Failed to load reports:', error);
        reportList.innerHTML = '<div class="p-3 text-red-500 text-sm">加载失败</div>';
    }
}

// Load and display report
async function loadReport(name) {
    try {
        const response = await fetch(`/api/reports/${name}`);
        const data = await response.json();

        if (data.error) {
            alert(`加载失败: ${data.error}`);
            return;
        }

        // Update UI
        reportTitle.textContent = name;
        reportContent.innerHTML = marked.parse(data.content);

        // Highlight active report
        document.querySelectorAll('.report-item').forEach(item => {
            item.classList.toggle('active', item.dataset.name === name);
        });

        // Show report view
        showReportView();
    } catch (error) {
        console.error('Failed to load report:', error);
        alert('加载报告失败');
    }
}

// View switching
function showChatView() {
    chatView.classList.remove('hidden');
    reportView.classList.add('hidden');
    btnBackChat.classList.add('hidden');

    // Clear active state
    document.querySelectorAll('.report-item').forEach(item => {
        item.classList.remove('active');
    });
}

function showReportView() {
    chatView.classList.add('hidden');
    reportView.classList.remove('hidden');
    btnBackChat.classList.remove('hidden');
}

// Event Listeners
function setupEventListeners() {
    // Send button
    btnSend.addEventListener('click', sendMessage);

    // Enter to send (Shift+Enter for new line)
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Interrupt button
    btnInterrupt.addEventListener('click', () => {
        ws.send(JSON.stringify({ type: 'interrupt' }));
    });

    // New session button
    btnNewSession.addEventListener('click', () => {
        if (confirm('确定要开始新对话吗？当前对话上下文将被清除。')) {
            ws.send(JSON.stringify({ type: 'new_session' }));
        }
    });

    // Back to chat button
    btnBackChat.addEventListener('click', showChatView);

    // Close report button
    btnCloseReport.addEventListener('click', showChatView);
}