"""Configuration settings module.

Uses pydantic-settings with multi-inheritance pattern (adapted from zypp monorepo)
to compose domain-specific settings classes into a single Settings instance.
All backends and projects import settings from here.
"""

import logging
from pathlib import Path
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("common.config")


class AppSettings(BaseSettings):
    """Application-level settings."""

    APP_NAME: str = Field(default="contained-ai-platform", alias="APP_NAME")
    APP_ENV: str = Field(default="development", alias="APP_ENV")
    APP_HOST: str = Field(default="0.0.0.0", alias="APP_HOST")
    APP_PORT: int = Field(default=8000, alias="APP_PORT")
    OCR_PROVIDER: str = Field(default="local", alias="OCR_PROVIDER")  # local (Baidu) or api (Gemini)
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://127.0.0.1:5173", "http://127.0.0.1:5174"],
        alias="CORS_ORIGINS",
    )
    AUTH_ENABLED: bool = Field(default=False, alias="AUTH_ENABLED")
    MAX_UPLOAD_SIZE: int = Field(default=524288000, alias="MAX_UPLOAD_SIZE")  # 500 MB
    MAX_JSON_SIZE: int = Field(default=1048576, alias="MAX_JSON_SIZE")  # 1 MB
    TOXICITY_THRESHOLD: float = Field(default=0.1, alias="TOXICITY_THRESHOLD")
    TIMEOUT_GRACEFUL_SHUTDOWN: int = Field(default=15, alias="TIMEOUT_GRACEFUL_SHUTDOWN")
    PLATFORM_VERSION: str = Field(default="3.0.0", alias="PLATFORM_VERSION")
    MAX_RAM_MB: int = Field(default=16384, alias="MAX_RAM_MB")
    DEEPEVAL_MODEL: str = Field(default="gemini/gemini-3.5-flash", alias="DEEPEVAL_MODEL")
    EVALOPS_CONSUMER_ENABLED: bool = Field(default=False, alias="EVALOPS_CONSUMER_ENABLED")


class DatabaseSettings(BaseSettings):
    """Database connection settings for Postgres, Qdrant, and Neo4j."""

    DATABASE_URL: str = Field(..., alias="DATABASE_URL")
    QDRANT_URL: str = Field(default="http://localhost:6333", alias="QDRANT_URL")
    QDRANT_API_KEY: Optional[str] = Field(default=None, alias="QDRANT_API_KEY")
    REDIS_URL: str = Field(default="redis://localhost:6379", alias="REDIS_URL")
    
    # Qdrant
    QDRANT_TIMEOUT: float = Field(default=60.0, alias="QDRANT_TIMEOUT")
    QDRANT_RETRIES: int = Field(default=3, alias="QDRANT_RETRIES")

    # Graph Database
    NEO4J_URL: str = Field(default="bolt://localhost:7687", alias="NEO4J_URL")
    NEO4J_USER: str = Field(default="neo4j", alias="NEO4J_USER")
    NEO4J_PASSWORD: str = Field(default="password", alias="NEO4J_PASSWORD")

    # Kafka Messaging
    KAFKA_BOOTSTRAP_SERVERS: str = Field(
        default="localhost:9092", alias="KAFKA_BOOTSTRAP_SERVERS"
    )


class LLMSettings(BaseSettings):
    """LLM API keys for LiteLLM multi-provider routing."""

    GOOGLE_API_KEY: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    OPENROUTER_API_KEY: Optional[str] = Field(default=None, alias="OPENROUTER_API_KEY")
    OPENAI_API_KEY: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    GROQ_API_KEY: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    CEREBRAS_API_KEY: Optional[str] = Field(default=None, alias="CEREBRAS_API_KEY")


class InferenceSettings(BaseSettings):
    """Inference server connection settings."""

    INFERENCE_SERVER_URL: str = Field(
        default="http://localhost:8010", alias="INFERENCE_SERVER_URL"
    )
    INFERENCE_SERVER_PORT: int = Field(default=8010, alias="INFERENCE_SERVER_PORT")
    INFERENCE_TIMEOUT: float = Field(default=120.0, alias="INFERENCE_TIMEOUT")
    CLASSIFIER_MODEL_PATH: str = Field(
        default="models/Arch-Router-1.5B-Q8_0.gguf", alias="CLASSIFIER_MODEL_PATH"
    )
    CLASSIFIER_IDLE_TIMEOUT: int = Field(
        default=300, alias="CLASSIFIER_IDLE_TIMEOUT"
    )
    VRAM_BUDGET_MB: int = Field(default=8000, alias="VRAM_BUDGET_MB")
    HF_HOME: str = Field(default="~/.cache/huggingface/hub", alias="HF_HOME")
    DEVICE: str = Field(default="auto", alias="DEVICE")


