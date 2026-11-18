"""Íconos de línea del diseño, dibujados como SVG en memoria (sin archivos externos)."""
from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_TRAZOS = {
    "inicio": '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V20h5v-6h4v6h5V9.5"/>',
    "pos": '<path d="M3 4h2.5l2.2 10.5h10.6L20.5 7H6.6"/><circle cx="9" cy="19" r="1.3"/><circle cx="17" cy="19" r="1.3"/>',
    "compras": '<path d="M2 6h11v10H2z"/><path d="M13 9h4.5l3.5 3.5V16h-8"/><circle cx="6" cy="17.5" r="1.8"/><circle cx="17" cy="17.5" r="1.8"/>',
    "facturacion": '<path d="M14 3H6.5A1.5 1.5 0 0 0 5 4.5v15A1.5 1.5 0 0 0 6.5 21h11a1.5 1.5 0 0 0 1.5-1.5V8z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h6"/>',
    "finanzas": '<path d="M3 20h18"/><path d="M6 20V11M10 20V5M14 20v-7M18 20V9"/>',
    "inventario": '<path d="M12 3 20 7.5v9L12 21l-8-4.5v-9z"/><path d="M4 7.5 12 12l8-4.5M12 12v9"/>',
    "reportes": '<rect x="5" y="4" width="14" height="17" rx="1.5"/><path d="M9 4V3h6v1"/><path d="M9 10h6M9 14h6M9 18h3"/>',
    "admin": '<path d="M12 3 4.5 6v5.5c0 4.6 3.2 8.4 7.5 9.5 4.3-1.1 7.5-4.9 7.5-9.5V6z"/><path d="m8.8 12 2.2 2.2 4.2-4.4"/>',
    "salir": '<path d="M10 4H5v16h5"/><path d="M14 8l-4 4 4 4M10 12h10"/>',
    "lapiz": '<path d="M15.5 4.5 19.5 8.5 8.5 19.5 4 20l.5-4.5z"/>',
    "x": '<path d="M6 6l12 12M18 6 6 18"/>',
    "ojo": '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "ojo_off": '<path d="M3 3l18 18"/><path d="M10.6 5.1A10.8 10.8 0 0 1 12 5c6.4 0 10 7 10 7a17 17 0 0 1-3.2 4"/><path d="M6.6 6.6A17 17 0 0 0 2 12s3.6 7 10 7a10 10 0 0 0 5.4-1.6"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/>',
    "documento": '<path d="M14 3H6.5A1.5 1.5 0 0 0 5 4.5v15A1.5 1.5 0 0 0 6.5 21h11a1.5 1.5 0 0 0 1.5-1.5V8z"/><path d="M14 3v5h5M9 13h6M9 17h4"/>',
    "movimientos": '<path d="M8 4v16M8 20l-3-3M8 20l3-3"/><path d="M16 20V4M16 4l-3 3M16 4l3 3"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "bascula": '<path d="M5 20h14l-2-9H7z"/><path d="M12 11V6M8 6h8"/>',
}


@lru_cache(maxsize=256)
def icono(nombre: str, color: str = "#2B2522", px: int = 20, grosor: float = 1.8) -> QIcon:
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" '
        f'stroke-width="{grosor}" stroke-linecap="round" stroke-linejoin="round">{_TRAZOS[nombre]}</svg>'
    )
    render = QSvgRenderer(QByteArray(svg.encode()))
    pix = QPixmap(QSize(px * 2, px * 2))
    pix.setDevicePixelRatio(2)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    render.render(p, QRectF(0, 0, px, px))
    p.end()
    return QIcon(pix)


def icono_doble(nombre: str, normal: str, activo: str, px: int = 20) -> QIcon:
    """Ícono que cambia de color cuando el botón está marcado (menú lateral)."""
    ic = QIcon()
    ic.addPixmap(icono(nombre, normal, px).pixmap(px, px), QIcon.Mode.Normal, QIcon.State.Off)
    ic.addPixmap(icono(nombre, activo, px).pixmap(px, px), QIcon.Mode.Normal, QIcon.State.On)
    return ic
