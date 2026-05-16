from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
