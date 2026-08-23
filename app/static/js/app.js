/**
 * Bhava Voice - Multi-Agent AI Web Application
 * Modular, real-time voice pipeline controller.
 */

class VoiceApp {
    constructor() {
        // Core Web API instances
        this.ws = null;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.audioContext = null;
        this.analyser = null;
        this.animFrameId = null;

        // State Flags
        this.isRecording = false;
        this.isSpeaking = false;
        this.isPlayingAudio = false;
        this.wasSpeaking = false;
        this.silenceStartTime = null;

        // Audio Playback Queue
        this.audioQueue = [];
        this.currentPlayingAudio = null;
        this.currentAgentBubble = null;
        this.sessionId = null;

        // Initialize App
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
        this.stopBtn = document.getElementById('stopBtn');
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

        // Modal Controls
        this.configModal = document.getElementById('configModal');
        this.configToggleBtn = document.getElementById('configToggleBtn');
        this.closeModalBtn = document.getElementById('closeModalBtn');
        this.saveConfigBtn = document.getElementById('saveConfigBtn');
        this.sttSelect = document.getElementById('sttSelect');
        this.dialogueSelect = document.getElementById('dialogueSelect');
        this.ttsSelect = document.getElementById('ttsSelect');
        this.vadSelect = document.getElementById('vadSelect');
        this.voiceSelect = document.getElementById('voiceSelect');
    }

