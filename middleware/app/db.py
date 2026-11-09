"""Conexión a MySQL con el usuario de mínimos permisos frutis_app."""
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import URL, Connection, Engine, create_engine

from app.config import get_settings


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    url = URL.create(
        "mysql+pymysql",
        username=settings.db_user,
        password=settings.db_password.get_secret_value(),
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
        query={"charset": "utf8mb4"},
    )
    return create_engine(url, pool_pre_ping=True, pool_recycle=3600)


def get_conn() -> Iterator[Connection]:
    with get_engine().connect() as conn:
        yield conn
