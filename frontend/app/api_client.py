"""Cliente HTTP único hacia el middleware (arquitectura, sección 5).

- Agrega el token Bearer a cada petición y lo reemplaza con `X-Token-Renovado`
  para que la sesión expire solo por inactividad.
- Valida el certificado del servidor con la autoridad certificadora local.
- Traduce los errores a `ErrorApi` con el mensaje que se le muestra al usuario.
"""
from typing import Any

import httpx

from app.config import Config

CABECERA_RENOVADO = "X-Token-Renovado"
SIN_SERVIDOR = "No hay conexión con el servidor. Revise la red e intente de nuevo."


class ErrorApi(Exception):
    def __init__(self, status: int, mensaje: str, errores: list | None = None, campo: str | None = None):
        super().__init__(mensaje)
        self.status = status
        self.mensaje = mensaje
        self.errores = errores or []
        # Campo del formulario que el middleware señala en el error, si lo hay.
        self.campo = campo


class SesionExpirada(ErrorApi):
    pass


class ApiClient:
    def __init__(self, config: Config):
        verify: Any = True
        if config.api_url.startswith("https") and config.ca_path:
            verify = config.ca_path
        self._http = httpx.Client(base_url=config.api_url, timeout=config.timeout, verify=verify)
        self._token: str | None = None

    # ---------------------------------------------------------- sesión
    @property
    def autenticado(self) -> bool:
        return self._token is not None

    def login(self, usuario: str, password: str) -> dict:
        datos = self._pedir("POST", "/auth/login", json={"usuario": usuario, "password": password}, auth=False)
        self._token = datos["access_token"]
        return datos

    def logout(self) -> None:
        try:
            if self._token:
                self._pedir("POST", "/auth/logout")
        except ErrorApi:
            pass
        finally:
            # El token solo vive en memoria y se borra al cerrar sesión.
            self._token = None

    # ---------------------------------------------------------- verbos
    def get(self, ruta: str, **params) -> Any:
        return self._pedir("GET", ruta, params={k: v for k, v in params.items() if v is not None})

    def post(self, ruta: str, cuerpo: dict) -> Any:
        return self._pedir("POST", ruta, json=cuerpo)

    def put(self, ruta: str, cuerpo: dict) -> Any:
        return self._pedir("PUT", ruta, json=cuerpo)

    def _pedir(self, metodo: str, ruta: str, auth: bool = True, **kwargs) -> Any:
        headers = {}
        if auth and self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            resp = self._http.request(metodo, ruta, headers=headers, **kwargs)
        except httpx.TransportError as exc:
            raise ErrorApi(0, SIN_SERVIDOR) from exc
        if renovado := resp.headers.get(CABECERA_RENOVADO):
            self._token = renovado
        if resp.status_code == 204:
            return None
        try:
            cuerpo = resp.json()
        except ValueError:
            cuerpo = {}
        if resp.status_code >= 400:
            mensaje = cuerpo.get("detail") if isinstance(cuerpo, dict) else None
            if not isinstance(mensaje, str):
                mensaje = "No se pudo completar la operación."
            if resp.status_code == 401 and auth:
                self._token = None
                raise SesionExpirada(401, mensaje)
            if not isinstance(cuerpo, dict):
                cuerpo = {}
            raise ErrorApi(resp.status_code, mensaje, cuerpo.get("errores"), cuerpo.get("campo"))
        return cuerpo

    def cerrar(self) -> None:
        self._http.close()
