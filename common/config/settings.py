"""Configuration settings module.

Uses pydantic-settings with multi-inheritance pattern (adapted from zypp monorepo)
to compose domain-specific settings classes into a single Settings instance.
All backends and projects import settings from here.
"""

import json
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Application-level settings."""

    APP_NAME: str = Field(default="akshat-ai-platform", alias="APP_NAME")
    APP_ENV: str = Field(default="development", alias="APP_ENV")
    APP_HOST: str = Field(default="0.0.0.0", alias="APP_HOST")
    APP_PORT: int = Field(default=8000, alias="APP_PORT")
    OCR_PROVIDER: str = Field(default="local", alias="OCR_PROVIDER")  # local (Baidu) or api (Gemini)


class DatabaseSettings(BaseSettings):
    """Database connection settings for Postgres, Qdrant, and Neo4j."""

    DATABASE_URL: str = Field(..., alias="DATABASE_URL")
    QDRANT_URL: str = Field(default="http://localhost:6333", alias="QDRANT_URL")
    QDRANT_API_KEY: Optional[str] = Field(default=None, alias="QDRANT_API_KEY")
    
    # Graph Database
    NEO4J_URL: str = Field(default="bolt://localhost:7687", alias="NEO4J_URL")
    NEO4J_USER: str = Field(default="neo4j", alias="NEO4J_USER")
    NEO4J_PASSWORD: str = Field(default="password", alias="NEO4J_PASSWORD")


class LLMSettings(BaseSettings):
    """LLM API keys for LiteLLM multi-provider routing."""

    GOOGLE_API_KEY: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    OPENROUTER_API_KEY: Optional[str] = Field(default=None, alias="OPENROUTER_API_KEY")
    OPENAI_API_KEY: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")


class InferenceSettings(BaseSettings):
    """Inference server connection settings."""

    INFERENCE_SERVER_URL: str = Field(
        default="http://localhost:8010", alias="INFERENCE_SERVER_URL"
    )
    CLASSIFIER_MODEL_PATH: str = Field(
        default="models/Arch-Router-1.5B-Q8_0.gguf", alias="CLASSIFIER_MODEL_PATH"
    )
    CLASSIFIER_IDLE_TIMEOUT: int = Field(
        default=300, alias="CLASSIFIER_IDLE_TIMEOUT"
    )


class ObservabilitySettings(BaseSettings):
    """Tracing and monitoring settings."""

    OTEL_SERVICE_NAME: str = Field(
        default="akshat-platform", alias="OTEL_SERVICE_NAME"
    )
    OTEL_EXPORTER_OTLP_ENDPOINT: str = Field(
        default="http://localhost:4317", alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    LANGSMITH_TRACING: bool = Field(default=False, alias="LANGSMITH_TRACING")
    LANGSMITH_API_KEY: Optional[str] = Field(default=None, alias="LANGSMITH_API_KEY")
    LANGSMITH_PROJECT: str = Field(
        default="akshat-platform", alias="LANGSMITH_PROJECT"
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


class Settings(
    AppSettings,
    DatabaseSettings,
    LLMSettings,
    InferenceSettings,
    ObservabilitySettings,
    RAGSettings,
    ProjectSettings,
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


settings = Settings()


def get_settings() -> Settings:
    """Helper function to fetch cached Settings instance (for compatibility)."""
    return settings
