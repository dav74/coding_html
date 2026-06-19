from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    OPENROUTER_API_KEY: str
    MODEL_NAME: str = "deepseek/deepseek-v4-flash"
    FRONTEND_ORIGIN: str = "http://localhost:5173"
    MAX_RETRIES: int = 2


settings = Settings()
