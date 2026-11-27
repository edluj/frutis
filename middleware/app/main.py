"""Aplicación FastAPI de Frutis: la única puerta a la base de datos (ADR-04)."""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api import admin, auth, compras, facturacion, finanzas, inventario, pos
from app.errores import ErrorNegocio

log = logging.getLogger(__name__)

app = FastAPI(title="Frutis ERP + POS", version="1.0.0")
app.include_router(auth.router)
app.include_router(pos.router)
app.include_router(inventario.router)
app.include_router(compras.router)
app.include_router(finanzas.router)
app.include_router(admin.router)
app.include_router(facturacion.router)


@app.exception_handler(ErrorNegocio)
def error_negocio(_: Request, exc: ErrorNegocio) -> JSONResponse:
    contenido = {"detail": exc.mensaje}
    if exc.campo:
        contenido["campo"] = exc.campo
    return JSONResponse(status_code=exc.status_code, content=contenido)


@app.exception_handler(RequestValidationError)
def error_validacion(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Sin el campo `input` de FastAPI: devolvería la contraseña recibida.
    errores = [
        {"campo": ".".join(str(parte) for parte in e["loc"]), "mensaje": e["msg"]}
        for e in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": "Datos inválidos.", "errores": errores})


@app.exception_handler(SQLAlchemyError)
def error_datos(_: Request, exc: SQLAlchemyError) -> JSONResponse:
    log.error("Error de base de datos: %s", type(exc).__name__)
    return JSONResponse(status_code=503, content={"detail": "Servicio de datos no disponible."})


@app.get("/salud", tags=["sistema"])
def salud() -> dict[str, str]:
    return {"estado": "ok"}
