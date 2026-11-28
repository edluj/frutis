from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.security.sanitizar import PATRON_TEXTO_SEGURO

PATRON_CODIGO_BARRAS = r"^[A-Za-z0-9\-]+$"
TASAS_IVA = {Decimal("0"), Decimal("0.16")}


class Categoria(BaseModel):
    id_categoria: int
    nombre: str
    descripcion: str | None
    activo: bool
    productos_activos: int


class CategoriaEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nombre: str = Field(min_length=1, max_length=60, pattern=PATRON_TEXTO_SEGURO)
    descripcion: str | None = Field(default=None, max_length=200, pattern=PATRON_TEXTO_SEGURO)
    activo: bool = True

    @field_validator("descripcion", mode="before")
    @classmethod
    def vacia_es_nula(cls, valor):
        return valor or None


class ProductoCatalogo(BaseModel):
    id_producto: int
    codigo_barras: str
    nombre: str
    id_categoria: int
    categoria: str
    unidad_venta: str
    precio_venta: Decimal
    costo_actual: Decimal
    tasa_iva: Decimal
    stock_minimo: Decimal
    es_frecuente: bool
    activo: bool
    existencia: Decimal
    estado: Literal["Normal", "Bajo", "Sin existencia", "Por caducar"]


class ProductoEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    codigo_barras: str = Field(min_length=1, max_length=32, pattern=PATRON_CODIGO_BARRAS)
    nombre: str = Field(min_length=1, max_length=120, pattern=PATRON_TEXTO_SEGURO)
    id_categoria: int = Field(gt=0)
    unidad_venta: Literal["kg", "pieza"]
    precio_venta: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    stock_minimo: Decimal = Field(ge=0, max_digits=10, decimal_places=3)
    # Los precios incluyen IVA; la fruta y la verdura van a tasa 0 %.
    tasa_iva: Decimal = Decimal("0")
    es_frecuente: bool = False
    activo: bool = True

    @field_validator("tasa_iva")
    @classmethod
    def tasa_valida(cls, valor: Decimal) -> Decimal:
        if valor not in TASAS_IVA:
            raise ValueError("La tasa de IVA debe ser 0 o 0.16.")
        return valor


# ---------------------------------------------------------------- mermas (HU-17)

MotivoMerma = Literal["maduracion", "golpe", "plaga", "devolucion", "caducidad", "otro"]


class LoteConExistencia(BaseModel):
    folio: str
    queda: Decimal
    caducidad: date
    costo: Decimal


class Merma(BaseModel):
    fecha: date
    id_producto: int
    producto: str
    unidad_venta: str
    lote: str
    cantidad: Decimal
    motivo: MotivoMerma
    costo: Decimal
    usuario: str
    observaciones: str | None


class MermaEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id_producto: int = Field(gt=0)
    folio_lote: str = Field(pattern=r"^L-\d{1,16}$")
    cantidad: Decimal = Field(gt=0, max_digits=10, decimal_places=3)
    motivo: MotivoMerma
    observaciones: str | None = Field(default=None, max_length=255, pattern=PATRON_TEXTO_SEGURO)

    @field_validator("observaciones", mode="before")
    @classmethod
    def vacias_son_nulas(cls, valor):
        return valor or None


class MermaRegistrada(BaseModel):
    costo: Decimal


# ---------------------------------------------------------------- existencias y caducidades (HU-24)

class Existencia(BaseModel):
    id_producto: int
    id_categoria: int
    nombre: str
    unidad_venta: str
    existencia: Decimal
    stock_minimo: Decimal
    # Promedio vendido por día en los últimos 30 días.
    venta_diaria: Decimal
    lotes: int
    valor: Decimal


class LotePorCaducar(BaseModel):
    caducidad: date
    dias: int
    id_producto: int
    producto: str
    unidad_venta: str
    lote: str
    proveedor: str
    recibido: Decimal
    queda: Decimal
    costo: Decimal


class Movimiento(BaseModel):
    fecha: date
    tipo: Literal["Entrada", "Venta", "Merma", "Devolución"]
    # Positiva si entra al inventario, negativa si sale.
    cantidad: Decimal
    referencia: str
    usuario: str


# ---------------------------------------------------------------- precios (HU-31)

class CambioPrecio(BaseModel):
    fecha: datetime
    anterior: Decimal
    nuevo: Decimal
    usuario: str
    motivo: str | None


class PrecioNuevo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_producto: int = Field(gt=0)
    precio_nuevo: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class AjustePreciosEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    motivo: str = Field(min_length=1, max_length=200, pattern=PATRON_TEXTO_SEGURO)
    cambios: list[PrecioNuevo] = Field(min_length=1, max_length=500)


class AjusteAplicado(BaseModel):
    productos: int
