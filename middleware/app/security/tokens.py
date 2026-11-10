"""Tokens JWT firmados; la sesión expira tras session_minutes de inactividad."""
from datetime import UTC, datetime, timedelta

import jwt

from app.config import get_settings

ALGORITMO = "HS256"


def crear_token(id_usuario: int, sesion_version: int) -> str:
    settings = get_settings()
    ahora = datetime.now(UTC)
    claims = {
        "sub": str(id_usuario),
        "ver": sesion_version,
        "iat": ahora,
        "exp": ahora + timedelta(minutes=settings.session_minutes),
    }
    return jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm=ALGORITMO)


def leer_token(token: str) -> tuple[int, int] | None:
    """Devuelve (id del usuario, versión de sesión), o None si el token no es válido o ya expiró."""
    try:
        claims = jwt.decode(
            token,
            get_settings().jwt_secret.get_secret_value(),
            algorithms=[ALGORITMO],
            options={"require": ["exp", "sub", "ver"]},
        )
        return int(claims["sub"]), int(claims["ver"])
    except (jwt.PyJWTError, ValueError, TypeError):
        return None
