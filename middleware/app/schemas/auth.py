from pydantic import BaseModel, ConfigDict, Field


class LoginEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    usuario: str = Field(min_length=1, max_length=50, pattern=r"^[\w.\-]+$")
    # El tope evita gastar CPU en PBKDF2 con textos enormes.
    password: str = Field(min_length=1, max_length=128)


class Permiso(BaseModel):
    modulo: str
    puede_ver: bool
    puede_crear: bool
    puede_editar: bool
    puede_eliminar: bool


class Perfil(BaseModel):
    id_usuario: int
    usuario: str
    nombre_completo: str
    rol: str
    permisos: list[Permiso]


class LoginSalida(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expira_minutos: int
    perfil: Perfil
