from pydantic import Field

from b2b_shared.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field(default="negociacao-service")
    service_port: int = Field(default=5006)
    negociacao_auction_poll_interval_seconds: int = Field(default=5)


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
