from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query, Request, Response, status
from sqlalchemy import Connection

from app.api.auth import ip_de
from app.db import get_conn
from app.integrations.pac import Pac, get_pac
from app.repositories import facturacion as repositorio
from app.schemas.facturacion import (
    PATRON_FOLIO_FACTURA, CancelacionEntrada, ClienteFiscal, ClienteFiscalEntrada, Factura, FacturaEntrada,
    TicketParaFactura, Timbres,
)
from app.schemas.pos import PATRON_FOLIO_VENTA
from app.security.dependencias import UsuarioActual, requiere
from app.security.sanitizar import PATRON_TEXTO_SEGURO
from app.services import facturacion as servicio

router = APIRouter(prefix="/facturacion", tags=["facturacion"])

Folio = Annotated[str, Path(pattern=PATRON_FOLIO_FACTURA)]


@router.get("/timbres", response_model=Timbres, dependencies=[Depends(requiere("facturacion", "ver"))])
def timbres(conn: Connection = Depends(get_conn)):
    return servicio.timbres(conn)


# ---------------------------------------------------------------- datos fiscales (HU-32)

@router.get("/clientes", response_model=list[ClienteFiscal], dependencies=[Depends(requiere("facturacion", "ver"))])
def clientes(
    busqueda: Annotated[str | None, Query(max_length=250, pattern=PATRON_TEXTO_SEGURO)] = None,
    conn: Connection = Depends(get_conn),
):
    return repositorio.listar_clientes(conn, busqueda)


@router.post("/clientes", response_model=ClienteFiscal, status_code=status.HTTP_201_CREATED)
def alta_cliente(
    datos: ClienteFiscalEntrada, request: Request,
    usuario: UsuarioActual = Depends(requiere("facturacion", "crear")), conn: Connection = Depends(get_conn),
):
    return servicio.guardar_cliente(conn, datos, usuario, ip_de(request))


@router.put("/clientes/{id_cliente}", response_model=ClienteFiscal)
def editar_cliente(
    id_cliente: Annotated[int, Path(gt=0)], datos: ClienteFiscalEntrada, request: Request,
    usuario: UsuarioActual = Depends(requiere("facturacion", "editar")), conn: Connection = Depends(get_conn),
):
    return servicio.guardar_cliente(conn, datos, usuario, ip_de(request), id_cliente)


# ---------------------------------------------------------------- facturas (HU-12a, HU-33)

@router.get("/tickets/{folio}", response_model=TicketParaFactura,
            dependencies=[Depends(requiere("facturacion", "crear"))])
def ticket(folio: Annotated[str, Path(pattern=PATRON_FOLIO_VENTA)], conn: Connection = Depends(get_conn)):
    """Conceptos del ticket con su clave SAT; rechaza los ya facturados o con devoluciones."""
    return servicio.ticket(conn, folio)


@router.get("/facturas", response_model=list[Factura], dependencies=[Depends(requiere("facturacion", "ver"))])
def facturas(
    texto: Annotated[str | None, Query(max_length=250, pattern=PATRON_TEXTO_SEGURO)] = None,
    desde: date | None = None,
    hasta: date | None = None,
    estatus: Literal["Todas", "Vigente", "Cancelada", "Borrador"] = "Todas",
    conn: Connection = Depends(get_conn),
):
    filas = repositorio.listar_facturas(conn, texto, desde, hasta)
    return filas if estatus == "Todas" else [f for f in filas if f["estatus"] == estatus]


@router.post("/facturas", response_model=Factura, status_code=status.HTTP_201_CREATED)
def timbrar(
    datos: FacturaEntrada, request: Request,
    usuario: UsuarioActual = Depends(requiere("facturacion", "crear")),
    conn: Connection = Depends(get_conn), pac: Pac = Depends(get_pac),
):
    return servicio.timbrar(conn, datos, usuario, ip_de(request), pac)


@router.get("/facturas/{folio}", response_model=Factura, dependencies=[Depends(requiere("facturacion", "ver"))])
def factura(folio: Folio, conn: Connection = Depends(get_conn)):
    return servicio.detalle(conn, folio)


@router.get("/facturas/{folio}/xml", dependencies=[Depends(requiere("facturacion", "ver"))])
def xml(folio: Folio, conn: Connection = Depends(get_conn)) -> Response:
    return Response(servicio.xml(conn, folio), media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="{folio}.xml"'})


@router.post("/facturas/{folio}/cancelacion", response_model=Factura)
def cancelar(
    folio: Folio, datos: CancelacionEntrada, request: Request,
    usuario: UsuarioActual = Depends(requiere("facturacion", "editar")),
    conn: Connection = Depends(get_conn), pac: Pac = Depends(get_pac),
):
    return servicio.cancelar(conn, folio, datos, usuario, ip_de(request), pac)
