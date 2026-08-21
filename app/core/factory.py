import logging
from app.core.config import settings, Settings
from app.core.interfaces.stt import BaseSTT
from app.core.interfaces.dialogue import BaseDialogueEngine
from app.core.interfaces.tts import BaseTTS

from app.services.stt import GroqSTT, MockSTT
from app.services.dialogue import MultiAgentEngine, MockDialogueEngine
from app.services.tts import EdgeTTSProvider, MockTTS

logger = logging.getLogger(__name__)


class VoicePipelineFactory:
    """
    Factory to instantiate swappable STT, Dialogue Engine, and TTS modules.
    Allows easy switching of providers via environment variables or runtime parameters.
    """

    @staticmethod
    def create_stt(provider_name: str = None, app_settings: Settings = settings) -> BaseSTT:
        provider = (provider_name or app_settings.stt_provider).lower()
        logger.info(f"Initializing STT Provider: '{provider}'")

        if provider == "groq":
            if not app_settings.groq_api_key:
                logger.warning("GROQ_API_KEY is empty. Falling back to MockSTT.")
                return MockSTT()
            return GroqSTT(api_key=app_settings.groq_api_key, model_name="whisper-large-v3")
        elif provider == "mock":
            return MockSTT()
        else:
            logger.warning(f"Unknown STT provider '{provider}'. Falling back to MockSTT.")
            return MockSTT()

    @staticmethod
    def create_dialogue(provider_name: str = None, app_settings: Settings = settings) -> BaseDialogueEngine:
        provider = (provider_name or app_settings.dialogue_provider).lower()
        logger.info(f"Initializing Dialogue Provider: '{provider}'")

        if provider == "multi_agent":
            return MultiAgentEngine(api_key=app_settings.groq_api_key)
        elif provider == "mock":
            return MockDialogueEngine()
        else:
            logger.warning(f"Unknown Dialogue provider '{provider}'. Falling back to MockDialogueEngine.")
            return MockDialogueEngine()

    @staticmethod
    def create_tts(provider_name: str = None, app_settings: Settings = settings) -> BaseTTS:
        provider = (provider_name or app_settings.tts_provider).lower()
        logger.info(f"Initializing TTS Provider: '{provider}'")

        if provider == "edge":
            return EdgeTTSProvider(default_voice=app_settings.default_tts_voice)
        elif provider == "mock":
            return MockTTS()
        else:
            logger.warning(f"Unknown TTS provider '{provider}'. Falling back to MockTTS.")
            return MockTTS()
