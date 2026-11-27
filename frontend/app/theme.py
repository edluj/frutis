"""Identidad visual de Frutis: colores, tipografías y hoja de estilos Qt.

Valores tomados del lienzo de diseño UX/UI (docs/diseno) y de la sección 5 de la
arquitectura: guinda #7A1E28, verde hoja #4E7A44, café coco #9C5A33, Fredoka para
títulos y Nunito Sans para texto.
"""
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

RECURSOS = Path(__file__).resolve().parent / "resources"


class C:
    """Paleta del diseño."""

    GUINDA = "#7A1E28"
    GUINDA_BOTON = "#7D1F2B"
    GUINDA_OSCURO = "#5A1520"
    GUINDA_HOVER = "#691923"
    GUINDA_SUAVE = "#F5E4E4"
    VERDE = "#4E7A44"
    VERDE_SUAVE = "#E6EFE1"
    VERDE_TEXTO = "#355A2D"
    CAFE = "#9C5A33"
    CAFE_CLARO = "#CFA88E"
    NARANJA = "#B85C1A"
    NARANJA_SUAVE = "#FDF1E1"
    NARANJA_TEXTO = "#8A4512"
    ROJO = "#B42318"
    ROJO_SUAVE = "#FDE9E7"
    FONDO = "#FAF6F1"
    CREMA = "#F3E9DF"
    CREMA_TOTAL = "#FAF6F1"
    BLANCO = "#FFFFFF"
    BORDE = "#EDE3D8"
    BORDE_CAMPO = "#E6DDD3"
    TEXTO = "#2B2522"
    TEXTO_SUAVE = "#6B625C"
    GRIS_BADGE = "#EFE8E1"
    GRIS_BADGE_TEXTO = "#5E554F"
    PISTA = "#EFE7DF"


TITULOS = "Fredoka"
TEXTO = "Nunito Sans"


