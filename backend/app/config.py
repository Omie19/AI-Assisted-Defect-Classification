from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./quality_inspection.db"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    upload_dir: str = "./uploads"
    max_upload_bytes: int = 8 * 1024 * 1024
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
