import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Bhava Voice Multi-Agent API"
    debug: bool = True

    # Providers: "mock", "groq", "edge", "multi_agent"
    stt_provider: str = "groq"
    dialogue_provider: str = "multi_agent"
    tts_provider: str = "edge"

    # API Keys
    groq_api_key: str = ""
    gemini_api_key: str = ""
    openrouter_api_key: str = ""

    # Voice & Language defaults
    default_tts_voice: str = "en-US-AvaNeural"
    stt_language: str = "en"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
