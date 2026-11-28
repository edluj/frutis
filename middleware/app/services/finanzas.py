"""Reglas de Finanzas: clientes de crédito (HU-39), cobros (HU-38b), gastos (HU-26), dashboard (HU-27) y flujo (HU-37)."""
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import Connection
from sqlalchemy.exc import DBAPIError

from app.errores import ErrorNegocio
from app.repositories import auditoria
from app.repositories import finanzas as repositorio
from app.schemas.finanzas import (
    ClienteCredito, ClienteCreditoEntrada, ClienteCreditoPos, CobroEntrada, CobroRegistrado, ConceptoEgreso, Dashboard,
    Flujo, GastoEntrada, SemanaDashboard, SemanaFlujo,
)
from app.security.dependencias import UsuarioActual


def guardar_cliente(
    conn: Connection, datos: ClienteCreditoEntrada, usuario: UsuarioActual, ip: str | None,
    id_cliente: int | None = None,
) -> ClienteCredito:
    if id_cliente is not None and repositorio.cliente(conn, id_cliente, bloquear=True) is None:
        raise ErrorNegocio(404, "Cliente de crédito no encontrado.")
    valores = datos.model_dump(exclude={"rfc_fiscal"})
    valores["id_cliente"] = None
    if datos.rfc_fiscal:
        valores["id_cliente"] = repositorio.id_fiscal(conn, datos.rfc_fiscal)
        if valores["id_cliente"] is None:
            raise ErrorNegocio(409, "No hay datos fiscales con ese RFC.", "fiscal")
    if id_cliente is None:
        id_cliente = repositorio.insertar_cliente(conn, valores)
        accion, detalle = "cliente_credito_alta", f"{datos.nombre} · límite ${datos.limite_credito}"
    else:
        repositorio.actualizar_cliente(conn, id_cliente, valores)
        estatus = "Activo" if datos.activo else "Suspendido"
        accion, detalle = "cliente_credito_edicion", f"{datos.nombre} · {estatus} · límite ${datos.limite_credito}"
    auditoria.registrar(conn, "finanzas", accion, detalle, ip, usuario.id_usuario, usuario.usuario)
    salida = ClienteCredito(**repositorio.cliente(conn, id_cliente))
    conn.commit()
    return salida


def clientes_para_pos(conn: Connection) -> list[ClienteCreditoPos]:
    # Solo activos: un cliente suspendido no compra a crédito (sp_registrar_venta también lo rechaza).
    vence = date.today()
    return [
        ClienteCreditoPos(
            **{k: c[k] for k in ("id_cliente_credito", "nombre", "limite_credito", "debe", "dias_credito", "vencido")},
            disponible=max(c["limite_credito"] - c["debe"], Decimal("0.00")), vence=vence + timedelta(days=c["dias_credito"]),
        )
        for c in repositorio.listar_clientes(conn, None, True)
    ]


# ---------------------------------------------------------------- cobros (HU-38b)

ER_SIGNAL_EXCEPTION = 1644
# La caja del POS distingue débito y crédito; las pantallas de Finanzas solo dicen "Tarjeta".
METODO_BASE = {"Efectivo": "Efectivo", "Transferencia": "Transferencia", "Tarjeta": "Tarjeta de débito"}


def _metodo(conn: Connection, nombre: str) -> int:
    id_metodo = repositorio.id_metodo(conn, METODO_BASE[nombre])
    if id_metodo is None:
        raise ErrorNegocio(409, "Método de pago no disponible.", "metodo")
    return id_metodo


def registrar_cobro(conn: Connection, ticket: str, datos: CobroEntrada, usuario: UsuarioActual, ip: str | None) -> CobroRegistrado:
    """Abono de un cliente con sp_registrar_cobro, que valida el saldo y la caja."""
    id_cxc = repositorio.id_cxc(conn, ticket)
    if id_cxc is None:
        raise ErrorNegocio(404, "Ese ticket no tiene cuenta por cobrar.")
    id_caja = datos.id_caja if datos.metodo == "Efectivo" else None
    try:
        saldo = repositorio.registrar_cobro(conn, id_cxc, datos.monto, _metodo(conn, datos.metodo), id_caja, usuario.id_usuario)
    except DBAPIError as exc:
        conn.rollback()
        if exc.orig is not None and exc.orig.args and exc.orig.args[0] == ER_SIGNAL_EXCEPTION:
            raise ErrorNegocio(409, str(exc.orig.args[1]), "monto") from exc
        raise
    auditoria.registrar(conn, "finanzas", "cobro", f"{ticket} · ${datos.monto} · {datos.metodo} · saldo ${saldo}",
                        ip, usuario.id_usuario, usuario.usuario)
    conn.commit()
    return CobroRegistrado(saldo=saldo)


# ---------------------------------------------------------------- gastos (HU-26)

def registrar_gasto(conn: Connection, datos: GastoEntrada, usuario: UsuarioActual, ip: str | None) -> None:
    if datos.fecha > date.today():
        raise ErrorNegocio(409, "La fecha del gasto no puede ser futura.", "fecha")
    concepto = datos.concepto + (f" · {datos.detalle}" if datos.detalle else "")
    repositorio.registrar_gasto(conn, datos.fecha, concepto, datos.monto, _metodo(conn, datos.metodo), usuario.id_usuario)
    auditoria.registrar(conn, "finanzas", "gasto", f"{concepto} · ${datos.monto}", ip, usuario.id_usuario, usuario.usuario)
    conn.commit()


