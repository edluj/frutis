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

**Contra el middleware** se configura con variables de entorno:

| Variable | Default | Uso |
| --- | --- | --- |
| `FRUTIS_API_URL` | `http://127.0.0.1:8443` | Dirección del middleware |
| `FRUTIS_CA_PATH` | — | Autoridad certificadora local para validar el certificado del servidor (HTTPS) |
| `FRUTIS_TERMINAL` | `POS-1` | Nombre de la terminal |
| `FRUTIS_TIMEOUT` | `5` | Segundos de espera por petición |

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

Hoy el middleware expone `/auth`, `/pos` y parte de `/inventario` (ver `middleware/README.md`). Con el servidor ya funcionan el login, el menú por rol y todo el Punto de Venta: apertura, cobro, corte y devoluciones, además de categorías y productos. La caja de la apertura es la terminal de `FRUTIS_TERMINAL`. Las demás pantallas muestran un aviso con la ruta que falta en lugar de inventar datos; en modo demostración se pueden recorrer todas.

| Módulo | Pantallas (código del diseño) | Historias | Ruta que falta en el middleware |
| --- | --- | --- | --- |
| Acceso | Login (ACC-01), Inicio y menú (ACC-02) | HU-04, HU-14, HU-21 | `/reportes/resumen-del-dia` para el resumen de inicio |
| Punto de Venta | Apertura (POS-01), Cobro (POS-02), Corte (POS-03), Devolución (POS-04) | HU-06, 07a, 08, 09, 15, 16a, 30, 36, 38a | Solo la lista de clientes de crédito del cobro (`/finanzas/clientes-credito`) |
| Proveedores y Compras | Proveedores, Registrar lote, Lotes, Detalle de lote, Cuentas por pagar, Estado de cuenta (PRV-01 a 06) | HU-11, 23, 25 | `/compras/...` |
| Facturación | Generar, Factura timbrada, Emitidas, Clientes fiscales (FAC-01 a 04) | HU-12a, 32, 33 | `/facturacion/...` y elegir PAC (R-06) |
| Finanzas | Dashboard, Gastos, Flujo, Clientes de crédito, Cuentas por cobrar, Estado de cuenta (FIN-01 a 06) | HU-26, 27, 37, 38b, 39 | `/finanzas/...` |
| Catálogo e Inventario | Categorías, Productos, Existencias, Lotes y caducidades, Movimientos, Ajuste e historial de precios, Mermas (CAT-01 a 08) | HU-10, 17, 22, 24, 31 | Categorías y productos (CAT-01, CAT-02) ya conectados. Faltan `/inventario/existencias`, `/inventario/lotes`, `/inventario/movimientos`, `/inventario/precios` y `/inventario/mermas` |
| Reportes | 12 reportes con exportación PDF y Excel (REP-01) | HU-28, 29 | `/reportes` |
| Administración | Usuarios, Roles y permisos, Auditoría, Cajas y dispositivos (ADM-01 a 04) | HU-18, 34, 35, 41 | `/admin/...` |

## Pendientes

- Báscula e impresora usan simulador (R-01, R-02): tocar la báscula en el cobro permite capturar el peso a mano, y el ticket se muestra en pantalla.
- `resources/aviso_privacidad.txt` tiene un texto provisional: falta el aviso vigente del cliente (HU-21).
- El emisor de la factura muestra `[RFC DEL EMISOR]` hasta tener los datos fiscales y el CSD de la frutería.
- Empaquetado con PyInstaller (`frutis.spec`) y servicio local de hardware en cada terminal.
