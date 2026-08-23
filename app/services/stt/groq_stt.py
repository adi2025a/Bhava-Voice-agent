import logging
from typing import Optional
from groq import AsyncGroq
from app.core.interfaces.stt import BaseSTT

logger = logging.getLogger(__name__)


class GroqSTT(BaseSTT):
    """Speech-to-Text implementation using Groq Whisper API (whisper-large-v3)."""

    def __init__(self, api_key: str, model_name: str = "whisper-large-v3"):
        if not api_key:
            raise ValueError(
                "Groq API key is missing. Set GROQ_API_KEY in .env or switch STT_PROVIDER=mock"
            )
        self.client = AsyncGroq(api_key=api_key)
        self.model_name = model_name

    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "input_audio.webm",
        language: Optional[str] = "en"
    ) -> str:
        if not audio_bytes or len(audio_bytes) < 100:
            return ""

        candidate_models = [self.model_name]
        if "whisper-large-v3-turbo" not in candidate_models:
            candidate_models.append("whisper-large-v3-turbo")

        last_error = None
        for model in candidate_models:
            try:
                transcription = await self.client.audio.transcriptions.create(
                    file=(filename, audio_bytes),
                    model=model,
                    prompt="Voice assistant conversation transcription",
                    response_format="text",
                    language=language or "en"
                )
                text = transcription if isinstance(transcription, str) else transcription.text
                return text.strip()
            except Exception as e:
                logger.warning(f"Groq STT transcription attempt with model '{model}' failed: {e}")
                last_error = e

        logger.error(f"All Groq STT models failed: {last_error}", exc_info=True)
        raise last_error
