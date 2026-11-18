"""ACC-02 · Ventana principal: menú lateral por rol (flujo B, HU-14) y navegación."""
import importlib

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QMainWindow, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from app.api_client import SesionExpirada
from app.config import Config
from app.datos import NoConectado
from app.iconos import icono, icono_doble
from app.sesion import Sesion
from app.theme import RECURSOS, C
from app.views.base import Contexto
from app.views.login import LoginView
from app.widgets import avisar, etiqueta, limpiar

# ruta -> (módulo de permisos, acción requerida, "paquete.modulo:Clase")
RUTAS = {
    "inicio": (None, "ver", "app.views.inicio:InicioView"),
    "pos.apertura": ("pos", "crear", "app.views.pos.apertura:AperturaView"),
    "pos.cobro": ("pos", "crear", "app.views.pos.cobro:CobroView"),
    "pos.corte": ("pos", "crear", "app.views.pos.corte:CorteView"),
    "pos.devolucion": ("pos", "crear", "app.views.pos.devolucion:DevolucionView"),
    "compras.proveedores": ("compras", "ver", "app.views.compras.proveedores:ProveedoresView"),
    "compras.lote_nuevo": ("compras", "crear", "app.views.compras.registrar_lote:RegistrarLoteView"),
    "compras.lotes": ("compras", "ver", "app.views.compras.lotes:LotesView"),
    "compras.lote": ("compras", "ver", "app.views.compras.detalle_lote:DetalleLoteView"),
    "compras.cxp": ("compras", "ver", "app.views.compras.cuentas_pagar:CuentasPagarView"),
    "compras.estado": ("compras", "ver", "app.views.compras.estado_cuenta:EstadoCuentaProveedorView"),
    "fac.generar": ("facturacion", "crear", "app.views.facturacion.generar:GenerarFacturaView"),
    "fac.timbrada": ("facturacion", "ver", "app.views.facturacion.timbrada:FacturaTimbradaView"),
    "fac.emitidas": ("facturacion", "ver", "app.views.facturacion.emitidas:FacturasEmitidasView"),
    "fac.clientes": ("facturacion", "ver", "app.views.facturacion.clientes:ClientesFiscalesView"),
    "fin.dashboard": ("finanzas", "ver", "app.views.finanzas.dashboard:DashboardView"),
    "fin.gastos": ("finanzas", "ver", "app.views.finanzas.gastos:GastosView"),
    "fin.flujo": ("finanzas", "ver", "app.views.finanzas.flujo:FlujoView"),
    "fin.clientes": ("finanzas", "ver", "app.views.finanzas.clientes_credito:ClientesCreditoView"),
    "fin.cxc": ("finanzas", "ver", "app.views.finanzas.cuentas_cobrar:CuentasCobrarView"),
    "fin.estado": ("finanzas", "ver", "app.views.finanzas.estado_cuenta:EstadoCuentaClienteView"),
    "inv.productos": ("inventario", "ver", "app.views.inventario.productos:ProductosView"),
    "inv.categorias": ("inventario", "ver", "app.views.inventario.categorias:CategoriasView"),
    "inv.existencias": ("inventario", "ver", "app.views.inventario.existencias:ExistenciasView"),
    "inv.lotes": ("inventario", "ver", "app.views.inventario.lotes:LotesCaducidadView"),
    "inv.movimientos": ("inventario", "ver", "app.views.inventario.movimientos:MovimientosView"),
    "inv.precios": ("inventario", "editar", "app.views.inventario.ajuste_precios:AjustePreciosView"),
    "inv.historial": ("inventario", "ver", "app.views.inventario.historial_precios:HistorialPreciosView"),
    "inv.mermas": ("inventario", "ver", "app.views.inventario.mermas:MermasView"),
    "reportes": ("reportes", "ver", "app.views.reportes:ReportesView"),
    "adm.usuarios": ("admin", "ver", "app.views.admin.usuarios:UsuariosView"),
    "adm.roles": ("admin", "ver", "app.views.admin.roles:RolesView"),
    "adm.auditoria": ("admin", "ver", "app.views.admin.auditoria:AuditoriaView"),
    "adm.cajas": ("admin", "ver", "app.views.admin.cajas:CajasView"),
}