class ObservabilitySettings(BaseSettings):
    """Tracing and monitoring settings."""

    LOG_LEVEL: str = Field(default="INFO", alias="LOG_LEVEL")
    OTEL_SERVICE_NAME: str = Field(
        default="contained-platform", alias="OTEL_SERVICE_NAME"
    )
    OTEL_EXPORTER_OTLP_ENDPOINT: str = Field(
        default="http://localhost:4317", alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    LANGSMITH_TRACING: bool = Field(default=False, alias="LANGSMITH_TRACING")
    LANGSMITH_API_KEY: Optional[str] = Field(default=None, alias="LANGSMITH_API_KEY")
    LANGSMITH_PROJECT: str = Field(
        default="contained-platform", alias="LANGSMITH_PROJECT"
    )
    LANGSMITH_ENDPOINT: str = Field(
        default="https://api.smith.langchain.com", alias="LANGSMITH_ENDPOINT"
    )


class RAGSettings(BaseSettings):
    """Retrieval settings for SyntraFlow RAG modes."""

    RAG_STRATEGY: str = Field(default="hybrid", alias="RAG_STRATEGY")  # vector, graph, hybrid


class ProjectSettings(BaseSettings):
    """Controls which project submodules are active (plug-and-play)."""

    ACTIVE_PROJECTS: list[str] = Field(
        default=["syntraflow", "guardroute", "evalops"],
        alias="ACTIVE_PROJECTS",
    )


class ModelOverrideSettings(BaseSettings):
    """Model selection overrides shorthand settings."""

    OCR_MODEL: str = Field(default="glm", alias="OCR_MODEL")
    ASR_MODEL: str = Field(default="sensevoice", alias="ASR_MODEL")
    EMBEDDING_MODEL: str = Field(default="jina", alias="EMBEDDING_MODEL")
    CLASSIFIER_MODEL: str = Field(default="arch", alias="CLASSIFIER_MODEL")
    COMPLETION_MODEL: str = Field(default="gemini", alias="COMPLETION_MODEL")


class Settings(
    AppSettings,
    DatabaseSettings,
    LLMSettings,
    InferenceSettings,
    ObservabilitySettings,
    RAGSettings,
    ProjectSettings,
    ModelOverrideSettings,
):
    """Combined settings for the entire platform.

    Composed via multi-inheritance (same pattern as zypp monorepo).
    Add new settings classes as parents here when adding features.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_settings(self) -> "Settings":
        # 1. Fail-fast / check required settings.
        # Enforce that DATABASE_URL is an asyncpg URL
        if not self.DATABASE_URL.startswith("postgresql+asyncpg://"):
            raise ValueError(
                f"DATABASE_URL must start with 'postgresql+asyncpg://' for async database operations. "
                f"Got: '{self.DATABASE_URL}'"
            )

        # Enforce QDRANT_API_KEY in production if specified
        if self.APP_ENV == "production" and not self.QDRANT_API_KEY:
            raise ValueError("QDRANT_API_KEY is required in production environment.")

        # 2. Log warnings for optional but recommended settings.
        recommended_vars = {
            "GOOGLE_API_KEY": "Required for primary completion model (Gemini)",
            "OPENROUTER_API_KEY": "Required for fallback tier compatibility",
            "GROQ_API_KEY": "Required for Groq provider integration",
            "CEREBRAS_API_KEY": "Required for Cerebras provider integration",
            "OPENAI_API_KEY": "Required by DeepEval QA tests",
        }
        for var_name, description in recommended_vars.items():
            if not getattr(self, var_name, None):
                logger.warning(
                    f"Optional but recommended environment variable '{var_name}' is missing. "
                    f"Description: {description}"
                )

        # 3. Validate ACTIVE_PROJECTS entries against available project directories.
        root_dir = Path(__file__).resolve().parent.parent.parent
        projects_dir = root_dir / "projects"

        if projects_dir.exists() and projects_dir.is_dir():
            existing_projects = {p.name for p in projects_dir.iterdir() if p.is_dir()}
            for project in self.ACTIVE_PROJECTS:
                if project not in existing_projects:
                    raise ValueError(
                        f"Project '{project}' listed in ACTIVE_PROJECTS but directory "
                        f"'{projects_dir / project}' does not exist. Available projects: {list(existing_projects)}"
                    )
        else:
            logger.warning(
                f"Projects directory '{projects_dir}' could not be located. "
                "Skipping ACTIVE_PROJECTS validation against local directories."
            )

        return self

    # --- Lowercase Compatibility Properties for Submodules ---
    @property
    def app_env(self) -> str:
        return self.APP_ENV

    @property
    def app_port(self) -> int:
        return self.APP_PORT

    @property
    def app_host(self) -> str:
        return self.APP_HOST

    @property
    def database_url(self) -> str:
        return self.DATABASE_URL

    @property
    def qdrant_url(self) -> str:
        return self.QDRANT_URL

    @property
    def qdrant_api_key(self) -> Optional[str]:
        return self.QDRANT_API_KEY

    @property
    def openrouter_api_key(self) -> Optional[str]:
        return self.OPENROUTER_API_KEY

    @property
    def openai_api_key(self) -> Optional[str]:
        return self.OPENAI_API_KEY

    @property
    def host(self) -> str:
        return self.APP_HOST

    @property
    def port(self) -> int:
        return self.APP_PORT

    @property
    def log_level(self) -> str:
        return self.LOG_LEVEL

    @property
    def vram_budget_mb(self) -> int:
        return self.VRAM_BUDGET_MB

    @property
    def platform_version(self) -> str:
        return self.PLATFORM_VERSION

    @property
    def max_ram_mb(self) -> int:
        return self.MAX_RAM_MB


settings = Settings()


def get_settings() -> Settings:
    """Helper function to fetch cached Settings instance (for compatibility)."""
    return settings

