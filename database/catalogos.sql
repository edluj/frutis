-- =============================================================================
-- Catálogos base de Frutis: se cargan en TODA instalación, también en producción.
--
-- Roles, matriz de permisos y métodos de pago. INSERT IGNORE: en una base que ya los
-- tiene no cambia nada, así no se pierden los permisos editados desde la pantalla de roles.
-- El primer Administrador se crea con: cd middleware && .venv/bin/python -m app.crear_administrador
-- =============================================================================

USE frutis;

-- Roles base del APR (flujo U)
INSERT IGNORE INTO roles (id_rol, nombre, descripcion, es_sistema) VALUES
  (1, 'Administrador', 'Acceso total; no se edita ni se elimina', TRUE),
  (2, 'Cajero',        'Cobro en mostrador y corte de caja',      FALSE),
  (3, 'Compras',       'Proveedores, lotes y cuentas por pagar',  FALSE),
  (4, 'Contador',      'Facturación, finanzas y reportes',        FALSE);

-- Matriz de permisos (ver, crear, editar, eliminar)
INSERT IGNORE INTO permisos (id_rol, modulo, puede_ver, puede_crear, puede_editar, puede_eliminar) VALUES
  (1, 'pos',         TRUE,  TRUE,  TRUE,  TRUE),
  (1, 'compras',     TRUE,  TRUE,  TRUE,  TRUE),
  (1, 'facturacion', TRUE,  TRUE,  TRUE,  TRUE),
  (1, 'finanzas',    TRUE,  TRUE,  TRUE,  TRUE),
  (1, 'inventario',  TRUE,  TRUE,  TRUE,  TRUE),
  (1, 'reportes',    TRUE,  TRUE,  TRUE,  TRUE),
  (1, 'admin',       TRUE,  TRUE,  TRUE,  TRUE),
  (2, 'pos',         TRUE,  TRUE,  FALSE, FALSE),
  (2, 'inventario',  TRUE,  FALSE, FALSE, FALSE),
  (3, 'compras',     TRUE,  TRUE,  TRUE,  TRUE),
  (3, 'inventario',  TRUE,  TRUE,  TRUE,  FALSE),
  (3, 'reportes',    TRUE,  FALSE, FALSE, FALSE),
  (4, 'facturacion', TRUE,  TRUE,  TRUE,  TRUE),
  (4, 'finanzas',    TRUE,  TRUE,  TRUE,  TRUE),
  (4, 'reportes',    TRUE,  FALSE, FALSE, FALSE),
  (4, 'pos',         TRUE,  FALSE, FALSE, FALSE);

-- Formas de pago (c_FormaPago del SAT)
INSERT IGNORE INTO metodos_pago (id_metodo, nombre, clave_sat, es_efectivo, es_credito, activo) VALUES
  (1, 'Efectivo',           '01', TRUE,  FALSE, TRUE),
  (2, 'Tarjeta de débito',  '28', FALSE, FALSE, TRUE),
  (3, 'Tarjeta de crédito', '04', FALSE, FALSE, TRUE),
  (4, 'Transferencia',      '03', FALSE, FALSE, TRUE),
  (5, 'Crédito',            '99', FALSE, TRUE,  TRUE),
  -- Solo para pagar a proveedores (HU-25): inactivo, no aparece en la caja del POS.
  (6, 'Cheque',             '02', FALSE, FALSE, FALSE);
