"""Fuentes de datos de las pantallas.

Las vistas nunca hablan con la red: piden datos a un objeto `Datos`.
- `DatosApi` usa el middleware (hoy expone /auth y /pos).
- `DatosDemo` guarda todo en memoria con los datos del lienzo de diseño; sirve para
  revisar las pantallas con el cliente y para desarrollar sin servidor.
"""


class NoConectado(Exception):
    """El middleware todavía no expone la ruta que necesita la pantalla."""

    def __init__(self, ruta: str):
        super().__init__(ruta)
        self.ruta = ruta
        self.mensaje = (
            f"Esta pantalla todavía no está conectada al servidor: falta la ruta {ruta} en el middleware. "
            "Mientras tanto se puede revisar en modo demostración (python -m app --demo)."
        )


class ErrorNegocio(Exception):
    """Regla de negocio rechazada (se muestra tal cual al usuario)."""

    def __init__(self, mensaje: str, campo: str | None = None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.campo = campo
