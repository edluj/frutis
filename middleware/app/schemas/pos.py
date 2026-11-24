from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.security.sanitizar import PATRON_NOTA, PATRON_TEXTO_SEGURO

PATRON_TERMINAL = r"^[\w.\-]+$"
PATRON_FOLIO_VENTA = r"^V\d{1,12}$"


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


# ---------------------------------------------------------------- apertura y corte (HU-15, HU-09)

class AperturaEntrada(BaseModel):
    # El cajero sale del token.
    model_config = ConfigDict(extra="forbid")

    terminal: str = Field(min_length=1, max_length=30, pattern=PATRON_TERMINAL)
    fondo_inicial: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class UltimoCorte(BaseModel):
    id_caja: int
    terminal: str
    cajero: str
    fecha_cierre: datetime
    efectivo_esperado: Decimal
    efectivo_contado: Decimal
    diferencia: Decimal
    observaciones: str | None


class VentasPorMetodo(BaseModel):
    metodo: str
    es_efectivo: bool
    es_credito: bool
    tickets: int
    importe: Decimal


class MovimientosEfectivo(BaseModel):
    cantidad: int
    importe: Decimal


class ResumenCorte(BaseModel):
    id_caja: int
    terminal: str
    fecha_apertura: datetime
    fondo_inicial: Decimal
    ventas: list[VentasPorMetodo]
    cobros_efectivo: MovimientosEfectivo
    devoluciones_efectivo: MovimientosEfectivo
    efectivo_esperado: Decimal


class CorteEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_caja: int = Field(gt=0)
    efectivo_contado: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    observaciones: str | None = Field(default=None, max_length=255, pattern=PATRON_NOTA)


class CorteSalida(BaseModel):
    id_caja: int
    efectivo_esperado: Decimal
    efectivo_contado: Decimal
    diferencia: Decimal


# ---------------------------------------------------------------- ticket y devoluciones (HU-30, SC-02)

class RenglonTicket(BaseModel):
    id_producto: int
    nombre: str
    unidad_venta: str
    cantidad: Decimal
    precio_unitario: Decimal
    importe: Decimal
    devuelto: Decimal


class Ticket(BaseModel):
    id_venta: int
    folio: str
    fecha: datetime
    metodo: str
    es_credito: bool
    total: Decimal
    estatus: str
    facturado: bool
    cliente: str | None
    renglones: list[RenglonTicket]


class Administrador(BaseModel):
    usuario: str
    nombre_completo: str


class AutorizacionEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    usuario: str = Field(min_length=1, max_length=50, pattern=r"^[\w.\-]+$")
    # El tope evita gastar CPU en PBKDF2 con textos enormes.
    password: str = Field(min_length=1, max_length=128)
    folio_venta: str = Field(pattern=PATRON_FOLIO_VENTA)


class AutorizacionSalida(BaseModel):
    autorizacion: str
    autorizado_por: str
    expira_minutos: int


class RenglonDevolucion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_producto: int = Field(gt=0)
    cantidad: Decimal = Field(gt=0, max_digits=10, decimal_places=3)
    estado: Literal["bueno", "danado"]


class DevolucionEntrada(BaseModel):
    # El cajero sale del token y el Administrador, de la autorización firmada.
    model_config = ConfigDict(extra="forbid")

    id_caja: int = Field(gt=0)
    folio_venta: str = Field(pattern=PATRON_FOLIO_VENTA)
    motivo: str = Field(min_length=1, max_length=200, pattern=PATRON_TEXTO_SEGURO)
    reembolso: Literal["efectivo", "tarjeta", "transferencia", "credito"]
    autorizacion: str = Field(min_length=1, max_length=2000)
    renglones: list[RenglonDevolucion] = Field(min_length=1, max_length=200)


class DevolucionSalida(BaseModel):
    folio: str
    total: Decimal
    reembolso: str
