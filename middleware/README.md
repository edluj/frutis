# middleware · EC-09, EC-10

API FastAPI sobre HTTPS en la red local. Es la única puerta a la base de datos.

- Autenticación con token por rol y matriz de permisos por módulo.
- Validación con Pydantic: los filtros de texto solo admiten letras, números y puntuación básica, así que se rechazan comillas y etiquetas (SQLi / XSS). Las consultas son siempre parametrizadas.
- Reglas de negocio y bitácora de auditoría.
- Controladores de báscula e impresora de tickets en `app/hardware/` (EC-10).
- Integración con el proveedor de timbrado CFDI en `app/integrations/pac.py`. Por SC-05 se usa `PacSimulado`: timbra sin internet ni CSD con el RFC de pruebas del SAT; un PAC real solo tiene que cumplir la interfaz `Pac`.

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
| `GET /pos/clientes-credito` | `pos` crear | Clientes de crédito activos con lo que deben, su disponible y el vencimiento de una venta de hoy (HU-38a) |
| `GET /pos/ventas/{folio}` | `pos` ver | Ticket con sus productos y lo ya devuelto |
| `GET /pos/cortes/actual` | `pos` ver | Resumen del turno abierto: ventas por método, cobros y devoluciones en efectivo, efectivo esperado (HU-09) |
| `GET /pos/cortes/ultimo` | `pos` ver | Último corte de una terminal (`terminal=POS-01`) |
| `POST /pos/cortes` | `pos` crear | Arqueo y cierre con `sp_cerrar_caja`; exige observaciones si hay diferencia |
| `GET /pos/devoluciones/administradores` | `pos` crear | Administradores activos que pueden autorizar |
| `POST /pos/devoluciones/autorizacion` | `pos` crear | El Administrador escribe su contraseña; devuelve una autorización firmada |
| `POST /pos/devoluciones` | `pos` crear | Devolución parcial o total con `sp_registrar_devolucion` (HU-30) |
| `GET /inventario/categorias` | `inventario` ver | Filtros `busqueda` y `activas`; incluye los productos activos de cada una |
| `POST /inventario/categorias`, `PUT /inventario/categorias/{id}` | `inventario` crear / editar | Nombre único; no se da de baja una categoría con productos activos (HU-22) |
| `GET /inventario/productos` | `inventario` ver | Filtros `busqueda` (nombre o código), `id_categoria` y `existencia` (`todas`, `bajo`, `por_caducar`); trae existencia por lotes y estado |
| `POST /inventario/productos`, `PUT /inventario/productos/{id}` | `inventario` crear / editar | Código de barras único, precio mayor a 0, baja lógica; cada cambio de precio queda en `historial_precios` (HU-10) |
| `GET /inventario/productos/{id}/lotes` | `inventario` ver | Lotes del producto con existencia, primero el que caduca antes |
| `GET /inventario/mermas` | `inventario` ver | Filtros `motivo`, `desde` y `hasta` |
| `POST /inventario/mermas` | `inventario` crear | Descuenta del lote y guarda el costo (cantidad × costo del lote); no puede superar la existencia del lote (HU-17) |
| `GET /compras/proveedores` | `compras` ver | Filtros `busqueda` (razón social o RFC) y `estatus` (`activos`, `inactivos`, `todos`); incluye el saldo por pagar |
| `POST /compras/proveedores`, `PUT /compras/proveedores/{id}` | `compras` crear / editar | RFC único de 12 o 13 caracteres, correo válido; no se da de baja con saldo por pagar (HU-23) |
| `GET /compras/lotes` | `compras` ver | Filtros `id_proveedor`, `desde`, `hasta` y `pago` (`Pagado`, `Pendiente`, `Vencido`) |
| `GET /compras/lotes/siguiente-folio` | `compras` crear | Folio que probablemente tendrá el próximo lote |
| `GET /compras/lotes/{folio}` | `compras` ver | Productos con recibido, vendido, merma y existencia; mermas y cuenta por pagar |
| `POST /compras/lotes` | `compras` crear | En una transacción: lote, existencia por producto, costo vigente y, si `dias_credito` > 0, la cuenta por pagar (HU-11) |
| `GET /finanzas/clientes-credito` | `finanzas` ver | Filtros `busqueda` y `estatus` (`activos`, `suspendidos`, `todos`); lo que debe cada cliente y si tiene una cuenta vencida |
| `POST /finanzas/clientes-credito`, `PUT /finanzas/clientes-credito/{id}` | `finanzas` crear / editar | Límite mayor a 0 y días de crédito obligatorios; un cliente suspendido no compra a crédito (HU-39) |
| `GET /admin/roles` | `admin` ver | Roles activos |
| `GET /admin/usuarios` | `admin` ver | Filtros `busqueda` (nombre o usuario) e `id_rol`; nunca devuelve el hash |
| `POST /admin/usuarios`, `PUT /admin/usuarios/{id}` | `admin` crear / editar | Usuario y correo únicos, contraseña de al menos 8 caracteres guardada con PBKDF2; nadie se da de baja ni se quita el rol de Administrador a sí mismo; una contraseña nueva o una baja cierran las sesiones del usuario (HU-18) |
| `GET /facturacion/timbres` | `facturacion` ver | Timbres disponibles de los contratados (`FRUTIS_TIMBRES_CONTRATADOS`) |
| `GET /facturacion/clientes` | `facturacion` ver | Datos fiscales activos con su número de facturas |
| `POST /facturacion/clientes`, `PUT /facturacion/clientes/{id}` | `facturacion` crear / editar | RFC único y válido, régimen de 3 dígitos, código postal de 5 y correo (HU-32) |
| `GET /facturacion/tickets/{folio}` | `facturacion` crear | Conceptos del ticket con clave SAT; rechaza tickets ya facturados o con devoluciones |
| `POST /facturacion/facturas` | `facturacion` crear | Guarda el borrador, lo timbra con el PAC y guarda UUID y XML; un ticket solo tiene una factura vigente; si el PAC no responde: 503 "Sin conexión a internet, no es posible timbrar." y el borrador se reintenta (HU-12a) |
| `GET /facturacion/facturas`, `GET /facturacion/facturas/{folio}` | `facturacion` ver | Filtros `texto` (folio, RFC o razón social), `desde`, `hasta` y `estatus` |
| `GET /facturacion/facturas/{folio}/xml` | `facturacion` ver | Descarga del XML timbrado |
| `POST /facturacion/facturas/{folio}/cancelacion` | `facturacion` editar | Motivo SAT 01 a 04; el 01 exige el folio de una factura vigente que la sustituye (HU-33) |

