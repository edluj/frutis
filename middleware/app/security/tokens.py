"""Tokens JWT firmados; la sesión expira tras session_minutes de inactividad."""
from datetime import UTC, datetime, timedelta

import jwt

from app.config import get_settings

ALGORITMO = "HS256"


def crear_token(id_usuario: int) -> str:
    settings = get_settings()
    ahora = datetime.now(UTC)
    claims = {
        "sub": str(id_usuario),
        "iat": ahora,
        "exp": ahora + timedelta(minutes=settings.session_minutes),
    }
    return jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm=ALGORITMO)


def leer_token(token: str) -> int | None:
    """Devuelve el id del usuario, o None si el token no es válido o ya expiró."""
    try:
        claims = jwt.decode(
            token,
            get_settings().jwt_secret.get_secret_value(),
            algorithms=[ALGORITMO],
            options={"require": ["exp", "sub"]},
        )
        return int(claims["sub"])
    except (jwt.PyJWTError, ValueError):
        return None
