from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class Producto(BaseModel):
    id_producto: int
    codigo_barras: str
    nombre: str
    unidad_venta: str
    precio_venta: Decimal
    tasa_iva: Decimal
    es_frecuente: bool
    existencia: Decimal


class MetodoPago(BaseModel):
    id_metodo: int
    nombre: str
    es_efectivo: bool
    es_credito: bool


class Caja(BaseModel):
    id_caja: int
    terminal: str
    fondo_inicial: Decimal
    fecha_apertura: datetime


class RenglonCarrito(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_producto: int = Field(gt=0)
    cantidad: Decimal = Field(gt=0, max_digits=10, decimal_places=3)


class VentaEntrada(BaseModel):
    # El cajero sale del token: un id_usuario en el cuerpo se rechaza.
    model_config = ConfigDict(extra="forbid")

    id_caja: int = Field(gt=0)
    id_metodo: int = Field(gt=0, le=255)
    monto_recibido: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    id_cliente_credito: int | None = Field(default=None, gt=0)
    carrito: list[RenglonCarrito] = Field(min_length=1, max_length=200)


class VentaSalida(BaseModel):
    id_venta: int
    folio: str
    total: Decimal
    cambio: Decimal
