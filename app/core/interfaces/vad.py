from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel, Field


class VADResult(BaseModel):
    is_speech: bool = Field(..., description="True if voice activity is detected in the audio chunk")
    confidence: float = Field(1.0, description="Confidence score between 0.0 and 1.0")
    speech_start: bool = Field(False, description="True if speech onset was detected in this frame")
    speech_end: bool = Field(False, description="True if trailing silence after speech was detected")


class BaseVAD(ABC):
    """Abstract Base Class for Voice Activity Detection (VAD) services."""

    @abstractmethod
    def process_chunk(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16000
    ) -> VADResult:
        """
        Analyze an incoming audio chunk and return voice activity status.
        
        :param audio_bytes: Raw binary audio chunk (PCM/WAV/WebM).
        :param sample_rate: Sample rate in Hz.
        :return: VADResult object.
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset internal state/silence buffers for a new stream."""
        pass
