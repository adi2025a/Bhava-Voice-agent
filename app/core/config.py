import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Bhava Voice Multi-Agent API"
    debug: bool = True

    # Providers: "mock", "groq", "edge", "multi_agent", "energy"
    stt_provider: str = "groq"
    dialogue_provider: str = "multi_agent"
    tts_provider: str = "edge"
    vad_provider: str = "silero"

    # API Keys
    groq_api_key: str = ""
    gemini_api_key: str = ""
    openrouter_api_key: str = ""
    groq_llm_model: str = "groq/compound-mini"

    # Voice & Language defaults
    default_tts_voice: str = "hi-IN-SwaraNeural"
    stt_language: str = "hi"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
