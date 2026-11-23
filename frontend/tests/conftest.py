import os

# Las pruebas de pantallas corren sin monitor (también en la CI).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    from app import theme

    app = QApplication.instance() or QApplication(["pruebas"])
    theme.aplicar(app)
    return app