    initWebSocket() {
        if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
            return;
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/voice`;
        console.log('[Bhava App] Connecting to WebSocket:', wsUrl);
        this.setWSStatus(false, 'Connecting...');

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('[Bhava App] WebSocket Connected successfully.');
            this.setWSStatus(true, 'Connected');
        };

        this.ws.onclose = () => {
            console.warn('[Bhava App] WebSocket connection closed. Retrying in 3 seconds...');
            this.setWSStatus(false, 'Disconnected');
            setTimeout(() => this.initWebSocket(), 3000);
        };

        this.ws.onerror = (err) => {
            console.error('[Bhava App] WebSocket Error:', err);
            this.setWSStatus(false, 'Error');
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleServerMessage(data);
            } catch (e) {
                console.error('[Bhava App] Error parsing server message:', e, event.data);
            }
        };
    }

    setWSStatus(connected, text) {
        const dot = this.wsStatusIndicator.querySelector('.dot');
        dot.className = `dot ${connected ? 'connected' : 'disconnected'}`;
        this.wsStatusText.textContent = text;
    }

    bindEvents() {
        this.micBtn.addEventListener('click', () => this.toggleMicrophone());
        if (this.stopBtn) {
            this.stopBtn.addEventListener('click', () => this.stopStreamingTurn());
        }
        
        this.sendTextBtn.addEventListener('click', () => this.sendTextMessage());
        this.textInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.sendTextMessage();
        });

        window.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') this.stopStreamingTurn();
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

    getSupportedMimeType() {
        const types = [
            'audio/webm;codecs=opus',
            'audio/webm',
            'audio/mp4',
            'audio/ogg;codecs=opus',
            'audio/wav'
        ];
        for (const t of types) {
            if (window.MediaRecorder && MediaRecorder.isTypeSupported(t)) {
                return t;
            }
        }
        return '';
    }

    async toggleMicrophone() {
        if (this.isRecording) {
            this.stopRecording();
        } else {
            await this.startRecording();
        }
    }

    async startRecording() {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            alert('WebSocket is disconnected. Reconnecting...');
            this.initWebSocket();
            return;
        }

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const mimeType = this.getSupportedMimeType();
            const options = mimeType ? { mimeType } : {};
            console.log('[Bhava App] Starting MediaRecorder with MIME:', mimeType || 'default');

            this.mediaRecorder = new MediaRecorder(stream, options);
            this.audioChunks = [];
            this.wasSpeaking = false;
            this.silenceStartTime = null;

            // Web Audio Analyser setup for real-time visualizer & PCM VAD
            if (!this.audioContext) {
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            }
            if (this.audioContext.state === 'suspended') {
                await this.audioContext.resume();
            }
            const source = this.audioContext.createMediaStreamSource(stream);
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 64;
            source.connect(this.analyser);

            this.mediaRecorder.ondataavailable = async (e) => {
                if (e.data && e.data.size > 0) {
                    this.audioChunks.push(e.data);
                    // Also stream live chunk over WebSocket for low latency buffer
                    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                        const arrayBuffer = await e.data.arrayBuffer();
                        this.ws.send(arrayBuffer);
                    }
                }
            };

            this.mediaRecorder.onstop = async () => {
                console.log('[Bhava App] MediaRecorder stopped. Total chunks collected:', this.audioChunks.length);
                if (stream) stream.getTracks().forEach(track => track.stop());

                if (this.audioChunks.length > 0) {
                    const completeBlob = new Blob(this.audioChunks, { type: mimeType || 'audio/webm' });
                    console.log('[Bhava App] Created complete audio Blob:', completeBlob.size, 'bytes');

                    if (completeBlob.size > 500) {
                        this.micStatusText.textContent = '⚡ Transcribing & Routing...';
                        
                        // Send complete audio blob over WebSocket or flush
                        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                            const buffer = await completeBlob.arrayBuffer();
                            this.ws.send(buffer);
                            this.ws.send(JSON.stringify({ type: 'flush_audio' }));
                        } else {
                            // REST fallback if WebSocket disconnected
                            this.uploadAudioBlobViaREST(completeBlob);
                        }
                    } else {
                        this.micStatusText.textContent = 'Click mic to speak';
                    }
                }
                this.audioChunks = [];
            };

            this.mediaRecorder.start(250);
            this.isRecording = true;
            this.micBtn.classList.add('recording');
            this.micStatusText.textContent = '🎙️ Listening... Speak now';
            this.drawVisualizer();

        } catch (err) {
            console.error('[Bhava App] Microphone Error:', err);
            alert('Microphone Access Error: ' + err.message);
        }
    }

    stopRecording() {
        if (this.mediaRecorder && this.isRecording) {
            console.log('[Bhava App] Manually stopping recording...');
            this.mediaRecorder.stop();
            this.isRecording = false;
            this.micBtn.classList.remove('recording');
            this.micStatusText.textContent = 'Processing turn...';
        }
    }

    async uploadAudioBlobViaREST(blob) {
        try {
            const formData = new FormData();
            formData.append('file', blob, 'recording.webm');
            console.log('[Bhava App] Sending audio blob via REST /api/transcribe...');
            const res = await fetch('/api/transcribe', { method: 'POST', body: formData });
            const data = await res.json();
            if (data.text) {
                console.log('[Bhava App] REST STT Transcribed Text:', data.text);
                this.appendUserMessage(data.text);
                // Send text input to prompt dialogue engine
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send(JSON.stringify({ type: 'text_input', text: data.text }));
                }
            }
        } catch (e) {
            console.error('[Bhava App] REST STT upload error:', e);
            alert('Audio STT Error: ' + e.message);
        }
    }

    sendTextMessage() {
        const text = this.textInput.value.trim();
        if (!text) return;
        
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            alert('WebSocket is disconnected. Reconnecting...');
            this.initWebSocket();
            return;
        }

        console.log('[Bhava App] Sending text input:', text);
        this.ws.send(JSON.stringify({ type: 'text_input', text: text }));
        this.textInput.value = '';
        this.micStatusText.textContent = 'Processing Query...';
    }

    handleServerMessage(data) {
        this.removePlaceholder();

        switch (data.type) {
            case 'session_init':
                this.sessionId = data.session_id;
                break;

            case 'vad_status':
                if (this.isRecording && !this.wasSpeaking) {
                    if (data.is_speech) {
                        this.micStatusText.textContent = `🗣️ Speech Detected (${Math.round(data.confidence * 100)}%)`;
                    }
                }
                break;

            case 'stt_result':
                this.appendUserMessage(data.text);
                break;

            case 'agent_thought':
                this.routingBanner.classList.remove('hidden');
                this.routerThought.textContent = data.thought;
                break;

            case 'agent_chunk':
                this.activeAgentName.textContent = `${data.agent} (${data.role})`;
                this.appendAgentChunk(data.agent, data.role, data.text, data.is_final);
                break;

            case 'audio_start':
                this.micStatusText.textContent = `🔊 ${data.agent || 'Agent'} is responding...`;
                break;

            case 'audio_chunk':
                this.enqueueAudioChunk(data.audio_b64, data.mime);
                break;

            case 'audio_end':
                if (this.isRecording) {
                    this.micStatusText.textContent = '🎙️ Listening for next turn...';
                } else {
                    this.micStatusText.textContent = 'Click mic to speak again';
                }
                break;

            case 'interrupted':
                this.stopAudioPlayback();
                this.micStatusText.textContent = '🛑 Turn Interrupted';
                break;

            case 'error':
                alert('Server Error: ' + data.message);
                this.micStatusText.textContent = 'Click mic to speak';
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

    stopStreamingTurn() {
        this.stopAudioPlayback();

        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'stop' }));
        }

        fetch('/api/stop', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: this.sessionId })
        }).catch(err => console.error('Error calling /api/stop:', err));

        this.micStatusText.textContent = '🛑 Interrupted';
        this.activeAgentName.textContent = 'Interrupted';
        if (this.currentAgentBubble) {
            const contentDiv = this.currentAgentBubble.querySelector('.msg-content');
            if (contentDiv) contentDiv.innerHTML += ' <em>[Interrupted by user]</em>';
            this.currentAgentBubble = null;
        }
    }

    stopAudioPlayback() {
        this.audioQueue = [];
        this.isPlayingAudio = false;
        if (this.currentPlayingAudio) {
            try {
                this.currentPlayingAudio.pause();
                this.currentPlayingAudio.currentTime = 0;
            } catch (e) {}
            this.currentPlayingAudio = null;
        }
    }

    playNextAudioInQueue() {
        if (this.isPlayingAudio || this.audioQueue.length === 0) return;

        this.isPlayingAudio = true;
        this.currentPlayingAudio = this.audioQueue.shift();

        this.currentPlayingAudio.onended = () => {
            this.isPlayingAudio = false;
            this.currentPlayingAudio = null;
            this.playNextAudioInQueue();
        };

        this.currentPlayingAudio.onerror = () => {
            this.isPlayingAudio = false;
            this.currentPlayingAudio = null;
            this.playNextAudioInQueue();
        };

        this.currentPlayingAudio.play().catch(e => {
            console.error('Audio playback error:', e);
            this.isPlayingAudio = false;
            this.currentPlayingAudio = null;
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

        // Real-time PCM Volume VAD
        let sum = 0;
        for (let i = 0; i < bufferLength; i++) {
            sum += dataArray[i];
        }
        const avgVolume = sum / bufferLength;

        const SPEECH_THRESHOLD = 8;
        const SILENCE_TIMEOUT_MS = 1200;

        if (avgVolume > SPEECH_THRESHOLD) {
            this.wasSpeaking = true;
            this.silenceStartTime = null;
            this.micStatusText.textContent = `🗣️ Speech Detected (Vol: ${Math.round(avgVolume)})`;
        } else if (this.wasSpeaking) {
            if (!this.silenceStartTime) {
                this.silenceStartTime = Date.now();
            } else {
                const silenceDuration = Date.now() - this.silenceStartTime;
                this.micStatusText.textContent = `⚡ Silence detected (${(silenceDuration / 1000).toFixed(1)}s)...`;

                if (silenceDuration >= SILENCE_TIMEOUT_MS) {
                    console.log('[Bhava App] Client VAD: 1.2s silence reached. Stopping recording turn...');
                    this.wasSpeaking = false;
                    this.silenceStartTime = null;
                    this.stopRecording();
                }
            }
        }

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
                if (data.active_providers.vad) this.vadSelect.value = data.active_providers.vad;
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
            vad_provider: this.vadSelect.value,
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
