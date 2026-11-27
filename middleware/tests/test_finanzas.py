"""Clientes de crédito (HU-39) y su lista para el cobro del POS (HU-38a)."""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.repositories import auditoria, usuarios
from app.repositories import finanzas as repo
from app.security.tokens import crear_token
from tests.conftest import CAJERO

CONTADOR = {**CAJERO, "id_usuario": 4, "usuario": "contador1", "id_rol": 4, "rol": "Contador"}
PERMISOS = {
    2: [{"modulo": "pos", "puede_ver": 1, "puede_crear": 1, "puede_editar": 0, "puede_eliminar": 0}],
    4: [{"modulo": "finanzas", "puede_ver": 1, "puede_crear": 1, "puede_editar": 1, "puede_eliminar": 1},
        {"modulo": "pos", "puede_ver": 1, "puede_crear": 0, "puede_editar": 0, "puede_eliminar": 0}],
}
CLIENTE = {"id_cliente_credito": 1, "nombre": "Fonda Doña Lupe", "telefono": "5555550202", "correo": None,
           "limite_credito": Decimal("1000.00"), "dias_credito": 15, "activo": 1, "rfc_fiscal": None,
           "debe": Decimal("68.00"), "vencido": 0}
ALTA = {"nombre": "Cocina Económica Rosy", "telefono": "55 3388 1200", "limite_credito": "3000.00",
        "dias_credito": 15, "correo": "", "rfc_fiscal": ""}


@pytest.fixture
def contador(cliente, monkeypatch):
    monkeypatch.setattr(usuarios, "buscar_activo", lambda c, i: {2: CAJERO, 4: CONTADOR}.get(i))
    monkeypatch.setattr(usuarios, "permisos_del_rol", lambda c, r: PERMISOS.get(r, []))
    monkeypatch.setattr(repo, "cliente", lambda c, i, bloquear=False: CLIENTE if i == 1 else None)
    return {"Authorization": f"Bearer {crear_token(4, 0)}"}


def test_alta_de_cliente_de_credito(cliente, contador, monkeypatch):
    insertar = MagicMock(return_value=1)
    monkeypatch.setattr(repo, "insertar_cliente", insertar)
    r = cliente.post("/finanzas/clientes-credito", json=ALTA, headers=contador)
    assert r.status_code == 201
    valores = insertar.call_args.args[1]
    assert valores["limite_credito"] == Decimal("3000.00") and valores["correo"] is None and valores["id_cliente"] is None
    assert auditoria.registrar.call_args.args[1:3] == ("finanzas", "cliente_credito_alta")


@pytest.mark.parametrize("cambio", [{"limite_credito": "0"}, {"dias_credito": 0}, {"telefono": "x"},
                                    {"nombre": "<script>"}, {"rfc_fiscal": "MAL"}])
def test_cliente_invalido_422(cliente, contador, cambio):
    assert cliente.post("/finanzas/clientes-credito", json={**ALTA, **cambio}, headers=contador).status_code == 422


def test_rfc_fiscal_inexistente_marca_el_campo(cliente, contador, monkeypatch):
    monkeypatch.setattr(repo, "id_fiscal", lambda c, rfc: None)
    r = cliente.post("/finanzas/clientes-credito", json={**ALTA, "rfc_fiscal": "LUGO750312HM4"}, headers=contador)
    assert r.status_code == 409 and r.json()["campo"] == "fiscal"


def test_suspender_cliente(cliente, contador, monkeypatch):
    actualizar = MagicMock()
    monkeypatch.setattr(repo, "actualizar_cliente", actualizar)
    r = cliente.put("/finanzas/clientes-credito/1", json={**ALTA, "activo": False}, headers=contador)
    assert r.status_code == 200 and actualizar.call_args.args[2]["activo"] is False
    assert "Suspendido" in auditoria.registrar.call_args.args[3]


def test_editar_cliente_inexistente_404(cliente, contador):
    assert cliente.put("/finanzas/clientes-credito/9", json=ALTA, headers=contador).status_code == 404


def test_cajero_no_administra_clientes_pero_los_ve_en_el_pos(cliente, contador, cabeceras, monkeypatch):
    listar = MagicMock(return_value=[CLIENTE])
    monkeypatch.setattr(repo, "listar_clientes", listar)
    assert cliente.get("/finanzas/clientes-credito", headers=cabeceras).status_code == 403
    r = cliente.get("/pos/clientes-credito", headers=cabeceras)
    assert r.status_code == 200
    assert listar.call_args.args[1:] == (None, True)
    [c] = r.json()
    assert c["disponible"] == "932.00" and c["vence"] == (date.today() + timedelta(days=15)).isoformat()


def test_contador_sin_permiso_de_cobro_no_usa_la_lista_del_pos(cliente, contador):
    assert cliente.get("/pos/clientes-credito", headers=contador).status_code == 403


def test_disponible_nunca_es_negativo(cliente, contador, cabeceras, monkeypatch):
    excedido = {**CLIENTE, "debe": Decimal("1200.00"), "vencido": 1}
    monkeypatch.setattr(repo, "listar_clientes", lambda c, b, a: [excedido])
    [c] = cliente.get("/pos/clientes-credito", headers=cabeceras).json()
    assert c["disponible"] == "0.00" and c["vencido"] is True
