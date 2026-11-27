"""Proveedor de timbrado CFDI (PAC).

Por SC-05 el proyecto no timbra ante el SAT: `PacSimulado` responde como lo haría el
ambiente de pruebas de un PAC, sin internet ni CSD. Un PAC real solo tiene que cumplir
la interfaz `Pac` y devolverse en `get_pac()`.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from xml.etree import ElementTree as ET

NS_TFD = "http://www.sat.gob.mx/TimbreFiscalDigital"
RFC_PAC_PRUEBAS = "SPR190613I52"


class SinConexion(Exception):
    """El PAC no respondió; la factura se queda como borrador."""


@dataclass(frozen=True)
class Timbre:
    uuid: str
    fecha: datetime
    xml: str


class Pac(Protocol):
    def timbrar(self, xml: str) -> Timbre: ...

    def cancelar(self, uuid: str, motivo: str, uuid_sustituto: str | None) -> datetime: ...


class PacSimulado:
    """Agrega un TimbreFiscalDigital marcado como simulado; no firma ni consulta al SAT."""

    def timbrar(self, xml: str) -> Timbre:
        ET.register_namespace("tfd", NS_TFD)
        comprobante = ET.fromstring(xml)
        folio_fiscal = str(uuid.uuid4()).upper()
        fecha = datetime.now().replace(microsecond=0)
        complemento = ET.SubElement(comprobante, "{http://www.sat.gob.mx/cfd/4}Complemento")
        ET.SubElement(complemento, f"{{{NS_TFD}}}TimbreFiscalDigital", {
            "Version": "1.1", "UUID": folio_fiscal, "FechaTimbrado": fecha.isoformat(),
            "RfcProvCertif": RFC_PAC_PRUEBAS, "SelloCFD": "SIMULADO", "NoCertificadoSAT": "00000000000000000000",
            "SelloSAT": "SIMULADO",
        })
        return Timbre(folio_fiscal, fecha, ET.tostring(comprobante, encoding="unicode", xml_declaration=True))

    def cancelar(self, uuid: str, motivo: str, uuid_sustituto: str | None) -> datetime:
        return datetime.now().replace(microsecond=0)


def get_pac() -> Pac:
    return PacSimulado()
