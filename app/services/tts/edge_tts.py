import logging
from typing import AsyncGenerator, Optional
import edge_tts
from app.core.interfaces.tts import BaseTTS

logger = logging.getLogger(__name__)


class EdgeTTSProvider(BaseTTS):
    """
    100% Free Text-to-Speech provider powered by Microsoft Edge Neural Voices.
    Requires no API keys and delivers ultra-realistic speech audio.
    """

    def __init__(self, default_voice: str = "en-US-AvaNeural"):
        self.default_voice = default_voice

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None
    ) -> bytes:
        if not text.strip():
            return b""

        target_voice = voice or self.default_voice
        communicate = edge_tts.Communicate(text, target_voice)
        audio_data = bytearray()

        try:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data.extend(chunk["data"])
            return bytes(audio_data)
        except Exception as e:
            logger.error(f"EdgeTTS synthesis error: {e}", exc_info=True)
            raise e

    async def synthesize_stream(
        self,
        text_generator: AsyncGenerator[str, None],
        voice: Optional[str] = None
    ) -> AsyncGenerator[bytes, None]:
        target_voice = voice or self.default_voice
        
        # Buffer text chunks into speakable sentences/fragments to pass to TTS stream
        text_buffer = ""
        async for chunk_text in text_generator:
            text_buffer += chunk_text
            # If buffer contains punctuation (sentence end), synthesize that sentence segment
            if any(p in text_buffer for p in [".", "!", "?", "\n", ";", ", "]):
                if text_buffer.strip():
                    communicate = edge_tts.Communicate(text_buffer, target_voice)
                    async for audio_chunk in communicate.stream():
                        if audio_chunk["type"] == "audio":
                            yield audio_chunk["data"]
                text_buffer = ""

        # Flush any remaining text in buffer
        if text_buffer.strip():
            communicate = edge_tts.Communicate(text_buffer, target_voice)
            async for audio_chunk in communicate.stream():
                if audio_chunk["type"] == "audio":
                    yield audio_chunk["data"]
