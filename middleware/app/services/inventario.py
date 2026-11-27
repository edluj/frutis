"""Reglas del catálogo: categorías (HU-22) y productos (HU-10)."""
from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError

from app.errores import ErrorNegocio
from app.repositories import auditoria
from app.repositories import inventario as repositorio
from app.schemas.inventario import Categoria, CategoriaEntrada, ProductoCatalogo, ProductoEntrada
from app.security.dependencias import UsuarioActual

ER_DUP_ENTRY = 1062
NOMBRE_REPETIDO = "Ya existe una categoría con ese nombre."
CODIGO_REPETIDO = "El código de barras ya está registrado."
MOTIVO_AJUSTE = "Ajuste individual"


def _auditar(conn: Connection, accion: str, detalle: str, ip: str | None, usuario: UsuarioActual) -> None:
    auditoria.registrar(conn, "inventario", accion, detalle, ip, usuario.id_usuario, usuario.usuario)


def _es_duplicado(exc: IntegrityError) -> bool:
    return exc.orig is not None and exc.orig.args and exc.orig.args[0] == ER_DUP_ENTRY


def _categoria_salida(conn: Connection, id_categoria: int) -> Categoria:
    fila = next(c for c in repositorio.listar_categorias(conn, None, False) if c["id_categoria"] == id_categoria)
    return Categoria(**fila)


def guardar_categoria(
    conn: Connection, datos: CategoriaEntrada, usuario: UsuarioActual, ip: str | None, id_categoria: int | None = None
) -> Categoria:
    if id_categoria is not None:
        if repositorio.categoria(conn, id_categoria, bloquear=True) is None:
            raise ErrorNegocio(404, "Categoría no encontrada.")
        if not datos.activo and (activos := repositorio.productos_activos_de(conn, id_categoria)):
            raise ErrorNegocio(409, f"No se puede dar de baja: tiene {activos} productos activos.", "estatus")
    if repositorio.nombre_categoria_en_uso(conn, datos.nombre, id_categoria):
        raise ErrorNegocio(409, NOMBRE_REPETIDO, "nombre")
    try:
        if id_categoria is None:
            id_categoria = repositorio.insertar_categoria(conn, datos.nombre, datos.descripcion, datos.activo)
            accion = "categoria_alta"
        else:
            repositorio.actualizar_categoria(conn, id_categoria, datos.nombre, datos.descripcion, datos.activo)
            accion = "categoria_edicion"
    except IntegrityError as exc:
        # Dos altas simultáneas con el mismo nombre: la llave única decide.
        conn.rollback()
        if _es_duplicado(exc):
            raise ErrorNegocio(409, NOMBRE_REPETIDO, "nombre") from exc
        raise
    _auditar(conn, accion, datos.nombre, ip, usuario)
    salida = _categoria_salida(conn, id_categoria)
    conn.commit()
    return salida


def guardar_producto(
    conn: Connection, datos: ProductoEntrada, usuario: UsuarioActual, ip: str | None, id_producto: int | None = None
) -> ProductoCatalogo:
    anterior = None
    if id_producto is not None:
        anterior = repositorio.producto(conn, id_producto, bloquear=True)
        if anterior is None:
            raise ErrorNegocio(404, "Producto no encontrado.")
    categoria = repositorio.categoria(conn, datos.id_categoria)
    # Un producto dado de baja puede quedarse en su categoría inactiva.
    if categoria is None or (datos.activo and not categoria["activo"]):
        raise ErrorNegocio(409, "Elija una categoría activa.", "categoria")
    if repositorio.codigo_en_uso(conn, datos.codigo_barras, id_producto):
        raise ErrorNegocio(409, CODIGO_REPETIDO, "codigo")

    valores = datos.model_dump()
    try:
        if anterior is None:
            id_producto = repositorio.insertar_producto(conn, valores)
            detalle, accion = f"{datos.codigo_barras} · {datos.nombre}", "producto_alta"
        else:
            repositorio.actualizar_producto(conn, id_producto, valores)
            detalle, accion = f"{datos.codigo_barras} · {datos.nombre}", "producto_edicion"
            # El historial guarda cada cambio de precio; los tickets pasados no cambian (HU-31).
            if anterior["precio_venta"] != datos.precio_venta:
                repositorio.registrar_cambio_precio(
                    conn, id_producto, anterior["precio_venta"], datos.precio_venta, usuario.id_usuario, MOTIVO_AJUSTE
                )
                detalle += f", precio {anterior['precio_venta']} -> {datos.precio_venta}"
    except IntegrityError as exc:
        conn.rollback()
        if _es_duplicado(exc):
            raise ErrorNegocio(409, CODIGO_REPETIDO, "codigo") from exc
        raise
    _auditar(conn, accion, detalle, ip, usuario)
    salida = ProductoCatalogo(**repositorio.producto_catalogo(conn, id_producto))
    conn.commit()
    return salida
