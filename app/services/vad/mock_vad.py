from app.core.interfaces.vad import BaseVAD, VADResult


class MockVAD(BaseVAD):
    """
    Mock/Passthrough VAD provider for keyless testing and development.
    Always marks audio buffers as containing speech.
    """

    def __init__(self, always_speech: bool = True):
        self.always_speech = always_speech

    def reset(self) -> None:
        pass

    def process_chunk(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16000
    ) -> VADResult:
        if not audio_bytes:
            return VADResult(is_speech=False, confidence=0.0)
            
        return VADResult(
            is_speech=self.always_speech,
            confidence=1.0 if self.always_speech else 0.0,
            speech_start=False,
            speech_end=False
        )
