from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query, Request, status
from sqlalchemy import Connection

from app.api.auth import ip_de
from app.db import get_conn
from app.repositories import finanzas as repositorio
from app.schemas.finanzas import ClienteCredito, ClienteCreditoEntrada
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
