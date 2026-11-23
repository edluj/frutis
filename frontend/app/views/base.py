"""Piezas comunes a todas las pantallas: contexto de la sesión y manejo de errores."""
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.api_client import SesionExpirada
from app.config import Config
from app.datos import ErrorNegocio, NoConectado
from app.sesion import Sesion
from app.theme import C
from app.widgets import Alerta, Pagina, avisar


@dataclass
class Contexto:
    datos: Any
    sesion: Sesion
    config: Config
    navegar: Callable[..., None]
    sesion_expirada: Callable[[], None]
    actualizar_caja: Callable[[], None] = lambda: None
    olvidar: Callable[[str], None] = lambda ruta: None
    pagina: Callable[[str], Any] = lambda ruta: None


class PaginaBase(Pagina):
    """Página con contexto y una franja de aviso para errores y rutas pendientes."""

    def __init__(self, ctx: Contexto, migas: str, titulo: str, estado: str | None = None, acciones=(),
                 punto: str = C.VERDE):
        super().__init__(migas, titulo, estado, acciones, punto)
        self.ctx = ctx
        self.aviso = Alerta("", "naranja")
        self.aviso.setVisible(False)
        self.cuerpo.addWidget(self.aviso)
        self.al_migas = lambda enlace: ctx.navegar(enlace)
        if ctx.datos.es_demo and estado is None:
            self.poner_estado("Modo demostración", C.NARANJA)

    def intentar(self, fn: Callable, *args, mostrar_dialogo: bool = True, **kwargs):
        """Ejecuta una llamada a datos. Devuelve el resultado o None si falló."""
        try:
            return fn(*args, **kwargs)
        except NoConectado as exc:
            self.aviso.mostrar(exc.mensaje, "naranja")
        except SesionExpirada:
            self.ctx.sesion_expirada()
        except ErrorNegocio as exc:
            if mostrar_dialogo:
                avisar(self, "No se pudo completar", exc.mensaje, error=True)
            else:
                raise
        return None

    def al_mostrar(self, **params) -> None:
        """Se llama cada vez que la pantalla se vuelve visible."""
