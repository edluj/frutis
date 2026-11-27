# frontend · EC-11

Aplicación de escritorio en Python + PySide6 (Qt), empaquetada con PyInstaller como `.exe` (Windows) o binario (Linux).

- Una sola aplicación con login y menú según el rol del token (flujos A y B).
- Las 36 pantallas del lienzo de diseño (`docs/diseno/Diseño UX UI Frutis ERP.pdf`): login, inicio, POS, compras, facturación, finanzas, inventario, reportes y administración.
- No contiene reglas de negocio ni credenciales de base de datos: todo pasa por el middleware (ADR-04). En pantalla solo se valida la forma (RFC, correo, montos) para dar respuesta inmediata.

## Ejecutar

Requiere Python 3.12 o superior.

```bash
cd frontend
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt     # Linux: .venv/bin/pip
.venv/Scripts/python -m app --demo                    # sin servidor, con los datos del diseño
.venv/Scripts/python -m app                           # contra el middleware
.venv/Scripts/python -m pytest                        # 42 pruebas, no necesitan monitor ni servidor
```

**Modo demostración** (`--demo` o `FRUTIS_DEMO=1`): todo vive en memoria con los datos del lienzo de diseño (fecha de referencia: lunes 2 de noviembre de 2026) y nada se guarda. Usuarios: `alopez` (Administrador), `mperez` (Cajero), `cruiz` (Contador); `lgomez` está inactivo. Contraseña `Frutis2026!`.

**Contra el middleware** se configura con `frutis.ini` junto al ejecutable (plantilla en `frutis.ini.example`) o con variables de entorno, que tienen prioridad:

| Variable | Default | Uso |
| --- | --- | --- |
| `FRUTIS_API_URL` | `http://127.0.0.1:8443` | Dirección del middleware |
| `FRUTIS_CA_PATH` | — | Autoridad certificadora local para validar el certificado del servidor (HTTPS) |
| `FRUTIS_TERMINAL` | `POS-1` | Nombre de la terminal |
| `FRUTIS_TIMEOUT` | `5` | Segundos de espera por petición |

## Ejecutable

`frutis.spec` empaqueta la aplicación con PyInstaller en un solo archivo, con las fuentes, las imágenes y el aviso de privacidad:

```bash
cd frontend
.venv/bin/pip install -r requirements-build.txt
.venv/bin/pyinstaller --noconfirm frutis.spec     # dist/Frutis en Linux, dist/Frutis.exe en Windows
QT_QPA_PLATFORM=offscreen dist/Frutis --verificar  # abre las 34 pantallas como Administrador (demostración)
```

`--verificar` existe porque `shell.py` abre cada pantalla con `importlib` y PyInstaller no las ve solo: `frutis.spec` las incluye con `collect_submodules("app")`, y la CI corre la verificación en el `.exe` y en el binario de Linux.

PyInstaller solo construye para el sistema donde corre. El workflow **Frontend** (`.github/workflows/frontend.yml`) corre las pruebas y genera `Frutis.exe` y el binario de Linux en cada Pull Request que toca `frontend/`; se descargan como artefactos de la ejecución. La instalación en las terminales está en `deploy/README.md`.

## Estructura

```
app/
├── __main__.py        # python -m app [--demo]
├── api_client.py      # cliente HTTP único: token en memoria, X-Token-Renovado, errores
├── config.py          # variables de entorno de la terminal
├── sesion.py          # perfil y matriz de permisos del usuario
├── theme.py           # colores, tipografías (Fredoka, Nunito Sans) y hoja de estilos
├── widgets.py         # componentes del diseño: página, tarjeta, KPI, campo, tabla, insignia, gráficas
├── formato.py         # $18,420.50 · −$24.50 · 1.250 kg · fechas en español
├── validaciones.py    # RFC, correo, CP, montos (solo forma; la regla final es del middleware)
├── exportar.py        # tablas a PDF (QPdfWriter) y Excel (.xlsx sin dependencias)
├── catalogos_sat.py   # régimen, uso de CFDI, forma y método de pago, motivos de cancelación
├── datos/
│   ├── api.py         # datos del middleware
│   ├── demo.py        # datos de demostración en memoria
│   └── reportes_demo.py
├── presenters/pos.py  # carrito, cambio, fondo inicial y arqueo (probado sin Qt)
├── views/             # una pantalla por archivo: pos/, compras/, facturacion/, finanzas/, inventario/, admin/
└── resources/         # logotipo, fuentes OFL y aviso de privacidad
```

