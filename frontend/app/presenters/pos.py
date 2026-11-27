"""Lógica de pantalla del Punto de Venta, sin Qt para poder probarla sola.

Los totales que aquí se calculan son solo para mostrarlos en tiempo real (HU-08);
el importe que vale es el que devuelve sp_registrar_venta.
"""
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

CERO = Decimal("0")
CENTAVO = Decimal("0.01")

SIN_EXISTENCIA = "Producto sin existencia suficiente."
MONTO_INSUFICIENTE = "El monto recibido es insuficiente."
CREDITO_EXCEDIDO = "La venta excede el crédito disponible del cliente."


def redondear(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVO, ROUND_HALF_UP)


@dataclass
class Renglon:
    id_producto: int
    nombre: str
    unidad: str  # kg | pieza
    precio: Decimal
    cantidad: Decimal
    existencia: Decimal

    @property
    def importe(self) -> Decimal:
        return redondear(self.precio * self.cantidad)

    @property
    def por_peso(self) -> bool:
        return self.unidad == "kg"


@dataclass
class Carrito:
    renglones: list[Renglon] = field(default_factory=list)

    def agregar(self, producto: dict, cantidad: Decimal) -> Renglon:
        """Suma al renglón del mismo producto. Lanza ValueError si no hay existencia."""
        if cantidad <= 0:
            raise ValueError("Ingrese una cantidad válida.")
        unidad = producto["unidad_venta"]
        if unidad != "kg" and cantidad != cantidad.to_integral_value():
            raise ValueError("Los productos por pieza se venden en cantidades enteras.")
        existente = next((r for r in self.renglones if r.id_producto == producto["id_producto"]), None)
        nueva = cantidad + (existente.cantidad if existente else CERO)
        if nueva > Decimal(str(producto["existencia"])):
            raise ValueError(SIN_EXISTENCIA)
        if existente:
            existente.cantidad = nueva
            return existente
        r = Renglon(producto["id_producto"], producto["nombre"], unidad, Decimal(str(producto["precio_venta"])),
                    cantidad, Decimal(str(producto["existencia"])))
        self.renglones.append(r)
        return r

    def cambiar_cantidad(self, indice: int, cantidad: Decimal) -> None:
        r = self.renglones[indice]
        if cantidad <= 0:
            raise ValueError("Ingrese una cantidad válida.")
        if cantidad > r.existencia:
            raise ValueError(SIN_EXISTENCIA)
        r.cantidad = cantidad

    def quitar(self, indice: int) -> None:
        del self.renglones[indice]

    def vaciar(self) -> None:
        self.renglones.clear()

    @property
    def total(self) -> Decimal:
        return sum((r.importe for r in self.renglones), CERO)

    @property
    def vacio(self) -> bool:
        return not self.renglones

    def __len__(self) -> int:
        return len(self.renglones)

    def para_api(self) -> list[dict]:
        return [{"id_producto": r.id_producto, "cantidad": r.cantidad} for r in self.renglones]


def cambio(total: Decimal, recibido: Decimal | None) -> Decimal | None:
    if recibido is None:
        return None
    return recibido - total


def validar_cobro(carrito: Carrito, metodo: dict | None, recibido: Decimal | None,
                  cliente: dict | None) -> str | None:
    """Devuelve el mensaje que impide cobrar, o None si se puede."""
    if carrito.vacio:
        return "Agregue al menos un producto."
    if metodo is None:
        return "Elija el método de pago."
    if metodo.get("es_efectivo"):
        if recibido is None or recibido < carrito.total:
            return MONTO_INSUFICIENTE
    if metodo.get("es_credito"):
        if cliente is None:
            return "Elija el cliente de crédito."
        if carrito.total > cliente["disponible"]:
            return CREDITO_EXCEDIDO
    return None


# ---------------------------------------------------------------- apertura de caja

DENOMINACIONES = [
    ("Billete de $500", Decimal("500")), ("Billete de $200", Decimal("200")), ("Billete de $100", Decimal("100")),
    ("Billete de $50", Decimal("50")), ("Billete de $20", Decimal("20")), ("Monedas de $10", Decimal("10")),
]


def fondo_inicial(piezas: dict[str, int], morralla: Decimal) -> Decimal:
    valores = dict(DENOMINACIONES)
    return sum((valores[n] * p for n, p in piezas.items()), CERO) + morralla


# ---------------------------------------------------------------- corte de caja

def diferencia_arqueo(contado: Decimal, esperado: Decimal) -> Decimal:
    return contado - esperado


def texto_diferencia(dif: Decimal) -> str:
    if dif < 0:
        return "Diferencia (faltante)"
    if dif > 0:
        return "Diferencia (sobrante)"
    return "Sin diferencia"


def error_corte(contado: Decimal | None, esperado: Decimal, observaciones: str, venta_en_proceso: bool) -> tuple[str | None, str | None]:
    """(campo, mensaje) del primer error del corte, o (None, None)."""
    if venta_en_proceso:
        return "general", "No se puede cerrar con una venta en proceso."
    if contado is None or contado < 0:
        return "contado", "Ingrese el efectivo contado."
    if contado != esperado and not observaciones.strip():
        return "observaciones", "Las observaciones son obligatorias si hay diferencia."
    return None, None
