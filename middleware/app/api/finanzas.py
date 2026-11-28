from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query, Request, status
from sqlalchemy import Connection

from app.api.auth import ip_de
from app.db import get_conn
from app.errores import ErrorNegocio
from app.schemas.pos import PATRON_FOLIO_VENTA
from app.repositories import finanzas as repositorio
from app.schemas.finanzas import (
    CajaAbierta, ClienteCredito, ClienteCreditoEntrada, CobroEntrada, CobroRegistrado, ConceptoGasto, CuentaPorCobrar,
    Dashboard, Flujo, Gasto, GastoEntrada, MovimientoCliente,
)
from app.security.dependencias import UsuarioActual, requiere
from app.security.sanitizar import PATRON_TEXTO_SEGURO
from app.services import finanzas as servicio

router = APIRouter(prefix="/finanzas", tags=["finanzas"])

ESTATUS = {"activos": True, "suspendidos": False, "todos": None}


# ---------------------------------------------------------------- clientes de crédito (HU-39)

@router.get("/clientes-credito", response_model=list[ClienteCredito],
            dependencies=[Depends(requiere("finanzas", "ver"))])
def clientes_credito(
    busqueda: Annotated[str | None, Query(max_length=150, pattern=PATRON_TEXTO_SEGURO)] = None,
    estatus: Literal["activos", "suspendidos", "todos"] = "todos",
    conn: Connection = Depends(get_conn),
):
    return repositorio.listar_clientes(conn, busqueda, ESTATUS[estatus])


@router.post("/clientes-credito", response_model=ClienteCredito, status_code=status.HTTP_201_CREATED)
def alta_cliente_credito(
    datos: ClienteCreditoEntrada,
    request: Request,
    usuario: UsuarioActual = Depends(requiere("finanzas", "crear")),
    conn: Connection = Depends(get_conn),
):
    return servicio.guardar_cliente(conn, datos, usuario, ip_de(request))


@router.put("/clientes-credito/{id_cliente}", response_model=ClienteCredito)
def editar_cliente_credito(
    id_cliente: Annotated[int, Path(gt=0)],
    datos: ClienteCreditoEntrada,
    request: Request,
    usuario: UsuarioActual = Depends(requiere("finanzas", "editar")),
    conn: Connection = Depends(get_conn),
):
    return servicio.guardar_cliente(conn, datos, usuario, ip_de(request), id_cliente)


# ---------------------------------------------------------------- cuentas por cobrar y cobros (HU-38b)

@router.get("/cuentas-por-cobrar", response_model=list[CuentaPorCobrar],
            dependencies=[Depends(requiere("finanzas", "ver"))])
def cuentas_por_cobrar(id_cliente: Annotated[int | None, Query(gt=0)] = None, conn: Connection = Depends(get_conn)):
    return repositorio.cuentas_por_cobrar(conn, id_cliente)


@router.get("/cajas-abiertas", response_model=list[CajaAbierta], dependencies=[Depends(requiere("finanzas", "crear"))])
def cajas_abiertas(conn: Connection = Depends(get_conn)):
    """Turnos donde puede entrar un cobro en efectivo."""
    return repositorio.cajas_abiertas(conn)


@router.post("/cuentas-por-cobrar/{ticket}/cobros", response_model=CobroRegistrado, status_code=status.HTTP_201_CREATED)
def registrar_cobro(
    ticket: Annotated[str, Path(pattern=PATRON_FOLIO_VENTA)],
    datos: CobroEntrada,
    request: Request,
    usuario: UsuarioActual = Depends(requiere("finanzas", "crear")),
    conn: Connection = Depends(get_conn),
):
    return servicio.registrar_cobro(conn, ticket, datos, usuario, ip_de(request))


@router.get("/clientes-credito/{id_cliente}/estado-de-cuenta", response_model=list[MovimientoCliente],
            dependencies=[Depends(requiere("finanzas", "ver"))])
def estado_de_cuenta(id_cliente: Annotated[int, Path(gt=0)], conn: Connection = Depends(get_conn)):
    if repositorio.cliente(conn, id_cliente) is None:
        raise ErrorNegocio(404, "Cliente de crédito no encontrado.")
    return repositorio.movimientos_cliente(conn, id_cliente)


# ---------------------------------------------------------------- gastos (HU-26)

@router.get("/gastos", response_model=list[Gasto], dependencies=[Depends(requiere("finanzas", "ver"))])
def gastos(
    concepto: ConceptoGasto | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    conn: Connection = Depends(get_conn),
):
    filas = repositorio.listar_gastos(conn, desde, hasta)
    return filas if concepto is None else [g for g in filas if g["concepto"] == concepto]


@router.post("/gastos", status_code=status.HTTP_201_CREATED)
def registrar_gasto(
    datos: GastoEntrada,
    request: Request,
    usuario: UsuarioActual = Depends(requiere("finanzas", "crear")),
    conn: Connection = Depends(get_conn),
) -> dict[str, str]:
    servicio.registrar_gasto(conn, datos, usuario, ip_de(request))
    return {"estado": "registrado"}


# ---------------------------------------------------------------- dashboard y flujo (HU-27, HU-37)

Anio = Annotated[int, Query(ge=2020, le=2100)]
Mes = Annotated[int, Query(ge=1, le=12)]


@router.get("/dashboard", response_model=Dashboard, dependencies=[Depends(requiere("finanzas", "ver"))])
def dashboard(anio: Anio, mes: Mes, conn: Connection = Depends(get_conn)):
    return servicio.dashboard(conn, anio, mes)


@router.get("/flujo", response_model=Flujo, dependencies=[Depends(requiere("finanzas", "ver"))])
def flujo(anio: Anio, mes: Mes, conn: Connection = Depends(get_conn)):
    return servicio.flujo(conn, anio, mes)
