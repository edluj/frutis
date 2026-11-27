"""Datos fiscales (HU-32), factura CFDI con PAC simulado (HU-12a) y cancelación (HU-33)."""
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock
from xml.etree import ElementTree as ET

import pytest

from app.config import get_settings
from app.integrations.pac import PacSimulado, SinConexion, Timbre, get_pac
from app.main import app
from app.repositories import auditoria, usuarios
from app.repositories import facturacion as repo
from app.security.tokens import crear_token
from tests.conftest import CAJERO

CONTADOR = {**CAJERO, "id_usuario": 4, "usuario": "contador1", "id_rol": 4, "rol": "Contador"}
PERMISOS = {4: [{"modulo": "facturacion", "puede_ver": 1, "puede_crear": 1, "puede_editar": 1, "puede_eliminar": 1}]}
VENTA = {"id_venta": 7, "folio": "V00000007", "metodo": "Efectivo", "subtotal": Decimal("35.77"), "iva": Decimal("0.00"),
         "total": Decimal("35.77"), "estatus": "pagada", "facturado": 0, "id_borrador": None}
RECEPTOR = {"id_cliente": 2, "rfc": "RSO100518KJ3", "razon_social": "Restaurante El Sol", "regimen_fiscal": "601",
            "codigo_postal": "06600", "correo": "pagos@elsol.mx", "facturas": 0}
CONCEPTOS = [{"nombre": "Jitomate saladet", "unidad_venta": "kg", "cantidad": Decimal("1.255"),
              "precio_unitario": Decimal("28.50"), "importe": Decimal("35.77"), "tasa_iva": Decimal("0.0000"),
              "clave_sat": "01010101"}]
FACTURA = {"folio": "F-000002", "folio_venta": "V00000007", "uuid": "AAAAAAAA-BBBB-4CCC-8DDD-EEEEEEEEEEEE",
           "estatus": "Vigente", "rfc": "RSO100518KJ3", "razon_social": "Restaurante El Sol", "codigo_postal": "06600",
           "correo": "pagos@elsol.mx", "uso_cfdi": "G03", "forma_pago": "01", "metodo_pago": "PUE",
           "subtotal": Decimal("35.77"), "iva": Decimal("0.00"), "total": Decimal("35.77"),
           "fecha_timbrado": datetime(2026, 11, 27, 10, 0), "fecha_cancelacion": None, "motivo_cancelacion": None,
           "id_factura": 2, "id_venta": 7, "xml_path": None}
PEDIDO = {"folio_venta": "V00000007", "rfc": "RSO100518KJ3", "regimen_fiscal": "601", "codigo_postal": "06600",
          "uso_cfdi": "G03", "forma_pago": "01", "metodo_pago": "PUE", "correo": "pagos@elsol.mx"}


class PacFalso:
    def __init__(self, falla=False):
        self.falla = falla
        self.recibido = None

    def timbrar(self, xml):
        if self.falla:
            raise SinConexion()
        self.recibido = xml
        return PacSimulado().timbrar(xml)

    def cancelar(self, uuid, motivo, sustituto):
        self.cancelado = (uuid, motivo, sustituto)
        return datetime(2026, 11, 27, 12, 0)


@pytest.fixture
def contador(cliente, monkeypatch, tmp_path):
    monkeypatch.setattr(usuarios, "buscar_activo", lambda c, i: {2: CAJERO, 4: CONTADOR}.get(i))
    monkeypatch.setattr(usuarios, "permisos_del_rol", lambda c, r: PERMISOS.get(r, []))
    monkeypatch.setattr(get_settings(), "cfdi_dir", tmp_path)
    monkeypatch.setattr(repo, "venta_para_factura", lambda c, f, b=True: VENTA if f == "V00000007" else None)
    monkeypatch.setattr(repo, "cliente_por_rfc", lambda c, rfc: RECEPTOR if rfc == "RSO100518KJ3" else None)
    monkeypatch.setattr(repo, "timbres_usados", lambda c: 37)
    monkeypatch.setattr(repo, "conceptos_de_venta", lambda c, v: CONCEPTOS)
    monkeypatch.setattr(repo, "factura", lambda c, f, bloquear=False: FACTURA if f == "F-000002" else None)
    monkeypatch.setattr(repo, "insertar_borrador", MagicMock(return_value=(2, "F-000002")))
    monkeypatch.setattr(repo, "marcar_timbrada", MagicMock())
    return {"Authorization": f"Bearer {crear_token(4, 0)}"}


