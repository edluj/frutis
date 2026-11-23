"""Arranque: python -m app [--demo] (desde la carpeta frontend/)."""
import argparse
import sys

from PySide6.QtWidgets import QApplication

from app import config as configuracion
from app import theme
from app.views.shell import VentanaPrincipal


def crear_datos(cfg: configuracion.Config):
    if cfg.demo:
        from app.datos.demo import DatosDemo
        return DatosDemo()
    from app.api_client import ApiClient
    from app.datos.api import DatosApi
    return DatosApi(ApiClient(cfg), cfg.terminal)


def main() -> int:
    parser = argparse.ArgumentParser(description="Frutis ERP + POS")
    parser.add_argument("--demo", action="store_true", help="usa datos de demostración en memoria, sin servidor")
    args, resto = parser.parse_known_args()
    cfg = configuracion.cargar(demo_forzado=args.demo)

    app = QApplication([sys.argv[0], *resto])
    app.setApplicationName("Frutis ERP + POS")
    theme.aplicar(app)
    ventana = VentanaPrincipal(crear_datos(cfg), cfg)
    ventana.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
