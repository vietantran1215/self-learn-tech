import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    demo_mode: bool = True
    auth_secret: str = "local-development-only-change-me"
    demo_password: str = "learn-local"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    chat_model: str = "gpt-4.1-mini"
    chat_temperature: float | None = Field(default=None, ge=0, le=2)
    embedding_model: str = "text-embedding-3-small"
    max_pdf_pages: int = Field(default=2000, ge=1)
    kafka_bootstrap: str = "localhost:9092"
    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "self-learn-tech"
    data_dir: Path = Path("data")

settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)

# Pass .env-based tracing configuration to LangChain/LangSmith integrations.
os.environ["LANGSMITH_TRACING"] = str(settings.langsmith_tracing).lower()
os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
if settings.langsmith_api_key:
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