# ---------------------------------------------------------------- dashboard y flujo (HU-27, HU-37)

CERO = Decimal("0.00")
MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
SERVICIOS = {"Luz", "Agua", "Gas"}


def _mes(anio: int, mes: int) -> tuple[date, date]:
    inicio = date(anio, mes, 1)
    return inicio, date(anio + mes // 12, mes % 12 + 1, 1)


def _semanas(inicio: date, fin: date) -> list[tuple[int, int]]:
    """1 al 7, 8 al 14, 15 al 21 y 22 al último día del mes."""
    ultimo = (fin - timedelta(days=1)).day
    return [(1, 7), (8, 14), (15, 21), (22, ultimo)]


def _suma(eventos, *clases, dias: tuple[int, int] | None = None) -> Decimal:
    return sum((e["monto"] for e in eventos if e["clase"] in clases
                and (dias is None or dias[0] <= e["fecha"].day <= dias[1])), CERO)


def _ingresos(eventos, dias=None) -> Decimal:
    return _suma(eventos, "venta_cobrada", "venta_credito", dias=dias) - _suma(eventos, "devolucion_pagada",
                                                                                "devolucion_credito", dias=dias)


def _egresos(eventos, dias=None) -> Decimal:
    return _suma(eventos, "compra_contado", "compra_credito", "gasto", dias=dias)


def _margen(ingresos: Decimal, utilidad: Decimal) -> Decimal:
    return (utilidad / ingresos * 100).quantize(Decimal("0.1")) if ingresos else Decimal("0.0")


def dashboard(conn: Connection, anio: int, mes: int) -> Dashboard:
    """Base devengada: ingresos = ventas − devoluciones; egresos = compras recibidas + gastos operativos."""
    inicio, fin = _mes(anio, mes)
    eventos = repositorio.eventos(conn, inicio, fin)
    ingresos, compras, gastos = _ingresos(eventos), _suma(eventos, "compra_contado", "compra_credito"), _suma(eventos, "gasto")
    egresos = compras + gastos
    anterior = repositorio.eventos(conn, *_mes(anio - (mes == 1), 12 if mes == 1 else mes - 1))
    ing_ant = _ingresos(anterior)
    conceptos: dict[str, Decimal] = {}
    for e in eventos:
        if e["clase"] == "gasto":
            clave = "Luz, agua y gas" if e["concepto"] in SERVICIOS else e["concepto"]
            conceptos[clave] = conceptos.get(clave, CERO) + e["monto"]
    filas = [("Compras a proveedores", compras)] + sorted(conceptos.items(), key=lambda kv: -kv[1])
    return Dashboard(
        ingresos=ingresos, tickets=sum(1 for e in eventos if e["clase"] in ("venta_cobrada", "venta_credito")),
        compras=compras, gastos=gastos, egresos=egresos, utilidad=ingresos - egresos,
        margen=_margen(ingresos, ingresos - egresos), margen_anterior=_margen(ing_ant, ing_ant - _egresos(anterior)),
        semanas=[SemanaDashboard(semana=f"Sem {i}", ingresos=_ingresos(eventos, d), egresos=_egresos(eventos, d))
                 for i, d in enumerate(_semanas(inicio, fin), 1)],
        conceptos=[ConceptoEgreso(concepto=c, importe=i, pct=(i / egresos * 100).quantize(Decimal("0.1")) if egresos else CERO)
                   for c, i in filas if i],
    )


def _entradas(eventos, dias=None) -> Decimal:
    return _suma(eventos, "venta_cobrada", "cobro", dias=dias) - _suma(eventos, "devolucion_pagada", dias=dias)


def _salidas(eventos, dias=None) -> Decimal:
    # Un lote de contado se paga al recibirlo; los de crédito, con sus abonos (pago_proveedor).
    return _suma(eventos, "pago_proveedor", "compra_contado", "gasto", dias=dias)


def flujo(conn: Connection, anio: int, mes: int) -> Flujo:
    """Base efectivo: las ventas a crédito entran hasta que el cliente paga."""
    inicio, fin = _mes(anio, mes)
    eventos = repositorio.eventos(conn, inicio, fin)
    previos = repositorio.eventos(conn, None, inicio)
    corto = MESES_CORTOS[mes - 1]
    return Flujo(
        inicial=_entradas(previos) - _salidas(previos),
        ventas=_suma(eventos, "venta_cobrada") - _suma(eventos, "devolucion_pagada"),
        cobros=_suma(eventos, "cobro"),
        pagos_proveedores=_suma(eventos, "pago_proveedor", "compra_contado"),
        gastos=_suma(eventos, "gasto"),
        credito=_suma(eventos, "venta_credito") - _suma(eventos, "devolucion_credito"),
        semanas=[SemanaFlujo(semana=f"{d[0]} al {d[1]} {corto}", entradas=_entradas(eventos, d), salidas=_salidas(eventos, d))
                 for d in _semanas(inicio, fin)],
    )
