-- =============================================================================
-- Pruebas de la base de datos: esquema, fn_importe_peso y sp_registrar_venta.
-- Se ejecutan sobre una base recién creada con schema.sql + functions + procedures + seed.sql.
-- Cada prueba imprime "OK ..." o detiene el script con "FALLA: ...".
-- =============================================================================

USE frutis;

DROP PROCEDURE IF EXISTS t_ok;
DROP PROCEDURE IF EXISTS t_espera_error;

DELIMITER $$

CREATE PROCEDURE t_ok(IN p_condicion BOOLEAN, IN p_nombre VARCHAR(100))
BEGIN
  DECLARE v_msg VARCHAR(128);
  IF p_condicion IS NULL OR NOT p_condicion THEN
    SET v_msg = LEFT(CONCAT('FALLA: ', p_nombre), 128);
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
  END IF;
  SELECT CONCAT('OK   ', p_nombre) AS resultado;
END$$

-- Ejecuta p_sql y exige que falle con un mensaje que empiece con p_esperado
CREATE PROCEDURE t_espera_error(IN p_sql TEXT, IN p_esperado VARCHAR(100), IN p_nombre VARCHAR(100))
BEGIN
  DECLARE v_error TEXT DEFAULT NULL;
  DECLARE v_msg   VARCHAR(128);
  DECLARE CONTINUE HANDLER FOR SQLEXCEPTION
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
  END;

  SET @t_sql = p_sql;
  PREPARE t_stmt FROM @t_sql;
  EXECUTE t_stmt;
  DEALLOCATE PREPARE t_stmt;

  IF v_error IS NULL OR v_error NOT LIKE CONCAT(p_esperado, '%') THEN
    SET v_msg = LEFT(CONCAT('FALLA: ', p_nombre, ' -> ', IFNULL(v_error, 'no hubo error')), 128);
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
  END IF;
  SELECT CONCAT('OK   ', p_nombre) AS resultado;
END$$

DELIMITER ;

-- -----------------------------------------------------------------------------
-- Esquema
-- -----------------------------------------------------------------------------

CALL t_ok(
  (SELECT COUNT(*) FROM information_schema.tables
   WHERE table_schema = 'frutis' AND table_type = 'BASE TABLE') = 23,
  'El esquema tiene 23 tablas (14 de la cotización + 6 de SC-01 + 3 de SC-03)');

CALL t_ok(
  (SELECT COUNT(*) FROM information_schema.tables
   WHERE table_schema = 'frutis' AND table_type = 'BASE TABLE' AND engine <> 'InnoDB') = 0,
  'Todas las tablas usan InnoDB');

-- -----------------------------------------------------------------------------
-- fn_importe_peso
-- -----------------------------------------------------------------------------

CALL t_ok(fn_importe_peso(5, 1.255) = 35.77, 'fn_importe_peso redondea a 2 decimales (1.255 kg x 28.50 = 35.77)');
CALL t_ok(fn_importe_peso(4, 3) = 105.00, 'fn_importe_peso calcula productos por pieza (3 x 35.00)');
CALL t_espera_error('SELECT fn_importe_peso(1, 0) INTO @x', 'Cantidad inválida.', 'fn_importe_peso rechaza cantidad cero');
CALL t_espera_error('SELECT fn_importe_peso(999, 1) INTO @x', 'Producto no encontrado', 'fn_importe_peso rechaza producto inexistente');

-- -----------------------------------------------------------------------------
-- sp_registrar_venta: cobro correcto con descuento FEFO
-- -----------------------------------------------------------------------------

-- 3 kg de manzana en efectivo: 2 kg salen del lote que caduca antes y 1 kg del siguiente
CALL sp_registrar_venta(1, 2, 1, 200.00, NULL, '[{"id_producto": 1, "cantidad": 3}]', @venta, @folio, @total, @cambio);

CALL t_ok(@folio = 'V00000001', 'El primer ticket recibe el folio V00000001');
CALL t_ok(@total = 135.00 AND @cambio = 65.00, 'Total 135.00 y cambio 65.00 sobre 200.00 recibidos');
CALL t_ok((SELECT COUNT(*) FROM ventas_detalle WHERE id_venta = @venta) = 2, 'La venta usa 2 lotes');
CALL t_ok((SELECT cantidad FROM ventas_detalle WHERE id_venta = @venta AND id_inventario = 1) = 2.000,
          'FEFO: toma primero los 2 kg del lote que caduca antes');
