-- =============================================================================
-- Frutis ERP + POS · Esquema de base de datos (EC-08)
-- MySQL 8.0 (>= 8.0.16) · InnoDB · utf8mb4
--
-- 23 tablas:
--   * 14 de la cotización.
--   * 6 de soporte aprobadas en SC-01 (#2), sin costo adicional:
--     roles, permisos, auditoria, clientes_fiscales, devoluciones, historial_precios.
--   * 3 de venta a crédito aprobadas en SC-03 (#4):
--     clientes_credito, cuentas_por_cobrar, cobros_clientes.
--
-- Convenciones:
--   * Nombres de tablas y columnas en minúsculas con guion bajo, para que el
--     esquema funcione igual en Windows y Linux (lower_case_table_names).
--   * Dinero DECIMAL(12,2); peso o cantidad DECIMAL(10,3).
--   * Bajas lógicas con la columna `activo`; nunca se borran catálogos con historia.
--   * Todas las tablas llevan `creado_en` y, si se editan, `actualizado_en`.
--
-- Orden de instalación: schema.sql -> functions/ -> procedures/ -> seed.sql (solo desarrollo).
-- =============================================================================

CREATE DATABASE IF NOT EXISTS frutis
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

USE frutis;

-- -----------------------------------------------------------------------------
-- Administración y seguridad (flujos A, T, U, V)
-- -----------------------------------------------------------------------------

-- Soporte SC-01 · Flujo U
CREATE TABLE roles (
  id_rol          TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
  nombre          VARCHAR(40)      NOT NULL,
  descripcion     VARCHAR(200)     NULL,
  es_sistema      BOOLEAN          NOT NULL DEFAULT FALSE COMMENT 'TRUE = no se edita ni se elimina (Administrador)',
  activo          BOOLEAN          NOT NULL DEFAULT TRUE,
  creado_en       DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en  DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT pk_roles PRIMARY KEY (id_rol),
  CONSTRAINT uq_roles_nombre UNIQUE (nombre)
) ENGINE=InnoDB COMMENT='Roles del sistema (soporte SC-01)';

-- Soporte SC-01 · Flujo U
CREATE TABLE permisos (
  id_permiso      SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  id_rol          TINYINT UNSIGNED  NOT NULL,
  modulo          ENUM('pos','compras','facturacion','finanzas','inventario','reportes','admin') NOT NULL,
  puede_ver       BOOLEAN NOT NULL DEFAULT FALSE,
  puede_crear     BOOLEAN NOT NULL DEFAULT FALSE,
  puede_editar    BOOLEAN NOT NULL DEFAULT FALSE,
  puede_eliminar  BOOLEAN NOT NULL DEFAULT FALSE,
  actualizado_en  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT pk_permisos PRIMARY KEY (id_permiso),
  CONSTRAINT uq_permisos_rol_modulo UNIQUE (id_rol, modulo),
  CONSTRAINT fk_permisos_rol FOREIGN KEY (id_rol) REFERENCES roles (id_rol) ON DELETE CASCADE
) ENGINE=InnoDB COMMENT='Matriz ver/crear/editar/eliminar por rol y módulo (soporte SC-01)';

-- Cotización · Flujos A y T
CREATE TABLE usuarios (
  id_usuario         INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  nombre_completo    VARCHAR(150)     NOT NULL,
  usuario            VARCHAR(50)      NOT NULL,
  correo             VARCHAR(120)     NOT NULL,
  password_hash      VARCHAR(255)     NOT NULL COMMENT 'Hash con sal; nunca texto plano',
  id_rol             TINYINT UNSIGNED NOT NULL,
  activo             BOOLEAN          NOT NULL DEFAULT TRUE,
  intentos_fallidos  TINYINT UNSIGNED NOT NULL DEFAULT 0,
  bloqueado_hasta    DATETIME         NULL,
  ultimo_acceso      DATETIME         NULL,
  creado_en          DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en     DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT pk_usuarios PRIMARY KEY (id_usuario),
  CONSTRAINT uq_usuarios_usuario UNIQUE (usuario),
  CONSTRAINT fk_usuarios_rol FOREIGN KEY (id_rol) REFERENCES roles (id_rol),
  CONSTRAINT ck_usuarios_correo CHECK (correo REGEXP '^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$')
) ENGINE=InnoDB COMMENT='Usuarios del sistema';

-- Soporte SC-01 · Flujo V
CREATE TABLE auditoria (
  id_auditoria  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  fecha         DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  id_usuario    INT UNSIGNED    NULL,
  usuario       VARCHAR(50)     NULL COMMENT 'Copia del nombre de usuario; también para intentos con usuario inexistente',
  modulo        VARCHAR(30)     NOT NULL,
  accion        VARCHAR(40)     NOT NULL,
  detalle       VARCHAR(1000)   NULL,
  ip            VARCHAR(45)     NULL,
  CONSTRAINT pk_auditoria PRIMARY KEY (id_auditoria),
  CONSTRAINT fk_auditoria_usuario FOREIGN KEY (id_usuario) REFERENCES usuarios (id_usuario),
  INDEX idx_auditoria_fecha (fecha),
  INDEX idx_auditoria_usuario (id_usuario, fecha),
  INDEX idx_auditoria_modulo (modulo, accion, fecha)
) ENGINE=InnoDB COMMENT='Bitácora de solo lectura (soporte SC-01)';

-- -----------------------------------------------------------------------------
-- Proveedores y compras (flujos F, G, H)
-- -----------------------------------------------------------------------------

-- Cotización · Flujo F
CREATE TABLE proveedores (
  id_proveedor    INT UNSIGNED      NOT NULL AUTO_INCREMENT,
  razon_social    VARCHAR(200)      NOT NULL,
  rfc             VARCHAR(13)       NOT NULL,
  telefono        VARCHAR(20)       NOT NULL,
  correo          VARCHAR(120)      NULL,
  dias_credito    SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  activo          BOOLEAN           NOT NULL DEFAULT TRUE,
  creado_en       DATETIME          NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en  DATETIME          NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT pk_proveedores PRIMARY KEY (id_proveedor),
  CONSTRAINT uq_proveedores_rfc UNIQUE (rfc),
  CONSTRAINT ck_proveedores_rfc CHECK (CHAR_LENGTH(rfc) IN (12, 13)),
  INDEX idx_proveedores_razon (razon_social)
) ENGINE=InnoDB COMMENT='Proveedores';

-- -----------------------------------------------------------------------------
-- Catálogo e inventario (flujos O, P, Q, R)
-- -----------------------------------------------------------------------------

-- Cotización · Flujo O
CREATE TABLE categorias (
  id_categoria    SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  nombre          VARCHAR(60)       NOT NULL,
  descripcion     VARCHAR(200)      NULL,
  activo          BOOLEAN           NOT NULL DEFAULT TRUE,
  creado_en       DATETIME          NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en  DATETIME          NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT pk_categorias PRIMARY KEY (id_categoria),
  CONSTRAINT uq_categorias_nombre UNIQUE (nombre)
) ENGINE=InnoDB COMMENT='Categorías de productos';

-- Cotización · Flujo P
CREATE TABLE productos (
  id_producto     INT UNSIGNED      NOT NULL AUTO_INCREMENT,
  codigo_barras   VARCHAR(32)       NOT NULL COMMENT 'Código impreso o interno para producto a granel',
  nombre          VARCHAR(120)      NOT NULL,
  id_categoria    SMALLINT UNSIGNED NOT NULL,
  unidad_venta    ENUM('kg','pieza') NOT NULL,
  precio_venta    DECIMAL(12,2)     NOT NULL COMMENT 'Precio por kg o por pieza, IVA incluido',
  costo_actual    DECIMAL(12,2)     NOT NULL DEFAULT 0.00 COMMENT 'Último costo de compra',
  tasa_iva        DECIMAL(5,4)      NOT NULL DEFAULT 0.0000,
  stock_minimo    DECIMAL(10,3)     NOT NULL DEFAULT 0.000,
  es_frecuente    BOOLEAN           NOT NULL DEFAULT FALSE COMMENT 'Aparece en los accesos rápidos del POS',
  activo          BOOLEAN           NOT NULL DEFAULT TRUE,
  creado_en       DATETIME          NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en  DATETIME          NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT pk_productos PRIMARY KEY (id_producto),
  CONSTRAINT uq_productos_codigo UNIQUE (codigo_barras),
  CONSTRAINT fk_productos_categoria FOREIGN KEY (id_categoria) REFERENCES categorias (id_categoria),
  CONSTRAINT ck_productos_precio CHECK (precio_venta > 0),
  CONSTRAINT ck_productos_costo CHECK (costo_actual >= 0),
  CONSTRAINT ck_productos_iva CHECK (tasa_iva IN (0.0000, 0.1600)),
  CONSTRAINT ck_productos_minimo CHECK (stock_minimo >= 0),
  INDEX idx_productos_nombre (nombre),
  INDEX idx_productos_categoria (id_categoria)
) ENGINE=InnoDB COMMENT='Catálogo de productos';

-- Soporte SC-01 · Flujo Q
CREATE TABLE historial_precios (
  id_historial     BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  id_producto      INT UNSIGNED    NOT NULL,
  precio_anterior  DECIMAL(12,2)   NOT NULL,
  precio_nuevo     DECIMAL(12,2)   NOT NULL,
  id_usuario       INT UNSIGNED    NOT NULL,
  motivo           VARCHAR(200)    NULL,
  fecha            DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT pk_historial_precios PRIMARY KEY (id_historial),
  CONSTRAINT fk_historial_producto FOREIGN KEY (id_producto) REFERENCES productos (id_producto),
  CONSTRAINT fk_historial_usuario FOREIGN KEY (id_usuario) REFERENCES usuarios (id_usuario),
  CONSTRAINT ck_historial_precio CHECK (precio_nuevo > 0),
  INDEX idx_historial_producto (id_producto, fecha)
) ENGINE=InnoDB COMMENT='Historial de cambios de precio (soporte SC-01)';

-- Cotización · Flujo G (cabecera del lote de compra)
CREATE TABLE lotes_compras (
  id_lote         INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  folio           VARCHAR(20)   NOT NULL,
  id_proveedor    INT UNSIGNED  NOT NULL,
  id_usuario      INT UNSIGNED  NOT NULL,
  fecha_entrada   DATE          NOT NULL,
  condicion_pago  ENUM('contado','credito') NOT NULL,
  total           DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  observaciones   VARCHAR(255)  NULL,
  creado_en       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT pk_lotes_compras PRIMARY KEY (id_lote),
  CONSTRAINT uq_lotes_folio UNIQUE (folio),
  CONSTRAINT fk_lotes_proveedor FOREIGN KEY (id_proveedor) REFERENCES proveedores (id_proveedor),
  CONSTRAINT fk_lotes_usuario FOREIGN KEY (id_usuario) REFERENCES usuarios (id_usuario),
  CONSTRAINT ck_lotes_total CHECK (total >= 0),
  INDEX idx_lotes_fecha (fecha_entrada)
) ENGINE=InnoDB COMMENT='Lotes de compra a proveedores';

-- Cotización · Flujos G y P (detalle del lote = existencia por lote)
CREATE TABLE inventario (
  id_inventario        INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  id_lote              INT UNSIGNED  NOT NULL,
  id_producto          INT UNSIGNED  NOT NULL,
  cantidad_inicial     DECIMAL(10,3) NOT NULL,
  cantidad_disponible  DECIMAL(10,3) NOT NULL,
  costo_unitario       DECIMAL(12,2) NOT NULL,
  fecha_caducidad      DATE          NOT NULL,
  creado_en            DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT pk_inventario PRIMARY KEY (id_inventario),
  CONSTRAINT uq_inventario_lote_producto UNIQUE (id_lote, id_producto),
  CONSTRAINT fk_inventario_lote FOREIGN KEY (id_lote) REFERENCES lotes_compras (id_lote),
  CONSTRAINT fk_inventario_producto FOREIGN KEY (id_producto) REFERENCES productos (id_producto),
  CONSTRAINT ck_inventario_inicial CHECK (cantidad_inicial > 0),
  CONSTRAINT ck_inventario_disponible CHECK (cantidad_disponible >= 0 AND cantidad_disponible <= cantidad_inicial),
  CONSTRAINT ck_inventario_costo CHECK (costo_unitario > 0),
  INDEX idx_inventario_fefo (id_producto, fecha_caducidad, id_inventario)
) ENGINE=InnoDB COMMENT='Existencia por lote y producto; la existencia total se calcula, no se captura';

-- Cotización · Flujo R
CREATE TABLE mermas (
  id_merma       INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  id_inventario  INT UNSIGNED  NOT NULL,
  cantidad       DECIMAL(10,3) NOT NULL,
  motivo         ENUM('maduracion','golpe','caducidad','devolucion','otro') NOT NULL,
  costo_total    DECIMAL(12,2) NOT NULL COMMENT 'cantidad x costo del lote',
  observaciones  VARCHAR(255)  NULL,
  id_usuario     INT UNSIGNED  NOT NULL,
  fecha          DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT pk_mermas PRIMARY KEY (id_merma),
  CONSTRAINT fk_mermas_inventario FOREIGN KEY (id_inventario) REFERENCES inventario (id_inventario),
  CONSTRAINT fk_mermas_usuario FOREIGN KEY (id_usuario) REFERENCES usuarios (id_usuario),
  CONSTRAINT ck_mermas_cantidad CHECK (cantidad > 0),
  CONSTRAINT ck_mermas_costo CHECK (costo_total >= 0),
  INDEX idx_mermas_fecha (fecha)
) ENGINE=InnoDB COMMENT='Pérdidas de producto por lote';

-- Cotización · Flujo H
CREATE TABLE cuentas_por_pagar (
  id_cxp             INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  id_lote            INT UNSIGNED  NOT NULL,
  monto_total        DECIMAL(12,2) NOT NULL,
  saldo              DECIMAL(12,2) NOT NULL,
  fecha_vencimiento  DATE          NOT NULL COMMENT 'fecha de entrada + días de crédito del proveedor',
  estatus            ENUM('pendiente','pagada') NOT NULL DEFAULT 'pendiente' COMMENT 'Vencida se calcula en v_cuentas_por_pagar',
  creado_en          DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT pk_cuentas_por_pagar PRIMARY KEY (id_cxp),
  CONSTRAINT uq_cxp_lote UNIQUE (id_lote),
  CONSTRAINT fk_cxp_lote FOREIGN KEY (id_lote) REFERENCES lotes_compras (id_lote),
  CONSTRAINT ck_cxp_monto CHECK (monto_total > 0),
  CONSTRAINT ck_cxp_saldo CHECK (saldo >= 0 AND saldo <= monto_total),
  CONSTRAINT ck_cxp_estatus CHECK ((estatus = 'pagada') = (saldo = 0)),
  INDEX idx_cxp_vencimiento (estatus, fecha_vencimiento)
) ENGINE=InnoDB COMMENT='Adeudos con proveedores por lote a crédito';

-- -----------------------------------------------------------------------------
-- Punto de venta (flujos C, D, E)
-- -----------------------------------------------------------------------------

-- Cotización · Flujo C
CREATE TABLE metodos_pago (
  id_metodo    TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
  nombre       VARCHAR(40)      NOT NULL,
  clave_sat    CHAR(2)          NOT NULL COMMENT 'Forma de pago del catálogo c_FormaPago del SAT',
  es_efectivo  BOOLEAN          NOT NULL DEFAULT FALSE COMMENT 'TRUE = exige monto recibido y calcula cambio',
  es_credito   BOOLEAN          NOT NULL DEFAULT FALSE COMMENT 'TRUE = venta a crédito; genera una cuenta por cobrar (SC-03)',
  activo       BOOLEAN          NOT NULL DEFAULT TRUE,
  CONSTRAINT pk_metodos_pago PRIMARY KEY (id_metodo),
  CONSTRAINT uq_metodos_nombre UNIQUE (nombre),
  CONSTRAINT ck_metodos_tipo CHECK (NOT (es_efectivo AND es_credito))
) ENGINE=InnoDB COMMENT='Métodos de pago';

-- Cotización · Flujo D (una fila por turno de caja)
CREATE TABLE cajas_pos (
  id_caja            INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  terminal           VARCHAR(30)   NOT NULL,
  id_usuario         INT UNSIGNED  NOT NULL COMMENT 'Cajero del turno',
  fondo_inicial      DECIMAL(12,2) NOT NULL,
  fecha_apertura     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  fecha_cierre       DATETIME      NULL,
  efectivo_esperado  DECIMAL(12,2) NULL COMMENT 'fondo + ventas en efectivo + cobros en efectivo - devoluciones en efectivo',
  efectivo_contado   DECIMAL(12,2) NULL,
  diferencia         DECIMAL(12,2) NULL COMMENT 'contado - esperado',
  observaciones      VARCHAR(255)  NULL,
  estatus            ENUM('abierta','cerrada') NOT NULL DEFAULT 'abierta',
  terminal_abierta   VARCHAR(30) GENERATED ALWAYS AS (IF(estatus = 'abierta', terminal, NULL)) STORED,
  CONSTRAINT pk_cajas_pos PRIMARY KEY (id_caja),
  CONSTRAINT uq_cajas_terminal_abierta UNIQUE (terminal_abierta),
  CONSTRAINT fk_cajas_usuario FOREIGN KEY (id_usuario) REFERENCES usuarios (id_usuario),
  CONSTRAINT ck_cajas_fondo CHECK (fondo_inicial >= 0),
  CONSTRAINT ck_cajas_cierre CHECK (estatus = 'abierta' OR (fecha_cierre IS NOT NULL AND efectivo_contado IS NOT NULL)),
  CONSTRAINT ck_cajas_observaciones CHECK (diferencia IS NULL OR diferencia = 0 OR COALESCE(CHAR_LENGTH(TRIM(observaciones)), 0) > 0),
  INDEX idx_cajas_apertura (fecha_apertura)
) ENGINE=InnoDB COMMENT='Turnos de caja: apertura, arqueo y cierre';

-- Cotización · Flujo C
CREATE TABLE ventas_cabecera (
  id_venta        INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  folio           VARCHAR(20)      NULL COMMENT 'V00000001; lo asigna sp_registrar_venta',
  id_caja         INT UNSIGNED     NOT NULL,
  id_usuario      INT UNSIGNED     NOT NULL,
  id_metodo       TINYINT UNSIGNED NOT NULL,
  subtotal        DECIMAL(12,2)    NOT NULL DEFAULT 0.00,
  iva             DECIMAL(12,2)    NOT NULL DEFAULT 0.00,
  total           DECIMAL(12,2)    NOT NULL DEFAULT 0.00,
  monto_recibido  DECIMAL(12,2)    NOT NULL DEFAULT 0.00,
  cambio          DECIMAL(12,2)    NOT NULL DEFAULT 0.00,
  estatus         ENUM('pagada','devuelta_parcial','devuelta','cancelada') NOT NULL DEFAULT 'pagada',
  fecha           DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT pk_ventas_cabecera PRIMARY KEY (id_venta),
  CONSTRAINT uq_ventas_folio UNIQUE (folio),
  CONSTRAINT fk_ventas_caja FOREIGN KEY (id_caja) REFERENCES cajas_pos (id_caja),
  CONSTRAINT fk_ventas_usuario FOREIGN KEY (id_usuario) REFERENCES usuarios (id_usuario),
  CONSTRAINT fk_ventas_metodo FOREIGN KEY (id_metodo) REFERENCES metodos_pago (id_metodo),
  CONSTRAINT ck_ventas_montos CHECK (subtotal >= 0 AND iva >= 0 AND total = subtotal + iva),
  CONSTRAINT ck_ventas_recibido CHECK (monto_recibido >= total AND cambio = monto_recibido - total),
  INDEX idx_ventas_fecha (fecha),
  INDEX idx_ventas_caja (id_caja)
) ENGINE=InnoDB COMMENT='Ticket de venta';

-- Cotización · Flujo C (una fila por producto y lote descontado)
CREATE TABLE ventas_detalle (
  id_detalle       BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  id_venta         INT UNSIGNED    NOT NULL,
  id_producto      INT UNSIGNED    NOT NULL,
  id_inventario    INT UNSIGNED    NOT NULL COMMENT 'Lote del que salió la mercancía',
  cantidad         DECIMAL(10,3)   NOT NULL,
  precio_unitario  DECIMAL(12,2)   NOT NULL COMMENT 'Precio vigente al cobrar, IVA incluido',
  importe          DECIMAL(12,2)   NOT NULL,
  tasa_iva         DECIMAL(5,4)    NOT NULL,
  costo_unitario   DECIMAL(12,2)   NOT NULL COMMENT 'Costo del lote; base de la utilidad real',
  CONSTRAINT pk_ventas_detalle PRIMARY KEY (id_detalle),
  CONSTRAINT fk_detalle_venta FOREIGN KEY (id_venta) REFERENCES ventas_cabecera (id_venta),
  CONSTRAINT fk_detalle_producto FOREIGN KEY (id_producto) REFERENCES productos (id_producto),
  CONSTRAINT fk_detalle_inventario FOREIGN KEY (id_inventario) REFERENCES inventario (id_inventario),
  CONSTRAINT ck_detalle_cantidad CHECK (cantidad > 0),
  CONSTRAINT ck_detalle_importe CHECK (importe >= 0),
  INDEX idx_detalle_venta (id_venta),
  INDEX idx_detalle_producto (id_producto)
) ENGINE=InnoDB COMMENT='Renglones del ticket';

-- Soporte SC-01 · Flujo E (una fila por renglón devuelto; `folio` agrupa la devolución)
CREATE TABLE devoluciones (
  id_devolucion    INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  folio            VARCHAR(20)     NOT NULL,
  id_venta         INT UNSIGNED    NOT NULL,
  id_detalle       BIGINT UNSIGNED NOT NULL,
  id_caja          INT UNSIGNED    NOT NULL COMMENT 'Caja donde se entregó el reembolso',
  cantidad         DECIMAL(10,3)   NOT NULL,
  importe          DECIMAL(12,2)   NOT NULL,
  motivo           VARCHAR(200)    NOT NULL,
  estado_producto  ENUM('bueno','danado') NOT NULL COMMENT 'bueno = regresa al inventario; danado = merma',
  id_usuario       INT UNSIGNED    NOT NULL,
  id_autoriza      INT UNSIGNED    NOT NULL,
  fecha            DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT pk_devoluciones PRIMARY KEY (id_devolucion),
  CONSTRAINT fk_devoluciones_venta FOREIGN KEY (id_venta) REFERENCES ventas_cabecera (id_venta),
  CONSTRAINT fk_devoluciones_detalle FOREIGN KEY (id_detalle) REFERENCES ventas_detalle (id_detalle),
  CONSTRAINT fk_devoluciones_caja FOREIGN KEY (id_caja) REFERENCES cajas_pos (id_caja),
  CONSTRAINT fk_devoluciones_usuario FOREIGN KEY (id_usuario) REFERENCES usuarios (id_usuario),
  CONSTRAINT fk_devoluciones_autoriza FOREIGN KEY (id_autoriza) REFERENCES usuarios (id_usuario),
  CONSTRAINT ck_devoluciones_cantidad CHECK (cantidad > 0),
  CONSTRAINT ck_devoluciones_importe CHECK (importe >= 0),
  INDEX idx_devoluciones_folio (folio),
  INDEX idx_devoluciones_venta (id_venta)
) ENGINE=InnoDB COMMENT='Devoluciones totales o parciales (soporte SC-01)';

-- -----------------------------------------------------------------------------
-- Facturación (flujos I, J, K)
-- -----------------------------------------------------------------------------

-- Soporte SC-01 · Flujo K
CREATE TABLE clientes_fiscales (
  id_cliente      INT UNSIGNED NOT NULL AUTO_INCREMENT,
  rfc             VARCHAR(13)  NOT NULL,
  razon_social    VARCHAR(250) NOT NULL,
  regimen_fiscal  CHAR(3)      NOT NULL COMMENT 'Catálogo c_RegimenFiscal del SAT',
  codigo_postal   CHAR(5)      NOT NULL,
  correo          VARCHAR(120) NOT NULL,
  activo          BOOLEAN      NOT NULL DEFAULT TRUE,
  creado_en       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT pk_clientes_fiscales PRIMARY KEY (id_cliente),
  CONSTRAINT uq_clientes_rfc UNIQUE (rfc),
  CONSTRAINT ck_clientes_rfc CHECK (CHAR_LENGTH(rfc) IN (12, 13)),
  CONSTRAINT ck_clientes_cp CHECK (codigo_postal REGEXP '^[0-9]{5}$')
) ENGINE=InnoDB COMMENT='Datos fiscales de clientes (soporte SC-01)';

-- Cotización · Flujos I y J
CREATE TABLE facturas_cfdi (
  id_factura          INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  id_venta            INT UNSIGNED  NOT NULL,
  id_cliente          INT UNSIGNED  NOT NULL,
  uuid                CHAR(36)      NULL COMMENT 'Folio fiscal; NULL mientras es borrador',
  serie               VARCHAR(10)   NULL,
  folio               VARCHAR(20)   NULL,
  uso_cfdi            CHAR(4)       NOT NULL,
  forma_pago          CHAR(2)       NOT NULL,
  metodo_pago         CHAR(3)       NOT NULL DEFAULT 'PUE',
  subtotal            DECIMAL(12,2) NOT NULL,
  iva                 DECIMAL(12,2) NOT NULL,
  total               DECIMAL(12,2) NOT NULL,
  xml_path            VARCHAR(255)  NULL,
  pdf_path            VARCHAR(255)  NULL,
  estatus             ENUM('borrador','timbrada','cancelada') NOT NULL DEFAULT 'borrador',
  motivo_cancelacion  CHAR(2)       NULL COMMENT '01 a 04 según el SAT',
  uuid_sustituto      CHAR(36)      NULL COMMENT 'Obligatorio con motivo 01',
  fecha_timbrado      DATETIME      NULL,
  fecha_cancelacion   DATETIME      NULL,
  id_usuario          INT UNSIGNED  NOT NULL,
  creado_en           DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  venta_vigente       INT UNSIGNED GENERATED ALWAYS AS (IF(estatus = 'cancelada', NULL, id_venta)) STORED,
  CONSTRAINT pk_facturas_cfdi PRIMARY KEY (id_factura),
  CONSTRAINT uq_facturas_uuid UNIQUE (uuid),
  CONSTRAINT uq_facturas_venta_vigente UNIQUE (venta_vigente) COMMENT 'Un ticket solo tiene una factura vigente',
  CONSTRAINT fk_facturas_venta FOREIGN KEY (id_venta) REFERENCES ventas_cabecera (id_venta),
  CONSTRAINT fk_facturas_cliente FOREIGN KEY (id_cliente) REFERENCES clientes_fiscales (id_cliente),
  CONSTRAINT fk_facturas_usuario FOREIGN KEY (id_usuario) REFERENCES usuarios (id_usuario),
  CONSTRAINT ck_facturas_total CHECK (total = subtotal + iva),
  CONSTRAINT ck_facturas_timbrada CHECK (estatus = 'borrador' OR uuid IS NOT NULL),
  CONSTRAINT ck_facturas_cancelada CHECK (estatus <> 'cancelada' OR motivo_cancelacion IS NOT NULL),
  CONSTRAINT ck_facturas_sustituto CHECK (motivo_cancelacion IS NULL OR motivo_cancelacion <> '01' OR uuid_sustituto IS NOT NULL),
  INDEX idx_facturas_cliente (id_cliente),
  INDEX idx_facturas_fecha (fecha_timbrado)
) ENGINE=InnoDB COMMENT='Facturas electrónicas CFDI';

-- -----------------------------------------------------------------------------
-- Finanzas (flujos L, M, N)
-- -----------------------------------------------------------------------------

-- Cotización · Flujos M y H (los pagos a proveedores se registran como egreso de tipo pago_proveedor)
CREATE TABLE gastos_operativos (
  id_gasto          INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  tipo              ENUM('operativo','pago_proveedor') NOT NULL DEFAULT 'operativo',
  concepto          VARCHAR(120)     NOT NULL,
  monto             DECIMAL(12,2)    NOT NULL,
  fecha             DATE             NOT NULL,
  id_metodo         TINYINT UNSIGNED NOT NULL,
  id_cxp            INT UNSIGNED     NULL COMMENT 'Cuenta por pagar que liquida, si tipo = pago_proveedor',
  comprobante_path  VARCHAR(255)     NULL,
  id_usuario        INT UNSIGNED     NOT NULL,
  creado_en         DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT pk_gastos_operativos PRIMARY KEY (id_gasto),
  CONSTRAINT fk_gastos_metodo FOREIGN KEY (id_metodo) REFERENCES metodos_pago (id_metodo),
  CONSTRAINT fk_gastos_cxp FOREIGN KEY (id_cxp) REFERENCES cuentas_por_pagar (id_cxp),
  CONSTRAINT fk_gastos_usuario FOREIGN KEY (id_usuario) REFERENCES usuarios (id_usuario),
  CONSTRAINT ck_gastos_monto CHECK (monto > 0),
  CONSTRAINT ck_gastos_tipo CHECK ((tipo = 'pago_proveedor') = (id_cxp IS NOT NULL)),
  INDEX idx_gastos_fecha (fecha, tipo)
) ENGINE=InnoDB COMMENT='Egresos: gastos operativos y pagos a proveedores';

-- SC-03 (#4) · Flujo N: clientes a los que se vende a crédito
CREATE TABLE clientes_credito (
  id_cliente_credito  INT UNSIGNED      NOT NULL AUTO_INCREMENT,
  nombre              VARCHAR(150)      NOT NULL,
  telefono            VARCHAR(20)       NOT NULL,
  correo              VARCHAR(120)      NULL,
  id_cliente          INT UNSIGNED      NULL COMMENT 'Datos fiscales, si el cliente también pide factura',
  limite_credito      DECIMAL(12,2)     NOT NULL COMMENT 'Saldo pendiente máximo permitido',
  dias_credito        SMALLINT UNSIGNED NOT NULL DEFAULT 15,
  activo              BOOLEAN           NOT NULL DEFAULT TRUE,
  creado_en           DATETIME          NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en      DATETIME          NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT pk_clientes_credito PRIMARY KEY (id_cliente_credito),
  CONSTRAINT fk_clientes_credito_fiscal FOREIGN KEY (id_cliente) REFERENCES clientes_fiscales (id_cliente),
  CONSTRAINT ck_clientes_credito_limite CHECK (limite_credito > 0),
  CONSTRAINT ck_clientes_credito_dias CHECK (dias_credito > 0),
  INDEX idx_clientes_credito_nombre (nombre)
) ENGINE=InnoDB COMMENT='Clientes con venta a crédito (SC-03)';

-- SC-03 (#4) · Flujo N: un adeudo por cada venta a crédito
CREATE TABLE cuentas_por_cobrar (
  id_cxc              INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  id_venta            INT UNSIGNED  NOT NULL,
  id_cliente_credito  INT UNSIGNED  NOT NULL,
  monto_total         DECIMAL(12,2) NOT NULL,
  saldo               DECIMAL(12,2) NOT NULL,
  fecha_vencimiento   DATE          NOT NULL COMMENT 'fecha de la venta + días de crédito del cliente',
  estatus             ENUM('pendiente','pagada') NOT NULL DEFAULT 'pendiente' COMMENT 'Vencida se calcula en v_cuentas_por_cobrar',
  creado_en           DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT pk_cuentas_por_cobrar PRIMARY KEY (id_cxc),
  CONSTRAINT uq_cxc_venta UNIQUE (id_venta),
  CONSTRAINT fk_cxc_venta FOREIGN KEY (id_venta) REFERENCES ventas_cabecera (id_venta),
  CONSTRAINT fk_cxc_cliente FOREIGN KEY (id_cliente_credito) REFERENCES clientes_credito (id_cliente_credito),
  CONSTRAINT ck_cxc_monto CHECK (monto_total > 0),
  CONSTRAINT ck_cxc_saldo CHECK (saldo >= 0 AND saldo <= monto_total),
  CONSTRAINT ck_cxc_estatus CHECK ((estatus = 'pagada') = (saldo = 0)),
  INDEX idx_cxc_cliente (id_cliente_credito, estatus),
  INDEX idx_cxc_vencimiento (estatus, fecha_vencimiento)
) ENGINE=InnoDB COMMENT='Adeudos de clientes por ventas a crédito (SC-03)';

-- SC-03 (#4) · Flujo N: abonos de los clientes; entran al flujo de efectivo
CREATE TABLE cobros_clientes (
  id_cobro    INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  id_cxc      INT UNSIGNED     NOT NULL,
  monto       DECIMAL(12,2)    NOT NULL,
  id_metodo   TINYINT UNSIGNED NOT NULL,
  id_caja     INT UNSIGNED     NULL COMMENT 'Turno de caja donde se recibió; si es efectivo entra al corte',
  id_usuario  INT UNSIGNED     NOT NULL,
  fecha       DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT pk_cobros_clientes PRIMARY KEY (id_cobro),
  CONSTRAINT fk_cobros_cxc FOREIGN KEY (id_cxc) REFERENCES cuentas_por_cobrar (id_cxc),
  CONSTRAINT fk_cobros_metodo FOREIGN KEY (id_metodo) REFERENCES metodos_pago (id_metodo),
  CONSTRAINT fk_cobros_caja FOREIGN KEY (id_caja) REFERENCES cajas_pos (id_caja),
  CONSTRAINT fk_cobros_usuario FOREIGN KEY (id_usuario) REFERENCES usuarios (id_usuario),
  CONSTRAINT ck_cobros_monto CHECK (monto > 0),
  INDEX idx_cobros_cxc (id_cxc),
  INDEX idx_cobros_fecha (fecha)
) ENGINE=InnoDB COMMENT='Cobros a clientes de crédito (SC-03)';

-- -----------------------------------------------------------------------------
-- Vistas
-- -----------------------------------------------------------------------------

-- Existencia total por producto y alerta de stock bajo (flujos B y P)
CREATE VIEW v_existencias AS
SELECT
  p.id_producto,
  p.codigo_barras,
  p.nombre,
  p.unidad_venta,
  p.stock_minimo,
  COALESCE(SUM(i.cantidad_disponible), 0.000) AS existencia,
  MIN(CASE WHEN i.cantidad_disponible > 0 THEN i.fecha_caducidad END) AS proxima_caducidad,
  CASE WHEN COALESCE(SUM(i.cantidad_disponible), 0) < p.stock_minimo THEN 'Bajo' ELSE 'Normal' END AS estado
FROM productos p
LEFT JOIN inventario i ON i.id_producto = p.id_producto
WHERE p.activo = TRUE
GROUP BY p.id_producto, p.codigo_barras, p.nombre, p.unidad_venta, p.stock_minimo;

-- Cuentas por pagar con estatus calculado (flujo H)
CREATE VIEW v_cuentas_por_pagar AS
SELECT
  c.id_cxp,
  l.folio AS folio_lote,
  pr.razon_social AS proveedor,
  c.monto_total,
  c.saldo,
  c.fecha_vencimiento,
  CASE
    WHEN c.estatus = 'pagada' THEN 'Pagada'
    WHEN c.fecha_vencimiento < CURDATE() THEN 'Vencida'
    ELSE 'Pendiente'
  END AS estatus,
  (c.estatus = 'pendiente' AND c.fecha_vencimiento BETWEEN CURDATE() AND CURDATE() + INTERVAL 3 DAY) AS por_vencer
FROM cuentas_por_pagar c
JOIN lotes_compras l ON l.id_lote = c.id_lote
JOIN proveedores pr ON pr.id_proveedor = l.id_proveedor;

-- Cuentas por cobrar con estatus calculado (flujo N, SC-03)
CREATE VIEW v_cuentas_por_cobrar AS
SELECT
  c.id_cxc,
  v.folio AS folio_venta,
  cc.id_cliente_credito,
  cc.nombre AS cliente,
  c.monto_total,
  c.saldo,
  c.fecha_vencimiento,
  CASE
    WHEN c.estatus = 'pagada' THEN 'Pagada'
    WHEN c.fecha_vencimiento < CURDATE() THEN 'Vencida'
    ELSE 'Pendiente'
  END AS estatus,
  (c.estatus = 'pendiente' AND c.fecha_vencimiento BETWEEN CURDATE() AND CURDATE() + INTERVAL 3 DAY) AS por_vencer
FROM cuentas_por_cobrar c
JOIN ventas_cabecera v ON v.id_venta = c.id_venta
JOIN clientes_credito cc ON cc.id_cliente_credito = c.id_cliente_credito;

-- -----------------------------------------------------------------------------
-- Triggers
-- -----------------------------------------------------------------------------

DELIMITER $$

-- SC-02 (#3): solo un usuario activo con el rol de sistema (Administrador) autoriza devoluciones
CREATE TRIGGER trg_devoluciones_autoriza_alta
BEFORE INSERT ON devoluciones
FOR EACH ROW
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM usuarios u JOIN roles r ON r.id_rol = u.id_rol
    WHERE u.id_usuario = NEW.id_autoriza AND u.activo = TRUE AND r.es_sistema = TRUE
  ) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Solo un Administrador puede autorizar devoluciones.';
  END IF;
END$$

CREATE TRIGGER trg_devoluciones_autoriza_cambio
BEFORE UPDATE ON devoluciones
FOR EACH ROW
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM usuarios u JOIN roles r ON r.id_rol = u.id_rol
    WHERE u.id_usuario = NEW.id_autoriza AND u.activo = TRUE AND r.es_sistema = TRUE
  ) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Solo un Administrador puede autorizar devoluciones.';
  END IF;
END$$

-- La bitácora de auditoría es de solo lectura (flujo V)

CREATE TRIGGER trg_auditoria_sin_cambios
BEFORE UPDATE ON auditoria
FOR EACH ROW
BEGIN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La bitácora de auditoría es de solo lectura.';
END$$

CREATE TRIGGER trg_auditoria_sin_borrado
BEFORE DELETE ON auditoria
FOR EACH ROW
BEGIN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La bitácora de auditoría es de solo lectura.';
END$$

DELIMITER ;
