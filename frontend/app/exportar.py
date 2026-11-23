"""Exportación de tablas a PDF y a Excel (.xlsx) desde la terminal (HU-28, HU-29).

El PDF se arma con QTextDocument + QPdfWriter y el Excel con un .xlsx mínimo escrito a
mano (sin dependencias extra). Las dos salidas usan lo mismo que se ve en pantalla.
"""
import html
import zipfile
from collections.abc import Sequence
from datetime import datetime
from xml.sax.saxutils import escape

from PySide6.QtCore import QMarginsF, QSizeF
from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument
from PySide6.QtWidgets import QFileDialog, QTableWidget, QWidget

from app.theme import C


def filas_de_tabla(tabla: QTableWidget) -> tuple[list[str], list[list[str]]]:
    """Encabezados y celdas de texto de una `Tabla` (ignora columnas de botones)."""
    cols = [i for i in range(tabla.columnCount()) if tabla.horizontalHeaderItem(i).text()]
    encabezados = [tabla.horizontalHeaderItem(i).text() for i in cols]
    filas = []
    for r in range(tabla.rowCount()):
        fila = []
        for c in cols:
            w = tabla.cellWidget(r, c)
            if w is not None:
                from PySide6.QtWidgets import QLabel
                etiquetas = [x.text() for x in w.findChildren(QLabel)]
                fila.append(" ".join(etiquetas))
            else:
                item = tabla.item(r, c)
                fila.append(item.text() if item else "")
        filas.append(fila)
    return encabezados, filas


def a_pdf(ruta: str, titulo: str, subtitulo: str, encabezados: Sequence[str], filas: Sequence[Sequence[str]]) -> None:
    cuerpo = "".join(
        "<tr>" + "".join(f"<td style='padding:4px 6px;border-bottom:1px solid {C.BORDE}'>{html.escape(str(c))}</td>"
                         for c in f) + "</tr>" for f in filas)
    cab = "".join(f"<th style='background:{C.CREMA};padding:5px 6px;text-align:left'>{html.escape(h)}</th>" for h in encabezados)
    doc = QTextDocument()
    doc.setHtml(
        f"<h2 style='color:{C.GUINDA}'>Frutería Frutis · {html.escape(titulo)}</h2>"
        f"<p style='color:{C.TEXTO_SUAVE}'>{html.escape(subtitulo)} · generado {datetime.now():%d/%m/%Y %H:%M}</p>"
        f"<table width='100%' cellspacing='0' style='font-size:9pt'><tr>{cab}</tr>{cuerpo}</table>")
    pdf = QPdfWriter(ruta)
    pdf.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.Letter), QPageLayout.Orientation.Landscape,
                                  QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter))
    pdf.setResolution(96)
    doc.setPageSize(QSizeF(pdf.width(), pdf.height()))
    doc.print_(pdf)


def _col(n: int) -> str:
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def a_xlsx(ruta: str, titulo: str, encabezados: Sequence[str], filas: Sequence[Sequence[str]]) -> None:
    def celda(r: int, c: int, v: str) -> str:
        return f'<c r="{_col(c)}{r}" t="inlineStr"><is><t>{escape(str(v))}</t></is></c>'

    todas = [list(encabezados)] + [list(f) for f in filas]
    hoja = "".join(f'<row r="{i + 1}">' + "".join(celda(i + 1, j, v) for j, v in enumerate(f)) + "</row>"
                   for i, f in enumerate(todas))
    nombre = escape(titulo[:31] or "Reporte")
    archivos = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '</Types>',
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>',
        "xl/workbook.xml": '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{nombre}" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '</Relationships>',
        "xl/worksheets/sheet1.xml": '<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{hoja}</sheetData></worksheet>',
    }
    with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as z:
        for nombre_archivo, contenido in archivos.items():
            z.writestr(nombre_archivo, contenido)


def exportar_tabla(padre: QWidget, tabla: QTableWidget, titulo: str, subtitulo: str = "", formato: str = "pdf") -> str | None:
    """Pide la ruta y exporta. Devuelve la ruta guardada o None si se canceló."""
    encabezados, filas = filas_de_tabla(tabla)
    sugerido = titulo.lower().replace(" ", "_").replace("·", "")
    if formato == "pdf":
        ruta, _ = QFileDialog.getSaveFileName(padre, "Exportar PDF", f"{sugerido}.pdf", "PDF (*.pdf)")
        if ruta:
            a_pdf(ruta, titulo, subtitulo, encabezados, filas)
    else:
        ruta, _ = QFileDialog.getSaveFileName(padre, "Exportar Excel", f"{sugerido}.xlsx", "Excel (*.xlsx)")
        if ruta:
            a_xlsx(ruta, titulo, encabezados, filas)
    return ruta or None
