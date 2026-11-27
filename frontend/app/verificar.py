"""Comprobación del ejecutable: `Frutis --verificar`.

PyInstaller solo incluye lo que ve importado, y shell.py abre las pantallas con importlib.
Esto entra como Administrador en modo demostración y abre cada pantalla de RUTAS, igual que
al usarlo; termina con 1 si alguna falla. Se corre sin monitor (QT_QPA_PLATFORM=offscreen).
"""
import traceback

# Pantallas que necesitan un dato para abrirse (folios y claves del modo demostración).
PARAMS = {"compras.lote": {"folio": "L-0235"}, "compras.estado": {"id_proveedor": 1},
          "fac.timbrada": {"folio": "F-0012"}, "fin.estado": {"id_cliente": 1}, "inv.movimientos": {"id_producto": 5}}
ADMINISTRADOR = "alopez"


def sin_dialogos() -> None:
    """Acepta los diálogos modales en lugar de esperar un clic."""
    from PySide6.QtWidgets import QMessageBox

    from app.views.pos import cobro

    def aceptar(caja):
        for b in caja.buttons():
            if caja.buttonRole(b) == QMessageBox.ButtonRole.AcceptRole:
                b.click()
                break
        return 0

    QMessageBox.exec = aceptar
    cobro.TicketDialogo.exec = lambda self: 0


def verificar() -> int:
    from PySide6.QtWidgets import QApplication

    from app import config, theme
    from app.datos.demo import PASSWORD_DEMO, DatosDemo
    from app.views.shell import RUTAS, VentanaPrincipal

    app = QApplication.instance() or QApplication(["frutis"])
    theme.aplicar(app)
    sin_dialogos()
    ventana = VentanaPrincipal(DatosDemo(), config.cargar(demo_forzado=True))
    ventana.login.usuario.setText(ADMINISTRADOR)
    ventana.login.password.setText(PASSWORD_DEMO)
    ventana.login._entrar()
    if ventana.shell is None:
        print("FALTA el inicio de sesión de demostración")
        return 1
    fallas = []
    for ruta in RUTAS:
        try:
            ventana.shell.navegar(ruta, **PARAMS.get(ruta, {}))
            if ventana.shell.ruta != ruta:
                fallas.append(f"{ruta}: no se abrió")
        except Exception:  # noqa: BLE001 - se reporta cualquier falla de la pantalla
            fallas.append(f"{ruta}:\n{traceback.format_exc()}")
    print(f"{len(RUTAS) - len(fallas)} de {len(RUTAS)} pantallas abiertas como {ADMINISTRADOR}")
    for f in fallas:
        print("FALTA", f)
    return 1 if fallas else 0
