from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query, Request, status
from sqlalchemy import Connection

from app.api.auth import ip_de
from app.db import get_conn
from app.errores import ErrorNegocio
from app.repositories import compras as repositorio
from app.schemas.compras import (
    PATRON_FOLIO_LOTE, CuentaPorPagar, LoteDetalle, LoteEntrada, LoteRegistrado, LoteResumen, MovimientoProveedor,
    PagoEntrada, PagoRegistrado, Proveedor, ProveedorEntrada,
)
from app.security.dependencias import UsuarioActual, requiere
from app.security.sanitizar import PATRON_TEXTO_SEGURO
from app.services import compras as servicio

router = APIRouter(prefix="/compras", tags=["compras"])

ESTATUS = {"activos": True, "inactivos": False, "todos": None}


# ---------------------------------------------------------------- proveedores (HU-23)

@router.get("/proveedores", response_model=list[Proveedor], dependencies=[Depends(requiere("compras", "ver"))])
def proveedores(
    busqueda: Annotated[str | None, Query(max_length=120, pattern=PATRON_TEXTO_SEGURO)] = None,
    estatus: Literal["activos", "inactivos", "todos"] = "activos",
    conn: Connection = Depends(get_conn),
):
    return repositorio.listar_proveedores(conn, busqueda, ESTATUS[estatus])


@router.post("/proveedores", response_model=Proveedor, status_code=status.HTTP_201_CREATED)
def alta_proveedor(
    datos: ProveedorEntrada,
    request: Request,
    usuario: UsuarioActual = Depends(requiere("compras", "crear")),
    conn: Connection = Depends(get_conn),
):
    return servicio.guardar_proveedor(conn, datos, usuario, ip_de(request))


@router.put("/proveedores/{id_proveedor}", response_model=Proveedor)
def editar_proveedor(
    id_proveedor: Annotated[int, Path(gt=0)],
    datos: ProveedorEntrada,
    request: Request,
    usuario: UsuarioActual = Depends(requiere("compras", "editar")),
    conn: Connection = Depends(get_conn),
):
    return servicio.guardar_proveedor(conn, datos, usuario, ip_de(request), id_proveedor)


# ---------------------------------------------------------------- lotes de compra (HU-11)

@router.get("/lotes/siguiente-folio", dependencies=[Depends(requiere("compras", "crear"))])
def siguiente_folio(conn: Connection = Depends(get_conn)) -> dict[str, str]:
    return {"folio": repositorio.siguiente_folio(conn)}


@router.get("/lotes", response_model=list[LoteResumen], dependencies=[Depends(requiere("compras", "ver"))])
def lotes(
    id_proveedor: Annotated[int | None, Query(gt=0)] = None,
    desde: date | None = None,
    hasta: date | None = None,
    pago: Literal["Todos", "Pagado", "Pendiente", "Vencido"] = "Todos",
    conn: Connection = Depends(get_conn),
):
    filas = repositorio.listar_lotes(conn, id_proveedor, desde, hasta)
    return filas if pago == "Todos" else [f for f in filas if f["pago"] == pago]


@router.get("/lotes/{folio}", response_model=LoteDetalle, dependencies=[Depends(requiere("compras", "ver"))])
def lote(folio: Annotated[str, Path(pattern=PATRON_FOLIO_LOTE)], conn: Connection = Depends(get_conn)):
    return servicio.detalle_lote(conn, folio)


@router.post("/lotes", response_model=LoteRegistrado, status_code=status.HTTP_201_CREATED)
def registrar_lote(
    datos: LoteEntrada,
    request: Request,
    usuario: UsuarioActual = Depends(requiere("compras", "crear")),
    conn: Connection = Depends(get_conn),
):
    return servicio.registrar_lote(conn, datos, usuario, ip_de(request))


# ---------------------------------------------------------------- cuentas por pagar (HU-25)

@router.get("/cuentas-por-pagar", response_model=list[CuentaPorPagar], dependencies=[Depends(requiere("compras", "ver"))])
def cuentas_por_pagar(
    id_proveedor: Annotated[int | None, Query(gt=0)] = None,
    conn: Connection = Depends(get_conn),
):
    return repositorio.cuentas_por_pagar(conn, id_proveedor)


@router.post("/cuentas-por-pagar/{folio}/pagos", response_model=PagoRegistrado, status_code=status.HTTP_201_CREATED)
def pagar_lote(
    folio: Annotated[str, Path(pattern=PATRON_FOLIO_LOTE)],
    datos: PagoEntrada,
    request: Request,
    usuario: UsuarioActual = Depends(requiere("compras", "crear")),
    conn: Connection = Depends(get_conn),
):
    return servicio.pagar_lote(conn, folio, datos, usuario, ip_de(request))


@router.get("/proveedores/{id_proveedor}/estado-de-cuenta", response_model=list[MovimientoProveedor],
            dependencies=[Depends(requiere("compras", "ver"))])
def estado_de_cuenta(id_proveedor: Annotated[int, Path(gt=0)], conn: Connection = Depends(get_conn)):
    """Toda la historia; la pantalla calcula el saldo inicial y el del periodo."""
    if repositorio.proveedor(conn, id_proveedor) is None:
        raise ErrorNegocio(404, "Proveedor no encontrado.")
    return repositorio.movimientos_proveedor(conn, id_proveedor)
