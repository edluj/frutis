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


# ---------------------------------------------------------------- mermas (HU-17)

FILA_LOTE = {"id_inventario": 4, "cantidad_disponible": Decimal("10.000"), "costo_unitario": Decimal("32.00"),
             "nombre": "Manzana roja", "unidad_venta": "kg"}
MERMA = {"id_producto": 1, "folio_lote": "L-00000002", "cantidad": "1.255", "motivo": "golpe", "observaciones": ""}


@pytest.fixture
def lote_manzana(monkeypatch):
    monkeypatch.setattr(repo, "existencia_de_lote", lambda c, p, f: FILA_LOTE if (p, f) == (1, "L-00000002") else None)
    registrar = MagicMock()
    monkeypatch.setattr(repo, "registrar_merma", registrar)
    return registrar


def test_merma_descuenta_y_calcula_el_costo_del_lote(cliente, compras, lote_manzana):
    r = cliente.post("/inventario/mermas", json=MERMA, headers=compras)
    assert r.status_code == 201
    # 1.255 kg x 32.00 = 40.16
    assert r.json() == {"costo": "40.16"}
    assert lote_manzana.call_args.args[1:] == (4, Decimal("1.255"), "golpe", Decimal("40.16"), None, 3)
    assert auditoria.registrar.call_args.args[2] == "merma_alta"


def test_merma_mayor_a_la_existencia_del_lote(cliente, compras, lote_manzana):
    r = cliente.post("/inventario/mermas", json={**MERMA, "cantidad": "10.001"}, headers=compras)
    assert r.status_code == 409
    assert r.json() == {"detail": "La cantidad supera la existencia del lote.", "campo": "cantidad"}
    lote_manzana.assert_not_called()


def test_merma_de_pieza_fraccionada(cliente, compras, lote_manzana, monkeypatch):
    pina = {**FILA_LOTE, "nombre": "Piña", "unidad_venta": "pieza"}
    monkeypatch.setattr(repo, "existencia_de_lote", lambda c, p, f: pina)
    r = cliente.post("/inventario/mermas", json={**MERMA, "cantidad": "1.5"}, headers=compras)
    assert r.status_code == 409 and r.json()["campo"] == "cantidad"
    lote_manzana.assert_not_called()


def test_merma_en_lote_que_no_tiene_el_producto(cliente, compras, lote_manzana):
    r = cliente.post("/inventario/mermas", json={**MERMA, "folio_lote": "L-00000001"}, headers=compras)
    assert r.status_code == 404 and r.json()["campo"] == "lote"


@pytest.mark.parametrize("cambio", [{"motivo": "robo"}, {"cantidad": "0"}, {"folio_lote": "1 OR 1=1"},
                                    {"observaciones": "<script>"}])
def test_merma_invalida_422(cliente, compras, cambio):
    assert cliente.post("/inventario/mermas", json={**MERMA, **cambio}, headers=compras).status_code == 422


def test_cajero_no_registra_mermas(cliente, compras, cabeceras):
    assert cliente.post("/inventario/mermas", json=MERMA, headers=cabeceras).status_code == 403


def test_lista_de_mermas_filtra_por_motivo(cliente, compras, monkeypatch):
    recibido = {}
    monkeypatch.setattr(repo, "listar_mermas", lambda c, m, d, h: recibido.update(motivo=m) or [])
    assert cliente.get("/inventario/mermas", params={"motivo": "plaga"}, headers=compras).status_code == 200
    assert recibido == {"motivo": "plaga"}


# ---------------------------------------------------------------- existencias, movimientos y precios (HU-24, HU-31)

def test_existencias_lotes_y_movimientos_solo_con_permiso_de_ver(cliente, compras, monkeypatch):
    monkeypatch.setattr(usuarios, "permisos_del_rol", lambda c, r: [])
    for ruta in ("/inventario/existencias", "/inventario/lotes", "/inventario/productos/1/movimientos",
                 "/inventario/productos/1/precios"):
        assert cliente.get(ruta, headers=compras).status_code == 403


def test_lotes_por_caducar_pasa_los_filtros(cliente, compras, monkeypatch):
    recibido = {}
    monkeypatch.setattr(repo, "lotes_por_caducar", lambda c, d, p, pr: recibido.update(dias=d, producto=p, proveedor=pr) or [])
    assert cliente.get("/inventario/lotes", params={"dias": 3, "id_producto": 1}, headers=compras).status_code == 200
    assert recibido == {"dias": 3, "producto": 1, "proveedor": None}
    assert cliente.get("/inventario/lotes", params={"dias": -1}, headers=compras).status_code == 422


AJUSTE = {"motivo": "Temporada alta", "cambios": [{"id_producto": 1, "precio_nuevo": "48.00"},
                                                  {"id_producto": 2, "precio_nuevo": "22.00"}]}


@pytest.fixture
def precios(monkeypatch):
    actuales = {1: {"id_producto": 1, "nombre": "Manzana", "precio_venta": Decimal("45.00"), "activo": 1},
                2: {"id_producto": 2, "nombre": "Plátano", "precio_venta": Decimal("22.00"), "activo": 1}}
    monkeypatch.setattr(repo, "precios_para_ajuste", lambda c, ids: {i: actuales[i] for i in ids if i in actuales})
    mocks = {"cambiar_precio": MagicMock(), "registrar_cambio_precio": MagicMock()}
    for n, m in mocks.items():
        monkeypatch.setattr(repo, n, m)
    return mocks


def test_ajuste_de_precios_solo_registra_los_que_cambian(cliente, compras, precios):
    r = cliente.post("/inventario/precios", json=AJUSTE, headers=compras)
    assert r.status_code == 200 and r.json() == {"productos": 1}
    precios["cambiar_precio"].assert_called_once()
    assert precios["registrar_cambio_precio"].call_args.args[1:] == (1, Decimal("45.00"), Decimal("48.00"), 3,
                                                                       "Temporada alta")
    assert auditoria.registrar.call_args.args[2] == "ajuste_precios"


@pytest.mark.parametrize(("cambios", "estado"), [
    ([{"id_producto": 9, "precio_nuevo": "10.00"}], 409),
    ([{"id_producto": 1, "precio_nuevo": "10.00"}, {"id_producto": 1, "precio_nuevo": "11.00"}], 409),
    ([{"id_producto": 1, "precio_nuevo": "0"}], 422),
    ([], 422),
])
def test_ajuste_rechazado_no_cambia_nada(cliente, compras, precios, cambios, estado):
    r = cliente.post("/inventario/precios", json={"motivo": "x", "cambios": cambios}, headers=compras)
    assert r.status_code == estado
    precios["cambiar_precio"].assert_not_called()


def test_cajero_no_ajusta_precios(cliente, compras, cabeceras, precios):
    assert cliente.post("/inventario/precios", json=AJUSTE, headers=cabeceras).status_code == 403
