# frontend · EC-11

Aplicación de escritorio en Python 3.12 + PySide6 (Qt), empaquetada con PyInstaller como `.exe` (Windows) o binario (Linux).

- Una sola aplicación con login y menú según el rol del token.
- 32 pantallas en 6 módulos, organizadas con el patrón Modelo–Vista–Presentador.
- No contiene reglas de negocio ni credenciales de base de datos: todo pasa por el middleware.

Estructura prevista: `app/views/`, `app/presenters/`, `app/api_client.py`, `app/resources/`, `requirements.txt`.
