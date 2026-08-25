import logging
from typing import Optional
from groq import AsyncGroq
from app.core.interfaces.stt import BaseSTT

logger = logging.getLogger(__name__)


WHISPER_HALLUCINATIONS = [
    "captioning by",
    "subtitles by",
    "inclusivemedia",
    "subtext-berlin",
    "amara.org",
    "thank you for watching",
    "thanks for watching",
    "subscribe",
    "www.",
    ".com",
    ".org",
    "bbc news"
]


def clean_whisper_text(text: str) -> str:
    """Filter out known Whisper AI subtitle hallucination phrases when transcribing silent audio."""
    if not text:
        return ""
    text_lower = text.strip().lower()
    for phrase in WHISPER_HALLUCINATIONS:
        if phrase in text_lower:
            logger.info(f"Filtered Whisper hallucination phrase: '{text}'")
            return ""
    return text.strip()


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
        language: Optional[str] = None
    ) -> str:
        if not audio_bytes or len(audio_bytes) < 100:
            return ""

        from app.core.config import settings
        target_language = language or settings.stt_language or "hi"

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
                    language=target_language
                )
                raw_text = transcription if isinstance(transcription, str) else transcription.text
                clean_text = clean_whisper_text(raw_text)
                return clean_text
            except Exception as e:
                logger.warning(f"Groq STT transcription attempt with model '{model}' failed: {e}")
                last_error = e

        logger.error(f"All Groq STT models failed: {last_error}", exc_info=True)
        raise last_error
