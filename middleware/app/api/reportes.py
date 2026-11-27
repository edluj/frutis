from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import Connection

from app.db import get_conn
from app.repositories import reportes as repositorio
from app.schemas.reportes import Reporte, ResumenDelDia
from app.security.dependencias import UsuarioActual, requiere, usuario_actual
from app.security.sanitizar import PATRON_TEXTO_SEGURO
from app.services import reportes as servicio

router = APIRouter(prefix="/reportes", tags=["reportes"])


@router.get("/resumen-del-dia", response_model=ResumenDelDia)
def resumen_del_dia(usuario: UsuarioActual = Depends(usuario_actual), conn: Connection = Depends(get_conn)):
    """Pantalla de inicio de cualquier rol; cada parte depende de sus permisos."""
    return servicio.resumen(conn, usuario)


@router.get("/cajeros", response_model=list[str], dependencies=[Depends(requiere("reportes", "ver"))])
def cajeros(conn: Connection = Depends(get_conn)):
    return repositorio.cajeros(conn)


@router.get("/{numero}", response_model=Reporte, dependencies=[Depends(requiere("reportes", "ver"))])
def reporte(
    numero: Annotated[int, Path(ge=1, le=12)],
    desde: date,
    hasta: date,
    cajero: Annotated[str | None, Query(max_length=150, pattern=PATRON_TEXTO_SEGURO)] = None,
    conn: Connection = Depends(get_conn),
):
    return servicio.reporte(conn, numero, desde, hasta, cajero)
