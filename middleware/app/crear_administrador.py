"""Crea un usuario Administrador: el primero de una instalación de producción.

    cd middleware && .venv/bin/python -m app.crear_administrador --usuario admin \\
        --nombre "Nombre Apellido" --correo admin@fruteria.mx

La contraseña se pide dos veces sin mostrarla (o se toma de FRUTIS_ADMIN_PASSWORD, para
automatizar). Usa la conexión de deploy/.env (frutis_app) y el mismo hash del login.
"""
import argparse
import getpass
import os
import sys

from pydantic import ValidationError
from sqlalchemy import Connection, text

from app.db import get_engine
from app.repositories import admin as repositorio
from app.repositories import auditoria
from app.schemas.admin import UsuarioEntrada
from app.security.passwords import hash_password

MIN_PASSWORD = 8


class NoSePuede(Exception):
    pass


def crear_administrador(conn: Connection, nombre: str, usuario: str, correo: str, password: str) -> int:
    if len(password) < MIN_PASSWORD:
        raise NoSePuede(f"La contraseña debe tener al menos {MIN_PASSWORD} caracteres.")
    id_rol = conn.execute(text("SELECT id_rol FROM roles WHERE es_sistema = TRUE AND activo = TRUE")).scalar()
    if id_rol is None:
        raise NoSePuede("No existe el rol Administrador: instale los catálogos (database/instalar.sh --migraciones).")
    try:
        datos = UsuarioEntrada(nombre_completo=nombre, usuario=usuario, correo=correo, id_rol=id_rol)
    except ValidationError as exc:
        campos = ", ".join(str(e["loc"][0]) for e in exc.errors())
        raise NoSePuede(f"Datos inválidos: {campos}.") from exc
    for columna, valor in (("usuario", datos.usuario), ("correo", datos.correo)):
        if repositorio.en_uso(conn, columna, valor, None):
            raise NoSePuede(f"Ya existe un usuario con ese {columna}.")
    id_usuario = repositorio.insertar_usuario(conn, datos.model_dump(exclude={"password"}), hash_password(password))
    auditoria.registrar(conn, "admin", "usuario_alta", f"{datos.usuario} · rol Administrador (crear_administrador)", None)
    conn.commit()
    return id_usuario


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Crea un usuario Administrador de Frutis")
    parser.add_argument("--usuario", required=True)
    parser.add_argument("--nombre", required=True, help="nombre completo")
    parser.add_argument("--correo", required=True)
    args = parser.parse_args(argv)
    password = os.environ.get("FRUTIS_ADMIN_PASSWORD")
    if not password:
        password = getpass.getpass("Contraseña: ")
        if password != getpass.getpass("Repita la contraseña: "):
            print("Las contraseñas no coinciden.", file=sys.stderr)
            return 1
    try:
        with get_engine().connect() as conn:
            crear_administrador(conn, args.nombre, args.usuario, args.correo, password)
    except NoSePuede as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"Administrador {args.usuario} creado. Ya puede iniciar sesión en Frutis.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
