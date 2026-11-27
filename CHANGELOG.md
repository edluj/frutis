# Historial de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Versionado semántico según el Plan de Gestión de Configuración (sección 6).

## [Sin publicar]

### Agregado
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
- El login responde con el mensaje del backlog: "Ingrese un usuario/contraseña correcta." (HU-04). Un usuario inactivo con la contraseña correcta recibe "Usuario inactivo, contacte al administrador."
- `sp_registrar_venta` recibe el parámetro `p_id_cliente_credito` después de `p_monto_recibido`.
- El prototipo anterior (middleware TCP y clientes Tkinter) se movió a `legacy/` como referencia.
- `.gitignore` ampliado para excluir secretos, respaldos y artefactos de empaquetado.

### Eliminado
- `Untitled4.ipynb`: análisis de regresión ajeno al proyecto.