@pytest.fixture
def pac():
    falso = PacFalso()
    app.dependency_overrides[get_pac] = lambda: falso
    yield falso
    app.dependency_overrides.pop(get_pac, None)


def test_cajero_no_factura(cliente, contador, cabeceras, pac):
    assert cliente.post("/facturacion/facturas", json=PEDIDO, headers=cabeceras).status_code == 403


def test_timbres_disponibles(cliente, contador):
    assert cliente.get("/facturacion/timbres", headers=contador).json() == {"disponibles": 963, "contratados": 1000}


def test_timbrar_guarda_borrador_xml_y_uuid(cliente, contador, pac, conn, tmp_path):
    r = cliente.post("/facturacion/facturas", json=PEDIDO, headers=contador)
    assert r.status_code == 201 and r.json()["folio"] == "F-000002"
    raiz = ET.fromstring(pac.recibido)
    ns = {"cfdi": "http://www.sat.gob.mx/cfd/4"}
    assert raiz.get("Total") == "35.77" and raiz.get("Folio") == "000002" and raiz.get("Fecha")
    assert raiz.find("cfdi:Receptor", ns).get("Rfc") == "RSO100518KJ3"
    concepto = raiz.find("cfdi:Conceptos/cfdi:Concepto", ns)
    assert concepto.get("ClaveUnidad") == "KGM" and concepto.get("Importe") == "35.77"
    id_factura, uuid, _, archivo = repo.marcar_timbrada.call_args.args[1:]
    assert id_factura == 2 and archivo.startswith(str(tmp_path))
    assert "TimbreFiscalDigital" in open(archivo, encoding="utf-8").read() and uuid in archivo
    # El borrador se confirma antes de llamar al PAC y el timbre después.
    assert conn.commit.call_count >= 2
    assert auditoria.registrar.call_args.args[2] == "factura_timbrada"


def test_un_ticket_solo_se_factura_una_vez(cliente, contador, pac, monkeypatch):
    monkeypatch.setattr(repo, "venta_para_factura", lambda c, f, b=True: {**VENTA, "facturado": 1})
    r = cliente.post("/facturacion/facturas", json=PEDIDO, headers=contador)
    assert r.status_code == 409 and r.json() == {
        "detail": "Este ticket ya fue facturado. Un ticket solo se factura una vez.", "campo": "ticket"}
    repo.insertar_borrador.assert_not_called()


def test_sin_conexion_conserva_el_borrador(cliente, contador, monkeypatch):
    falla = PacFalso(falla=True)
    app.dependency_overrides[get_pac] = lambda: falla
    try:
        r = cliente.post("/facturacion/facturas", json=PEDIDO, headers=contador)
    finally:
        app.dependency_overrides.pop(get_pac, None)
    assert r.status_code == 503 and r.json()["detail"] == "Sin conexión a internet, no es posible timbrar."
    repo.insertar_borrador.assert_called_once()
    repo.marcar_timbrada.assert_not_called()
    assert auditoria.registrar.call_args.args[2] == "factura_borrador"


def test_reintento_reutiliza_el_borrador(cliente, contador, pac, monkeypatch):
    monkeypatch.setattr(repo, "venta_para_factura", lambda c, f, b=True: {**VENTA, "id_borrador": 2})
    actualizar = MagicMock(return_value="F-000002")
    monkeypatch.setattr(repo, "actualizar_borrador", actualizar)
    assert cliente.post("/facturacion/facturas", json=PEDIDO, headers=contador).status_code == 201
    actualizar.assert_called_once()
    repo.insertar_borrador.assert_not_called()


@pytest.mark.parametrize(("cambio", "estado", "campo"), [
    ({"folio_venta": "V00000099"}, 404, "ticket"), ({"rfc": "XAXX010101000"}, 409, "rfc")])