# Submenú que aparece debajo del módulo activo.
SUBMENU = {
    "pos": [("Cobro", "pos.cobro"), ("Corte de caja", "pos.corte"), ("Devolución", "pos.devolucion")],
    "compras": [("Proveedores", "compras.proveedores"), ("Registrar lote", "compras.lote_nuevo"),
                ("Lotes de compra", "compras.lotes"), ("Cuentas por pagar", "compras.cxp")],
    "facturacion": [("Generar factura", "fac.generar"), ("Facturas emitidas", "fac.emitidas"),
                    ("Datos fiscales de clientes", "fac.clientes")],
    "finanzas": [("Dashboard financiero", "fin.dashboard"), ("Gastos operativos", "fin.gastos"),
                 ("Flujo de efectivo", "fin.flujo"), ("Clientes de crédito", "fin.clientes"),
                 ("Cuentas por cobrar", "fin.cxc")],
    "inventario": [("Productos", "inv.productos"), ("Categorías", "inv.categorias"), ("Existencias", "inv.existencias"),
                   ("Lotes y caducidades", "inv.lotes"), ("Mermas", "inv.mermas"), ("Ajuste de precios", "inv.precios"),
                   ("Historial de precios", "inv.historial")],
    "reportes": [],
    "admin": [("Usuarios", "adm.usuarios"), ("Roles y permisos", "adm.roles"), ("Auditoría", "adm.auditoria"),
              ("Cajas y dispositivos", "adm.cajas")],
}
INICIO_MODULO = {
    "compras": "compras.proveedores", "facturacion": "fac.generar", "finanzas": "fin.dashboard",
    "inventario": "inv.productos", "reportes": "reportes", "admin": "adm.usuarios",
}


def modulo_accesible(sesion: Sesion, modulo: str) -> bool:
    """Un módulo aparece en el menú si el rol puede abrir al menos una de sus pantallas."""
    rutas = [r for _, r in SUBMENU.get(modulo, [])] + [INICIO_MODULO.get(modulo, "")]
    return any(r in RUTAS and sesion.puede(RUTAS[r][0], RUTAS[r][1]) for r in rutas)


