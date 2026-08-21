from fastapi import APIRouter
from pydantic import BaseModel
from app.core.config import settings
from app.services.dialogue.multi_agent import AGENTS_CONFIG

router = APIRouter(prefix="/api", tags=["System"])


class ConfigUpdateReq(BaseModel):
    stt_provider: str | None = None
    dialogue_provider: str | None = None
    tts_provider: str | None = None
    default_tts_voice: str | None = None


@router.get("/status")
async def get_status():
    return {
        "status": "online",
        "app_name": settings.app_name,
        "active_providers": {
            "stt": settings.stt_provider,
            "dialogue": settings.dialogue_provider,
            "tts": settings.tts_provider
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
    if req.default_tts_voice:
        settings.default_tts_voice = req.default_tts_voice

    return {
        "message": "Configuration updated successfully",
        "active_providers": {
            "stt": settings.stt_provider,
            "dialogue": settings.dialogue_provider,
            "tts": settings.tts_provider,
            "default_tts_voice": settings.default_tts_voice
        }
    }
