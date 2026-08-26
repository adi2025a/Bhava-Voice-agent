# Bhava 3 (Bhava Voice Multi-Agent API)

**Bhava 3** is a real-time, modular, multi-agent voice pipeline built on FastAPI, WebSockets, Silero VAD, Groq STT (Whisper), Multi-Agent Dialogue orchestrations, and Edge TTS. It features interactive streaming, real-time voice activity detection, multi-agent dialogue routing, and web UI streaming dashboard capabilities.

---

## 🌟 Key Features

- **Voice Activity Detection (VAD)**: Powered by Silero VAD (ONNX) for real-time speech boundary detection.
- **Speech-to-Text (STT)**: High-speed transcription via Groq (Whisper Models) with support for fallback/mock providers.
- **Multi-Agent Dialogue Engine**: Orchestrates conversations using Groq / Gemini / OpenRouter models.
- **Text-to-Speech (TTS)**: Low-latency audio synthesis using `edge-tts` (Microsoft Edge Neural Voices) with configurable voices (e.g. `hi-IN-SwaraNeural`, `en-US-AvaNeural`).
- **WebSocket Streaming (`/ws/voice`)**: Duplex audio streaming for real-time interactive voice conversations.
- **REST Endpoints**: Comprehensive endpoints for standalone STT, TTS synthesis, agent configuration, and status checks.
- **Built-in Web Dashboard**: Static dashboard hosted directly via FastAPI (`/`) for instant browser testing.

---

## 🏗 Architecture & Project Structure

```text
Bhava 3/
├── app/
│   ├── api/
│   │   ├── routes.py       # REST API endpoints (TTS, STT, status, agents)
│   │   └── websocket.py    # WebSocket audio streaming pipeline & session handling
│   ├── core/
│   │   └── config.py       # Pydantic Settings & environment variable configurations
│   ├── services/
│   │   ├── dialogue/       # Multi-agent orchestrators and providers
│   │   ├── stt/            # Speech-to-text service implementations (Groq, Mock)
│   │   ├── tts/            # Text-to-speech engine wrapper (Edge-TTS, Mock)
│   │   └── vad/            # Silero VAD processor & chunk boundary detection
│   ├── static/             # Web browser UI & static frontend assets
│   └── main.py             # FastAPI Application entry point
├── .env.example            # Environment variables configuration template
├── pyproject.toml          # UV / Python dependency definition
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.12+**
- Recommended tool: [`uv`](https://github.com/astral-sh/uv) or standard `pip` / `venv`.

### 1. Installation

Using `uv` (Recommended):
```bash
uv sync
```

Using standard `pip`:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Environment Configuration

Copy `.env.example` to `.env` and fill in your API credentials:

```bash
cp .env.example .env
```

Edit `.env`:
```ini
# Provider Settings: "mock" or real providers ("groq", "edge", "multi_agent")
STT_PROVIDER=groq
DIALOGUE_PROVIDER=multi_agent
TTS_PROVIDER=edge
VAD_PROVIDER=silero

# API Keys
GROQ_API_KEY=your_groq_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Default Voice and Language
DEFAULT_TTS_VOICE=hi-IN-SwaraNeural
STT_LANGUAGE=hi
```

---

## 💻 Running the Application

Start the server using `uvicorn`:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Or execute directly with Python:

```bash
python -m app.main
```

Once running:
- **Web Dashboard**: Access [`http://localhost:8000`](http://localhost:8000) in your browser.
- **Interactive OpenAPI Specs**: Access [`http://localhost:8000/docs`](http://localhost:8000/docs).
- **WebSocket Endpoint**: `ws://localhost:8000/ws/voice`

---

## 📡 API & WebSocket Usage

### WebSockets (`/ws/voice`)
Connect to the interactive audio streaming pipeline:
- **Client -> Server**: Send raw audio frames / JSON control frames.
- **Server -> Client**: Streams VAD status, live transcribed text, and output audio chunks (MP3/PCM).

### REST Endpoints
- `GET /health` or `GET /api/status` - Health check & active service metadata.
- `POST /api/tts` - Convert input text into audio file response.
- `POST /api/stt` - Upload an audio snippet for transcription.

---

## 📜 License

This project is open source and available under standard software licensing terms.
