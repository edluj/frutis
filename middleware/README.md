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
| `POST /pos/cajas` | `pos` crear | Apertura con `sp_abrir_caja`: terminal y fondo inicial; una caja abierta por terminal y por cajero (HU-15) |
| `POST /pos/ventas` | `pos` crear | Cobro con `sp_registrar_venta`; el cajero sale del token |
| `GET /pos/ventas/{folio}` | `pos` ver | Ticket con sus productos y lo ya devuelto |
| `GET /pos/cortes/actual` | `pos` ver | Resumen del turno abierto: ventas por método, cobros y devoluciones en efectivo, efectivo esperado (HU-09) |
| `GET /pos/cortes/ultimo` | `pos` ver | Último corte de una terminal (`terminal=POS-01`) |
| `POST /pos/cortes` | `pos` crear | Arqueo y cierre con `sp_cerrar_caja`; exige observaciones si hay diferencia |
| `GET /pos/devoluciones/administradores` | `pos` crear | Administradores activos que pueden autorizar |
| `POST /pos/devoluciones/autorizacion` | `pos` crear | El Administrador escribe su contraseña; devuelve una autorización firmada |
| `POST /pos/devoluciones` | `pos` crear | Devolución parcial o total con `sp_registrar_devolucion` (HU-30) |

**Autorización de devoluciones (SC-02).** El Administrador escribe su contraseña en la terminal del cajero. Si es correcta, el middleware entrega una autorización firmada que vale 5 minutos, solo para ese cajero y ese ticket, y no sirve como sesión. Los intentos fallidos cuentan para el bloqueo de 5 intentos de esa cuenta. Una contraseña incorrecta responde 403, no 401, para que la terminal no crea que expiró la sesión del cajero. Al registrar la devolución, la base vuelve a exigir que quien autoriza sea Administrador (triggers `trg_devoluciones_autoriza_*`).

**Reembolso.** Efectivo sale del cajón y se resta en el corte; una venta a crédito se reembolsa solo como abono a su cuenta; el reverso a tarjeta solo aplica a tickets pagados con tarjeta. Lo que está en buen estado regresa a su lote; lo que está en mal estado se registra como merma.

**Mensajes del login (APR, flujo A).** Credenciales incorrectas o usuario inexistente: "Ingrese un usuario/contraseña correcta." Un usuario o rol inactivo recibe "Usuario inactivo, contacte al administrador." solo si la contraseña es correcta; con una contraseña incorrecta recibe el mensaje general, así el login no revela qué usuarios existen.

Cada respuesta autenticada trae `X-Token-Renovado`: el cliente reemplaza su token con ese valor para que la sesión expire por inactividad.
