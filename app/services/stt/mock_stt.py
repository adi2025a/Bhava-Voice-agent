import random
from typing import Optional
from app.core.interfaces.stt import BaseSTT


class MockSTT(BaseSTT):
    """Fallback Mock STT for keyless testing and development."""

    MOCK_PHRASES = [
        "Hello assistant, can you tell me a story about space travel?",
        "What is the capital of France and what is it famous for?",
        "Can you write a short Python function to reverse a string?",
        "How does speech recognition and multi-agent routing work?",
        "Give me a quick update on today's weather forecast."
    ]

    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "input_audio.webm",
        language: Optional[str] = "en"
    ) -> str:
        if not audio_bytes:
            return ""
        # Return a randomly selected prompt simulating STT output
        return random.choice(self.MOCK_PHRASES)
