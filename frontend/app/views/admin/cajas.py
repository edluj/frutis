"""ADM-04 · Cajas, métodos de pago y dispositivos de la terminal (HU-41, HU-07a, HU-16a)."""
from PySide6.QtWidgets import QFrame, QInputDialog, QVBoxLayout

from app.datos import ErrorNegocio
from app.theme import C
from app.views.base import Contexto, PaginaBase
from app.widgets import (
    Alerta, Badge, Campo, Card, Celda, Col, Tabla, avisar, boton, casilla, columnas, combo, entrada, etiqueta, hbox,
)

MODELOS = ["[MODELO POR CONFIRMAR]"]


class CajasView(PaginaBase):
    def __init__(self, ctx: Contexto):
        super().__init__(ctx, "Administración", "Cajas, pagos y dispositivos",
                         estado="Modo demostración · sin servidor" if ctx.datos.es_demo else ctx.config.api_url,
                         punto=C.NARANJA if ctx.datos.es_demo else C.VERDE)
        c = self.intentar(ctx.datos.configuracion_cajas)
        if not c:
            self.terminar()
            return
        puede = ctx.sesion.puede("admin", "editar")
        cajas = Tabla([Col("Caja", estirar=True), Col("Terminal"), Col("IP"), Col("Estado")])
        cajas.poner_filas([[Celda(x["nombre"], True), x["terminal"], x["ip"],
                            Badge(x["estado"], "verde" if x["abierta"] else "gris")] for x in c["cajas"]])
        agregar = boton("+ Agregar caja", "secundario", self._agregar_caja)
        agregar.setVisible(ctx.sesion.puede("admin", "crear"))
        izq = Card("Cajas y terminales", derecha=[agregar]).agregar(
            cajas, etiqueta("Cada terminal solo puede tener una caja abierta a la vez.", "Muted"))

        metodos = Tabla([Col("Método", estirar=True), Col("Clave SAT"), Col("Entra al cajón"), Col("Genera cuenta por cobrar"),
                         Col("Activo", "centro")])
        filas = []
        for m in c["metodos"]:
            cb = casilla("", m["activo"])
            cb.setEnabled(puede and not m["es_efectivo"])
            cb.toggled.connect(lambda on, m=m: self.intentar(ctx.datos.activar_metodo, m["id_metodo"], on))
            filas.append([Celda(m["nombre"], True), m["clave_sat"], "Sí" if m["es_efectivo"] else "No",
                          "Sí" if m["es_credito"] else "No", cb])
        metodos.poner_filas(filas)
        der = Card("Métodos de pago").agregar(metodos)
        self.agregar(columnas(izq, der))

        d = c["dispositivos"]
        self.bascula_modelo = combo(MODELOS, d["bascula_modelo"])
        self.puerto = combo(["COM3 · 9600 baudios", "COM4 · 9600 baudios", "USB"], d["puerto"])
        self.impresora_modelo = combo(MODELOS, d["impresora_modelo"])
        self.papel = combo(["80 mm", "58 mm"], d["papel"])
        self.lector = combo(["Teclado (USB)", "Serie"], d["lector"])
        self.prueba_lector = entrada(placeholder="Escanea un código para probar")
        self.prueba_lector.returnPressed.connect(self._probar_lector)
        self.c_lector = Campo("Prueba de lectura", self.prueba_lector)
        bascula = _equipo("Báscula", Badge("Simulador", "naranja"), Campo("Modelo", self.bascula_modelo),
                          Campo("Puerto", self.puerto), boton("Leer peso de prueba", "secundario", self._probar_bascula))
        impresora = _equipo("Impresora de tickets", Badge("Simulador", "naranja"), Campo("Modelo", self.impresora_modelo),
                            Campo("Ancho de papel", self.papel),
                            boton("Imprimir ticket de prueba", "secundario", self._probar_impresora))
        guardar = boton("Guardar dispositivos", "primario", self._guardar)
        guardar.setEnabled(puede)
        lector = _equipo("Lector de códigos", Badge("Conectado", "verde"), Campo("Modo", self.lector), self.c_lector, guardar)
        self.agregar(Card("Dispositivos de la Caja 1").agregar(
            Alerta("Los modelos de báscula e impresora están pendientes de confirmar con el cliente (R-01, R-02). "
                   "Mientras tanto la caja usa el simulador.", "naranja"),
            hbox(bascula, impresora, lector, espacio=16)))
        self.terminar()

    def _agregar_caja(self) -> None:
        nombre, ok = QInputDialog.getText(self, "Agregar caja", "Nombre de la caja (ej. Caja 3 · Pasillo):")
        if not ok or not nombre.strip():
            return
        terminal, ok = QInputDialog.getText(self, "Agregar caja", "Terminal (ej. POS-3):")
        if not ok or not terminal.strip():
            return
        ip, ok = QInputDialog.getText(self, "Agregar caja", "IP de la terminal en la LAN:")
        if not ok:
            return
        try:
            self.intentar(self.ctx.datos.agregar_caja, nombre.strip(), terminal.strip().upper(), ip.strip(), mostrar_dialogo=False)
        except ErrorNegocio as exc:
            avisar(self, "Agregar caja", exc.mensaje, error=True)
            return
        self.ctx.navegar("adm.cajas")

    def _probar_bascula(self) -> None:
        peso = self.intentar(self.ctx.datos.leer_bascula)
        if peso is not None:
            avisar(self, "Báscula", f"Lectura del simulador: {peso:.3f} kg.\nCon el equipo real, prueba con la pesa patrón "
                   "de 1 kg (tolerancia ±0.005 kg).")

    def _probar_impresora(self) -> None:
        avisar(self, "Impresora", "Ticket de prueba enviado al simulador: se mostraría en pantalla en lugar de imprimirse.")

    def _probar_lector(self) -> None:
        codigo = self.prueba_lector.text().strip()
        prods = self.intentar(self.ctx.datos.productos_pos, codigo=codigo) or []
        if prods:
            self.prueba_lector.setText(f"{codigo} · {prods[0]['nombre']}")
            self.c_lector.error(None)
        else:
            self.c_lector.error("No hay un producto con ese código.")

    def _guardar(self) -> None:
        self.intentar(self.ctx.datos.guardar_dispositivos, dict(
            bascula_modelo=self.bascula_modelo.currentText(), puerto=self.puerto.currentText(),
            impresora_modelo=self.impresora_modelo.currentText(), papel=self.papel.currentText(),
            lector=self.lector.currentText()))
        if not self.aviso.isVisible():
            avisar(self, "Dispositivos", "Configuración guardada.")


def _equipo(titulo: str, estado, *campos) -> QFrame:
    marco = QFrame()
    marco.setObjectName("Equipo")
    marco.setStyleSheet(f"QFrame#Equipo {{ border: 1px solid {C.BORDE}; border-radius: 10px; background: white; }}")
    lay = QVBoxLayout(marco)
    lay.setContentsMargins(14, 14, 14, 14)
    lay.setSpacing(12)
    lay.addLayout(hbox(etiqueta(f"<b>{titulo}</b>", rico=True), "stretch", estado))
    for c in campos[:-1]:
        lay.addWidget(c)
    lay.addStretch(1)
    lay.addWidget(campos[-1])
    return marco
