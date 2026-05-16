from pydantic import Field

from b2b_shared.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field(default="mercado-service")
    service_port: int = Field(default=5005)
    mercado_matching_tolerance_percent: float = Field(default=5.0)
    mercado_default_auction_duration_seconds: int = Field(default=120)


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