def test_ticket_o_rfc_desconocido(cliente, contador, pac, cambio, estado, campo):
    r = cliente.post("/facturacion/facturas", json={**PEDIDO, **cambio}, headers=contador)
    assert r.status_code == estado and r.json()["campo"] == campo


def test_ticket_con_devoluciones_no_se_factura(cliente, contador, pac, monkeypatch):
    monkeypatch.setattr(repo, "venta_para_factura", lambda c, f, b=True: {**VENTA, "estatus": "devuelta_parcial"})
    assert cliente.post("/facturacion/facturas", json=PEDIDO, headers=contador).status_code == 409


def test_sin_timbres(cliente, contador, pac, monkeypatch):
    monkeypatch.setattr(repo, "timbres_usados", lambda c: 1000)
    assert cliente.post("/facturacion/facturas", json=PEDIDO, headers=contador).status_code == 409


@pytest.mark.parametrize("cambio", [{"metodo_pago": "XXX"}, {"codigo_postal": "123"}, {"rfc": "BAD"},
                                    {"folio_venta": "1 OR 1=1"}, {"correo": "x"}])
def test_pedido_invalido_422(cliente, contador, cambio):
    assert cliente.post("/facturacion/facturas", json={**PEDIDO, **cambio}, headers=contador).status_code == 422


def test_cancelar_con_motivo_01_exige_sustituta_vigente(cliente, contador, pac):
    r = cliente.post("/facturacion/facturas/F-000002/cancelacion", json={"motivo": "01"}, headers=contador)
    assert r.status_code == 409 and r.json()["campo"] == "sustituto"
    r = cliente.post("/facturacion/facturas/F-000002/cancelacion", json={"motivo": "01", "folio_sustituto": "F-000002"},
                     headers=contador)
    assert r.status_code == 409


def test_cancelar_con_motivo_02(cliente, contador, pac, monkeypatch):
    marcar = MagicMock()
    monkeypatch.setattr(repo, "marcar_cancelada", marcar)
    r = cliente.post("/facturacion/facturas/F-000002/cancelacion", json={"motivo": "02"}, headers=contador)
    assert r.status_code == 200
    assert pac.cancelado == (FACTURA["uuid"], "02", None)
    assert marcar.call_args.args[1:3] == (2, "02")


def test_solo_se_cancelan_vigentes(cliente, contador, pac, monkeypatch):
    monkeypatch.setattr(repo, "factura", lambda c, f, bloquear=False: {**FACTURA, "estatus": "Cancelada"})
    assert cliente.post("/facturacion/facturas/F-000002/cancelacion", json={"motivo": "02"},
                        headers=contador).status_code == 409


def test_alta_de_cliente_fiscal_con_rfc_repetido(cliente, contador, monkeypatch):
    monkeypatch.setattr(repo, "rfc_en_uso", lambda c, rfc, e: True)
    datos = {"rfc": "RSO100518KJ3", "razon_social": "Restaurante El Sol", "regimen_fiscal": "601",
             "codigo_postal": "06600", "correo": "pagos@elsol.mx"}
    r = cliente.post("/facturacion/clientes", json=datos, headers=contador)
    assert r.status_code == 409 and r.json()["campo"] == "rfc"


def test_pac_simulado_agrega_el_timbre():
    timbre = PacSimulado().timbrar('<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" Total="1.00"/>')
    assert isinstance(timbre, Timbre) and len(timbre.uuid) == 36
    assert "TimbreFiscalDigital" in timbre.xml and timbre.uuid in timbre.xml


def test_ticket_para_factura(cliente, contador, monkeypatch):
    r = cliente.get("/facturacion/tickets/V00000007", headers=contador)
    assert r.status_code == 200 and r.json()["conceptos"][0]["clave_sat"] == "01010101"
    monkeypatch.setattr(repo, "venta_para_factura", lambda c, f, b=True: {**VENTA, "facturado": 1})
    r = cliente.get("/facturacion/tickets/V00000007", headers=contador)
    assert r.status_code == 409 and r.json()["campo"] == "ticket"
