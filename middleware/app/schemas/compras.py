from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.security.sanitizar import PATRON_TEXTO_SEGURO

# Persona moral (12) o física (13); la regla final la pone la base (ck_proveedores_rfc).
PATRON_RFC = r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$"
PATRON_TELEFONO = r"^[\d +()\-]{7,20}$"
PATRON_CORREO = r"^[^@\s'\"<>;]+@[^@\s'\"<>;]+\.[^@\s'\"<>;]+$"
PATRON_FACTURA = r"^[A-Za-z0-9\-/ ]+$"
PATRON_FOLIO_LOTE = r"^L-\d{1,16}$"


def _vacio_es_nulo(valor):
    return valor or None


class Proveedor(BaseModel):
    id_proveedor: int
    razon_social: str
    rfc: str
    telefono: str
    correo: str | None
    direccion: str | None
    dias_credito: int
    activo: bool
    saldo: Decimal


class ProveedorEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    razon_social: str = Field(min_length=1, max_length=200, pattern=PATRON_TEXTO_SEGURO)
    rfc: str = Field(pattern=PATRON_RFC)
    telefono: str = Field(pattern=PATRON_TELEFONO)
    correo: str | None = Field(default=None, max_length=120, pattern=PATRON_CORREO)
    direccion: str | None = Field(default=None, max_length=200, pattern=PATRON_TEXTO_SEGURO)
    dias_credito: int = Field(ge=0, le=365)
    activo: bool = True

    _nulos = field_validator("correo", "direccion", mode="before")(_vacio_es_nulo)

    @field_validator("rfc", mode="before")
    @classmethod
    def rfc_mayusculas(cls, valor):
        return valor.strip().upper() if isinstance(valor, str) else valor


class RenglonLote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_producto: int = Field(gt=0)
    cantidad: Decimal = Field(gt=0, max_digits=10, decimal_places=3)
    costo: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    caducidad: date


class LoteEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id_proveedor: int = Field(gt=0)
    factura: str | None = Field(default=None, max_length=40, pattern=PATRON_FACTURA)
    entrada: date
    # 0 = contado; si es mayor, se crea la cuenta por pagar con ese plazo.
    dias_credito: int = Field(ge=0, le=365)
    renglones: list[RenglonLote] = Field(min_length=1, max_length=100)

    _nulos = field_validator("factura", mode="before")(_vacio_es_nulo)


class LoteRegistrado(BaseModel):
    folio: str
    total: Decimal


class LoteResumen(BaseModel):
    folio: str
    id_proveedor: int
    proveedor: str
    entrada: date
    productos: int
    total: Decimal
    kilos: Decimal
    dias_credito: int
    pago: Literal["Pagado", "Pendiente", "Vencido"]
    saldo: Decimal
    caducidad: date


class RenglonDetalle(BaseModel):
    id_producto: int
    nombre: str
    unidad_venta: str
    recibido: Decimal
    costo: Decimal
    vendido: Decimal
    merma: Decimal
    existencia: Decimal
    caducidad: date
    dias: int


class MermaDeLote(BaseModel):
    fecha: date
    producto: str
    cantidad: Decimal
    motivo: str
    costo: Decimal


class LoteDetalle(BaseModel):
    folio: str
    proveedor: str
    entrada: date
    factura: str | None
    total: Decimal
    dias_credito: int
    vence: date | None
    pagado: Decimal
    saldo: Decimal
    pago: Literal["Pagado", "Pendiente", "Vencido"]
    productos: list[RenglonDetalle]
    mermas: list[MermaDeLote]


# ---------------------------------------------------------------- cuentas por pagar (HU-25)

class CuentaPorPagar(BaseModel):
    lote: str
    id_proveedor: int
    proveedor: str
    vence: date
    total: Decimal
    saldo: Decimal


class PagoEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    monto: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    metodo: Literal["Transferencia", "Efectivo", "Cheque"]
    referencia: str | None = Field(default=None, max_length=60, pattern=PATRON_TEXTO_SEGURO)

    _nulos = field_validator("referencia", mode="before")(_vacio_es_nulo)


class PagoRegistrado(BaseModel):
    saldo: Decimal


class MovimientoProveedor(BaseModel):
    fecha: date
    movimiento: str
    referencia: str
    cargo: Decimal
    abono: Decimal
