from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.compras import PATRON_CORREO, PATRON_RFC, PATRON_TELEFONO
from app.security.sanitizar import PATRON_TEXTO_SEGURO


class ClienteCredito(BaseModel):
    id_cliente_credito: int
    nombre: str
    telefono: str
    correo: str | None
    limite_credito: Decimal
    dias_credito: int
    activo: bool
    rfc_fiscal: str | None
    debe: Decimal
    vencido: bool


class ClienteCreditoPos(BaseModel):
    """Lo que el cajero necesita para vender a crédito (HU-38a)."""

    id_cliente_credito: int
    nombre: str
    limite_credito: Decimal
    debe: Decimal
    disponible: Decimal
    dias_credito: int
    vence: date
    vencido: bool


class ClienteCreditoEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nombre: str = Field(min_length=1, max_length=150, pattern=PATRON_TEXTO_SEGURO)
    telefono: str = Field(pattern=PATRON_TELEFONO)
    correo: str | None = Field(default=None, max_length=120, pattern=PATRON_CORREO)
    limite_credito: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    dias_credito: int = Field(gt=0, le=365)
    activo: bool = True
    # RFC de clientes_fiscales cuando el cliente también pide factura.
    rfc_fiscal: str | None = Field(default=None, pattern=PATRON_RFC)

    @field_validator("correo", "rfc_fiscal", mode="before")
    @classmethod
    def vacio_es_nulo(cls, valor):
        return valor or None