Las vistas nunca llaman a la red: piden datos a un objeto `datos` (`DatosApi` o `DatosDemo`) con la misma interfaz.

## Pantallas y estado de conexión

Hoy el middleware expone `/auth`, `/pos` y parte de `/inventario`, `/compras`, `/finanzas`, `/admin` y `/facturacion` (ver `middleware/README.md`). Con el servidor ya funcionan el login, el menú por rol y todo el Punto de Venta: apertura, cobro, corte y devoluciones, además de categorías, productos, mermas, proveedores, lotes de compra, clientes de crédito, usuarios y facturación (con el PAC simulado de SC-05). La caja de la apertura es la terminal de `FRUTIS_TERMINAL`. Las demás pantallas muestran un aviso con la ruta que falta en lugar de inventar datos; en modo demostración se pueden recorrer todas.

| Módulo | Pantallas (código del diseño) | Historias | Ruta que falta en el middleware |
| --- | --- | --- | --- |
| Acceso | Login (ACC-01), Inicio y menú (ACC-02) | HU-04, HU-14, HU-21 | `/reportes/resumen-del-dia` para el resumen de inicio |
| Punto de Venta | Apertura (POS-01), Cobro (POS-02), Corte (POS-03), Devolución (POS-04) | HU-06, 07a, 08, 09, 15, 16a, 30, 36, 38a | Ninguna: la venta a crédito ya usa `/pos/clientes-credito` |
| Proveedores y Compras | Proveedores, Registrar lote, Lotes, Detalle de lote, Cuentas por pagar, Estado de cuenta (PRV-01 a 06) | HU-11, 23, 25 | Ninguna: las 6 pantallas usan el servidor |
| Facturación | Generar, Factura timbrada, Emitidas, Clientes fiscales (FAC-01 a 04) | HU-12a, 32, 33 | Ninguna: generar, factura timbrada, emitidas y clientes fiscales usan `/facturacion` con el PAC simulado. Falta el PDF y "Guardar borrador" sin timbrar |
| Finanzas | Dashboard, Gastos, Flujo, Clientes de crédito, Cuentas por cobrar, Estado de cuenta (FIN-01 a 06) | HU-26, 27, 37, 38b, 39 | Clientes de crédito (FIN-04) ya conectados. Faltan `/finanzas/dashboard`, `/finanzas/gastos`, `/finanzas/flujo`, `/finanzas/cuentas-por-cobrar` y `/finanzas/cobros` |
| Catálogo e Inventario | Categorías, Productos, Existencias, Lotes y caducidades, Movimientos, Ajuste e historial de precios, Mermas (CAT-01 a 08) | HU-10, 17, 22, 24, 31 | Ninguna: las 8 pantallas usan el servidor; la vista previa del ajuste de precios se calcula en la pantalla |
| Reportes | 12 reportes con exportación PDF y Excel (REP-01) | HU-28, 29 | `/reportes` |
| Administración | Usuarios, Roles y permisos, Auditoría, Cajas y dispositivos (ADM-01 a 04) | HU-18, 34, 35, 41 | Usuarios (ADM-01) ya conectado. Faltan los permisos por rol, la auditoría y las cajas (`/admin/roles/...`, `/admin/auditoria`, `/admin/cajas`, `/admin/metodos-pago`, `/admin/dispositivos`) |

## Pendientes

- Báscula e impresora usan simulador (R-01, R-02): tocar la báscula en el cobro permite capturar el peso a mano, y el ticket se muestra en pantalla.
- `resources/aviso_privacidad.txt` tiene un texto provisional: falta el aviso vigente del cliente (HU-21).
- El emisor de la factura muestra `[RFC DEL EMISOR]` hasta tener los datos fiscales y el CSD de la frutería.
- Servicio local de hardware en cada terminal: fuera de alcance por SC-05 (se usa el simulador).
