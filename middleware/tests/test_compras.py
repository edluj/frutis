"""Compras: proveedores (HU-23) y lotes de compra (HU-11)."""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.repositories import auditoria, usuarios
from app.repositories import compras as repo
from app.security.tokens import crear_token
from tests.conftest import CAJERO

COMPRAS = {**CAJERO, "id_usuario": 3, "usuario": "compras1", "id_rol": 3, "rol": "Compras"}
PERMISOS = {3: [{"modulo": "compras", "puede_ver": 1, "puede_crear": 1, "puede_editar": 1, "puede_eliminar": 1}]}
PROVEEDOR = {
    "id_proveedor": 1, "razon_social": "Hortalizas del Valle", "rfc": "HVA010203AB1", "telefono": "55 1234 5678",
    "correo": "ventas@hvalle.mx", "direccion": "Central de Abasto, nave I", "dias_credito": 15, "activo": 1,
    "saldo": Decimal("0.00"),
}
ALTA = {"razon_social": "Hortalizas del Valle", "rfc": "hva010203ab1", "telefono": "55 1234 5678",
        "correo": "", "direccion": "", "dias_credito": 15}
HOY = date.today()
PRODUCTOS = {1: {"id_producto": 1, "nombre": "Manzana roja", "unidad_venta": "kg", "activo": 1},
             4: {"id_producto": 4, "nombre": "Piña", "unidad_venta": "pieza", "activo": 1}}
LOTE = {
    "id_proveedor": 1, "factura": "A-4302", "entrada": HOY.isoformat(), "dias_credito": 15,
    "renglones": [
        {"id_producto": 1, "cantidad": "20.500", "costo": "30.00", "caducidad": (HOY + timedelta(days=7)).isoformat()},
        {"id_producto": 4, "cantidad": "10", "costo": "22.15", "caducidad": (HOY + timedelta(days=9)).isoformat()},
    ],
}


@pytest.fixture
def compras(cliente, monkeypatch):
    monkeypatch.setattr(usuarios, "buscar_activo", lambda c, i: {2: CAJERO, 3: COMPRAS}.get(i))
    monkeypatch.setattr(usuarios, "permisos_del_rol", lambda c, r: PERMISOS.get(r, []))
    monkeypatch.setattr(repo, "proveedor", lambda c, i, bloquear=False: PROVEEDOR if i == 1 else None)
    monkeypatch.setattr(repo, "rfc_en_uso", lambda c, rfc, e: False)
    monkeypatch.setattr(repo, "productos_para_lote", lambda c, ids: {i: PRODUCTOS[i] for i in ids if i in PRODUCTOS})
    return {"Authorization": f"Bearer {crear_token(3, 0)}"}


@pytest.fixture
def escritura(monkeypatch):
    llamadas = {n: MagicMock() for n in ("insertar_existencia", "actualizar_costo", "insertar_cuenta_por_pagar")}
    llamadas["insertar_lote"] = MagicMock(return_value=(9, "L-00000009"))
    for nombre, mock in llamadas.items():
        monkeypatch.setattr(repo, nombre, mock)
    return llamadas


# ---------------------------------------------------------------- permisos

def test_cajero_no_entra_a_compras(cliente, compras, cabeceras):
    assert cliente.get("/compras/proveedores", headers=cabeceras).status_code == 403
    assert cliente.post("/compras/lotes", json=LOTE, headers=cabeceras).status_code == 403


# ---------------------------------------------------------------- proveedores

def test_alta_de_proveedor_normaliza_rfc_y_vacios(cliente, compras, monkeypatch):
    insertar = MagicMock(return_value=1)
    monkeypatch.setattr(repo, "insertar_proveedor", insertar)
    r = cliente.post("/compras/proveedores", json=ALTA, headers=compras)
    assert r.status_code == 201
    valores = insertar.call_args.args[1]
    assert valores["rfc"] == "HVA010203AB1" and valores["correo"] is None and valores["direccion"] is None
    assert auditoria.registrar.call_args.args[1:3] == ("compras", "proveedor_alta")


def test_rfc_repetido_marca_el_campo(cliente, compras, monkeypatch):
    monkeypatch.setattr(repo, "rfc_en_uso", lambda c, rfc, e: True)
    r = cliente.post("/compras/proveedores", json=ALTA, headers=compras)
    assert r.status_code == 409 and r.json() == {"detail": "Ya existe un proveedor con ese RFC.", "campo": "rfc"}


def test_no_se_da_de_baja_un_proveedor_con_saldo(cliente, compras, monkeypatch):
    con_saldo = {**PROVEEDOR, "saldo": Decimal("1020.00")}
    monkeypatch.setattr(repo, "proveedor", lambda c, i, bloquear=False: con_saldo)
    actualizar = MagicMock()
    monkeypatch.setattr(repo, "actualizar_proveedor", actualizar)
    r = cliente.put("/compras/proveedores/1", json={**ALTA, "activo": False}, headers=compras)
    assert r.status_code == 409 and r.json()["campo"] == "estatus"
    actualizar.assert_not_called()