class BarraLateral(QFrame):
    def __init__(self, shell: "Shell"):
        super().__init__()
        self.shell = shell
        self.setObjectName("Sidebar")
        self.setFixedWidth(250)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(15, 20, 15, 22)
        self.lay.setSpacing(6)
        self.grupo = QButtonGroup(self)
        self.grupo.setExclusive(True)
        self.botones: dict[str, QPushButton] = {}
        self.subbotones: dict[str, QPushButton] = {}

    def construir(self, sesion: Sesion, modulo_activo: str | None, ruta_activa: str | None) -> None:
        limpiar(self.lay)
        self.grupo = QButtonGroup(self)
        self.botones.clear()
        self.subbotones.clear()

        avatar = etiqueta("")
        avatar.setPixmap(QPixmap(str(RECURSOS / "img" / "avatar.png")).scaled(
            52, 52, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        avatar.setStyleSheet("border: 2px solid white; border-radius: 28px;")
        avatar.setFixedSize(56, 56)
        marca = QVBoxLayout()
        marca.setSpacing(0)
        marca.addWidget(etiqueta("Frutis", "MarcaNombre"))
        marca.addWidget(etiqueta("ERP + POS", "MarcaSub"))
        cab = QHBoxLayout()
        cab.setContentsMargins(4, 0, 0, 18)
        cab.setSpacing(12)
        cab.addWidget(avatar)
        cab.addLayout(marca)
        cab.addStretch(1)
        self.lay.addLayout(cab)

        opciones = [("inicio", "Inicio", "inicio")] + sesion.modulos_menu
        for clave, nombre, ic in opciones:
            b = QPushButton(nombre)
            b.setObjectName("Nav")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setIcon(icono_doble(ic, "white", C.GUINDA, 22))
            b.setIconSize(QSize(22, 22))
            b.setChecked(clave == (modulo_activo or "inicio"))
            b.clicked.connect(lambda _=False, c=clave: self.shell.abrir_modulo(c))
            self.grupo.addButton(b)
            self.botones[clave] = b
            self.lay.addWidget(b)
            if clave == modulo_activo:
                for texto_, ruta in SUBMENU.get(clave, []):
                    mod, accion, _ = RUTAS[ruta]
                    if not sesion.puede(mod, accion):
                        continue
                    sb = QPushButton(texto_)
                    sb.setObjectName("SubNav")
                    sb.setCheckable(True)
                    sb.setCursor(Qt.CursorShape.PointingHandCursor)
                    sb.setChecked(ruta == ruta_activa or (ruta == "pos.cobro" and ruta_activa == "pos.apertura"))
                    sb.clicked.connect(lambda _=False, r=ruta: self.shell.navegar(r))
                    self.subbotones[ruta] = sb
                    self.lay.addWidget(sb)
        self.lay.addStretch(1)

        linea = QFrame()
        linea.setObjectName("SidebarLinea")
        self.lay.addWidget(linea)
        self.lay.addSpacing(10)
        pie = QVBoxLayout()
        pie.setContentsMargins(10, 0, 0, 0)
        pie.setSpacing(2)
        pie.addWidget(etiqueta(sesion.nombre_completo, "UsuarioNombre"))
        pie.addWidget(etiqueta(sesion.descripcion, "UsuarioRol"))
        self.lay.addLayout(pie)
        self.lay.addSpacing(14)
        salir = QPushButton("Cerrar sesión")
        salir.setObjectName("CerrarSesion")
        salir.setIcon(icono("salir", "white", 20))
        salir.setIconSize(QSize(20, 20))
        salir.setCursor(Qt.CursorShape.PointingHandCursor)
        salir.clicked.connect(self.shell.cerrar_sesion)
        self.lay.addWidget(salir)


class Shell(QWidget):
    """Barra lateral + área de la pantalla activa."""

    def __init__(self, ventana: "VentanaPrincipal", datos, sesion: Sesion, config: Config):
        super().__init__()
        self.ventana = ventana
        self.datos = datos
        self.sesion = sesion
        sesion.modulos_menu = [m for m in sesion.modulos_visibles() if modulo_accesible(sesion, m[0])]
        self.ctx = Contexto(datos, sesion, config, self.navegar, ventana.sesion_expirada,
                            self.actualizar_caja, self.olvidar, lambda r: self.paginas.get(r))
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.barra = BarraLateral(self)
        lay.addWidget(self.barra)
        self.pila = QStackedWidget()
        lay.addWidget(self.pila, 1)
        self.paginas: dict[str, QWidget] = {}
        self.ruta: str | None = None
        self.navegar("inicio")

    def abrir_modulo(self, modulo: str) -> None:
        if modulo == "inicio":
            self.navegar("inicio")
        elif modulo == "pos":
            self.navegar("pos")
        else:
            self.navegar(INICIO_MODULO[modulo])

    def navegar(self, ruta: str, **params) -> None:
        if ruta == "pos":
            ruta = self._ruta_pos()
        modulo, accion, destino = RUTAS[ruta]
        if modulo and not self.sesion.puede(modulo, accion):
            avisar(self, "Sin permiso", "Tu rol no tiene acceso a esta pantalla.", error=True)
            return
        anterior = self.paginas.get(ruta)
        if anterior is not None and getattr(anterior, "persistente", False):
            pagina = anterior
        else:
            ruta_mod, clase = destino.split(":")
            pagina = getattr(importlib.import_module(ruta_mod), clase)(self.ctx)
            if anterior is not None:
                self.pila.removeWidget(anterior)
                anterior.deleteLater()
            self.paginas[ruta] = pagina
            self.pila.addWidget(pagina)
        self.pila.setCurrentWidget(pagina)
        self.ruta = ruta
        self.barra.construir(self.sesion, modulo, ruta)
        pagina.al_mostrar(**params)

    def _ruta_pos(self) -> str:
        try:
            return "pos.cobro" if self.datos.caja_actual() else "pos.apertura"
        except NoConectado:
            return "pos.apertura"
        except SesionExpirada:
            self.ventana.sesion_expirada()
            return "inicio"

    def actualizar_caja(self) -> None:
        """La caja del pie del menú cambia al abrir o cerrar turno."""
        try:
            self.sesion.caja = self.datos.caja_de_sesion()
        except (NoConectado, SesionExpirada):
            self.sesion.caja = None
        self.barra.construir(self.sesion, RUTAS[self.ruta][0] if self.ruta else None, self.ruta)

    def olvidar(self, ruta: str) -> None:
        """Descarta una pantalla guardada (por ejemplo el cobro al cerrar la caja)."""
        pagina = self.paginas.pop(ruta, None)
        if pagina is not None:
            self.pila.removeWidget(pagina)
            pagina.deleteLater()

    def cerrar_sesion(self) -> None:
        cobro = self.paginas.get("pos.cobro")
        if cobro is not None and not cobro.carrito.vacio:
            from app.widgets import confirmar
            if not confirmar(self, "Venta en proceso", "Hay una venta en proceso. ¿Cerrar sesión y descartarla?",
                             "Cerrar sesión", peligro=True):
                return
        self.ventana.cerrar_sesion()


class VentanaPrincipal(QMainWindow):
    def __init__(self, datos, config: Config):
        super().__init__()
        self.datos = datos
        self.config = config
        self.setWindowTitle("Frutis ERP + POS")
        self.resize(1334, 896)
        self.setMinimumSize(1180, 760)
        self.pila = QStackedWidget()
        self.setCentralWidget(self.pila)
        self.login = LoginView(datos)
        self.login.sesion_iniciada.connect(self._entrar)
        self.pila.addWidget(self.login)
        self.shell: Shell | None = None

    def _entrar(self, perfil: dict) -> None:
        sesion = Sesion.desde_perfil(perfil)
        try:
            sesion.caja = self.datos.caja_de_sesion()
        except (NoConectado, SesionExpirada):
            sesion.caja = None
        self.shell = Shell(self, self.datos, sesion, self.config)
        self.pila.addWidget(self.shell)
        self.pila.setCurrentWidget(self.shell)

    def _salir_a_login(self) -> None:
        if self.shell is not None:
            self.pila.removeWidget(self.shell)
            self.shell.deleteLater()
            self.shell = None
        self.pila.setCurrentWidget(self.login)
        self.login.reiniciar()

    def cerrar_sesion(self) -> None:
        self.datos.logout()
        self._salir_a_login()

    def sesion_expirada(self) -> None:
        self._salir_a_login()
        self.login.campo_password.error("La sesión expiró por inactividad. Vuelve a iniciar sesión.")