CALL t_ok((SELECT cantidad_disponible FROM inventario WHERE id_inventario = 1) = 0.000
      AND (SELECT cantidad_disponible FROM inventario WHERE id_inventario = 4) = 9.000,
          'El inventario queda en 0 y 9 kg');
CALL t_ok((SELECT total = subtotal + iva AND estatus = 'pagada' FROM ventas_cabecera WHERE id_venta = @venta),
          'La cabecera cuadra: total = subtotal + IVA');

-- Producto repetido en el carrito y pago con tarjeta (sin monto recibido)
CALL sp_registrar_venta(1, 2, 2, NULL, NULL,
  '[{"id_producto": 2, "cantidad": 1.255}, {"id_producto": 2, "cantidad": 0.745}, {"id_producto": 4, "cantidad": 2}]',
  @venta2, @folio2, @total2, @cambio2);

CALL t_ok(@total2 = 114.00 AND @cambio2 = 0.00, 'Tarjeta: 2 kg de plátano + 2 piñas = 114.00, sin cambio');
CALL t_ok((SELECT COUNT(*) FROM ventas_detalle WHERE id_venta = @venta2 AND id_producto = 2) = 1,
          'Un producto repetido en el carrito se registra en un solo renglón');
CALL t_ok((SELECT monto_recibido FROM ventas_cabecera WHERE id_venta = @venta2) = 114.00,
          'En pagos sin efectivo el monto recibido es igual al total');

-- -----------------------------------------------------------------------------
-- sp_registrar_venta: errores y rollback
-- -----------------------------------------------------------------------------

SET @ventas_antes = (SELECT COUNT(*) FROM ventas_cabecera);
SET @detalle_antes = (SELECT COUNT(*) FROM ventas_detalle);

CALL t_espera_error(
  'CALL sp_registrar_venta(1, 2, 1, 10.00, NULL, ''[{"id_producto": 3, "cantidad": 1}]'', @a, @b, @c, @d)',
  'El monto recibido es insuficiente.', 'Rechaza monto recibido menor al total');
CALL t_ok((SELECT cantidad_disponible FROM inventario WHERE id_inventario = 5) = 8.000,
          'Rollback: el aguacate conserva sus 8 kg');

CALL t_espera_error(
  'CALL sp_registrar_venta(1, 2, 1, 500.00, NULL, ''[{"id_producto": 1, "cantidad": 1}, {"id_producto": 6, "cantidad": 2}]'', @a, @b, @c, @d)',
  'Producto sin existencia suficiente: Limón', 'Rechaza producto sin existencia suficiente');
CALL t_ok((SELECT cantidad_disponible FROM inventario WHERE id_inventario = 4) = 9.000
      AND (SELECT cantidad_disponible FROM inventario WHERE id_inventario = 7) = 1.500,
          'Rollback: no descuenta la manzana ya procesada ni el limón');

CALL t_espera_error(
  'CALL sp_registrar_venta(1, 2, 1, 500.00, NULL, ''[{"id_producto": 4, "cantidad": 1.5}]'', @a, @b, @c, @d)',
  'Los productos por pieza', 'Rechaza piezas fraccionadas');

CALL t_espera_error(
  'CALL sp_registrar_venta(1, 2, 1, 500.00, NULL, ''[]'', @a, @b, @c, @d)',
  'El carrito está vacío.', 'Rechaza carrito vacío');

CALL t_espera_error(
  'CALL sp_registrar_venta(1, 2, 1, 500.00, NULL, ''[{"id_producto": 999, "cantidad": 1}]'', @a, @b, @c, @d)',
  'Producto no encontrado', 'Rechaza producto inexistente');

CALL t_espera_error(
  'CALL sp_registrar_venta(1, 2, 1, 500.00, NULL, ''[{"id_producto": 1, "cantidad": -2}]'', @a, @b, @c, @d)',
  'Cantidad inválida.', 'Rechaza cantidad negativa');

CALL t_espera_error(
  'CALL sp_registrar_venta(1, 2, 9, 500.00, NULL, ''[{"id_producto": 1, "cantidad": 1}]'', @a, @b, @c, @d)',
  'Método de pago inválido.', 'Rechaza método de pago inexistente');

