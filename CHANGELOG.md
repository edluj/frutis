# Historial de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Versionado semántico según el Plan de Gestión de Configuración (sección 6).

## [Sin publicar]

### Agregado
- Facturación CFDI 4.0 de punta a punta con PAC simulado (HU-12a, HU-32, HU-33; SC-05): datos fiscales de clientes, timbrado desde un ticket con UUID y XML, un ticket por factura vigente, borrador que se conserva si el PAC no responde, descarga del XML y cancelación con motivo SAT. Los XML se guardan en `middleware/cfdi/` (fuera del repositorio).
- Administración de usuarios de punta a punta (HU-18): rutas `/admin/usuarios` y `/admin/roles`; usuario y correo únicos, contraseña guardada con PBKDF2, nadie se da de baja a sí mismo, y una contraseña nueva o una baja cierran las sesiones abiertas del usuario.
- Clientes de crédito y venta a crédito de punta a punta (HU-39, HU-38a): rutas `/finanzas/clientes-credito` para darlos de alta, editarlos y suspenderlos, y `/pos/clientes-credito` para que el cajero elija al cliente en el cobro con su disponible.
- Mermas por lote de punta a punta (HU-17): rutas `/inventario/mermas` y `/inventario/productos/{id}/lotes`; la merma descuenta del lote y guarda su costo. Motivo "Plaga u hongo" en la base (`database/migraciones/004_mermas_motivo_plaga.sql`). El resumen de la pantalla muestra el mes actual.
- Compras conectado de punta a punta (HU-23, HU-11): rutas `/compras/proveedores` y `/compras/lotes`; registrar un lote suma la existencia por producto, actualiza el costo vigente y, a crédito, crea la cuenta por pagar en la misma transacción. Las pantallas de proveedores, registrar lote, lotes y detalle de lote ya usan el servidor.
- Columnas `proveedores.direccion` y `lotes_compras.factura_proveedor`, que capturan las pantallas; bases instaladas: `database/migraciones/003_compras_direccion_factura.sql`.
- Catálogo conectado de punta a punta (HU-22, HU-10): rutas `/inventario/categorias` y `/inventario/productos` en el middleware, con nombre y código de barras únicos, baja lógica, historial de precios y bitácora; las pantallas Categorías (CAT-01) y Productos (CAT-02) ya usan el servidor.
- Los errores de negocio del middleware indican el `campo` del formulario al que se refieren.
- Apertura, corte de caja y devoluciones de punta a punta (HU-09, HU-15, HU-30, SC-02):
  - Base de datos: `sp_abrir_caja`, `sp_cerrar_caja`, `sp_registrar_devolucion` y `fn_efectivo_esperado`, con 48 pruebas nuevas.
  - Middleware: rutas `POST /pos/cajas`, `GET /pos/cortes/actual`, `GET /pos/cortes/ultimo`, `POST /pos/cortes`, `GET /pos/ventas/{folio}` y `/pos/devoluciones` (administradores, autorización firmada del Administrador y registro).
  - Frontend: las pantallas de apertura, corte y devolución ya usan el servidor.
- Columna `devoluciones.reembolso` para saber qué devoluciones salieron del cajón; bases instaladas: `database/migraciones/002_devoluciones_reembolso.sql`.
- Cerrar sesión invalida el token (SC-04, #14, HU-14): columna `usuarios.sesion_version` y migración `database/migraciones/001_sc04_sesion_version.sql`.
- CI del middleware en cada Pull Request (HU-40) y rechazo de comillas y etiquetas en los filtros del POS (HU-03).
- Esqueleto del middleware FastAPI: `/auth` (JWT, PBKDF2, límite de 5 intentos), `/pos` (productos, métodos de pago, caja actual y cobro con `sp_registrar_venta`), matriz de permisos, bitácora y pruebas.
- Venta a crédito (SC-03, #4): tablas `clientes_credito`, `cuentas_por_cobrar` y `cobros_clientes`, método de pago "Crédito", `sp_registrar_cobro` y vista `v_cuentas_por_cobrar`; `sp_registrar_venta` valida el límite de crédito.
- Solo el Administrador autoriza devoluciones (SC-02, #3), validado con triggers.
- Base de datos MySQL 8.0 (HU-01, HU-02): esquema de 20 tablas, `fn_importe_peso`, `sp_registrar_venta` con descuento FEFO, datos de prueba, 35 pruebas e instalador.
- GitHub Actions que prueba la base de datos en MySQL 8.0 en cada Pull Request.
- Estructura del repositorio por capas: `frontend/`, `middleware/`, `database/`, `deploy/` y `docs/`.
- Plan de Gestión de Configuración en `docs/gestion/`.
- Plantillas de Pull Request y de solicitud de cambio.
- `CHANGELOG.md` y nuevo `README.md`.

### Cambiado
- Alcance (SC-05, #19): sin báscula ni impresora reales (HU-07b, HU-16b), sin timbrado en producción (HU-12b), sin prueba de desempeño (HU-19) ni manual (HU-20); la factura CFDI (HU-12a) se hace con un PAC simulado.
- El login responde con el mensaje del backlog: "Ingrese un usuario/contraseña correcta." (HU-04). Un usuario inactivo con la contraseña correcta recibe "Usuario inactivo, contacte al administrador."
- `sp_registrar_venta` recibe el parámetro `p_id_cliente_credito` después de `p_monto_recibido`.
- El prototipo anterior (middleware TCP y clientes Tkinter) se movió a `legacy/` como referencia.
- `.gitignore` ampliado para excluir secretos, respaldos y artefactos de empaquetado.

### Eliminado
- `Untitled4.ipynb`: análisis de regresión ajeno al proyecto.
