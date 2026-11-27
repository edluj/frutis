# -*- mode: python ; coding: utf-8 -*-
# EC-14 · Ejecutable de Frutis ERP + POS (PyInstaller).
#   cd frontend && pyinstaller --noconfirm frutis.spec
# Resultado: dist/Frutis (Linux) o dist/Frutis.exe (Windows). Se construye en cada sistema:
# PyInstaller no genera el .exe desde Linux (lo hace .github/workflows/frontend.yml).
import sys

from PyInstaller.utils.hooks import collect_submodules

# collect_submodules importa el paquete en otro proceso: necesita frontend/ en la ruta.
sys.path.insert(0, SPECPATH)

# Módulos de Qt que la aplicación no usa: solo QtCore, QtGui, QtWidgets y QtSvg.
SIN_USAR = [
    "PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets", "PySide6.QtWebChannel", "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    "PySide6.Qt3DCore", "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtBluetooth", "PySide6.QtPositioning", "PySide6.QtSensors",
    "PySide6.QtSerialPort", "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtDesigner", "PySide6.QtHelp",
    "PySide6.QtUiTools", "PySide6.QtXml", "tkinter", "pytest", "pyflakes",
]

a = Analysis(
    ["app/__main__.py"],
    pathex=["."],
    datas=[("app/resources", "app/resources")],
    # shell.py abre cada pantalla con importlib a partir de RUTAS: PyInstaller no las ve solo.
    hiddenimports=["PySide6.QtSvg", *collect_submodules("app")],
    excludes=SIN_USAR,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Frutis",
    icon="app/resources/img/logo.png",
    # Sin consola: es una aplicación de ventana para la caja.
    console=False,
    upx=False,
    strip=False,
)