INSERT INTO cajas_pos (id_caja, terminal, id_usuario, fondo_inicial, fecha_cierre, efectivo_esperado, efectivo_contado, diferencia, estatus)
VALUES (2, 'POS-02', 2, 300.00, NOW(), 300.00, 300.00, 0.00, 'cerrada');

CALL t_espera_error(
  'CALL sp_registrar_venta(2, 2, 1, 500.00, NULL, ''[{"id_producto": 1, "cantidad": 1}]'', @a, @b, @c, @d)',
  'No hay una caja abierta.', 'Rechaza cobro en caja cerrada');

CALL t_ok((SELECT COUNT(*) FROM ventas_cabecera) = @ventas_antes
      AND (SELECT COUNT(*) FROM ventas_detalle) = @detalle_antes,
          'Ningún cobro fallido deja ventas o renglones a medias');

-- -----------------------------------------------------------------------------
-- SC-03: venta a crédito y cobros a clientes
-- -----------------------------------------------------------------------------

-- 1 kg de aguacate a crédito para la Fonda Doña Lupe (límite 1000.00, 15 días)
CALL sp_registrar_venta(1, 2, 5, NULL, 1, '[{"id_producto": 3, "cantidad": 1}]', @venta3, @folio3, @total3, @cambio3);

CALL t_ok(@total3 = 68.00 AND @cambio3 = 0.00, 'Venta a crédito de 68.00 sin cambio');
CALL t_ok((SELECT saldo = 68.00 AND estatus = 'pendiente' AND fecha_vencimiento = CURDATE() + INTERVAL 15 DAY
           FROM cuentas_por_cobrar WHERE id_venta = @venta3),
          'La venta a crédito crea la cuenta por cobrar con vencimiento a 15 días');

CALL t_espera_error(
  'CALL sp_registrar_venta(1, 2, 5, NULL, NULL, ''[{"id_producto": 3, "cantidad": 1}]'', @a, @b, @c, @d)',
  'Cliente de crédito no encontrado', 'Rechaza venta a crédito sin cliente');

-- 2 kg de aguacate (136.00) superan el límite de 100.00 del Restaurante El Huerto
CALL t_espera_error(
  'CALL sp_registrar_venta(1, 2, 5, NULL, 2, ''[{"id_producto": 3, "cantidad": 2}]'', @a, @b, @c, @d)',
  'El cliente excede su límite de crédito.', 'Rechaza venta que rebasa el límite de crédito');
CALL t_ok((SELECT cantidad_disponible FROM inventario WHERE id_inventario = 5) = 7.000,
          'Rollback: la venta rechazada por límite no descuenta inventario');

SET @cxc = (SELECT id_cxc FROM cuentas_por_cobrar WHERE id_venta = @venta3);

CALL sp_registrar_cobro(@cxc, 50.00, 1, 1, 2, @saldo);
CALL t_ok(@saldo = 18.00 AND (SELECT estatus FROM cuentas_por_cobrar WHERE id_cxc = @cxc) = 'pendiente',
          'Un abono parcial deja saldo de 18.00 pendiente');

CALL t_espera_error('CALL sp_registrar_cobro(@cxc, 20.00, 1, 1, 2, @s)', 'El cobro no puede ser mayor al saldo.',
                    'Rechaza un cobro mayor al saldo');
CALL t_espera_error('CALL sp_registrar_cobro(@cxc, 10.00, 5, NULL, 2, @s)', 'Método de pago inválido para un cobro.',
                    'Rechaza cobrar con el método Crédito');
CALL t_espera_error('CALL sp_registrar_cobro(@cxc, 10.00, 1, 2, 2, @s)', 'No hay una caja abierta.',
                    'Rechaza cobro en caja cerrada');

CALL sp_registrar_cobro(@cxc, 18.00, 4, NULL, 4, @saldo);
CALL t_ok(@saldo = 0.00 AND (SELECT estatus FROM cuentas_por_cobrar WHERE id_cxc = @cxc) = 'pagada',
          'El abono final liquida la cuenta y la marca como pagada');
CALL t_ok((SELECT SUM(monto) FROM cobros_clientes WHERE id_cxc = @cxc) = 68.00,
          'Los cobros registrados suman el total de la venta');
