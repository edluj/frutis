"""Hash PBKDF2-SHA256, mismo formato del prototipo y de database/seed.sql."""
import hashlib
import secrets

ITERACIONES = 210_000


def hash_password(password: str) -> str:
    sal = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(sal), ITERACIONES)
    return f"pbkdf2_sha256${ITERACIONES}${sal}${digest.hex()}"


def verificar_password(password: str, guardado: str) -> bool:
    try:
        algoritmo, iteraciones, sal, digest = guardado.strip().split("$", 3)
        if algoritmo != "pbkdf2_sha256":
            return False
        calculado = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(sal), int(iteraciones)
        ).hex()
    except (ValueError, TypeError):
        return False
    return secrets.compare_digest(calculado, digest)


# Se verifica contra este hash cuando el usuario no existe, para que el tiempo
# de respuesta no revele qué usuarios son válidos.
HASH_SENUELO = hash_password(secrets.token_hex(16))
