"""Reglas del catálogo: categorías (HU-22), productos (HU-10), mermas (HU-17) y precios (HU-31)."""
from decimal import Decimal

from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError

from app.errores import ErrorNegocio
from app.repositories import auditoria
from app.repositories import inventario as repositorio
from app.schemas.inventario import (
    AjusteAplicado, AjustePreciosEntrada, Categoria, CategoriaEntrada, MermaEntrada, MermaRegistrada,
    ProductoCatalogo, ProductoEntrada,
)
from app.security.dependencias import UsuarioActual

ER_DUP_ENTRY = 1062
NOMBRE_REPETIDO = "Ya existe una categoría con ese nombre."
CODIGO_REPETIDO = "El código de barras ya está registrado."
MOTIVO_AJUSTE = "Ajuste individual"
CENTAVO = Decimal("0.01")


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


def registrar_merma(conn: Connection, datos: MermaEntrada, usuario: UsuarioActual, ip: str | None) -> MermaRegistrada:
    """Descuenta la merma de un lote y guarda su costo (HU-17)."""
    fila = repositorio.existencia_de_lote(conn, datos.id_producto, datos.folio_lote)
    if fila is None:
        raise ErrorNegocio(404, "El producto no está en ese lote.", "lote")
    if fila["unidad_venta"] == "pieza" and datos.cantidad != datos.cantidad.to_integral_value():
        raise ErrorNegocio(409, f"{fila['nombre']} se maneja por pieza: use cantidades enteras.", "cantidad")
    if datos.cantidad > fila["cantidad_disponible"]:
        raise ErrorNegocio(409, "La cantidad supera la existencia del lote.", "cantidad")
    costo = (datos.cantidad * fila["costo_unitario"]).quantize(CENTAVO)
    repositorio.registrar_merma(
        conn, fila["id_inventario"], datos.cantidad, datos.motivo, costo, datos.observaciones, usuario.id_usuario
    )
    _auditar(conn, "merma_alta", f"{fila['nombre']} {datos.cantidad} · {datos.folio_lote} · ${costo} · {datos.motivo}",
             ip, usuario)
    conn.commit()
    return MermaRegistrada(costo=costo)


def ajustar_precios(conn: Connection, datos: AjustePreciosEntrada, usuario: UsuarioActual, ip: str | None) -> AjusteAplicado:
    """Cambia varios precios en una transacción y guarda cada cambio en el historial (HU-31)."""
    ids = [c.id_producto for c in datos.cambios]
    if len(set(ids)) != len(ids):
        raise ErrorNegocio(409, "Un producto aparece dos veces en el ajuste.")
    actuales = repositorio.precios_para_ajuste(conn, ids)
    for c in datos.cambios:
        p = actuales.get(c.id_producto)
        if p is None or not p["activo"]:
            raise ErrorNegocio(409, "Producto no encontrado o inactivo.")
    cambiados = 0
    for c in datos.cambios:
        anterior = actuales[c.id_producto]["precio_venta"]
        if anterior == c.precio_nuevo:
            continue
        repositorio.cambiar_precio(conn, c.id_producto, c.precio_nuevo)
        repositorio.registrar_cambio_precio(conn, c.id_producto, anterior, c.precio_nuevo, usuario.id_usuario, datos.motivo)
        cambiados += 1
    _auditar(conn, "ajuste_precios", f"{cambiados} productos · {datos.motivo}", ip, usuario)
    conn.commit()
    return AjusteAplicado(productos=cambiados)
