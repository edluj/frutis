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


# ---------------------------------------------------------------- autorización de devoluciones (SC-02)
# Comprobante de que un Administrador escribió su contraseña. Sirve solo para el
# cajero que la pidió y el ticket indicado, y vence pronto. No lleva "ver", así que
# no sirve como token de sesión; y un token de sesión no lleva "tipo", así que no
# sirve como autorización.

MINUTOS_AUTORIZACION = 5
TIPO_AUTORIZACION = "autorizacion_devolucion"


def crear_autorizacion(id_admin: int, usuario_admin: str, id_cajero: int, folio_venta: str) -> str:
    ahora = datetime.now(UTC)
    claims = {
        "sub": str(id_admin),
        "usr": usuario_admin,
        "tipo": TIPO_AUTORIZACION,
        "para": id_cajero,
        "folio": folio_venta,
        "iat": ahora,
        "exp": ahora + timedelta(minutes=MINUTOS_AUTORIZACION),
    }
    return jwt.encode(claims, get_settings().jwt_secret.get_secret_value(), algorithm=ALGORITMO)


def leer_autorizacion(token: str, id_cajero: int, folio_venta: str) -> tuple[int, str] | None:
    """Devuelve (id, usuario) del Administrador, o None si no corresponde a este cajero y ticket."""
    try:
        claims = jwt.decode(
            token,
            get_settings().jwt_secret.get_secret_value(),
            algorithms=[ALGORITMO],
            options={"require": ["exp", "sub", "usr", "tipo", "para", "folio"]},
        )
        if claims["tipo"] != TIPO_AUTORIZACION or claims["para"] != id_cajero or claims["folio"] != folio_venta:
            return None
        return int(claims["sub"]), str(claims["usr"])
    except (jwt.PyJWTError, ValueError, TypeError):
        return None
