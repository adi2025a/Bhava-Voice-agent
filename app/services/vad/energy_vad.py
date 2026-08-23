import struct
import math
import logging
from app.core.interfaces.vad import BaseVAD, VADResult

logger = logging.getLogger(__name__)


class EnergyVAD(BaseVAD):
    """
    Fast, modular Energy-based Voice Activity Detector (RMS threshold).
    Computes root-mean-square amplitude of audio frames to detect speech vs silence
    and identify trailing silence duration (end of speech turn).
    """

    def __init__(
        self,
        energy_threshold: float = 300.0,
        silence_duration_threshold_ms: float = 700.0
    ):
        self.energy_threshold = energy_threshold
        self.silence_duration_threshold_ms = silence_duration_threshold_ms
        self.is_currently_speaking = False
        self.silence_accumulator_ms = 0.0

    def reset(self) -> None:
        self.is_currently_speaking = False
        self.silence_accumulator_ms = 0.0

    def _calculate_rms(self, audio_bytes: bytes) -> float:
        """Calculate Root Mean Square (RMS) amplitude from 16-bit PCM bytes."""
        if not audio_bytes or len(audio_bytes) < 2:
            return 0.0

        # Attempt decoding 16-bit signed PCM samples
        sample_count = len(audio_bytes) // 2
        if sample_count == 0:
            return 0.0

        try:
            format_str = f"<{sample_count}h"
            samples = struct.unpack(format_str, audio_bytes[:sample_count * 2])
            sum_squares = sum(s * s for s in samples)
            rms = math.sqrt(sum_squares / sample_count)
            return rms
        except Exception:
            # Fallback for non-PCM container bytes (e.g. raw WebM frame header heuristics)
            non_zero = sum(1 for b in audio_bytes if b > 20)
            ratio = non_zero / len(audio_bytes)
            return ratio * 1000.0

    def process_chunk(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16000
    ) -> VADResult:
        if not audio_bytes:
            return VADResult(is_speech=False, confidence=0.0)

        rms = self._calculate_rms(audio_bytes)
        is_speech = rms >= self.energy_threshold
        confidence = min(1.0, rms / (self.energy_threshold * 2.0)) if is_speech else 0.0

        speech_start = False
        speech_end = False

        # Approximate chunk duration assuming 16-bit mono PCM
        chunk_duration_ms = (len(audio_bytes) / (2 * sample_rate)) * 1000.0 if sample_rate > 0 else 50.0

        if is_speech:
            if not self.is_currently_speaking:
                speech_start = True
                self.is_currently_speaking = True
            self.silence_accumulator_ms = 0.0
        else:
            if self.is_currently_speaking:
                self.silence_accumulator_ms += chunk_duration_ms
                if self.silence_accumulator_ms >= self.silence_duration_threshold_ms:
                    speech_end = True
                    self.is_currently_speaking = False
                    self.silence_accumulator_ms = 0.0

        return VADResult(
            is_speech=is_speech,
            confidence=confidence,
            speech_start=speech_start,
            speech_end=speech_end
        )
