from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.compras import PATRON_CORREO, PATRON_RFC
from app.schemas.pos import PATRON_FOLIO_VENTA
from app.security.sanitizar import PATRON_TEXTO_SEGURO

PATRON_FOLIO_FACTURA = r"^F-\d{1,12}$"
PATRON_UUID = r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$"
EstatusFactura = Literal["Borrador", "Vigente", "Cancelada"]


class ClienteFiscal(BaseModel):
    id_cliente: int
    rfc: str
    razon_social: str
    regimen_fiscal: str
    codigo_postal: str
    correo: str
    facturas: int


class ClienteFiscalEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    rfc: str = Field(pattern=PATRON_RFC)
    razon_social: str = Field(min_length=1, max_length=250, pattern=PATRON_TEXTO_SEGURO)
    regimen_fiscal: str = Field(pattern=r"^\d{3}$")
    codigo_postal: str = Field(pattern=r"^\d{5}$")
    correo: str = Field(max_length=120, pattern=PATRON_CORREO)


class FacturaEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    folio_venta: str = Field(pattern=PATRON_FOLIO_VENTA)
    rfc: str = Field(pattern=PATRON_RFC)
    regimen_fiscal: str = Field(pattern=r"^\d{3}$")
    codigo_postal: str = Field(pattern=r"^\d{5}$")
    uso_cfdi: str = Field(pattern=r"^[A-Z]\d{2}$|^CP01$|^S01$")
    forma_pago: str = Field(pattern=r"^\d{2}$")
    metodo_pago: Literal["PUE", "PPD"]
    correo: str = Field(max_length=120, pattern=PATRON_CORREO)


class Concepto(BaseModel):
    nombre: str
    unidad_venta: str
    cantidad: Decimal
    precio_unitario: Decimal
    importe: Decimal
    tasa_iva: Decimal
    clave_sat: str


class TicketParaFactura(BaseModel):
    folio: str
    total: Decimal
    metodo: str
    conceptos: list[Concepto]


class Factura(BaseModel):
    folio: str
    folio_venta: str
    uuid: str | None
    estatus: EstatusFactura
    rfc: str
    razon_social: str
    codigo_postal: str
    correo: str
    uso_cfdi: str
    forma_pago: str
    metodo_pago: str
    subtotal: Decimal
    iva: Decimal
    total: Decimal
    fecha_timbrado: datetime | None
    fecha_cancelacion: datetime | None
    motivo_cancelacion: str | None
    conceptos: list[Concepto] = []


class CancelacionEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    motivo: Literal["01", "02", "03", "04"]
    # Con motivo 01 (errores con relación) es obligatorio el folio de la factura que la sustituye.
    folio_sustituto: str | None = Field(default=None, pattern=PATRON_FOLIO_FACTURA)


class Timbres(BaseModel):
    disponibles: int
    contratados: int
