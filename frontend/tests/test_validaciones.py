from decimal import Decimal as D

from app import formato as fmt
from app.validaciones import (
    cantidad_positiva, error_correo, error_cp, error_rfc, error_usuario, monto_positivo, tipo_rfc,
)


def test_rfc_moral_y_fisica():
    assert tipo_rfc("HVA010203AB1") == "moral"
    assert tipo_rfc("RAJU800101AB2") == "fisica"
    assert tipo_rfc("CGO150806K2") is None  # 11 caracteres, el caso del diseño
    assert error_rfc("CGO150806K2", solo_moral=True) == "El RFC debe tener 12 caracteres (persona moral)."
    assert error_rfc("") == "El RFC es obligatorio."
    assert error_rfc("rso100518kj3") is None


def test_correo():
    assert error_correo("rosa.martinez@frutis") == "Ingresa el formato de correo correcto."
    assert error_correo("pagos@elsol.mx") is None
    assert error_correo("", obligatorio=False) is None


def test_usuario_y_cp():
    assert error_usuario("mperez") is None
    assert error_usuario("m perez") is not None
    assert error_cp("06600") is None and error_cp("6600") is not None


def test_montos_y_cantidades():
    assert monto_positivo("$1,000.50") == (D("1000.50"), None)
    assert monto_positivo("0")[1] == "Ingrese un monto válido."
    assert monto_positivo("10.123")[1] is not None
    assert cantidad_positiva("0.500 kg") == D("0.500")
    assert cantidad_positiva("1.5", decimales=0) is None


def test_formato_del_diseno():
    assert fmt.dinero(D("18420.5")) == "$18,420.50"
    assert fmt.dinero(D("-24.5")) == "−$24.50"
    assert fmt.cantidad(D("1.25"), "kg") == "1.250 kg"
    assert fmt.cantidad(D("8"), "pieza") == "8 pza"
    assert fmt.precio_unitario(D("42"), "kg") == "$42.00/kg"
    assert fmt.leer_dinero("$1,234.50") == D("1234.50")
