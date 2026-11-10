# Historial de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Versionado semántico según el Plan de Gestión de Configuración (sección 6).

## [Sin publicar]

### Agregado
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
