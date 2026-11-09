"""Arranque: python -m app (desde la carpeta middleware/)."""
import logging

import uvicorn

from app.config import get_settings

LOOPBACK = "127.0.0.1"


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    tls = bool(settings.cert_path and settings.key_path)
    host = settings.bind_host
    if not tls and host != LOOPBACK:
        # Sin certificado no se expone a la red: token y contraseñas irían en claro.
        logging.warning("Sin FRUTIS_CERT_PATH/FRUTIS_KEY_PATH: escuchando solo en %s", LOOPBACK)
        host = LOOPBACK
    uvicorn.run(
        "app.main:app",
        host=host,
        port=settings.port,
        ssl_certfile=settings.cert_path or None,
        ssl_keyfile=settings.key_path or None,
    )


if __name__ == "__main__":
    main()
