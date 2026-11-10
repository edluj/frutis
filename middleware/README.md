# middleware · EC-09, EC-10

API FastAPI sobre HTTPS en la red local. Es la única puerta a la base de datos.

- Autenticación con token por rol y matriz de permisos por módulo.
- Validación con Pydantic: los filtros de texto solo admiten letras, números y puntuación básica, así que se rechazan comillas y etiquetas (SQLi / XSS). Las consultas son siempre parametrizadas.
- Reglas de negocio y bitácora de auditoría.
- Controladores de báscula e impresora de tickets en `app/hardware/` (EC-10).
- Integración con el proveedor de timbrado CFDI en `app/integrations/`.

Estructura: `app/{api,security,schemas,services,repositories}/`, `tests/`, `requirements.txt`. Faltan `app/hardware/` y `app/integrations/`.

Del prototipo en `legacy/middleware.py` se reutilizan el hash PBKDF2, el límite de 5 intentos fallidos y el enmascarado de contraseñas en la bitácora.

## Ejecutar

Requiere Python 3.12, la base instalada y `deploy/.env` con los datos de `frutis_app` y `FRUTIS_JWT_SECRET` (al menos 32 caracteres; `openssl rand -hex 32`).

```bash
cd middleware
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest      # no necesita MySQL
.venv/bin/python -m app         # documentación en /docs
```

Sin `FRUTIS_CERT_PATH` y `FRUTIS_KEY_PATH` el servidor escucha solo en `127.0.0.1`, aunque `FRUTIS_BIND_HOST` diga otra cosa.

## Rutas

| Ruta | Permiso | Uso |
| --- | --- | --- |
| `POST /auth/login` | Público | Devuelve token y perfil con la matriz de permisos; bloquea 5 minutos tras 5 intentos fallidos |
| `GET /auth/me`, `POST /auth/logout` | Sesión | Perfil actual; el cierre de sesión invalida los tokens del usuario en todas sus terminales (SC-04) |
| `GET /pos/productos` | `pos` ver | Filtros `codigo`, `busqueda` y `frecuentes` |
| `GET /pos/metodos-pago` | `pos` ver | Métodos de pago activos |
| `GET /pos/cajas/actual` | `pos` ver | Caja abierta del usuario |
| `POST /pos/ventas` | `pos` crear | Cobro con `sp_registrar_venta`; el cajero sale del token |

**Mensajes del login (APR, flujo A).** Credenciales incorrectas o usuario inexistente: "Ingrese un usuario/contraseña correcta." Un usuario o rol inactivo recibe "Usuario inactivo, contacte al administrador." solo si la contraseña es correcta; con una contraseña incorrecta recibe el mensaje general, así el login no revela qué usuarios existen.

Cada respuesta autenticada trae `X-Token-Renovado`: el cliente reemplaza su token con ese valor para que la sesión expire por inactividad.
