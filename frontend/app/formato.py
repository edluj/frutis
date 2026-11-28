"""Formato de dinero, peso y fechas como aparecen en el diseño."""
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

MENOS = "−"  # signo menos tipográfico del diseño (−$24.50)

_MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
_MESES_LARGOS = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]
_DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def dec(valor) -> Decimal:
    if isinstance(valor, Decimal):
        return valor
    try:
        return Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def dinero(valor, signo: bool = False) -> str:
    """$18,420.50 · −$24.50 · con signo=True los positivos llevan '+'."""
    v = dec(valor).quantize(Decimal("0.01"), ROUND_HALF_UP)
    texto = f"${abs(v):,.2f}"
    if v < 0:
        return MENOS + texto
    return ("+" + texto) if signo and v > 0 else texto


def leer_dinero(texto: str) -> Decimal | None:
    """Convierte '$1,000.50' o '1000.5' en Decimal; None si no es un número válido."""
    limpio = (texto or "").replace("$", "").replace(",", "").replace(MENOS, "-").strip()
    if not limpio:
        return None
    try:
        return Decimal(limpio)
    except InvalidOperation:
        return None


def cantidad(valor, unidad: str, decimales: int = 3) -> str:
    """1.250 kg · 8 pza. La pieza nunca lleva decimales."""
    u = "pza" if unidad in ("pieza", "pza") else unidad
    v = dec(valor)
    if u == "pza":
        return f"{v:,.0f} pza"
    return f"{v:,.{decimales}f} {u}"


def precio_unitario(precio, unidad: str) -> str:
    return f"{dinero(precio)}/kg" if unidad == "kg" else f"{dinero(precio)} pza"


def porcentaje(valor, decimales: int = 1) -> str:
    v = dec(valor)
    texto = f"{abs(v):.{decimales}f} %"
    return (MENOS + texto) if v < 0 else texto


def fecha(d: date | datetime | None) -> str:
    return d.strftime("%d/%m/%Y") if d else "—"


def fecha_hora(d: datetime | None) -> str:
    return d.strftime("%d/%m/%Y %H:%M") if d else "—"


def fecha_corta(d: date) -> str:
    """25 oct 2026"""
    return f"{d.day} {_MESES[d.month - 1]} {d.year}"


def fecha_larga(d: date) -> str:
    """Lunes 2 de noviembre de 2026"""
    return f"{_DIAS[d.weekday()]} {d.day} de {_MESES_LARGOS[d.month - 1]} de {d.year}"


def mes_anio(d: date) -> str:
    """Octubre 2026"""
    return f"{_MESES_LARGOS[d.month - 1].capitalize()} {d.year}"


def saludo(ahora: datetime) -> str:
    if ahora.hour < 12:
        return "Buenos días"
    if ahora.hour < 19:
        return "Buenas tardes"
    return "Buenas noches"


def leer_fecha(texto: str) -> date | None:
    try:
        return datetime.strptime(texto.strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def meses_recientes(n: int, hoy: date | None = None) -> list[str]:
    """["Noviembre 2026", "Octubre 2026", ...]: periodos de Finanzas con servidor."""
    hoy = hoy or date.today()
    salida, anio, mes = [], hoy.year, hoy.month
    for _ in range(n):
        salida.append(f"{_MESES_LARGOS[mes - 1].capitalize()} {anio}")
        anio, mes = (anio - 1, 12) if mes == 1 else (anio, mes - 1)
    return salida


def periodo_a_mes(texto: str) -> tuple[int, int]:
    """"Noviembre 2026" -> (2026, 11)."""
    nombre, anio = texto.lower().split()
    return int(anio), _MESES_LARGOS.index(nombre) + 1
