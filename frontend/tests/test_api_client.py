"""Cliente HTTP: token en memoria, renovación por inactividad y traducción de errores."""
import httpx
import pytest

from app.api_client import ApiClient, ErrorApi, SesionExpirada
from app.config import Config
from app.datos import ErrorNegocio, NoConectado
from app.datos.api import DatosApi

CFG = Config(api_url="http://middleware.test", ca_path=None, terminal="POS-1", demo=False, timeout=2)
PERFIL = dict(id_usuario=2, usuario="cajero1", nombre_completo="Cajero de prueba", rol="Cajero",
              permisos=[dict(modulo="pos", puede_ver=True, puede_crear=True, puede_editar=False, puede_eliminar=False)])


def cliente(manejador) -> ApiClient:
    api = ApiClient(CFG)
    api._http = httpx.Client(base_url=CFG.api_url, transport=httpx.MockTransport(manejador))
    return api


def test_login_guarda_token_y_lo_renueva():
    vistos = []

    def manejador(req: httpx.Request):
        vistos.append(req.headers.get("Authorization"))
        if req.url.path == "/auth/login":
            return httpx.Response(200, json=dict(access_token="t1", expira_minutos=60, perfil=PERFIL))
        return httpx.Response(200, json=[], headers={"X-Token-Renovado": "t2"})

    api = cliente(manejador)
    api.login("cajero1", "x")
    api.get("/pos/metodos-pago")
    api.get("/pos/metodos-pago")
    assert vistos == [None, "Bearer t1", "Bearer t2"]


def test_401_borra_el_token_y_avisa_sesion_expirada():
    api = cliente(lambda req: httpx.Response(401, json={"detail": "Sesión inválida o expirada."}))
    api._token = "viejo"
    with pytest.raises(SesionExpirada):
        api.get("/pos/productos")
    assert not api.autenticado


def test_logout_borra_el_token_aunque_falle_la_red():
    def manejador(req):
        raise httpx.ConnectError("sin red")

    api = cliente(manejador)
    api._token = "t"
    api.logout()
    assert not api.autenticado


def test_sin_servidor_da_mensaje_claro():
    def manejador(req):
        raise httpx.ConnectError("sin red")

    with pytest.raises(ErrorApi, match="No hay conexión con el servidor"):
        cliente(manejador).get("/salud")


def test_login_incorrecto_usa_el_mensaje_del_apr():
    datos = DatosApi(cliente(lambda req: httpx.Response(401, json={"detail": "Usuario o contraseña incorrectos."})), "POS-1")
    with pytest.raises(ErrorNegocio, match="Ingrese un usuario/contraseña correcta."):
        datos.login("x", "y")


def test_venta_rechazada_por_la_base_llega_como_error_de_negocio():
    def manejador(req):
        assert req.url.path == "/pos/ventas"
        return httpx.Response(409, json={"detail": "Producto sin existencia suficiente."})

    datos = DatosApi(cliente(manejador), "POS-1")
    from decimal import Decimal
    with pytest.raises(ErrorNegocio, match="sin existencia"):
        datos.registrar_venta(1, 1, Decimal("100"), None, [dict(id_producto=1, cantidad=Decimal("1.250"))])


def test_caja_cerrada_devuelve_none():
    datos = DatosApi(cliente(lambda req: httpx.Response(404, json={"detail": "No hay una caja abierta."})), "POS-1")
    assert datos.caja_actual() is None


def test_rutas_que_faltan_en_el_middleware():
    datos = DatosApi(cliente(lambda req: httpx.Response(200, json={})), "POS-1")
    with pytest.raises(NoConectado) as exc:
        datos.lista_gastos()
    assert exc.value.ruta == "/finanzas/gastos"
