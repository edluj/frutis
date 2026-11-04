-- =============================================================================
-- Datos de prueba para desarrollo y CI. NUNCA se carga en producción.
-- Contraseña de todos los usuarios de prueba: Frutis2026!
-- =============================================================================

USE frutis;

-- Roles base propuestos en el APR (flujo U); pendientes de confirmar en SC-02 (#3)
INSERT INTO roles (id_rol, nombre, descripcion, es_sistema) VALUES
  (1, 'Administrador', 'Acceso total; no se edita ni se elimina', TRUE),
  (2, 'Cajero',        'Cobro en mostrador y corte de caja',      FALSE),
  (3, 'Compras',       'Proveedores, lotes y cuentas por pagar',  FALSE),
  (4, 'Contador',      'Facturación, finanzas y reportes',        FALSE);

-- Matriz de permisos (ver, crear, editar, eliminar)
INSERT INTO permisos (id_rol, modulo, puede_ver, puede_crear, puede_editar, puede_eliminar) VALUES
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

INSERT INTO usuarios (id_usuario, nombre_completo, usuario, correo, password_hash, id_rol) VALUES
  (1, 'Administrador de prueba', 'admin',     'admin@frutis.test',     'pbkdf2_sha256$210000$c873d8bd77070764e47d848d30db5c15$d47a3a0bc3080bdc345fdb94158a37116b917bb588196b17f0a85fcbe2291053', 1),
  (2, 'Cajero de prueba',        'cajero1',   'cajero1@frutis.test',   'pbkdf2_sha256$210000$c873d8bd77070764e47d848d30db5c15$d47a3a0bc3080bdc345fdb94158a37116b917bb588196b17f0a85fcbe2291053', 2),
  (3, 'Compras de prueba',       'compras1',  'compras1@frutis.test',  'pbkdf2_sha256$210000$c873d8bd77070764e47d848d30db5c15$d47a3a0bc3080bdc345fdb94158a37116b917bb588196b17f0a85fcbe2291053', 3),
  (4, 'Contador de prueba',      'contador1', 'contador1@frutis.test', 'pbkdf2_sha256$210000$c873d8bd77070764e47d848d30db5c15$d47a3a0bc3080bdc345fdb94158a37116b917bb588196b17f0a85fcbe2291053', 4);

INSERT INTO metodos_pago (id_metodo, nombre, clave_sat, es_efectivo, es_credito) VALUES
  (1, 'Efectivo',           '01', TRUE,  FALSE),
  (2, 'Tarjeta de débito',  '28', FALSE, FALSE),
  (3, 'Tarjeta de crédito', '04', FALSE, FALSE),
  (4, 'Transferencia',      '03', FALSE, FALSE),
  (5, 'Crédito',            '99', FALSE, TRUE);

INSERT INTO categorias (id_categoria, nombre, descripcion) VALUES
  (1, 'Frutas',   'Fruta fresca'),
  (2, 'Verduras', 'Verdura y hortaliza fresca');

INSERT INTO productos (id_producto, codigo_barras, nombre, id_categoria, unidad_venta, precio_venta, costo_actual, stock_minimo, es_frecuente) VALUES
  (1, 'FRU-0001', 'Manzana roja',      1, 'kg',    45.00, 32.00, 10.000, TRUE),
  (2, 'FRU-0002', 'Plátano',           1, 'kg',    22.00, 14.00,  5.000, TRUE),
  (3, 'FRU-0003', 'Aguacate hass',     1, 'kg',    68.00, 50.00,  3.000, TRUE),
  (4, 'FRU-0004', 'Piña',              1, 'pieza', 35.00, 22.00,  4.000, FALSE),
  (5, 'VER-0001', 'Jitomate saladet',  2, 'kg',    28.50, 18.00,  5.000, TRUE),
  (6, 'VER-0002', 'Limón sin semilla', 2, 'kg',    32.00, 20.00,  2.000, FALSE);

INSERT INTO proveedores (id_proveedor, razon_social, rfc, telefono, correo, dias_credito) VALUES
  (1, 'Distribuidora de la Central de Abasto SA de CV', 'DCA010101AB1', '5555550101', 'ventas@dca.test', 15);

-- Lote 1 (contado, caduca antes) y lote 2 (crédito) para probar el descuento FEFO
INSERT INTO lotes_compras (id_lote, folio, id_proveedor, id_usuario, fecha_entrada, condicion_pago, total) VALUES
  (1, 'L-00000001', 1, 3, CURDATE() - INTERVAL 5 DAY, 'contado',  560.00),
  (2, 'L-00000002', 1, 3, CURDATE() - INTERVAL 1 DAY, 'credito', 1020.00);

INSERT INTO inventario (id_inventario, id_lote, id_producto, cantidad_inicial, cantidad_disponible, costo_unitario, fecha_caducidad) VALUES
  (1, 1, 1,  2.000,  2.000, 30.00, CURDATE() + INTERVAL 2 DAY),
  (2, 1, 2, 20.000, 20.000, 14.00, CURDATE() + INTERVAL 4 DAY),
  (3, 1, 4, 10.000, 10.000, 22.00, CURDATE() + INTERVAL 6 DAY),
  (4, 2, 1, 10.000, 10.000, 32.00, CURDATE() + INTERVAL 7 DAY),
  (5, 2, 3,  8.000,  8.000, 50.00, CURDATE() + INTERVAL 5 DAY),
  (6, 2, 5, 15.000, 15.000, 18.00, CURDATE() + INTERVAL 3 DAY),
  (7, 2, 6,  1.500,  1.500, 20.00, CURDATE() + INTERVAL 10 DAY);

INSERT INTO cuentas_por_pagar (id_cxp, id_lote, monto_total, saldo, fecha_vencimiento) VALUES
  (1, 2, 1020.00, 1020.00, CURDATE() - INTERVAL 1 DAY + INTERVAL 15 DAY);

INSERT INTO clientes_fiscales (id_cliente, rfc, razon_social, regimen_fiscal, codigo_postal, correo) VALUES
  (1, 'XAXX010101000', 'PUBLICO EN GENERAL', '616', '06000', 'facturas@frutis.test');

-- Clientes de crédito (SC-03)
INSERT INTO clientes_credito (id_cliente_credito, nombre, telefono, limite_credito, dias_credito) VALUES
  (1, 'Fonda Doña Lupe',       '5555550202', 1000.00, 15),
  (2, 'Restaurante El Huerto', '5555550303',  100.00,  7);

-- Caja abierta del cajero de prueba
INSERT INTO cajas_pos (id_caja, terminal, id_usuario, fondo_inicial) VALUES
  (1, 'POS-01', 2, 500.00);
