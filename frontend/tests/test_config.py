"""Configuración de la terminal: frutis.ini y variables de entorno."""
import pytest

from app import config


@pytest.fixture
def carpeta(tmp_path, monkeypatch):
    for clave in ("API_URL", "CA_PATH", "TERMINAL", "TIMEOUT", "DEMO"):
        monkeypatch.delenv(f"FRUTIS_{clave}", raising=False)
    monkeypatch.setattr(config, "carpeta_base", lambda: tmp_path)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_sin_archivo_usa_los_valores_por_omision(carpeta):
    cfg = config.cargar()
    assert (cfg.api_url, cfg.ca_path, cfg.terminal, cfg.demo, cfg.timeout) == ("http://127.0.0.1:8443", None, "POS-1", False, 5.0)


def test_lee_frutis_ini_y_resuelve_la_ca_relativa(carpeta):
    (carpeta / "frutis.ini").write_text(
        "[terminal]\napi_url = https://192.168.1.10:8443/\nca_path = frutis-ca.crt\nterminal = POS-02\ntimeout = 8\n",
        encoding="utf-8")
    cfg = config.cargar()
    assert cfg.api_url == "https://192.168.1.10:8443"
    assert cfg.ca_path == str(carpeta / "frutis-ca.crt")
    assert (cfg.terminal, cfg.timeout) == ("POS-02", 8.0)


def test_el_entorno_tiene_prioridad(carpeta, monkeypatch):
    (carpeta / "frutis.ini").write_text("[terminal]\nterminal = POS-02\n", encoding="utf-8")
    monkeypatch.setenv("FRUTIS_TERMINAL", "POS-09")
    assert config.cargar().terminal == "POS-09"


def test_demo_forzado(carpeta):
    assert config.cargar(demo_forzado=True).demo is True
