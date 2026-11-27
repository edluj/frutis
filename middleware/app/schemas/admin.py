from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.compras import PATRON_CORREO
from app.security.sanitizar import PATRON_TEXTO_SEGURO


class Rol(BaseModel):
    id_rol: int
    nombre: str


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
