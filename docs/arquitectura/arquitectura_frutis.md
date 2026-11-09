# Documento de Arquitectura – Frutis ERP + POS

| | |
| --- | --- |
| **Proyecto** | ERP integrado con POS – Frutería Frutis |
| **Autor** | Edson Lujano |
| **Versión** | 1.1 (versión 1.0 del 26 de octubre de 2026, actualizada el 9 de noviembre de 2026) |
| **Repositorio** | [edluj/frutis](https://github.com/edluj/frutis) |

> **Cambios de la versión 1.1.** El contenido de la 1.0 se conserva. Se actualizó lo que cambió después: la base de datos pasó de 14 a 23 tablas por las solicitudes de cambio SC-01, SC-02 y SC-03; ya está instalada en el servidor (MySQL 8.0 sobre Rocky Linux), y el repositorio ya tiene la estructura por capas. Cada cambio está marcado con **(v1.1)**.

## Contenido

1. [Introducción](#1-introducción)
2. [Estado actual y brechas](#2-estado-actual-y-brechas)
3. [Vista general de la arquitectura](#3-vista-general-de-la-arquitectura)
4. [Stack tecnológico y decisiones](#4-stack-tecnológico-y-decisiones)
5. [Capa Frontend](#5-capa-frontend-aplicación-de-escritorio)
6. [Capa Middleware](#6-capa-middleware-seguridad-y-lógica-de-negocio)
7. [Capa Backend](#7-capa-backend-base-de-datos)
8. [Flujo del cobro POS](#8-flujo-del-cobro-pos)
9. [Seguridad, requisitos no funcionales y despliegue](#9-seguridad-requisitos-no-funcionales-y-despliegue)
10. [Estructura del repositorio y plan de migración](#10-estructura-del-repositorio-y-plan-de-migración)
11. [Riesgos y pendientes](#11-riesgos-y-pendientes)

---

## 1. Introducción

Frutis ERP + POS se construirá en Python con tres capas separadas: un cliente de escritorio PySide6, un middleware FastAPI en el servidor local y una base de datos MySQL 8. Este documento fija esas decisiones antes de la construcción, como pide la consideración de la cotización de validar la arquitectura con el cliente antes de codificar.

**Alcance.** Cubre los 6 módulos y 32 pantallas del APR, la base de datos (14 tablas cotizadas, hoy 23 **(v1.1)**), el Stored Procedure de cobro, la Función escalar, la capa de seguridad, los controladores de báscula e impresora y la integración CFDI. No cubre soporte posterior, migración de datos históricos ni tienda en línea.

**Referencias.**

- Cotización Frutis ERP, versión 1.0, 15 de octubre de 2026 (y versión 2.0 del 27 de octubre **(v1.1)**).
- APR – Análisis preliminar Frutis ERP (flujos A a V y puntos pendientes).
- Plan de Trabajo CMMI y Product Backlog del proyecto.
- Diccionario de datos Frutis v1.1 **(v1.1)**.
- Repositorio [edluj/frutis](https://github.com/edluj/frutis), commit a533909 (análisis inicial).

## 2. Estado actual y brechas

> **(v1.1)** Esta sección describe el repositorio al 26 de octubre. El código descrito ya se movió a `legacy/` y `Untitled4.ipynb` se eliminó.

El repositorio original era un prototipo funcional de seguridad, no una base para el ERP: guardaba todo en archivos de texto y mezclaba seguridad, negocio y persistencia en un solo archivo de 742 líneas.

| Archivo | Contenido | Qué se conserva |
| --- | --- | --- |
| `middleware.py` | Servidor TCP con TLS, protocolo de texto con `\|`, login PBKDF2, token en memoria de 1 h, límite de 5 intentos por IP, bitácora en `.txt` | Hash PBKDF2, límite de intentos, enmascarado de contraseñas en la bitácora, validación de campos |
| `admin_gui.py`, `supervisor_gui.py`, `empleado_gui.py` | Tres clientes Tkinter, uno por rol | Flujo de venta por unidad (kilos o unidades) como referencia funcional |
| `README.md`, `.gitignore` | Protocolo y variables de entorno | Exclusión de certificados y datos |
| `Untitled4.ipynb` | Regresión lineal sobre otro dataset | Nada: se elimina del repositorio |

**Brechas contra la cotización y el APR.**

- No hay MySQL, ni tablas, ni Stored Procedure, ni Función escalar. **(v1.1: resuelto en `database/`.)**
- La venta escribe stock y venta en dos archivos por separado: no es atómica (ACID). **(v1.1: resuelto con `sp_registrar_venta`.)**
- El servidor atiende una conexión a la vez; varias terminales POS se bloquean entre sí.
- Los clientes no validan el certificado del servidor (`CERT_NONE`).
- Los roles son admin, supervisor y empleado; el APR propone Administrador, Cajero, Compras y Contador.
- Hay tres ejecutables; el APR pide una sola aplicación con menú por rol.
- El README no refleja el quinto campo de VENTA e INVENTARIO ni los comandos LISTAR_PRODUCTOS y SET_PRODUCTO.

## 3. Vista general de la arquitectura

Las tres capas corren en la red local de la frutería: el frontend en cada terminal, el middleware y MySQL en el servidor, y solo el timbrado CFDI sale a internet.

```text
        TERMINAL POS (una o varias)                          SERVIDOR LOCAL
 ┌───────────────────────────────────────┐      ┌───────────────────────────────────────┐
 │  FRONTEND · PySide6                   │      │  MIDDLEWARE · FastAPI                 │
 │  32 pantallas, menú por rol           │HTTPS │  TLS → JWT → permisos → Pydantic      │
 │  api_client.py (token + certificado)  │─────►│  → servicios → repositorios           │
 │                                       │ LAN  │  → auditoría                          │
 │  Servicio de hardware (localhost)     │      │                 │ consultas           │
 │   ├─ báscula (serie/USB)              │      │                 │ parametrizadas      │
 │   ├─ impresora térmica (ESC/POS)      │      │                 ▼ y CALL sp_...       │
 │   └─ lector de códigos                │      │  BACKEND · MySQL 8 (InnoDB)           │
 └───────────────────────────────────────┘      │  tablas, sp_registrar_venta,          │
                                                │  fn_importe_peso, triggers            │
                                                └─────────────────┬─────────────────────┘
                                                                  │ HTTPS (única salida)
                                                                  ▼
                                                     Proveedor de timbrado CFDI (PAC)
```

El frontend nunca se conecta a MySQL: toda lectura o escritura pasa por el middleware, que valida token, permiso y datos antes de llegar a la base.

## 4. Stack tecnológico y decisiones

Todo el sistema usa Python 3.12, el lenguaje que el equipo ya domina, para que las tres capas compartan validaciones, modelos y herramientas.

| Capa | Tecnología | Versión objetivo | Uso |
| --- | --- | --- | --- |
| Frontend | PySide6 (Qt) | 6.x | Interfaz de escritorio táctil, 32 pantallas |
| Frontend | PyInstaller | 6.x | Empaquetado `.exe` (Windows) y binario (Linux) |
| Middleware | FastAPI + Uvicorn | estable | API REST sobre HTTPS en la LAN |
| Middleware | Pydantic | 2.x | Validación y sanitización de cada petición |
| Middleware | SQLAlchemy Core + PyMySQL | 2.x | Acceso a datos con consultas parametrizadas |
| Middleware | PyJWT + passlib | – | Tokens por rol y hash de contraseñas |
| Middleware | pyserial, python-escpos | – | Báscula (puerto serie/USB) e impresora térmica ESC/POS |
| Backend | MySQL | 8.0 (probado también en 8.4) **(v1.1)** | 23 tablas InnoDB, Stored Procedures, Función escalar y triggers **(v1.1)** |
| Backend | Rocky Linux | 10 **(v1.1)** | Sistema operativo del servidor local |
| Diseño | Lienzo de diseño UX/UI **(v1.1)** | – | 35 pantallas: las 32 del APR más login, menú y reportes |

**Decisiones de arquitectura (ADR).**

- **ADR-01 · PySide6 sobre JavaFX y WPF.** Licencia LGPL sin costo, soporte táctil y mismo lenguaje que el middleware. WPF solo corre en Windows y la cotización también pide Linux.
- **ADR-02 · FastAPI sobre Flask.** Valida con Pydantic de forma nativa, es asíncrono para varias terminales y genera documentación OpenAPI de la API.
- **ADR-03 · HTTPS/JSON reemplaza el protocolo de texto con `|`.** Elimina el parseo manual y su riesgo de inyección de campos.
- **ADR-04 · El frontend nunca habla con MySQL.** Toda petición pasa por el middleware, que valida el token y el permiso antes de tocar datos.
- **ADR-05 · El cobro vive en un Stored Procedure.** La venta, su detalle y el descuento de inventario ocurren en una transacción única con rollback.
- **ADR-06 · Una sola aplicación con menú por rol** en lugar de tres clientes separados.
- **ADR-07 · Reglas críticas también en la base (v1.1).** Que solo el Administrador autorice devoluciones y que la bitácora no se pueda modificar se garantizan con triggers, no solo en el middleware.

## 5. Capa Frontend (aplicación de escritorio)

El frontend es una sola aplicación PySide6 que solo presenta información y captura datos: no contiene reglas de negocio ni credenciales de base de datos.

**Responsabilidades.**

- Login con contraseña enmascarada, botón mostrar/ocultar y aviso de privacidad (flujo A).
- Menú principal que muestra solo los módulos que permite el rol del token (flujo B).
- 32 pantallas en 6 módulos, más una pantalla parametrizable de reportes.
- Guardar el token en memoria durante la sesión y borrarlo al cerrar sesión.
- Validación de forma en pantalla (campos obligatorios, formato de RFC y correo) para respuesta inmediata; la validación definitiva la hace el middleware.

**Organización interna.** Patrón MVP (Modelo–Vista–Presentador): las vistas Qt no llaman a la API directamente, lo hace un presentador por pantalla a través de un único cliente HTTP.

| Carpeta | Contenido |
| --- | --- |
| `frontend/app/views/` | Pantallas Qt por módulo: `pos/`, `compras/`, `facturacion/`, `finanzas/`, `inventario/`, `admin/` |
| `frontend/app/presenters/` | Lógica de pantalla: qué pedir a la API y cómo mostrarlo |
| `frontend/app/api_client.py` | Cliente HTTPS único: agrega el token, valida el certificado del servidor y maneja errores |
| `frontend/app/resources/` | Logotipo, colores y tipografías de la identidad de Frutis |

**POS táctil.** La pantalla de cobro usa botones de al menos 48 px, accesos rápidos a productos frecuentes y un flujo de 3 toques: agregar producto, elegir método de pago, cobrar.

**Identidad visual (v1.1).** Guinda `#7A1E28` como color principal, verde hoja `#4E7A44` para estados correctos y café coco `#9C5A33` para acentos; tipografías Fredoka (títulos) y Nunito Sans (texto), tomadas del logotipo de Frutis.

## 6. Capa Middleware (seguridad y lógica de negocio)

El middleware es la única puerta a los datos: una API FastAPI en el servidor local que autentica, autoriza, sanitiza, aplica las reglas de negocio y controla el hardware.

**Cadena de una petición.**

1. **TLS:** el cliente valida el certificado del servidor (fin de `CERT_NONE`).
2. **Autenticación:** el token JWT se verifica en cada petición; expira a los 60 minutos de inactividad.
3. **Autorización:** el rol del token se compara con la matriz de permisos ver/crear/editar/eliminar por módulo (flujo U).
4. **Sanitización:** Pydantic valida tipo, longitud y formato; el texto se limpia contra XSS antes de guardarse.
5. **Negocio:** el servicio del módulo aplica las reglas del APR.
6. **Datos:** consultas siempre parametrizadas o llamada al Stored Procedure, nunca SQL concatenado (contra SQLi).
7. **Auditoría:** usuario, fecha, módulo, acción, detalle e IP en la tabla de bitácora.

**Módulos internos.**

| Carpeta | Responsabilidad |
| --- | --- |
| `middleware/app/api/` | Rutas REST por módulo (`/auth`, `/pos`, `/compras`, `/facturacion`, `/finanzas`, `/inventario`, `/admin`, `/reportes`) |
| `middleware/app/security/` | JWT, hash de contraseñas, matriz de permisos, límite de 5 intentos fallidos |
| `middleware/app/schemas/` | Modelos Pydantic de entrada y salida |
| `middleware/app/services/` | Reglas de negocio por módulo |
| `middleware/app/repositories/` | Acceso a MySQL y llamadas a los Stored Procedures |
| `middleware/app/hardware/` | Lectura de báscula, impresión de tickets, apertura de cajón |
| `middleware/app/integrations/cfdi.py` | Cliente de la API de timbrado del proveedor externo |

**Conexión a la base (v1.1).** El middleware se conecta con el usuario `frutis_app` (SELECT, INSERT, UPDATE y EXECUTE sobre `frutis`, más DELETE solo en `permisos`). Las credenciales viven en el `.env` del servidor (plantilla en `deploy/.env.example`), nunca en el repositorio.

**Hardware.** La báscula y la impresora se conectan a cada terminal POS, no al servidor. Por eso el controlador de hardware corre como un servicio local ligero en cada terminal, con la misma base de código, y el frontend lo consulta en `localhost`. El modelo exacto de cada equipo sigue pendiente (APR, punto 7); mientras tanto se desarrolla con simulador detrás de una interfaz común **(v1.1)**.

**CFDI.** El timbrado es la única salida a internet. Si no hay conexión, la factura queda como borrador y se reintenta.

## 7. Capa Backend (base de datos)

El backend es una base MySQL 8 con motor InnoDB, con llaves foráneas en todas las relaciones y la lógica del cobro dentro de la base.

**(v1.1) Instalada** el 4 de noviembre de 2026 en el servidor Rocky Linux con MySQL 8.0, con las 50 pruebas automáticas en verde. Se instala con `database/instalar.sh`; el detalle de cada tabla está en el diccionario de datos v1.1.

**Tablas de la cotización por módulo (14).**

| Módulo | Tablas |
| --- | --- |
| Administración | `usuarios` |
| Proveedores y Compras | `proveedores`, `lotes_compras`, `cuentas_por_pagar` |
| Catálogo e Inventario | `categorias`, `productos`, `inventario`, `mermas` |
| Punto de Venta | `cajas_pos`, `ventas_cabecera`, `ventas_detalle`, `metodos_pago` |
| Facturación | `facturas_cfdi` |
| Finanzas | `gastos_operativos` |

**Tablas de soporte que piden los flujos del APR (6).** Se propusieron como cambio de alcance menor. **(v1.1)** El cliente las aprobó sin costo adicional (SC-01).

| Tabla | Flujo que la necesita |
| --- | --- |
| `roles`, `permisos` | U – Roles y permisos |
| `auditoria` | V – Bitácora de movimientos |
| `clientes_fiscales` | K – Datos fiscales de clientes |
| `devoluciones` | E – Devoluciones |
| `historial_precios` | Q – Ajuste de precios |

**(v1.1) Tablas de venta a crédito (3).** El cliente confirmó que habrá venta a crédito, sin costo adicional (SC-03).

| Tabla | Uso |
| --- | --- |
| `clientes_credito` | Clientes con límite de crédito y días de plazo |
| `cuentas_por_cobrar` | Una cuenta por cada venta a crédito, con saldo y vencimiento |
| `cobros_clientes` | Pagos que hace el cliente a sus cuentas |

**Stored Procedure `sp_registrar_venta`.** Recibe la caja, el cajero, el método de pago, el monto recibido, el cliente de crédito (si aplica) **(v1.1)** y el carrito en JSON. Dentro de una transacción:

1. Bloquea las filas de inventario de los productos del carrito (`SELECT … FOR UPDATE`).
2. Verifica existencia suficiente; si falta, hace `ROLLBACK` y devuelve el error.
3. Si la venta es a crédito, verifica el límite del cliente y crea la cuenta por cobrar **(v1.1)**.
4. Inserta `ventas_cabecera` y una fila de `ventas_detalle` por producto.
5. Descuenta inventario por lote, primero el que caduca antes (FEFO).
6. Hace `COMMIT` y devuelve folio, total y cambio.

**(v1.1) Stored Procedure `sp_registrar_cobro`.** Registra un pago a una cuenta por cobrar, actualiza su saldo y rechaza cobros mayores al saldo.

**Función escalar `fn_importe_peso(producto_id, peso_kg)`.** Devuelve el importe redondeado a 2 decimales: peso × precio por kg vigente. La usan el Stored Procedure y los reportes, así el cálculo existe en un solo lugar.

**(v1.1) Vistas y triggers.**

- Vistas `v_existencias`, `v_cuentas_por_pagar` y `v_cuentas_por_cobrar`.
- Triggers `trg_devoluciones_autoriza_alta` y `trg_devoluciones_autoriza_cambio`: solo un Administrador activo puede autorizar devoluciones (SC-02).
- Triggers `trg_auditoria_sin_cambios` y `trg_auditoria_sin_borrado`: la bitácora es de solo lectura.

**Convenciones.** Dinero en `DECIMAL(12,2)`, peso en `DECIMAL(10,3)`, precios con IVA incluido **(v1.1)**, bajas lógicas con columna `activo`, y `creado_en` / `actualizado_en` en todas las tablas.

## 8. Flujo del cobro POS

Un cobro cruza las tres capas en 9 pasos, y la venta, su detalle y el descuento de inventario ocurren en una sola transacción dentro de MySQL.

```text
 Frontend (PySide6)          Servicio de hardware        Middleware (FastAPI)          MySQL
        │                            │                            │                        │
 1. Escanea o toca producto ─────────────────────────────────────►│ GET /pos/productos     │
        │◄──────────────────────────────────────────── precio ────│◄── consulta ───────────│
 2. Pide el peso ───────────────────►│                            │                        │
        │◄────────────── peso (kg) ──│                            │                        │
 3. Calcula importe y total en pantalla                           │                        │
 4. Elige método de pago y monto recibido                         │                        │
 5. POST /pos/ventas ────────────────────────────────────────────►│ valida token, rol      │
        │                            │                            │ y datos (Pydantic)     │
        │                            │                 6. CALL sp_registrar_venta ────────►│ BEGIN … COMMIT
        │                            │                            │◄─ folio, total, cambio ┤ (una transacción)
 7. Recibe folio y cambio ◄───────────────────────────────────────│ 7. registra auditoría  │
 8. Imprime ticket ─────────────────►│ ESC/POS                    │                        │
 9. Limpia la pantalla para la siguiente venta                    │                        │
```

Si falta existencia o falla cualquier parte del paso 6, la base hace `ROLLBACK`: no queda venta parcial y el frontend muestra *"No se pudo registrar la venta, intente de nuevo."* (flujo C del APR).

## 9. Seguridad, requisitos no funcionales y despliegue

Cada requisito no funcional de la cotización tiene un mecanismo concreto en la arquitectura y una forma de probarlo.

| Requisito | Mecanismo | Cómo se verifica |
| --- | --- | --- |
| Cobro en máximo 3 toques | Accesos rápidos y botón de pago directo en la pantalla POS | Prueba de usabilidad con un cajero |
| Consulta de precio y cobro en menos de 1 s | Índices en código de barras, conexión persistente a MySQL, todo en la LAN | Prueba de carga con tiempos medidos en el middleware |
| Integridad ACID | Stored Procedure con transacción y llaves foráneas InnoDB | Prueba de corte de red a mitad del cobro: no debe quedar venta parcial |
| Autenticación por rol | JWT con rol, matriz de permisos validada en cada petición | Pruebas de acceso con cada rol a cada ruta |
| Protección SQLi / XSS | Pydantic, consultas parametrizadas, limpieza de texto | Pruebas con cargas maliciosas conocidas |
| Contraseñas | Hash con sal (bcrypt o el PBKDF2 actual); nunca en texto plano | Revisión de la tabla `usuarios` |
| Aviso de privacidad | Botón en el login con el texto legal vigente | Revisión funcional |

> **(v1.1)** Los casos de prueba de cada requisito están en la *Matriz de pruebas – Frutis ERP* (167 casos, 35 pantallas).

**Despliegue en la frutería.**

- **Servidor local** (multinúcleo, 16 GB RAM, SSD): MySQL 8 y el middleware como servicio del sistema, escuchando solo en la red privada.
- **Terminales POS:** el ejecutable PySide6 y el servicio de hardware local, conectados a la báscula, impresora y lector.
- **Red LAN privada:** el puerto del middleware (y el 3306 de MySQL, con regla de firewalld) solo acepta IPs de la red interna **(v1.1)**.
- **Internet:** solo desde el servidor y solo hacia el proveedor de timbrado CFDI.
- **Respaldos:** `mysqldump` diario del servidor a un disco externo, con el usuario `frutis_respaldo` **(v1.1)**.

**Certificados.** El servidor usa un certificado propio generado durante la instalación; cada terminal lleva la autoridad certificadora local para validarlo.

## 10. Estructura del repositorio y plan de migración

El repositorio se reorganiza en una carpeta por capa; el código anterior pasa a `legacy/` como referencia y no se despliega.

```text
frutis/
├── frontend/            # App PySide6
│   ├── app/{views,presenters,resources}/
│   ├── app/api_client.py
│   └── frutis.spec      # PyInstaller
├── middleware/          # API FastAPI
│   ├── app/{api,security,schemas,services,repositories,hardware,integrations}/
│   ├── tests/
│   └── requirements.txt
├── database/
│   ├── schema.sql       # Tablas, índices, llaves foráneas, vistas y triggers
│   ├── procedures/      # sp_registrar_venta.sql, sp_registrar_cobro.sql
│   ├── functions/fn_importe_peso.sql
│   ├── seed.sql         # Datos de prueba
│   ├── tests/           # 50 pruebas automáticas
│   └── instalar.sh
├── deploy/              # .env.example e instalador del servidor Rocky Linux
├── docs/                # gestion/, requisitos/, arquitectura/, diseno/, pruebas/, entrega/
├── legacy/              # middleware.py y clientes Tkinter anteriores
└── README.md
```

**Pasos de migración.**

- [x] Mover `middleware.py` y los tres `*_gui.py` a `legacy/`; eliminar `Untitled4.ipynb`. **(v1.1)**
- [x] Crear `database/` con `schema.sql`, los Stored Procedures y la Función; probarlos con `seed.sql`. **(v1.1)**
- [ ] Crear el esqueleto de FastAPI con `/auth` y `/pos`, reutilizando el hash y el límite de intentos del código anterior.
- [ ] Crear el esqueleto de PySide6 con login, menú por rol y pantalla de cobro.
- [ ] Prueba de humo de extremo a extremo: login → venta → ticket.
- [ ] Actualizar el README con la nueva instalación y ejecución.

**Flujo de trabajo en Git.** Ramas `main` y `develop` protegidas; una rama por historia del backlog (`feature/HU-xx-<nombre>`), Pull Request hacia `develop` con la integración continua en verde, y paso de `develop` a `main` solo en un release. El detalle está en el Plan de Gestión de Configuración **(v1.1)**.

## 11. Riesgos y pendientes

El mayor riesgo técnico es el hardware: sin los modelos de báscula e impresora no se pueden escribir ni probar sus controladores.

| Riesgo | Impacto | Mitigación |
| --- | --- | --- |
| Modelos de báscula, impresora y lector desconocidos | Retrasa los controladores y las pruebas integrales | Pedir los modelos por escrito; simulador de báscula e impresora para desarrollar mientras tanto |
| ~~Tablas de soporte fuera de las 14 cotizadas~~ | ~~Cambio de alcance~~ | **(v1.1) Cerrado:** aprobadas sin costo (SC-01) |
| Número de terminales POS sin definir | Dimensionamiento y pruebas de concurrencia | Diseñar para varias terminales desde el inicio; confirmar el número |
| Proveedor de timbrado CFDI sin elegir | Bloquea el módulo de facturación | Elegir proveedor con entorno de pruebas antes de la construcción de Facturación |
| CSD del cliente sin entregar **(v1.1)** | Bloquea el timbrado en producción | Pedirlo antes del 16 de noviembre; desarrollar contra el ambiente de pruebas del PAC |
| Requisito de menos de 1 s | Rechazo en la aceptación | Medir tiempos desde el primer prototipo del cobro |

**Pendientes por confirmar con el cliente.**

- [ ] Modelos de báscula, impresora térmica y lector de códigos.
- [ ] Número de terminales POS y si habrá más de una sucursal.
- [x] Visto bueno a las tablas de soporte adicionales. **(v1.1: SC-01)**
- [ ] Roles definitivos y matriz de permisos. **(v1.1: ya se decidió que solo el Administrador autoriza devoluciones, SC-02)**
- [ ] Proveedor de timbrado CFDI.
- [ ] Si la caja tiene cajón de dinero que deba abrirse al cobrar.
