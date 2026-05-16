from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from b2b_shared.auth.jwt import JWTValidationError, JWTValidator

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    sub: UUID
    empresa_id: UUID | None
    email: str | None
    nome: str | None
    role: str | None
    raw_claims: dict


def _get_validator(request: Request) -> JWTValidator:
    validator = getattr(request.app.state, "jwt_validator", None)
    if validator is None:
        raise RuntimeError(
            "JWTValidator não foi configurado em app.state.jwt_validator"
        )
    return validator


def require_user(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
    ],
) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token ausente",
            headers={"WWW-Authenticate": "Bearer"},
        )

    validator = _get_validator(request)
    try:
        claims = validator.decode(credentials.credentials)
    except JWTValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token inválido: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        sub = UUID(str(claims["sub"]))
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Claim 'sub' inválida ou ausente",
        ) from exc

    empresa_raw = claims.get("empresa_id")
    empresa_id = UUID(str(empresa_raw)) if empresa_raw else None

    return CurrentUser(
        sub=sub,
        empresa_id=empresa_id,
        email=claims.get("email"),
        nome=claims.get("name") or claims.get("nome"),
        role=claims.get("role"),
        raw_claims=claims,
    )
