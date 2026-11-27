"""Recorrido de pantallas en modo demostración: cada rol abre lo que su matriz permite.

Las pantallas se crean sin monitor (offscreen). Los diálogos modales se reemplazan para
que la prueba no se quede esperando un clic.
"""
from decimal import Decimal as D

import pytest

from app import config
from app.datos.demo import DatosDemo, PASSWORD_DEMO
from app.verificar import PARAMS
from app.views.shell import RUTAS, VentanaPrincipal


@pytest.fixture
def ventana(qapp, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    def aceptar(caja):  # en lugar de esperar el clic del usuario, acepta el diálogo
        for b in caja.buttons():
            if caja.buttonRole(b) == QMessageBox.ButtonRole.AcceptRole:
                b.click()
                break
        return 0

    monkeypatch.setattr(QMessageBox, "exec", aceptar)
    from app.views.pos import cobro
    monkeypatch.setattr(cobro.TicketDialogo, "exec", lambda self: 0)
    v = VentanaPrincipal(DatosDemo(), config.cargar(True))
    v.resize(1334, 896)
    return v


def entrar(v, usuario):
    v.login.usuario.setText(usuario)
    v.login.password.setText(PASSWORD_DEMO)
    v.login._entrar()
    assert v.shell is not None, f"no entró {usuario}"
    return v.shell


def test_login_incorrecto_muestra_el_mensaje_del_apr(ventana):
    ventana.login.usuario.setText("mperez")
    ventana.login.password.setText("mala")
    ventana.login._entrar()
    assert ventana.shell is None
    assert ventana.login.campo_password.msg.text() == "Ingrese un usuario/contraseña correcta."


def test_usuario_inactivo_no_entra(ventana):
    ventana.login.usuario.setText("lgomez")
    ventana.login.password.setText(PASSWORD_DEMO)
    ventana.login._entrar()
    assert ventana.shell is None


@pytest.mark.parametrize("usuario", ["alopez", "mperez", "cruiz"])
def test_cada_rol_abre_solo_sus_pantallas(ventana, usuario):
    sh = entrar(ventana, usuario)
    permitidas = 0
    for ruta, (modulo, accion, _) in RUTAS.items():
        if modulo and not sh.sesion.puede(modulo, accion):
            continue
        sh.navegar(ruta, **PARAMS.get(ruta, {}))
        assert sh.ruta in (ruta, "pos.cobro", "pos.apertura")
        permitidas += 1
    assert permitidas > 3


def test_menu_por_rol(ventana):
    sh = entrar(ventana, "mperez")
    claves = [m[0] for m in sh.sesion.modulos_menu]
    assert claves == ["pos", "inventario"]  # matriz del Cajero en seed.sql


def test_cobro_en_efectivo_de_punta_a_punta(ventana):
    sh = entrar(ventana, "mperez")
    sh.navegar("pos")
    cobro = sh.paginas["pos.cobro"]
    datos = ventana.datos
    datos.peso_simulado = D("1.250")
    manzana = next(p for p in cobro.productos if p["nombre"] == "Manzana Gala")
    cobro._agregar(manzana)  # toque 1
    assert cobro.lbl_total.text() == "$52.50"
    cobro._elegir_metodo("Efectivo")  # toque 2
    cobro.recibido.setText("100")
    assert "47.50" in cobro.lbl_cambio.text()
    existencia_antes = datos.existencia(1)
    cobro._cobrar()  # toque 3
    assert cobro.carrito.vacio
    assert cobro.ultima_venta["cambio"] == D("47.50")
    assert datos.existencia(1) == existencia_antes - D("1.250")


def test_monto_insuficiente(ventana):
    sh = entrar(ventana, "mperez")
    sh.navegar("pos")
    cobro = sh.paginas["pos.cobro"]
    cobro._agregar(next(p for p in cobro.productos if p["unidad_venta"] == "pza"))
    cobro.recibido.setText("1")
    cobro._cobrar()
    assert cobro.error_cobro.text() == "El monto recibido es insuficiente."
    assert not cobro.carrito.vacio


def test_corte_y_apertura(ventana):
    sh = entrar(ventana, "mperez")
    sh.navegar("pos.corte")
    corte = sh.paginas["pos.corte"]
    corte.contado.setText("10650")
    corte._cerrar()  # falta observación
    assert "obligatorias" in corte.campo_obs.msg.text()
    corte.obs.setPlainText("Faltante por cambio mal entregado")
    corte._cerrar()
    assert sh.ruta == "pos.apertura"
    apertura = sh.paginas["pos.apertura"]
    list(apertura.piezas.values())[1].setValue(5)  # 5 × $200
    apertura._abrir()
    assert sh.ruta == "pos.cobro"
    assert ventana.datos.turno["fondo"] == D("1000")


def test_devolucion_requiere_administrador(ventana):
    sh = entrar(ventana, "mperez")
    sh.navegar("pos.devolucion", folio="V00001031")
    dev = sh.paginas["pos.devolucion"]
    cb, cant, estado, _ = dev.filas[0]
    cb.setChecked(True)
    cant.setText("0.500")
    assert not dev.btn_procesar.isEnabled()
    dev.pass_admin.setText("mala")
    dev._autorizar()
    assert not dev.btn_procesar.isEnabled()
    dev.pass_admin.setText(PASSWORD_DEMO)
    dev._autorizar()
    assert dev.btn_procesar.isEnabled()


def test_verificacion_del_ejecutable_abre_todas_las_pantallas(qapp, capsys):
    # El ejecutable corre esta misma comprobación con --verificar (CI del frontend).
    from app.verificar import verificar
    assert verificar() == 0, capsys.readouterr().out
