"""Errores de negocio que llegan al cliente con su mensaje tal cual."""


class ErrorNegocio(Exception):
    def __init__(self, status_code: int, mensaje: str):
        super().__init__(mensaje)
        self.status_code = status_code
        self.mensaje = mensaje
