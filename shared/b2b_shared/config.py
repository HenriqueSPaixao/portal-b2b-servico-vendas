from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class BaseServiceSettings(BaseSettings):
    """Configuração comum a qualquer microsserviço do domínio Vendas.

    Cada serviço pode estender adicionando seus próprios campos.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    service_name: str = Field(default="vendas-service")
    service_port: int = Field(default=8000)
    log_level: str = Field(default="INFO")

    database_url: str = Field(...)
    db_schema: str = Field(default="portal_b2b")

    kafka_bootstrap_servers: str = Field(...)
    kafka_client_id_prefix: str = Field(default="vendas")

    jwt_secret: str = Field(...)
    jwt_issuer: str = Field(default="portal-autenticacao")
    jwt_audience: str = Field(default="portal-b2b")
    jwt_clock_skew_seconds: int = Field(default=60)

    cors_allow_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:3005",
            "http://localhost:3006",
        ]
    )

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, v):
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v