**Autorización de devoluciones (SC-02).** El Administrador escribe su contraseña en la terminal del cajero. Si es correcta, el middleware entrega una autorización firmada que vale 5 minutos, solo para ese cajero y ese ticket, y no sirve como sesión. Los intentos fallidos cuentan para el bloqueo de 5 intentos de esa cuenta. Una contraseña incorrecta responde 403, no 401, para que la terminal no crea que expiró la sesión del cajero. Al registrar la devolución, la base vuelve a exigir que quien autoriza sea Administrador (triggers `trg_devoluciones_autoriza_*`).

**Reembolso.** Efectivo sale del cajón y se resta en el corte; una venta a crédito se reembolsa solo como abono a su cuenta; el reverso a tarjeta solo aplica a tickets pagados con tarjeta. Lo que está en buen estado regresa a su lote; lo que está en mal estado se registra como merma.

**Mensajes del login (APR, flujo A).** Credenciales incorrectas o usuario inexistente: "Ingrese un usuario/contraseña correcta." Un usuario o rol inactivo recibe "Usuario inactivo, contacte al administrador." solo si la contraseña es correcta; con una contraseña incorrecta recibe el mensaje general, así el login no revela qué usuarios existen.

**Errores por campo.** Cuando una regla se refiere a un dato del formulario, la respuesta trae también `campo` (por ejemplo `{"detail": "El código de barras ya está registrado.", "campo": "codigo"}`) para que la pantalla lo marque.

Cada respuesta autenticada trae `X-Token-Renovado`: el cliente reemplaza su token con ese valor para que la sesión expire por inactividad.
