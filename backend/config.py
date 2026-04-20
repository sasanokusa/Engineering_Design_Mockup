from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Local School AI Minutes"
    data_dir: Path = Field(default=Path("./data"), alias="LOCAL_SCHOOL_AI_DATA_DIR")
    database_url: str | None = Field(default=None, alias="DATABASE_URL")

    llm_provider: str = Field(default="openai_compatible", alias="LLM_PROVIDER")
    llm_base_url: str = Field(default="http://localhost:8001/v1", alias="LLM_BASE_URL")
    llm_api_key: str = Field(default="local-dev-key", alias="LLM_API_KEY")
    llm_model: str = Field(default="gemma-4-e4b", alias="LLM_MODEL")
    llm_temperature: float = Field(default=0.1, alias="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=2048, alias="LLM_MAX_TOKENS")

    asr_provider: str = Field(default="whisper_cpp", alias="ASR_PROVIDER")
    asr_model_size: str = Field(default="base", alias="ASR_MODEL_SIZE")
    asr_language: str = Field(default="ja", alias="ASR_LANGUAGE")
    asr_device: str = Field(default="cpu", alias="ASR_DEVICE")
    asr_model_path: Path | None = Field(default=None, alias="ASR_MODEL_PATH")
    asr_whisper_cpp_binary: str = Field(default="whisper-cli", alias="ASR_WHISPER_CPP_BINARY")

    @property
    def resolved_data_dir(self) -> Path:
        return self.data_dir.expanduser().resolve()

    @property
    def resolved_upload_dir(self) -> Path:
        return self.resolved_data_dir / "uploads" / "audio"

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{self.resolved_data_dir / 'local_school_ai.db'}"

    @property
    def resolved_asr_model_path(self) -> Path:
        if self.asr_model_path:
            return self.asr_model_path.expanduser().resolve()
        return (Path("./models/whisper") / f"ggml-{self.asr_model_size}.bin").resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()

