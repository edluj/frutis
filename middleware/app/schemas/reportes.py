from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

# La pantalla da formato a cada celda según el tipo de su columna.
Tipo = Literal["texto", "entero", "dinero", "fecha", "porcentaje"]


class Columna(BaseModel):
    nombre: str
    alineacion: Literal["izq", "der"] = "izq"
    tipo: Tipo = "texto"


class Barra(BaseModel):
    nombre: str
    fraccion: float
    valor: Decimal
    tipo: Literal["dinero", "porcentaje", "tickets"]


class Reporte(BaseModel):
    titulo: str
    columnas: list[Columna]
    filas: list[list[str | int | Decimal | None]]
    total: list[str | int | Decimal | None] | None = None
    barras: list[Barra] = []


class Alerta(BaseModel):
    etiqueta: str
    texto: str
    tono: Literal["naranja", "rojo"]


class ResumenDelDia(BaseModel):
    ventas_hoy: Decimal
    tickets: int
    caja_abierta: bool
    caja_detalle: str
    caducar: int | None
    caducar_detalle: str
    por_cobrar: Decimal | None
    por_cobrar_detalle: str
    alertas: list[Alerta]
