from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Contract Review Agent"
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4.1"
    openai_embedding_model: str = "text-embedding-3-small"

    resend_api_key: SecretStr | None = None
    resend_webhook_secret: SecretStr | None = None
    resend_base_url: str = "https://api.resend.com"

    database_url: str = "sqlite:///./data/app.db"
    qdrant_path: str = "./data/qdrant"
    storage_dir: str = "./data/storage"
    knowledge_dir: str = "./data/kb"
    samples_dir: str = "./data/samples"

    @property
    def storage_path(self) -> Path:
        return Path(self.storage_dir)

    @property
    def knowledge_path(self) -> Path:
        return Path(self.knowledge_dir)

    @property
    def qdrant_storage_path(self) -> Path:
        return Path(self.qdrant_path)

    @property
    def samples_path(self) -> Path:
        return Path(self.samples_dir)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

