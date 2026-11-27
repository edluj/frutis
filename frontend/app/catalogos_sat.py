"""Catálogos del SAT usados en las pantallas de facturación (CFDI 4.0)."""

REGIMENES = [
    ("601 General de Ley Personas Morales", "601"),
    ("603 Personas Morales con Fines no Lucrativos", "603"),
    ("605 Sueldos y Salarios", "605"),
    ("606 Arrendamiento", "606"),
    ("612 Personas Físicas con Actividades Empresariales", "612"),
    ("616 Sin obligaciones fiscales", "616"),
    ("621 Incorporación Fiscal", "621"),
    ("626 Régimen Simplificado de Confianza", "626"),
]
USOS_CFDI = [
    ("G01 Adquisición de mercancías", "G01"),
    ("G03 Gastos en general", "G03"),
    ("S01 Sin efectos fiscales", "S01"),
]
FORMAS_PAGO = [
    ("01 Efectivo", "01"),
    ("03 Transferencia electrónica", "03"),
    ("04 Tarjeta de crédito", "04"),
    ("28 Tarjeta de débito", "28"),
    ("99 Por definir", "99"),
]
METODOS_PAGO = [
    ("PUE Pago en una sola exhibición", "PUE"),
    ("PPD Pago en parcialidades o diferido", "PPD"),
]
MOTIVOS_CANCELACION = [
    ("01 Comprobante emitido con errores con relación", "01"),
    ("02 Comprobante emitido con errores sin relación", "02"),
    ("03 No se llevó a cabo la operación", "03"),
    ("04 Operación nominativa relacionada en una factura global", "04"),
]
# Forma de pago SAT sugerida según el método con que se cobró el ticket.
FORMA_POR_METODO = {"Efectivo": "01", "Transferencia": "03", "Tarjeta de crédito": "04", "Tarjeta de débito": "28"}


def nombre(catalogo: list[tuple[str, str]], clave: str) -> str:
    return next((t for t, c in catalogo if c == clave), clave)
