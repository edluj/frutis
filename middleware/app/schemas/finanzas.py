from datetime import date
from decimal import Decimal
from typing import Literal

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


# ---------------------------------------------------------------- cuentas por cobrar y cobros (HU-38b)

MetodoCobro = Literal["Efectivo", "Transferencia", "Tarjeta"]


class CuentaPorCobrar(BaseModel):
    ticket: str
    id_cliente: int
    cliente: str
    venta: date
    vence: date
    total: Decimal
    saldo: Decimal


class CajaAbierta(BaseModel):
    id_caja: int
    terminal: str


class CobroEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    monto: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    metodo: MetodoCobro
    # Turno donde se recibe el efectivo; sin caja el cobro no entra a ningún corte.
    id_caja: int | None = Field(default=None, gt=0)


class CobroRegistrado(BaseModel):
    saldo: Decimal


class MovimientoCliente(BaseModel):
    fecha: date
    movimiento: str
    referencia: str
    cargo: Decimal
    abono: Decimal


# ---------------------------------------------------------------- gastos (HU-26)

ConceptoGasto = Literal["Sueldos", "Renta", "Luz", "Agua", "Gas", "Mantenimiento", "Transporte", "Otros"]


class Gasto(BaseModel):
    fecha: date
    concepto: str
    detalle: str
    metodo: str
    monto: Decimal
    comprobante: bool
    usuario: str


class GastoEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    fecha: date
    concepto: ConceptoGasto
    detalle: str | None = Field(default=None, max_length=100, pattern=PATRON_TEXTO_SEGURO)
    metodo: MetodoCobro
    monto: Decimal = Field(gt=0, max_digits=12, decimal_places=2)

    @field_validator("detalle", mode="before")
    @classmethod
    def detalle_vacio(cls, valor):
        return valor or None


# ---------------------------------------------------------------- dashboard y flujo (HU-27, HU-37)

class ConceptoEgreso(BaseModel):
    concepto: str
    importe: Decimal
    pct: Decimal


class SemanaDashboard(BaseModel):
    semana: str
    ingresos: Decimal
    egresos: Decimal


class Dashboard(BaseModel):
    ingresos: Decimal
    tickets: int
    compras: Decimal
    gastos: Decimal
    egresos: Decimal
    utilidad: Decimal
    margen: Decimal
    margen_anterior: Decimal
    semanas: list[SemanaDashboard]
    conceptos: list[ConceptoEgreso]


class SemanaFlujo(BaseModel):
    semana: str
    entradas: Decimal
    salidas: Decimal


class Flujo(BaseModel):
    inicial: Decimal
    ventas: Decimal
    cobros: Decimal
    pagos_proveedores: Decimal
    gastos: Decimal
    credito: Decimal
    semanas: list[SemanaFlujo]
