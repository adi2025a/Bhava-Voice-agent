from abc import ABC, abstractmethod
from typing import Optional


class BaseSTT(ABC):
    """Abstract Base Class for Speech-To-Text services."""

    @abstractmethod
    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "input_audio.webm",
        language: Optional[str] = "en"
    ) -> str:
        """
        Transcribe raw audio bytes into text.
        
        :param audio_bytes: Raw binary audio data (WebM, WAV, MP3, PCM).
        :param filename: Filename with extension matching the audio format.
        :param language: ISO language code (e.g., 'en').
        :return: Transcribed text string.
        """
        pass
