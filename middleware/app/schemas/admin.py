from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.compras import PATRON_CORREO
from app.security.sanitizar import PATRON_TEXTO_SEGURO


class Rol(BaseModel):
    id_rol: int
    nombre: str
    usuarios: int = 0
    # El rol del sistema (Administrador) no se edita.
    es_sistema: bool = False


class Usuario(BaseModel):
    # Nunca incluye el hash de la contraseña.
    id_usuario: int
    nombre_completo: str
    usuario: str
    correo: str
    id_rol: int
    rol: str
    ultimo_acceso: datetime | None
    activo: bool


class UsuarioEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nombre_completo: str = Field(min_length=1, max_length=150, pattern=PATRON_TEXTO_SEGURO)
    usuario: str = Field(min_length=3, max_length=50, pattern=r"^[\w.\-]+$")
    correo: str = Field(max_length=120, pattern=PATRON_CORREO)
    id_rol: int = Field(gt=0)
    activo: bool = True
    # Obligatoria al dar de alta; al editar, vacía o ausente = no cambia.
    password: str | None = Field(default=None, max_length=128)


# ---------------------------------------------------------------- roles y permisos (HU-34)

Modulo = Literal["pos", "compras", "facturacion", "finanzas", "inventario", "reportes", "admin"]
MODULOS: tuple[str, ...] = ("pos", "compras", "facturacion", "finanzas", "inventario", "reportes", "admin")


class PermisoModulo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modulo: Modulo
    puede_ver: bool = False
    puede_crear: bool = False
    puede_editar: bool = False
    puede_eliminar: bool = False


class PermisosEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Los módulos que no vengan quedan sin ningún permiso.
    permisos: list[PermisoModulo] = Field(max_length=len(MODULOS))


class RolEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nombre: str = Field(min_length=1, max_length=40, pattern=PATRON_TEXTO_SEGURO)


# ---------------------------------------------------------------- auditoría (HU-35)

class RegistroAuditoria(BaseModel):
    fecha: datetime
    usuario: str | None
    modulo: str
    accion: str
    detalle: str | None
    ip: str | None


# ---------------------------------------------------------------- cajas y métodos de pago (HU-41)

class Terminal(BaseModel):
    terminal: str
    abierta: bool
    cajero: str | None
    ultima_apertura: datetime


class MetodoPagoConfig(BaseModel):
    id_metodo: int
    nombre: str
    clave_sat: str
    es_efectivo: bool
    es_credito: bool
    activo: bool


class ActivacionEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activo: bool
