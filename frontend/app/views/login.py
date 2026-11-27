"""ACC-01 · Inicio de sesión (flujo A, HU-04 y HU-21)."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLineEdit, QPlainTextEdit, QVBoxLayout, QWidget

from app.api_client import ErrorApi
from app.datos import ErrorNegocio
from app.iconos import icono
from app.theme import RECURSOS, C
from app.widgets import Campo, boton, entrada, etiqueta, texto


class AvisoPrivacidad(QDialog):
    def __init__(self, padre: QWidget):
        super().__init__(padre)
        self.setWindowTitle("Aviso de privacidad")
        self.resize(640, 520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(14)
        lay.addWidget(etiqueta("Aviso de privacidad", "LoginTitulo"))
        cuerpo = QPlainTextEdit()
        cuerpo.setReadOnly(True)
        archivo = RECURSOS / "aviso_privacidad.txt"
        cuerpo.setPlainText(archivo.read_text(encoding="utf-8") if archivo.exists() else "")
        lay.addWidget(cuerpo, 1)
        lay.addWidget(boton("Cerrar", "primario", self.accept), 0, Qt.AlignmentFlag.AlignRight)


class LoginView(QWidget):
    sesion_iniciada = Signal(dict)

    def __init__(self, datos):
        super().__init__()
        self.datos = datos
        raiz = QHBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        # Mitad izquierda: identidad de Frutis.
        marca = QFrame()
        marca.setObjectName("LoginMarca")
        lm = QVBoxLayout(marca)
        lm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lm.setSpacing(28)
        logo = etiqueta("")
        logo.setPixmap(QPixmap(str(RECURSOS / "img" / "logo.png")).scaled(
            360, 360, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lema = texto("Sistema de punto de venta y administración de\nla frutería", 17, color="white")
        lema.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lm.addWidget(logo)
        lm.addWidget(lema)
        raiz.addWidget(marca, 1)

        # Mitad derecha: formulario.
        lado = QWidget()
        lado.setObjectName("LoginForm")
        ll = QVBoxLayout(lado)
        ll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        form = QWidget()
        form.setFixedWidth(420)
        lf = QVBoxLayout(form)
        lf.setContentsMargins(0, 0, 0, 0)
        lf.setSpacing(10)
        lf.addWidget(etiqueta("Inicia sesión", "LoginTitulo"))
        lf.addWidget(texto("Usa el usuario que te asignó el administrador.", 15, color=C.TEXTO_SUAVE))
        lf.addSpacing(14)

        self.usuario = entrada(placeholder="Usuario", max_len=50)
        self.usuario.setAccessibleName("Usuario")
        self.campo_usuario = Campo("Usuario", self.usuario)
        self.password = entrada(placeholder="Contraseña", password=True, max_len=128)
        self.password.setAccessibleName("Contraseña")
        self._ojo = QAction(icono("ojo", C.TEXTO_SUAVE, 18), "Mostrar contraseña", self.password)
        self._ojo.triggered.connect(self._alternar)
        self.password.addAction(self._ojo, QLineEdit.ActionPosition.TrailingPosition)
        self.campo_password = Campo("Contraseña", self.password)
        lf.addWidget(self.campo_usuario)
        lf.addSpacing(10)
        lf.addWidget(self.campo_password)
        lf.addSpacing(18)

        self.entrar = boton("Entrar", "primario", self._entrar)
        self.entrar.setMinimumHeight(52)
        self.entrar.setStyleSheet("font-size: 16px;")
        lf.addWidget(self.entrar)
        lf.addSpacing(6)
        aviso = etiqueta('<a href="#" style="color:%s">Aviso de privacidad</a>' % C.GUINDA, rico=True)
        aviso.linkActivated.connect(lambda _: AvisoPrivacidad(self).exec())
        lf.addWidget(aviso)
        lf.addWidget(texto("¿Olvidaste tu contraseña? Pídela al administrador.", 13, color=C.TEXTO_SUAVE))
        if getattr(datos, "es_demo", False):
            lf.addSpacing(10)
            nota = texto("Modo demostración: alopez (Administrador), mperez (Cajero), cruiz (Contador). "
                         "Contraseña Frutis2026!", 12, color=C.NARANJA_TEXTO, ajustar=True)
            lf.addWidget(nota)
        ll.addWidget(form)
        raiz.addWidget(lado, 1)

        self.usuario.returnPressed.connect(self.password.setFocus)
        self.password.returnPressed.connect(self._entrar)
        self.password.textEdited.connect(lambda *_: self.campo_password.error(None))

    def _alternar(self) -> None:
        oculto = self.password.echoMode() == QLineEdit.EchoMode.Password
        self.password.setEchoMode(QLineEdit.EchoMode.Normal if oculto else QLineEdit.EchoMode.Password)
        self._ojo.setIcon(icono("ojo_off" if oculto else "ojo", C.TEXTO_SUAVE, 18))
        self._ojo.setText("Ocultar contraseña" if oculto else "Mostrar contraseña")

    def _entrar(self) -> None:
        usuario, password = self.usuario.text().strip(), self.password.text()
        self.campo_usuario.error(None)
        if not usuario or not password:
            self.campo_password.error("Ingrese un usuario/contraseña correcta.")
            return
        self.entrar.setEnabled(False)
        self.entrar.setText("Entrando…")
        self.entrar.repaint()
        try:
            perfil = self.datos.login(usuario, password)
        except (ErrorNegocio, ErrorApi) as exc:
            self.campo_password.error(exc.mensaje)
            self.password.selectAll()
            self.password.setFocus()
            return
        finally:
            self.entrar.setEnabled(True)
            self.entrar.setText("Entrar")
        self.password.clear()
        self.sesion_iniciada.emit(perfil)

    def reiniciar(self) -> None:
        self.password.clear()
        self.campo_password.error(None)
        self.usuario.setFocus()
