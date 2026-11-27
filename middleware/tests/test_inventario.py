"""Catálogo: categorías (HU-22) y productos (HU-10)."""
from decimal import Decimal
from unittest.mock import MagicMock

import pymysql
import pytest
from sqlalchemy.exc import IntegrityError

from app.repositories import auditoria, usuarios
from app.repositories import inventario as repo
from app.security.tokens import crear_token
from tests.conftest import CAJERO

COMPRAS = {**CAJERO, "id_usuario": 3, "usuario": "compras1", "id_rol": 3, "rol": "Compras"}
PERMISOS = {
    2: [{"modulo": "inventario", "puede_ver": 1, "puede_crear": 0, "puede_editar": 0, "puede_eliminar": 0}],
    3: [{"modulo": "inventario", "puede_ver": 1, "puede_crear": 1, "puede_editar": 1, "puede_eliminar": 0}],
}
CATEGORIA = {"id_categoria": 1, "nombre": "Frutas", "descripcion": "Fruta fresca", "activo": 1, "productos_activos": 4}
PRODUCTO = {
    "id_producto": 1, "codigo_barras": "FRU-0001", "nombre": "Manzana roja", "id_categoria": 1, "categoria": "Frutas",
    "unidad_venta": "kg", "precio_venta": Decimal("45.00"), "costo_actual": Decimal("32.00"),
    "tasa_iva": Decimal("0.0000"), "stock_minimo": Decimal("10.000"), "es_frecuente": 1, "activo": 1,
    "existencia": Decimal("9.000"), "estado": "Bajo",
}
NUEVO = {"codigo_barras": "FRU-0009", "nombre": "Mango ataulfo", "id_categoria": 1, "unidad_venta": "kg",
         "precio_venta": "38.50", "stock_minimo": "5"}


@pytest.fixture
def compras(cliente, monkeypatch):
    monkeypatch.setattr(usuarios, "buscar_activo", lambda c, i: {2: CAJERO, 3: COMPRAS}.get(i))
    monkeypatch.setattr(usuarios, "permisos_del_rol", lambda c, r: PERMISOS.get(r, []))
    monkeypatch.setattr(repo, "categoria", lambda c, i, bloquear=False: CATEGORIA if i == 1 else None)
    monkeypatch.setattr(repo, "listar_categorias", lambda c, b, a: [CATEGORIA])
    monkeypatch.setattr(repo, "nombre_categoria_en_uso", lambda c, n, e: False)
    monkeypatch.setattr(repo, "productos_activos_de", lambda c, i: 0)
    monkeypatch.setattr(repo, "codigo_en_uso", lambda c, codigo, e: False)
    monkeypatch.setattr(repo, "producto", lambda c, i, bloquear=False: {"id_producto": 1, "precio_venta": Decimal("45.00")})
    monkeypatch.setattr(repo, "producto_catalogo", lambda c, i: PRODUCTO)
    return {"Authorization": f"Bearer {crear_token(3, 0)}"}


def _duplicado():
    return IntegrityError("INSERT", {}, pymysql.err.IntegrityError(1062, "Duplicate entry"))


# ---------------------------------------------------------------- permisos

def test_cajero_ve_el_catalogo_pero_no_lo_edita(cliente, compras, cabeceras, monkeypatch):
    monkeypatch.setattr(repo, "listar_productos", lambda c, b, i: [PRODUCTO])
    assert cliente.get("/inventario/productos", headers=cabeceras).status_code == 200
    assert cliente.post("/inventario/productos", json=NUEVO, headers=cabeceras).status_code == 403
    assert cliente.put("/inventario/categorias/1", json={"nombre": "X"}, headers=cabeceras).status_code == 403


def test_sin_token_401(cliente):
    assert cliente.get("/inventario/categorias").status_code == 401


# ---------------------------------------------------------------- categorías

def test_alta_de_categoria_audita(cliente, compras, monkeypatch):
    insertar = MagicMock(return_value=1)
    monkeypatch.setattr(repo, "insertar_categoria", insertar)
    r = cliente.post("/inventario/categorias", json={"nombre": "Frutas", "descripcion": ""}, headers=compras)
    assert r.status_code == 201
    assert insertar.call_args.args[1:] == ("Frutas", None, True)
    assert auditoria.registrar.call_args.args[1:3] == ("inventario", "categoria_alta")


def test_nombre_de_categoria_repetido_marca_el_campo(cliente, compras, monkeypatch):
    monkeypatch.setattr(repo, "nombre_categoria_en_uso", lambda c, n, e: True)
    r = cliente.post("/inventario/categorias", json={"nombre": "Frutas"}, headers=compras)
    assert r.status_code == 409
    assert r.json() == {"detail": "Ya existe una categoría con ese nombre.", "campo": "nombre"}


def test_alta_simultanea_con_el_mismo_nombre(cliente, compras, monkeypatch, conn):
    monkeypatch.setattr(repo, "insertar_categoria", MagicMock(side_effect=_duplicado()))
    r = cliente.post("/inventario/categorias", json={"nombre": "Frutas"}, headers=compras)
    assert r.status_code == 409 and r.json()["campo"] == "nombre"
    conn.rollback.assert_called()