@pytest.mark.parametrize(
    "cambio",
    [{"rfc": "HVA01"}, {"rfc": "HVA010203AB1'"}, {"correo": "sin-arroba"}, {"correo": "a@b.c<script>"},
     {"telefono": "abc"}, {"dias_credito": -1}, {"razon_social": "<b>X</b>"}],
)
def test_proveedor_invalido_422(cliente, compras, cambio):
    assert cliente.post("/compras/proveedores", json={**ALTA, **cambio}, headers=compras).status_code == 422


def test_rfc_de_persona_fisica(cliente, compras, monkeypatch):
    monkeypatch.setattr(repo, "insertar_proveedor", MagicMock(return_value=1))
    r = cliente.post("/compras/proveedores", json={**ALTA, "rfc": "GOML800101AB1"}, headers=compras)
    assert r.status_code == 201


# ---------------------------------------------------------------- lotes

def test_lote_a_credito_suma_inventario_costo_y_cuenta_por_pagar(cliente, compras, escritura):
    r = cliente.post("/compras/lotes", json=LOTE, headers=compras)
    assert r.status_code == 201
    # 20.500 x 30.00 = 615.00 y 10 x 22.15 = 221.50
    assert r.json() == {"folio": "L-00000009", "total": "836.50"}
    assert escritura["insertar_lote"].call_args.args[1:] == (1, 3, HOY, True, Decimal("836.50"), "A-4302")
    assert escritura["insertar_existencia"].call_count == 2
    assert escritura["actualizar_costo"].call_args.args[1:] == (4, Decimal("22.15"))
    assert escritura["insertar_cuenta_por_pagar"].call_args.args[1:] == (9, Decimal("836.50"), HOY + timedelta(days=15))
    assert auditoria.registrar.call_args.args[2] == "lote_alta"


def test_lote_de_contado_no_crea_cuenta_por_pagar(cliente, compras, escritura):
    r = cliente.post("/compras/lotes", json={**LOTE, "dias_credito": 0, "factura": ""}, headers=compras)
    assert r.status_code == 201
    assert escritura["insertar_lote"].call_args.args[4] is False
    assert escritura["insertar_lote"].call_args.args[6] is None
    escritura["insertar_cuenta_por_pagar"].assert_not_called()


@pytest.mark.parametrize(
    ("cambio", "mensaje"),
    [
        ({"id_proveedor": 99}, "Elija un proveedor activo."),
        ({"entrada": (HOY + timedelta(days=1)).isoformat()}, "La fecha de entrada no puede ser futura."),
        ({"renglones": [LOTE["renglones"][0], LOTE["renglones"][0]]}, "Un producto aparece dos veces"),
        ({"renglones": [{**LOTE["renglones"][1], "cantidad": "2.5"}]}, "Piña se compra por pieza"),
        ({"renglones": [{**LOTE["renglones"][0], "caducidad": (HOY - timedelta(days=1)).isoformat()}]},
         "La caducidad de Manzana roja es anterior"),
        ({"renglones": [{**LOTE["renglones"][0], "id_producto": 77}]}, "Producto no encontrado o inactivo."),
    ],
)
def test_lote_rechazado_no_escribe_nada(cliente, compras, escritura, cambio, mensaje):
    r = cliente.post("/compras/lotes", json={**LOTE, **cambio}, headers=compras)
    assert r.status_code == 409 and r.json()["detail"].startswith(mensaje)
    escritura["insertar_lote"].assert_not_called()


@pytest.mark.parametrize(
    "renglon",
    [{"cantidad": "0"}, {"costo": "0"}, {"costo": "-5"}, {"cantidad": "1.2345"}, {"id_usuario": 1}],
)
def test_renglon_invalido_422(cliente, compras, renglon):
    lote = {**LOTE, "renglones": [{**LOTE["renglones"][0], **renglon}]}
    assert cliente.post("/compras/lotes", json=lote, headers=compras).status_code == 422


def test_lote_sin_renglones_422(cliente, compras):
    assert cliente.post("/compras/lotes", json={**LOTE, "renglones": []}, headers=compras).status_code == 422


def test_filtro_de_pago_en_lotes(cliente, compras, monkeypatch):
    base = {"folio": "L-00000001", "id_proveedor": 1, "proveedor": "X", "entrada": HOY, "productos": 2,
            "total": Decimal("10"), "kilos": Decimal("2"), "dias_credito": 0, "pago": "Pagado",
            "saldo": Decimal("0"), "caducidad": HOY}
    vencido = {**base, "folio": "L-00000002", "pago": "Vencido", "dias_credito": 15, "saldo": Decimal("10")}
    monkeypatch.setattr(repo, "listar_lotes", lambda c, p, d, h: [vencido, base])
    r = cliente.get("/compras/lotes", params={"pago": "Vencido"}, headers=compras)
    assert [f["folio"] for f in r.json()] == ["L-00000002"]


def test_detalle_de_lote_inexistente_404_y_folio_invalido_422(cliente, compras, monkeypatch):
    monkeypatch.setattr(repo, "lote", lambda c, f: None)
    assert cliente.get("/compras/lotes/L-00000099", headers=compras).status_code == 404
    assert cliente.get("/compras/lotes/1 OR 1=1", headers=compras).status_code == 422
