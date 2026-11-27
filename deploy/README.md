# deploy · EC-15

Instalación del servidor local y de las terminales. Nada de esta carpeta lleva secretos: `.env` y `certificados/` están fuera de Git.

| Archivo | Uso |
| --- | --- |
| `.env.example` | Plantilla de la configuración del servidor; se copia como `.env` |
| `generar_certificados.sh` | Autoridad certificadora local y certificado HTTPS del servidor |
| `frutis-middleware.service` | Servicio de systemd para que el middleware arranque solo |

## Servidor (Rocky Linux)

1. **Base de datos:** `database/README.md` (`instalar.sh`) y los usuarios `frutis_app` y `frutis_respaldo`.
2. **Configuración:** `cp deploy/.env.example deploy/.env` y llenar `FRUTIS_DB_USER`, `FRUTIS_DB_PASSWORD` y `FRUTIS_JWT_SECRET` (`openssl rand -hex 32`).
3. **Middleware:**
   ```bash
   cd middleware && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
   ```
4. **Certificados:** con las IP o nombres con que las terminales buscan al servidor:
   ```bash
   ./deploy/generar_certificados.sh 192.168.1.10
   ```
   Agregar a `deploy/.env` las tres líneas que imprime (`FRUTIS_BIND_HOST`, `FRUTIS_CERT_PATH`, `FRUTIS_KEY_PATH`). Sin certificado el middleware solo escucha en `127.0.0.1`. Guardar `certificados/frutis-ca.key` fuera del servidor: con ella se firman certificados.
5. **Abrir el puerto solo a la red interna** (ajustar la red):
   ```bash
   sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="192.168.1.0/24" port port="8443" protocol="tcp" accept'
   sudo firewall-cmd --reload
   ```
6. **Arrancar:** a mano con `cd middleware && .venv/bin/python -m app`, o como servicio con `frutis-middleware.service` (instrucciones dentro del archivo). La plantilla del servicio no se ha probado en el servidor de desarrollo.

## Terminales (Windows o Linux)

1. Descargar `Frutis-Windows` o `Frutis-Linux` de la ejecución de **Frontend** en GitHub Actions, o construirlo (`frontend/README.md`).
2. En una carpeta, poner juntos el ejecutable, `frutis-ca.crt` (de `deploy/certificados/` del servidor) y `frutis.ini` a partir de `frutis.ini.example`:
   ```ini
   [terminal]
   api_url = https://192.168.1.10:8443
   ca_path = frutis-ca.crt
   terminal = POS-01
   ```
3. Abrir `Frutis.exe` (o `./Frutis` en Linux). Sin servidor se puede probar con `Frutis.exe --demo`.

El binario de Linux se construye en Ubuntu 24.04: necesita glibc 2.39 o posterior (Rocky Linux 10 la tiene) y un escritorio con X11 o Wayland.