def cargar_fuentes() -> None:
    """Registra las fuentes del logotipo; si faltan, Qt usa la del sistema."""
    for archivo in (RECURSOS / "fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(archivo))


def fuente_titulo(px: int, peso: QFont.Weight = QFont.Weight.DemiBold) -> QFont:
    f = QFont(TITULOS)
    f.setPixelSize(px)
    f.setWeight(peso)
    return f


def fuente_texto(px: int = 14, peso: QFont.Weight = QFont.Weight.Normal) -> QFont:
    f = QFont(TEXTO)
    f.setPixelSize(px)
    f.setWeight(peso)
    return f


QSS = f"""
* {{
    font-family: "{TEXTO}";
    color: {C.TEXTO};
}}
QMainWindow, QWidget#Contenido, QScrollArea#Cuerpo, QWidget#CuerpoInterior {{
    background: {C.FONDO};
}}
QToolTip {{
    background: {C.TEXTO}; color: white; border: none; padding: 4px 8px;
}}

/* ---------- Barra lateral ---------- */
QFrame#Sidebar {{ background: {C.GUINDA_OSCURO}; }}
QFrame#Sidebar QLabel {{ color: white; background: transparent; }}
QLabel#MarcaNombre {{ font-family: "{TITULOS}"; font-size: 26px; font-weight: 600; }}
QLabel#MarcaSub {{ color: #F2C9CC; font-size: 12px; font-weight: 700; letter-spacing: 2px; }}
QPushButton#Nav {{
    background: transparent; color: white; border: none; border-radius: 10px;
    text-align: left; padding: 11px 12px; font-size: 14px; font-weight: 700;
}}
QPushButton#Nav:hover {{ background: rgba(255,255,255,0.08); }}
QPushButton#Nav:checked {{ background: white; color: {C.GUINDA}; }}
QPushButton#SubNav {{
    background: transparent; color: #F2D6D8; border: none; border-radius: 8px;
    text-align: left; padding: 7px 14px 7px 52px; font-size: 13px; font-weight: 600;
}}
QPushButton#SubNav:hover {{ background: rgba(255,255,255,0.08); color: white; }}
QPushButton#SubNav:checked {{ color: white; background: rgba(255,255,255,0.14); }}
QFrame#SidebarLinea {{ background: rgba(255,255,255,0.18); max-height: 1px; min-height: 1px; }}
QLabel#UsuarioNombre {{ font-size: 15px; font-weight: 800; }}
QLabel#UsuarioRol {{ color: #F2C9CC; font-size: 12px; }}
QPushButton#CerrarSesion {{
    background: transparent; color: white; border: none; text-align: left;
    font-size: 15px; font-weight: 700; padding: 6px 8px;
}}
QPushButton#CerrarSesion:hover {{ color: #F2C9CC; }}

/* ---------- Encabezado de página ---------- */
QFrame#Encabezado {{ background: white; border-bottom: 1px solid {C.BORDE}; }}
QLabel#Migas {{ color: {C.TEXTO_SUAVE}; font-size: 13px; }}
QLabel#Migas a {{ color: {C.GUINDA}; }}
QLabel#TituloPagina {{ font-family: "{TITULOS}"; font-size: 22px; font-weight: 600; }}
QLabel#Estado {{ color: {C.TEXTO_SUAVE}; font-size: 13px; }}

/* ---------- Tarjetas ---------- */
QFrame#Card {{ background: white; border: 1px solid {C.BORDE}; border-radius: 12px; }}
QFrame#Card QLabel {{ background: transparent; }}
QLabel#CardTitulo {{ font-family: "{TITULOS}"; font-size: 17px; font-weight: 600; color: {C.GUINDA}; }}
QLabel#KpiTitulo {{ color: {C.TEXTO_SUAVE}; font-size: 12px; font-weight: 700; }}
QLabel#KpiValor {{ font-family: "{TITULOS}"; font-size: 28px; font-weight: 600; }}
QLabel#KpiDetalle {{ color: {C.TEXTO_SUAVE}; font-size: 12px; }}
QLabel#Etiqueta {{ color: {C.TEXTO_SUAVE}; font-size: 12px; font-weight: 700; }}
QLabel#Muted {{ color: {C.TEXTO_SUAVE}; font-size: 13px; }}
QLabel#Valor {{ font-size: 14px; }}
QLabel#Error {{ color: {C.ROJO}; font-size: 12px; font-weight: 700; }}
QLabel#Ayuda {{ color: {C.TEXTO_SUAVE}; font-size: 12px; }}
QLabel#Link {{ color: {C.GUINDA}; text-decoration: underline; }}

/* ---------- Campos ---------- */
QLineEdit, QComboBox, QDateEdit, QTextEdit, QPlainTextEdit, QDoubleSpinBox, QSpinBox {{
    background: white; border: 1px solid {C.BORDE_CAMPO}; border-radius: 8px;
    padding: 9px 12px; font-size: 14px; min-height: 22px;
    selection-background-color: {C.GUINDA_SUAVE}; selection-color: {C.TEXTO};
}}
QSpinBox, QLineEdit[compacto="true"], QComboBox[compacto="true"] {{
    padding: 4px 10px; min-height: 24px;
}}
QSpinBox::up-button, QSpinBox::down-button {{ width: 0; border: none; }}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {C.GUINDA};
}}
QLineEdit[error="true"], QComboBox[error="true"], QPlainTextEdit[error="true"] {{
    background: {C.ROJO_SUAVE}; border: 1px solid {C.ROJO};
}}
QLineEdit:disabled, QComboBox:disabled {{ background: {C.FONDO}; color: {C.TEXTO_SUAVE}; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox::down-arrow {{ image: url({(RECURSOS / 'img' / 'chevron.svg').as_posix()}); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{
    background: white; border: 1px solid {C.BORDE}; selection-background-color: {C.GUINDA_SUAVE};
    selection-color: {C.TEXTO}; outline: none; padding: 4px;
}}
QDateEdit::drop-down {{ border: none; width: 28px; }}
QDateEdit::down-arrow {{ image: url({(RECURSOS / 'img' / 'chevron.svg').as_posix()}); width: 12px; height: 12px; }}
QCheckBox {{ spacing: 10px; font-size: 14px; background: transparent; }}
QCheckBox::indicator {{
    width: 20px; height: 20px; border: 1.5px solid #8F8680; border-radius: 4px; background: white;
}}
QCheckBox::indicator:checked {{
    background: {C.GUINDA}; border-color: {C.GUINDA};
    image: url({(RECURSOS / 'img' / 'check.svg').as_posix()});
}}
QCheckBox::indicator:disabled {{ background: {C.FONDO}; border-color: {C.BORDE}; }}
QCheckBox:disabled {{ color: {C.TEXTO_SUAVE}; }}

/* ---------- Botones ---------- */
QPushButton {{ font-size: 14px; font-weight: 700; border-radius: 8px; padding: 10px 18px; }}
QPushButton[tipo="primario"] {{ background: {C.GUINDA_BOTON}; color: white; border: none; }}
QPushButton[tipo="primario"]:hover {{ background: {C.GUINDA_HOVER}; }}
QPushButton[tipo="primario"]:disabled {{ background: #C9A6A9; }}
QPushButton[tipo="peligro"] {{ background: {C.ROJO}; color: white; border: none; }}
QPushButton[tipo="peligro"]:hover {{ background: #9A1D13; }}
QPushButton[tipo="secundario"] {{ background: white; color: {C.GUINDA}; border: 1px solid {C.GUINDA}; }}
QPushButton[tipo="secundario"]:hover {{ background: {C.GUINDA_SUAVE}; }}
QPushButton[tipo="texto"] {{ background: transparent; color: {C.TEXTO_SUAVE}; border: none; }}
QPushButton[tipo="texto"]:hover {{ color: {C.GUINDA}; }}
QPushButton[tipo="link"] {{
    background: transparent; color: {C.GUINDA}; border: none; text-decoration: underline;
    font-weight: 600; padding: 2px 4px;
}}
QPushButton[tipo="icono"] {{
    background: white; border: 1px solid {C.BORDE_CAMPO}; border-radius: 8px; padding: 0;
    min-width: 34px; max-width: 34px; min-height: 34px; max-height: 34px;
}}
QPushButton[tipo="icono"]:hover {{ border-color: {C.GUINDA}; }}
QPushButton[tipo="opcion"] {{
    background: white; color: {C.TEXTO}; border: 1px solid {C.BORDE_CAMPO}; min-height: 30px;
}}
QPushButton[tipo="opcion"]:hover {{ border-color: {C.GUINDA}; }}
QPushButton[tipo="opcion"]:checked {{ background: {C.GUINDA_BOTON}; color: white; border-color: {C.GUINDA_BOTON}; }}
QPushButton[tipo="producto"] {{
    background: white; border: 1px solid {C.BORDE_CAMPO}; border-radius: 10px;
    text-align: left; padding: 10px 12px; min-height: 64px;
}}
QPushButton[tipo="producto"]:hover {{ border-color: {C.GUINDA}; background: {C.FONDO}; }}
QPushButton[tipo="modulo"] {{
    background: white; border: 1px solid {C.BORDE}; border-radius: 12px;
    text-align: left; padding: 16px 18px; font-size: 15px; font-weight: 800; min-height: 70px;
}}
QPushButton[tipo="modulo"]:hover {{ border-color: {C.GUINDA}; background: {C.FONDO}; }}

/* ---------- Tablas ---------- */
QTableWidget {{
    background: white; border: 1px solid {C.BORDE}; border-radius: 10px;
    gridline-color: transparent; font-size: 14px; outline: none;
    selection-background-color: {C.GUINDA_SUAVE}; selection-color: {C.TEXTO};
}}
QTableWidget::item {{ border-bottom: 1px solid {C.BORDE}; padding: 0 12px; }}
QHeaderView::section {{
    background: {C.CREMA}; color: {C.TEXTO}; border: none; padding: 10px 12px;
    font-size: 12px; font-weight: 800;
}}
QTableCornerButton::section {{ background: {C.CREMA}; border: none; }}

/* ---------- Barras de desplazamiento ---------- */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #D6CBC0; border-radius: 4px; min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #D6CBC0; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ---------- Login ---------- */
QFrame#LoginMarca {{ background: {C.GUINDA}; }}
QFrame#LoginMarca QLabel {{ color: white; background: transparent; }}
QWidget#LoginForm {{ background: {C.FONDO}; }}
QLabel#LoginTitulo {{ font-family: "{TITULOS}"; font-size: 34px; font-weight: 600; color: {C.GUINDA}; }}

/* ---------- Diálogos ---------- */
QDialog {{ background: {C.FONDO}; }}
QMessageBox {{ background: white; }}
QMessageBox QLabel {{ font-size: 14px; }}
"""


def aplicar(app: QApplication) -> None:
    cargar_fuentes()
    app.setFont(fuente_texto(14))
    app.setStyleSheet(QSS)