def test_no_se_da_de_baja_una_categoria_con_productos_activos(cliente, compras, monkeypatch):
    monkeypatch.setattr(repo, "productos_activos_de", lambda c, i: 4)
    actualizar = MagicMock()
    monkeypatch.setattr(repo, "actualizar_categoria", actualizar)
    r = cliente.put("/inventario/categorias/1", json={"nombre": "Frutas", "activo": False}, headers=compras)
    assert r.status_code == 409
    assert r.json() == {"detail": "No se puede dar de baja: tiene 4 productos activos.", "campo": "estatus"}
    actualizar.assert_not_called()


def test_editar_categoria_inexistente_404(cliente, compras):
    assert cliente.put("/inventario/categorias/99", json={"nombre": "X"}, headers=compras).status_code == 404


@pytest.mark.parametrize("nombre", ["<script>", "Frutas'; DROP TABLE x", ""])
def test_categoria_con_texto_invalido_422(cliente, compras, nombre):
    assert cliente.post("/inventario/categorias", json={"nombre": nombre}, headers=compras).status_code == 422


# ---------------------------------------------------------------- productos

def test_filtro_bajo_el_minimo_excluye_normales_y_bajas(cliente, compras, monkeypatch):
    normal = {**PRODUCTO, "id_producto": 2, "estado": "Normal"}
    baja = {**PRODUCTO, "id_producto": 3, "activo": 0}
    monkeypatch.setattr(repo, "listar_productos", lambda c, b, i: [PRODUCTO, normal, baja])
    r = cliente.get("/inventario/productos", params={"existencia": "bajo"}, headers=compras)
    assert [p["id_producto"] for p in r.json()] == [1]
    todas = cliente.get("/inventario/productos", headers=compras).json()
    assert len(todas) == 3


def test_alta_de_producto(cliente, compras, monkeypatch):
    insertar = MagicMock(return_value=9)
    monkeypatch.setattr(repo, "insertar_producto", insertar)
    r = cliente.post("/inventario/productos", json=NUEVO, headers=compras)
    assert r.status_code == 201
    valores = insertar.call_args.args[1]
    assert valores["precio_venta"] == Decimal("38.50") and valores["tasa_iva"] == Decimal("0")
    assert auditoria.registrar.call_args.args[2] == "producto_alta"


def test_codigo_repetido_marca_el_campo(cliente, compras, monkeypatch):
    monkeypatch.setattr(repo, "codigo_en_uso", lambda c, codigo, e: True)
    r = cliente.post("/inventario/productos", json=NUEVO, headers=compras)
    assert r.status_code == 409
    assert r.json() == {"detail": "El código de barras ya está registrado.", "campo": "codigo"}


def test_categoria_inactiva_solo_para_productos_de_baja(cliente, compras, monkeypatch):
    inactiva = {**CATEGORIA, "activo": 0}
    monkeypatch.setattr(repo, "categoria", lambda c, i, bloquear=False: inactiva)
    monkeypatch.setattr(repo, "actualizar_producto", MagicMock())
    r = cliente.put("/inventario/productos/1", json={**NUEVO, "precio_venta": "45.00"}, headers=compras)
    assert r.status_code == 409 and r.json()["campo"] == "categoria"
    r = cliente.put("/inventario/productos/1", json={**NUEVO, "precio_venta": "45.00", "activo": False}, headers=compras)
    assert r.status_code == 200


def test_cambio_de_precio_queda_en_el_historial(cliente, compras, monkeypatch):
    monkeypatch.setattr(repo, "actualizar_producto", MagicMock())
    historial = MagicMock()
    monkeypatch.setattr(repo, "registrar_cambio_precio", historial)
    assert cliente.put("/inventario/productos/1", json={**NUEVO, "precio_venta": "48.00"}, headers=compras).status_code == 200
    assert historial.call_args.args[1:] == (1, Decimal("45.00"), Decimal("48.00"), 3, "Ajuste individual")


def test_mismo_precio_no_toca_el_historial(cliente, compras, monkeypatch):
    monkeypatch.setattr(repo, "actualizar_producto", MagicMock())
    historial = MagicMock()
    monkeypatch.setattr(repo, "registrar_cambio_precio", historial)
    cliente.put("/inventario/productos/1", json={**NUEVO, "precio_venta": "45.00"}, headers=compras)
    historial.assert_not_called()


@pytest.mark.parametrize(
    "cambio",
    [{"precio_venta": "0"}, {"precio_venta": "-1"}, {"unidad_venta": "litro"}, {"tasa_iva": "0.08"},
     {"codigo_barras": "FRU 01"}, {"nombre": "<b>Mango</b>"}, {"id_producto": 5}],
)
def test_producto_invalido_422(cliente, compras, cambio):
    assert cliente.post("/inventario/productos", json={**NUEVO, **cambio}, headers=compras).status_code == 422


def test_acepta_iva_de_16(cliente, compras, monkeypatch):
    monkeypatch.setattr(repo, "insertar_producto", MagicMock(return_value=9))
    r = cliente.post("/inventario/productos", json={**NUEVO, "tasa_iva": "0.16"}, headers=compras)
    assert r.status_code == 201
