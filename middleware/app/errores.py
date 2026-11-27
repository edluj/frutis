"""Errores de negocio que llegan al cliente con su mensaje tal cual."""


class ErrorNegocio(Exception):
    def __init__(self, status_code: int, mensaje: str, campo: str | None = None):
        super().__init__(mensaje)
        self.status_code = status_code
        self.mensaje = mensaje
        # Campo del formulario al que se refiere el error, para marcarlo en pantalla.
        self.campo = campo
