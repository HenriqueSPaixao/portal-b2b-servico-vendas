from dataclasses import dataclass
from typing import Any

from jose import JWTError, jwt


class JWTValidationError(Exception):
    pass


@dataclass(frozen=True)
class JWTValidator:
    secret: str
    issuer: str
    audience: str
    clock_skew_seconds: int = 60
    algorithm: str = "HS256"

    def decode(self, token: str) -> dict[str, Any]:
        try:
            return jwt.decode(
                token,
                self.secret,
                algorithms=[self.algorithm],
                audience=self.audience,
                issuer=self.issuer,
                options={"leeway": self.clock_skew_seconds},
            )
        except JWTError as exc:
            raise JWTValidationError(str(exc)) from exc
