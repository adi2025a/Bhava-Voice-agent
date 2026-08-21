class VoiceApp {
    constructor() {
        this.ws = null;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.isRecording = false;
        this.audioContext = null;
        this.analyser = null;
        this.animFrameId = null;
        this.currentAgentBubble = null;
        this.audioQueue = [];
        this.isPlayingAudio = false;

        this.initDOMElements();
        this.initWebSocket();
        this.initCanvasVisualizer();
        this.bindEvents();
        this.loadCurrentConfig();
    }

    initDOMElements() {
        this.wsStatusIndicator = document.getElementById('wsStatusIndicator');
        this.wsStatusText = document.getElementById('wsStatusText');
        this.micBtn = document.getElementById('micBtn');
        this.micStatusText = document.getElementById('micStatusText');
        this.textInput = document.getElementById('textInput');
        this.sendTextBtn = document.getElementById('sendTextBtn');
        this.chatHistory = document.getElementById('chatHistory');
        this.clearChatBtn = document.getElementById('clearChatBtn');
        this.canvas = document.getElementById('waveformCanvas');

        // Banners & Badges
        this.routingBanner = document.getElementById('routingBanner');
        this.routerThought = document.getElementById('routerThought');
        this.activeAgentBadge = document.getElementById('activeAgentBadge');
        this.activeAgentName = document.getElementById('activeAgentName');

        // Modal
        this.configModal = document.getElementById('configModal');
        this.configToggleBtn = document.getElementById('configToggleBtn');
        this.closeModalBtn = document.getElementById('closeModalBtn');
        this.saveConfigBtn = document.getElementById('saveConfigBtn');
        this.sttSelect = document.getElementById('sttSelect');
        this.dialogueSelect = document.getElementById('dialogueSelect');
        this.ttsSelect = document.getElementById('ttsSelect');
        this.voiceSelect = document.getElementById('voiceSelect');
    }

    initWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/voice`;
        
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            this.setWSStatus(true, 'Connected');
        };

        this.ws.onclose = () => {
            this.setWSStatus(false, 'Disconnected');
            setTimeout(() => this.initWebSocket(), 3000);
        };

        this.ws.onerror = (err) => {
            console.error('WebSocket Error:', err);
            this.setWSStatus(false, 'Error');
        };

        this.ws.onmessage = (event) => {
            this.handleServerMessage(JSON.parse(event.data));
        };
    }

    setWSStatus(connected, text) {
        const dot = this.wsStatusIndicator.querySelector('.dot');
        dot.className = `dot ${connected ? 'connected' : 'disconnected'}`;
        this.wsStatusText.textContent = text;
    }

    bindEvents() {
        this.micBtn.addEventListener('click', () => this.toggleMicrophone());
        
        this.sendTextBtn.addEventListener('click', () => this.sendTextMessage());
        this.textInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.sendTextMessage();
        });

        this.clearChatBtn.addEventListener('click', () => {
            this.chatHistory.innerHTML = `
                <div class="chat-placeholder">
                    <div class="placeholder-icon">💬</div>
                    <p>Session reset. Speak or type to start a new turn.</p>
                </div>`;
            this.activeAgentName.textContent = 'Waiting...';
            this.routingBanner.classList.add('hidden');
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type: 'reset' }));
            }
        });

        // Modal Controls
        this.configToggleBtn.addEventListener('click', () => this.configModal.classList.remove('hidden'));
        this.closeModalBtn.addEventListener('click', () => this.configModal.classList.add('hidden'));
        this.saveConfigBtn.addEventListener('click', () => this.saveConfiguration());
    }

    async toggleMicrophone() {
        if (this.isRecording) {
            this.stopRecording();
        } else {
            await this.startRecording();
        }
    }

    async startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
            this.audioChunks = [];

            // Web Audio Analyser setup for visualizer
            if (!this.audioContext) {
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            }
            const source = this.audioContext.createMediaStreamSource(stream);
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 64;
            source.connect(this.analyser);

            this.mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) {
                    this.audioChunks.push(e.data);
                }
            };

            this.mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
                const arrayBuffer = await audioBlob.arrayBuffer();
                
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send(arrayBuffer);
                }
                stream.getTracks().forEach(track => track.stop());
            };

            this.mediaRecorder.start(100);
            this.isRecording = true;
            this.micBtn.classList.add('recording');
            this.micStatusText.textContent = 'Listening... Click to Stop';
            this.drawVisualizer();
        } catch (err) {
            console.error('Microphone Access Error:', err);
            alert('Could not access microphone: ' + err.message);
        }
    }

    stopRecording() {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            this.isRecording = false;
            this.micBtn.classList.remove('recording');
            this.micStatusText.textContent = 'Processing Audio...';
        }
    }

    sendTextMessage() {
        const text = this.textInput.value.trim();
        if (!text) return;
        
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'text_input', text: text }));
            this.textInput.value = '';
            this.micStatusText.textContent = 'Processing Query...';
        }
    }

    handleServerMessage(data) {
        this.removePlaceholder();

        switch (data.type) {
            case 'stt_result':
                this.appendUserMessage(data.text);
                this.micStatusText.textContent = 'Click to Speak';
                break;

            case 'agent_thought':
                this.routingBanner.classList.remove('hidden');
                this.routerThought.textContent = data.thought;
                break;

            case 'agent_chunk':
                this.activeAgentName.textContent = `${data.agent} (${data.role})`;
                this.appendAgentChunk(data.agent, data.role, data.text, data.is_final);
                break;

            case 'audio_chunk':
                this.enqueueAudioChunk(data.audio_b64, data.mime);
                break;

            case 'audio_end':
                // Completed turn audio synthesis
                break;

            case 'error':
                alert('Server Error: ' + data.message);
                this.micStatusText.textContent = 'Click to Speak';
                break;
        }
    }

    removePlaceholder() {
        const placeholder = this.chatHistory.querySelector('.chat-placeholder');
        if (placeholder) placeholder.remove();
    }

    appendUserMessage(text) {
        const div = document.createElement('div');
        div.className = 'message-bubble user';
        div.innerHTML = `<div class="msg-header">YOU</div>${this.escapeHTML(text)}`;
        this.chatHistory.appendChild(div);
        this.scrollToBottom();
        this.currentAgentBubble = null;
    }

    appendAgentChunk(agentName, role, text, isFinal) {
        if (!this.currentAgentBubble) {
            this.currentAgentBubble = document.createElement('div');
            this.currentAgentBubble.className = 'message-bubble agent';
            this.currentAgentBubble.innerHTML = `
                <div class="msg-header">
                    <span>${this.escapeHTML(agentName)}</span>
                    <span class="msg-role">${this.escapeHTML(role)}</span>
                </div>
                <div class="msg-content"></div>`;
            this.chatHistory.appendChild(this.currentAgentBubble);
        }

        const contentDiv = this.currentAgentBubble.querySelector('.msg-content');
        contentDiv.innerHTML += this.escapeHTML(text);
        this.scrollToBottom();

        if (isFinal) {
            this.currentAgentBubble = null;
        }
    }

    enqueueAudioChunk(base64Data, mimeType) {
        const audioUrl = `data:${mimeType};base64,${base64Data}`;
        const audio = new Audio(audioUrl);
        this.audioQueue.push(audio);
        this.playNextAudioInQueue();
    }

    playNextAudioInQueue() {
        if (this.isPlayingAudio || this.audioQueue.length === 0) return;

        this.isPlayingAudio = true;
        const currentAudio = this.audioQueue.shift();

        currentAudio.onended = () => {
            this.isPlayingAudio = false;
            this.playNextAudioInQueue();
        };

        currentAudio.onerror = () => {
            this.isPlayingAudio = false;
            this.playNextAudioInQueue();
        };

        currentAudio.play().catch(e => {
            console.error('Audio playback error:', e);
            this.isPlayingAudio = false;
        });
    }

    initCanvasVisualizer() {
        this.ctx = this.canvas.getContext('2d');
        this.resizeCanvas();
        window.addEventListener('resize', () => this.resizeCanvas());
    }

    resizeCanvas() {
        this.canvas.width = this.canvas.offsetWidth * window.devicePixelRatio;
        this.canvas.height = this.canvas.offsetHeight * window.devicePixelRatio;
        this.ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    }

    drawVisualizer() {
        if (!this.isRecording || !this.analyser) {
            this.ctx.clearRect(0, 0, this.canvas.offsetWidth, this.canvas.offsetHeight);
            return;
        }

        this.animFrameId = requestAnimationFrame(() => this.drawVisualizer());
        const bufferLength = this.analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);
        this.analyser.getByteFrequencyData(dataArray);

        const width = this.canvas.offsetWidth;
        const height = this.canvas.offsetHeight;
        this.ctx.clearRect(0, 0, width, height);

        const barWidth = (width / bufferLength) * 2;
        let x = 0;

        for (let i = 0; i < bufferLength; i++) {
            const barHeight = (dataArray[i] / 255) * height * 0.8;

            const gradient = this.ctx.createLinearGradient(0, height, 0, 0);
            gradient.addColorStop(0, '#00f2fe');
            gradient.addColorStop(1, '#7f00ff');

            this.ctx.fillStyle = gradient;
            this.ctx.fillRect(x, height - barHeight, barWidth - 2, barHeight);

            x += barWidth;
        }
    }

    async loadCurrentConfig() {
        try {
            const res = await fetch('/api/status');
            const data = await res.json();
            if (data.active_providers) {
                this.sttSelect.value = data.active_providers.stt;
                this.dialogueSelect.value = data.active_providers.dialogue;
                this.ttsSelect.value = data.active_providers.tts;
            }
        } catch (e) {
            console.error('Failed to load status:', e);
        }
    }

    async saveConfiguration() {
        const payload = {
            stt_provider: this.sttSelect.value,
            dialogue_provider: this.dialogueSelect.value,
            tts_provider: this.ttsSelect.value,
            default_tts_voice: this.voiceSelect.value
        };

        try {
            const res = await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            alert('Settings updated! Connection will automatically use new modules.');
            this.configModal.classList.add('hidden');
        } catch (e) {
            alert('Error updating config: ' + e.message);
        }
    }

    scrollToBottom() {
        this.chatHistory.scrollTop = this.chatHistory.scrollHeight;
    }

    escapeHTML(str) {
        if (!str) return '';
        return str.replace(/[&<>'"]/g, 
            tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
        );
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.voiceApp = new VoiceApp();
});
