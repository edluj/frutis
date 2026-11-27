"""Validación de forma en pantalla (respuesta inmediata al usuario).

La validación definitiva la hace el middleware con Pydantic (arquitectura, sección 5);
aquí solo se evita mandar peticiones que de seguro serán rechazadas.
"""
import re
from decimal import Decimal

from app.formato import leer_dinero

# RFC: 3 letras (moral, 12 caracteres) o 4 letras (física, 13), fecha AAMMDD y homoclave.
_RFC_MORAL = re.compile(r"^[A-ZÑ&]{3}\d{6}[A-Z\d]{3}$")
_RFC_FISICA = re.compile(r"^[A-ZÑ&]{4}\d{6}[A-Z\d]{3}$")
_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
_USUARIO = re.compile(r"^[\w.\-]+$")
_CP = re.compile(r"^\d{5}$")


def tipo_rfc(rfc: str) -> str | None:
    """'moral', 'fisica' o None si el formato no es válido."""
    rfc = (rfc or "").strip().upper()
    if _RFC_MORAL.match(rfc):
        return "moral"
    if _RFC_FISICA.match(rfc):
        return "fisica"
    return None


def error_rfc(rfc: str, solo_moral: bool = False) -> str | None:
    rfc = (rfc or "").strip().upper()
    if not rfc:
        return "El RFC es obligatorio."
    tipo = tipo_rfc(rfc)
    if solo_moral and tipo != "moral":
        return "El RFC debe tener 12 caracteres (persona moral)."
    if tipo is None:
        return "El RFC debe tener 12 caracteres (persona moral) o 13 (persona física)."
    return None


def error_correo(correo: str, obligatorio: bool = True) -> str | None:
    correo = (correo or "").strip()
    if not correo:
        return "El correo es obligatorio." if obligatorio else None
    if not _CORREO.match(correo) or len(correo) > 120:
        return "Ingresa el formato de correo correcto."
    return None


def error_usuario(usuario: str) -> str | None:
    usuario = (usuario or "").strip()
    if not usuario:
        return "El usuario es obligatorio."
    if len(usuario) > 50 or not _USUARIO.match(usuario):
        return "Solo letras, números, punto, guion y guion bajo (máximo 50)."
    return None


def error_cp(cp: str) -> str | None:
    return None if _CP.match((cp or "").strip()) else "El código postal tiene 5 dígitos."


def error_obligatorio(texto: str, nombre: str, maximo: int | None = None) -> str | None:
    texto = (texto or "").strip()
    if not texto:
        return f"{nombre} es obligatorio."
    if maximo and len(texto) > maximo:
        return f"Máximo {maximo} caracteres."
    return None


def monto_positivo(texto: str, mensaje: str = "Ingrese un monto válido.") -> tuple[Decimal | None, str | None]:
    """Devuelve (monto, error). El monto debe ser mayor a 0 y tener máximo 2 decimales."""
    valor = leer_dinero(texto)
    if valor is None or valor <= 0 or valor.as_tuple().exponent < -2:
        return None, mensaje
    return valor, None


def cantidad_positiva(texto: str, decimales: int = 3) -> Decimal | None:
    valor = leer_dinero((texto or "").replace("kg", "").replace("pza", ""))
    if valor is None or valor <= 0 or valor.as_tuple().exponent < -decimales:
        return None
    return valor
