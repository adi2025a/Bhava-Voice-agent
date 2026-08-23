from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel
from app.core.config import settings
from app.services.dialogue.multi_agent import AGENTS_CONFIG
from app.core.factory import VoicePipelineFactory

router = APIRouter(prefix="/api", tags=["System"])


class ConfigUpdateReq(BaseModel):
    stt_provider: str | None = None
    dialogue_provider: str | None = None
    tts_provider: str | None = None
    vad_provider: str | None = None
    default_tts_voice: str | None = None


@router.get("/status")
async def get_status():
    return {
        "status": "online",
        "app_name": settings.app_name,
        "active_providers": {
            "stt": settings.stt_provider,
            "dialogue": settings.dialogue_provider,
            "tts": settings.tts_provider,
            "vad": settings.vad_provider
        },
        "has_groq_key": bool(settings.groq_api_key)
    }


@router.get("/agents")
async def get_agents():
    return {
        "supervisor": {
            "name": "Supervisor Router",
            "role": "Evaluates user intent and dynamically routes turn to specialized agent."
        },
        "worker_agents": [
            {"name": name, "role": info["role"]} for name, info in AGENTS_CONFIG.items()
        ]
    }


@router.post("/config")
async def update_config(req: ConfigUpdateReq):
    if req.stt_provider:
        settings.stt_provider = req.stt_provider
    if req.dialogue_provider:
        settings.dialogue_provider = req.dialogue_provider
    if req.tts_provider:
        settings.tts_provider = req.tts_provider
    if req.vad_provider:
        settings.vad_provider = req.vad_provider
    if req.default_tts_voice:
        settings.default_tts_voice = req.default_tts_voice

    return {
        "message": "Configuration updated successfully",
        "active_providers": {
            "stt": settings.stt_provider,
            "dialogue": settings.dialogue_provider,
            "tts": settings.tts_provider,
            "vad": settings.vad_provider,
            "default_tts_voice": settings.default_tts_voice
        }
    }


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    stt_service = VoicePipelineFactory.create_stt()
    contents = await file.read()
    filename = file.filename or "input.webm"
    text = await stt_service.transcribe(contents, filename=filename)
    return {"text": text}


class StopReq(BaseModel):
    session_id: str | None = None


@router.post("/stop")
async def stop_turn(req: StopReq = None):
    from app.api.websocket import stop_active_session_turn, ACTIVE_SESSIONS
    
    stopped = False
    if req and req.session_id:
        stopped = stop_active_session_turn(req.session_id)
    else:
        # Cancel all active sessions if no specific session_id supplied
        for sess_id in list(ACTIVE_SESSIONS.keys()):
            if stop_active_session_turn(sess_id):
                stopped = True

    return {
        "status": "stopped" if stopped else "no_active_turn",
        "message": "Streaming response turn stopped successfully." if stopped else "No active streaming turn was running."
    }
