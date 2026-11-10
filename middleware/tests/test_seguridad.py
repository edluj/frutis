from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import jwt

from app.config import get_settings
from app.repositories import auditoria, usuarios
from app.security.passwords import hash_password, verificar_password
from app.security.tokens import ALGORITMO, leer_token
from tests.conftest import CAJERO, PASSWORD, PERMISOS_CAJERO


def test_hash_verifica_y_usa_sal():
    h = hash_password("abc")
    assert verificar_password("abc", h)
    assert not verificar_password("abd", h)
    assert h != hash_password("abc")


def test_verifica_hash_de_seed():
    seed = Path(__file__).resolve().parents[2] / "database" / "seed.sql"
    with seed.open(encoding="utf-8") as f:
        linea = next(x for x in f if "'cajero1'" in x)
    guardado = next(p for p in linea.split("'") if p.startswith("pbkdf2_sha256$"))
    assert verificar_password(PASSWORD, guardado)


def test_hash_corrupto_no_truena():
    assert not verificar_password("abc", "basura")
    assert not verificar_password("abc", "pbkdf2_sha256$x$zz$yy")


def test_token_expirado_o_alterado():
    secreto = get_settings().jwt_secret.get_secret_value()
    vencido = jwt.encode(
        {"sub": "2", "ver": 0, "exp": datetime.now(UTC) - timedelta(minutes=1)}, secreto, algorithm=ALGORITMO
    )
    assert leer_token(vencido) is None
    otro = jwt.encode(
        {"sub": "2", "ver": 0, "exp": datetime.now(UTC) + timedelta(minutes=1)}, "x" * 40, algorithm=ALGORITMO
    )
    assert leer_token(otro) is None
    assert leer_token("no-es-token") is None
    sin_version = jwt.encode(
        {"sub": "2", "exp": datetime.now(UTC) + timedelta(minutes=1)}, secreto, algorithm=ALGORITMO
    )
    assert leer_token(sin_version) is None


def _login(cliente, password=PASSWORD):
    return cliente.post("/auth/login", json={"usuario": "cajero1", "password": password})


def test_login_correcto(cliente, monkeypatch):
    monkeypatch.setattr(usuarios, "buscar_para_login", lambda c, u: CAJERO)
    monkeypatch.setattr(usuarios, "registrar_acceso", MagicMock())
    r = _login(cliente)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["perfil"]["rol"] == "Cajero"
    assert leer_token(cuerpo["access_token"]) == (2, 0)
    assert "password_hash" not in r.text


def test_login_incorrecto_cuenta_el_intento(cliente, monkeypatch):
    fallido = MagicMock()
    monkeypatch.setattr(usuarios, "buscar_para_login", lambda c, u: CAJERO)
    monkeypatch.setattr(usuarios, "registrar_intento_fallido", fallido)
    r = _login(cliente, "mala")
    assert r.status_code == 401
    fallido.assert_called_once()


def test_login_usuario_inexistente_mismo_mensaje(cliente, monkeypatch):
    monkeypatch.setattr(usuarios, "buscar_para_login", lambda c, u: None)
    r = _login(cliente, "mala")
    assert r.status_code == 401
    assert r.json()["detail"] == "Ingrese un usuario/contraseña correcta."


def test_cuenta_bloqueada_rechaza_aun_con_password_correcta(cliente, monkeypatch):
    monkeypatch.setattr(usuarios, "buscar_para_login", lambda c, u: {**CAJERO, "bloqueado": 1})
    assert _login(cliente).status_code == 429


def test_error_de_validacion_no_devuelve_la_password(cliente):
    r = cliente.post("/auth/login", json={"usuario": "a b", "password": "SecretoVisible"})
    assert r.status_code == 422
    assert "SecretoVisible" not in r.text


def test_sin_token_401(cliente):
    assert cliente.get("/auth/me").status_code == 401
    assert cliente.get("/pos/productos").status_code == 401
    assert cliente.post("/pos/ventas", json={}).status_code == 401


def test_usuario_desactivado_pierde_la_sesion(cliente, monkeypatch, cabeceras):
    monkeypatch.setattr(usuarios, "buscar_activo", lambda c, i: None)
    assert cliente.get("/auth/me", headers=cabeceras).status_code == 401


def test_peticion_valida_renueva_token(cliente, cabeceras):
    r = cliente.get("/auth/me", headers=cabeceras)
    assert r.status_code == 200
    assert leer_token(r.headers["X-Token-Renovado"]) == (2, 0)


def test_logout_audita(cliente, cabeceras):
    assert cliente.post("/auth/logout", headers=cabeceras).status_code == 204
    assert auditoria.registrar.call_args.args[2] == "logout"


def test_logout_invalida_el_token_y_sus_renovaciones(cliente, cabeceras):
    renovado = cliente.get("/auth/me", headers=cabeceras).headers["X-Token-Renovado"]
    assert cliente.post("/auth/logout", headers=cabeceras).status_code == 204
    assert cliente.get("/auth/me", headers=cabeceras).status_code == 401
    assert cliente.get("/auth/me", headers={"Authorization": f"Bearer {renovado}"}).status_code == 401


def test_inactivo_con_password_correcta_recibe_su_mensaje(cliente, monkeypatch):
    monkeypatch.setattr(usuarios, "buscar_para_login", lambda c, u: {**CAJERO, "activo": 0})
    r = _login(cliente)
    assert r.status_code == 403
    assert r.json()["detail"] == "Usuario inactivo, contacte al administrador."


def test_inactivo_con_password_mala_no_se_distingue(cliente, monkeypatch):
    monkeypatch.setattr(usuarios, "buscar_para_login", lambda c, u: {**CAJERO, "activo": 0})
    monkeypatch.setattr(usuarios, "registrar_intento_fallido", MagicMock())
    r = _login(cliente, "mala")
    assert r.status_code == 401
    assert r.json()["detail"] == "Ingrese un usuario/contraseña correcta."


def test_rol_sin_permiso_403(cliente, monkeypatch, cabeceras):
    solo_ver = [{**PERMISOS_CAJERO[0], "puede_crear": 0}]
    monkeypatch.setattr(usuarios, "permisos_del_rol", lambda c, r: solo_ver)
    venta = {"id_caja": 1, "id_metodo": 1, "carrito": [{"id_producto": 1, "cantidad": "1"}]}
    assert cliente.post("/pos/ventas", json=venta, headers=cabeceras).status_code == 403


def test_rol_sin_el_modulo_403(cliente, monkeypatch, cabeceras):
    monkeypatch.setattr(usuarios, "permisos_del_rol", lambda c, r: [])
    assert cliente.get("/pos/productos", headers=cabeceras).status_code == 403