CALL t_ok((SELECT estatus FROM v_cuentas_por_cobrar WHERE id_cxc = @cxc) = 'Pagada',
          'v_cuentas_por_cobrar muestra la cuenta como Pagada');

-- -----------------------------------------------------------------------------
-- SC-02: solo un Administrador autoriza devoluciones
-- -----------------------------------------------------------------------------

CALL t_espera_error(
  'INSERT INTO devoluciones (folio, id_venta, id_detalle, id_caja, cantidad, importe, motivo, estado_producto, id_usuario, id_autoriza) VALUES (''D-1'', 1, 1, 1, 0.5, 15.00, ''Golpeada'', ''danado'', 2, 2)',
  'Solo un Administrador puede autorizar devoluciones.', 'Un cajero no puede autorizar devoluciones');

INSERT INTO devoluciones (folio, id_venta, id_detalle, id_caja, cantidad, importe, motivo, estado_producto, id_usuario, id_autoriza)
VALUES ('D-1', 1, 1, 1, 0.5, 15.00, 'Golpeada', 'danado', 2, 1);
CALL t_ok((SELECT COUNT(*) FROM devoluciones WHERE folio = 'D-1') = 1, 'El Administrador sí autoriza devoluciones');

CALL t_espera_error('UPDATE devoluciones SET id_autoriza = 4 WHERE folio = ''D-1''',
  'Solo un Administrador puede autorizar devoluciones.', 'No se puede cambiar el autorizador a otro rol');

-- -----------------------------------------------------------------------------
-- Reglas del esquema
-- -----------------------------------------------------------------------------

CALL t_espera_error(
  'INSERT INTO cajas_pos (terminal, id_usuario, fondo_inicial) VALUES (''POS-01'', 2, 100.00)',
  'Duplicate entry', 'Solo una caja abierta por terminal');

CALL t_espera_error(
  'UPDATE cajas_pos SET estatus = ''cerrada'', fecha_cierre = NOW(), efectivo_contado = 480, diferencia = -20 WHERE id_caja = 1',
  'Check constraint', 'No se cierra caja con diferencia sin observaciones');

CALL t_espera_error(
  'UPDATE inventario SET cantidad_disponible = -1 WHERE id_inventario = 2',
  'Check constraint', 'La existencia por lote no puede ser negativa');

CALL t_espera_error(
  'INSERT INTO usuarios (nombre_completo, usuario, correo, password_hash, id_rol) VALUES (''X'', ''x1'', ''correo-invalido'', ''h'', 2)',
  'Check constraint', 'Rechaza correo con formato inválido');

INSERT INTO auditoria (id_usuario, usuario, modulo, accion, detalle, ip)
VALUES (1, 'admin', 'admin', 'login', 'Inicio de sesión de prueba', '127.0.0.1');

CALL t_espera_error('UPDATE auditoria SET detalle = ''x''', 'La bitácora de auditoría es de solo lectura.',
                    'La bitácora no se puede editar');
CALL t_espera_error('DELETE FROM auditoria', 'La bitácora de auditoría es de solo lectura.',
                    'La bitácora no se puede borrar');

INSERT INTO facturas_cfdi (id_venta, id_cliente, uuid, uso_cfdi, forma_pago, subtotal, iva, total, estatus, fecha_timbrado, id_usuario)
VALUES (1, 1, '11111111-1111-1111-1111-111111111111', 'S01', '01', 135.00, 0.00, 135.00, 'timbrada', NOW(), 4);

CALL t_espera_error(
  'INSERT INTO facturas_cfdi (id_venta, id_cliente, uso_cfdi, forma_pago, subtotal, iva, total, id_usuario) VALUES (1, 1, ''S01'', ''01'', 135.00, 0.00, 135.00, 4)',
  'Duplicate entry', 'Un ticket no se factura dos veces');

CALL t_ok((SELECT estado FROM v_existencias WHERE id_producto = 1) = 'Bajo',
          'v_existencias marca "Bajo" la manzana (9 kg con mínimo de 10)');

CALL t_ok((SELECT estatus FROM v_cuentas_por_pagar WHERE id_cxp = 1) = 'Pendiente',
          'v_cuentas_por_pagar calcula el estatus del adeudo');

SELECT 'Todas las pruebas pasaron' AS resultado;

DROP PROCEDURE t_ok;
DROP PROCEDURE t_espera_error;
