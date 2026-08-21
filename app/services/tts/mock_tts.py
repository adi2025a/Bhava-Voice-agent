import wave
import io
from typing import AsyncGenerator, Optional
from app.core.interfaces.tts import BaseTTS


class MockTTS(BaseTTS):
    """Fallback Mock TTS that generates silent/sine audio bytes."""

    def _generate_silent_wav(self, duration_sec: float = 1.0) -> bytes:
        sample_rate = 16000
        num_samples = int(sample_rate * duration_sec)
        
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(b'\x00\x00' * num_samples)
        
        return buf.getvalue()

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None
    ) -> bytes:
        return self._generate_silent_wav(0.5)

    async def synthesize_stream(
        self,
        text_generator: AsyncGenerator[str, None],
        voice: Optional[str] = None
    ) -> AsyncGenerator[bytes, None]:
        async for _ in text_generator:
            yield self._generate_silent_wav(0.2)
