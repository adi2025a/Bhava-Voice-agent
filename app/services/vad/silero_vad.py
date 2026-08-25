import logging
import numpy as np
import torch
from silero_vad import load_silero_vad
from app.core.interfaces.vad import BaseVAD, VADResult

logger = logging.getLogger(__name__)


class SileroVAD(BaseVAD):
    """
    State-of-the-art Neural Network Voice Activity Detector (Silero VAD).
    Uses a deep learning model trained on 6,000+ hours of speech and diverse background noise.
    Accurately distinguishes actual human speech from fan noise, AC hum, and keyboard clicks.
    """

    def __init__(
        self,
        threshold: float = 0.5,
        silence_duration_threshold_ms: float = 800.0
    ):
        self.threshold = threshold
        self.silence_duration_threshold_ms = silence_duration_threshold_ms
        self.is_currently_speaking = False
        self.silence_accumulator_ms = 0.0
        try:
            self.model = load_silero_vad()
            logger.info("Silero VAD Deep Learning Model initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to load Silero VAD model: {e}")
            self.model = None

    def reset(self) -> None:
        self.is_currently_speaking = False
        self.silence_accumulator_ms = 0.0
        if self.model and hasattr(self.model, "reset_states"):
            try:
                self.model.reset_states()
            except Exception:
                pass

    def process_chunk(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16000
    ) -> VADResult:
        if not audio_bytes or not self.model:
            return VADResult(is_speech=False, confidence=0.0)

        # Ignore container header bytes
        if audio_bytes.startswith(b'\x1a\x45\xdf\xa3'):
            return VADResult(is_speech=False, confidence=0.0)

        try:
            int16_samples = np.frombuffer(audio_bytes, dtype=np.int16)
            if len(int16_samples) == 0:
                return VADResult(is_speech=False, confidence=0.0)

            float_samples = int16_samples.astype(np.float32) / 32768.0
            tensor = torch.from_numpy(float_samples)

            speech_prob = self.model(tensor, sample_rate).item()
            is_speech = speech_prob >= self.threshold

            speech_start = False
            speech_end = False
            chunk_duration_ms = (len(int16_samples) / sample_rate) * 1000.0 if sample_rate > 0 else 250.0

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
                confidence=round(speech_prob, 2),
                speech_start=speech_start,
                speech_end=speech_end
            )
        except Exception as e:
            logger.debug(f"Silero VAD chunk evaluation fallback: {e}")
            return VADResult(is_speech=False, confidence=0.0)
