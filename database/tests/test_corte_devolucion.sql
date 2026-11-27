-- =============================================================================
-- Pruebas de apertura (HU-15), corte de caja (HU-09) y devoluciones (HU-30, SC-02).
-- Corren después de test_cobro.sql sobre la misma base, pero usan su propio
-- cajero, terminal y lote para no depender de lo que esas pruebas dejaron.
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

-- Cajero propio y un lote de jitomate que caduca antes, para que una venta use 2 lotes
INSERT INTO usuarios (id_usuario, nombre_completo, usuario, correo, password_hash, id_rol)
VALUES (5, 'Segundo cajero de prueba', 'cajero2', 'cajero2@frutis.test', 'sin-uso', 2);

INSERT INTO lotes_compras (id_lote, folio, id_proveedor, id_usuario, fecha_entrada, condicion_pago, total)
VALUES (3, 'L-00000003', 1, 3, CURDATE(), 'contado', 36.00);
INSERT INTO inventario (id_inventario, id_lote, id_producto, cantidad_inicial, cantidad_disponible, costo_unitario, fecha_caducidad)
VALUES (8, 3, 5, 2.000, 2.000, 18.00, CURDATE() + INTERVAL 1 DAY);

-- -----------------------------------------------------------------------------
-- sp_abrir_caja (HU-15)
-- -----------------------------------------------------------------------------

CALL t_espera_error('CALL sp_abrir_caja(''POS-01'', 5, 100.00, @c)', 'Ya hay una caja abierta en esta terminal.',
                    'No abre una segunda caja en una terminal ocupada');
CALL t_espera_error('CALL sp_abrir_caja(''POS-09'', 2, 100.00, @c)', 'Ya tiene una caja abierta en la terminal POS-01.',
                    'Un cajero no tiene dos turnos abiertos');
CALL t_espera_error('CALL sp_abrir_caja(''POS-03'', 5, -1.00, @c)', 'Ingrese un fondo inicial válido.',
                    'Rechaza fondo inicial negativo');
CALL t_espera_error('CALL sp_abrir_caja(''   '', 5, 100.00, @c)', 'Terminal inválida.', 'Rechaza terminal vacía');
CALL t_espera_error('CALL sp_abrir_caja(''POS-03'', 999, 100.00, @c)', 'Usuario no encontrado o inactivo.',
                    'Rechaza usuario inexistente');

CALL sp_abrir_caja(' POS-03 ', 5, 500.00, @caja);
CALL t_ok((SELECT terminal = 'POS-03' AND id_usuario = 5 AND fondo_inicial = 500.00 AND estatus = 'abierta'
             AND fecha_apertura IS NOT NULL
           FROM cajas_pos WHERE id_caja = @caja),
          'Abre la caja con cajero, terminal, fondo y fecha de apertura');

-- -----------------------------------------------------------------------------
-- Ventas y cobro del turno
-- -----------------------------------------------------------------------------

-- Efectivo: 3 kg de jitomate (2 kg del lote 8 y 1 kg del lote 6) = 85.50
CALL sp_registrar_venta(@caja, 5, 1, 100.00, NULL, '[{"id_producto": 5, "cantidad": 3}]', @va, @fa, @ta, @ca);
-- Tarjeta de débito: 2 piñas = 70.00
CALL sp_registrar_venta(@caja, 5, 2, NULL, NULL, '[{"id_producto": 4, "cantidad": 2}]', @vb, @fb, @tb, @cb);
-- Crédito a la Fonda Doña Lupe: 1 kg de plátano = 22.00
CALL sp_registrar_venta(@caja, 5, 5, NULL, 1, '[{"id_producto": 2, "cantidad": 1}]', @vc, @fc, @tc, @cc);
-- Efectivo: 1 kg de aguacate = 68.00
CALL sp_registrar_venta(@caja, 5, 1, 68.00, NULL, '[{"id_producto": 3, "cantidad": 1}]', @vd, @fd, @td, @cd);

SET @cxc = (SELECT id_cxc FROM cuentas_por_cobrar WHERE id_venta = @vc);
CALL sp_registrar_cobro(@cxc, 10.00, 1, @caja, 5, @saldo);

CALL t_ok((SELECT COUNT(*) FROM ventas_detalle WHERE id_venta = @va) = 2, 'La venta de jitomate usa 2 lotes');
CALL t_ok(fn_efectivo_esperado(@caja) = 663.50,
          'Efectivo esperado = 500 fondo + 153.50 ventas en efectivo + 10 cobro; tarjeta y crédito no cuentan');

-- -----------------------------------------------------------------------------
-- sp_registrar_devolucion: errores (nada debe quedar a medias)
-- -----------------------------------------------------------------------------

SET @inv6 = (SELECT cantidad_disponible FROM inventario WHERE id_inventario = 6);
SET @mermas_antes = (SELECT COUNT(*) FROM mermas);
SET @devoluciones_antes = (SELECT COUNT(*) FROM devoluciones);
SET @r_jitomate = '[{"id_producto": 5, "cantidad": 1, "estado": "bueno"}]';

SET @sql = CONCAT('CALL sp_registrar_devolucion(''', @fa, ''', @caja, 5, 5, ''Producto en mal estado'', ''efectivo'', @r_jitomate, @f, @t)');
CALL t_espera_error(@sql, 'Solo un Administrador puede autorizar devoluciones.', 'SC-02: un cajero no autoriza su devolución');
CALL t_ok((SELECT cantidad_disponible FROM inventario WHERE id_inventario = 6) = @inv6
      AND (SELECT COUNT(*) FROM devoluciones) = @devoluciones_antes,
          'Rollback: la devolución rechazada por el trigger no regresa inventario');

CALL t_espera_error('CALL sp_registrar_devolucion(''V99999999'', @caja, 5, 1, ''x'', ''efectivo'', @r_jitomate, @f, @t)',
                    'No existe un ticket con ese número.', 'Rechaza ticket inexistente');
SET @sql = CONCAT('CALL sp_registrar_devolucion(''', @fa, ''', @caja, 5, 1, ''x'', ''efectivo'', ''[{"id_producto": 5, "cantidad": 3.5, "estado": "bueno"}]'', @f, @t)');
CALL t_espera_error(@sql, 'La cantidad a devolver de Jitomate saladet no es válida.', 'No devuelve más de lo vendido');
SET @sql = CONCAT('CALL sp_registrar_devolucion(''', @fa, ''', @caja, 5, 1, ''x'', ''efectivo'', ''[{"id_producto": 5, "cantidad": 2, "estado": "bueno"}, {"id_producto": 5, "cantidad": 1.5, "estado": "danado"}]'', @f, @t)');
CALL t_espera_error(@sql, 'La cantidad a devolver de Jitomate', 'Suma los renglones repetidos del mismo producto');
SET @sql = CONCAT('CALL sp_registrar_devolucion(''', @fa, ''', @caja, 5, 1, ''x'', ''efectivo'', ''[{"id_producto": 1, "cantidad": 1, "estado": "bueno"}]'', @f, @t)');
CALL t_espera_error(@sql, 'La cantidad a devolver de Manzana roja no es válida.', 'Rechaza un producto que no está en el ticket');
SET @sql = CONCAT('CALL sp_registrar_devolucion(''', @fb, ''', @caja, 5, 1, ''x'', ''tarjeta'', ''[{"id_producto": 4, "cantidad": 0.5, "estado": "bueno"}]'', @f, @t)');
CALL t_espera_error(@sql, 'La cantidad a devolver de Piña no es válida.', 'Las piezas se devuelven enteras');
SET @sql = CONCAT('CALL sp_registrar_devolucion(''', @fa, ''', @caja, 5, 1, ''x'', ''efectivo'', ''[{"id_producto": 5, "cantidad": 1, "estado": "roto"}]'', @f, @t)');
CALL t_espera_error(@sql, 'Estado del producto inválido.', 'Rechaza un estado del producto desconocido');
SET @sql = CONCAT('CALL sp_registrar_devolucion(''', @fa, ''', @caja, 5, 1, ''x'', ''efectivo'', ''[]'', @f, @t)');
CALL t_espera_error(@sql, 'Marque al menos un producto.', 'Rechaza una devolución sin productos');
SET @sql = CONCAT('CALL sp_registrar_devolucion(''', @fa, ''', @caja, 5, 1, ''   '', ''efectivo'', @r_jitomate, @f, @t)');
CALL t_espera_error(@sql, 'Escriba el motivo de la devolución.', 'Exige el motivo');
SET @sql = CONCAT('CALL sp_registrar_devolucion(''', @fa, ''', @caja, 5, 1, ''x'', ''vales'', @r_jitomate, @f, @t)');
CALL t_espera_error(@sql, 'Forma de reembolso inválida.', 'Rechaza una forma de reembolso desconocida');
SET @sql = CONCAT('CALL sp_registrar_devolucion(''', @fa, ''', @caja, 5, 1, ''x'', ''credito'', @r_jitomate, @f, @t)');
CALL t_espera_error(@sql, 'Solo una venta a crédito se reembolsa como abono.', 'Una venta de contado no se abona a crédito');
SET @sql = CONCAT('CALL sp_registrar_devolucion(''', @fa, ''', @caja, 5, 1, ''x'', ''tarjeta'', @r_jitomate, @f, @t)');
CALL t_espera_error(@sql, 'El ticket no se pagó con tarjeta.', 'Solo se revierte a tarjeta un pago con tarjeta');
SET @sql = CONCAT('CALL sp_registrar_devolucion(''', @fc, ''', @caja, 5, 1, ''x'', ''efectivo'', ''[{"id_producto": 2, "cantidad": 1, "estado": "bueno"}]'', @f, @t)');
CALL t_espera_error(@sql, 'Una venta a crédito se reembolsa como abono a su cuenta.', 'Una venta a crédito no se reembolsa en efectivo');
SET @sql = CONCAT('CALL sp_registrar_devolucion(''', @fa, ''', 2, 5, 1, ''x'', ''efectivo'', @r_jitomate, @f, @t)');
CALL t_espera_error(@sql, 'No hay una caja abierta.', 'No devuelve desde una caja cerrada');

CALL t_ok((SELECT cantidad_disponible FROM inventario WHERE id_inventario = 6) = @inv6
      AND (SELECT COUNT(*) FROM mermas) = @mermas_antes
      AND (SELECT COUNT(*) FROM devoluciones) = @devoluciones_antes
      AND (SELECT estatus FROM ventas_cabecera WHERE id_venta = @va) = 'pagada',
          'Ninguna devolución fallida deja inventario, mermas o devoluciones a medias');

-- -----------------------------------------------------------------------------
-- sp_registrar_devolucion: devolución parcial y total
-- -----------------------------------------------------------------------------

-- 2 kg en buen estado y 0.5 kg en mal estado del ticket de jitomate
CALL sp_registrar_devolucion(@fa, @caja, 5, 1, 'Producto en mal estado', 'efectivo',
  '[{"id_producto": 5, "cantidad": 2, "estado": "bueno"}, {"id_producto": 5, "cantidad": 0.5, "estado": "danado"}]',
  @folio_dev, @total_dev);

CALL t_ok(@folio_dev = CONCAT('D', LPAD(@va, 8, '0'), '-1'), 'La devolución recibe el folio D<venta>-1');
CALL t_ok(@total_dev = 71.25, 'Devuelve 2.5 kg de jitomate a 28.50 = 71.25');
CALL t_ok((SELECT COUNT(*) FROM devoluciones WHERE folio = @folio_dev) = 3,
          'Una fila por lote: 1 kg del lote 6, 1 kg y 0.5 kg del lote 8');
CALL t_ok((SELECT cantidad_disponible FROM inventario WHERE id_inventario = 6) = @inv6 + 1
      AND (SELECT cantidad_disponible FROM inventario WHERE id_inventario = 8) = 1.000,
          'Lo que está en buen estado regresa a sus lotes');
CALL t_ok((SELECT cantidad = 0.500 AND motivo = 'devolucion' AND costo_total = 9.00 AND id_inventario = 8
           FROM mermas WHERE observaciones LIKE CONCAT('Devolución ', @folio_dev, '%')),
          'Lo que está en mal estado se registra como merma al costo del lote (0.5 x 18.00)');
CALL t_ok((SELECT estatus FROM ventas_cabecera WHERE id_venta = @va) = 'devuelta_parcial',
          'El ticket queda como devuelto en parte');
CALL t_ok(fn_efectivo_esperado(@caja) = 592.25, 'El reembolso en efectivo se resta del esperado (663.50 - 71.25)');

-- El resto del ticket: el importe cierra al centavo con lo cobrado
CALL sp_registrar_devolucion(@fa, @caja, 5, 1, 'El cliente cambió de opinión', 'efectivo',
  '[{"id_producto": 5, "cantidad": 0.5, "estado": "bueno"}]', @folio_dev2, @total_dev2);

CALL t_ok(@folio_dev2 = CONCAT('D', LPAD(@va, 8, '0'), '-2') AND @total_dev2 = 14.25,
          'La segunda devolución del ticket es la -2 y devuelve 14.25');
CALL t_ok((SELECT SUM(importe) FROM devoluciones WHERE id_venta = @va) = @ta,
          'La devolución total suma exactamente el total del ticket');
CALL t_ok((SELECT estatus FROM ventas_cabecera WHERE id_venta = @va) = 'devuelta', 'El ticket queda como devuelto');
SET @sql = CONCAT('CALL sp_registrar_devolucion(''', @fa, ''', @caja, 5, 1, ''x'', ''efectivo'', @r_jitomate, @f, @t)');
CALL t_espera_error(@sql, 'El ticket ya se devolvió por completo.', 'Un ticket devuelto no se devuelve otra vez');

-- Tarjeta: no toca el efectivo
CALL sp_registrar_devolucion(@fb, @caja, 5, 1, 'Producto equivocado', 'tarjeta',
  '[{"id_producto": 4, "cantidad": 1, "estado": "bueno"}]', @f, @total_tarjeta);
CALL t_ok(@total_tarjeta = 35.00 AND fn_efectivo_esperado(@caja) = 578.00,
          'El reverso a tarjeta no cambia el efectivo esperado');

-- Crédito: descuenta el saldo de la cuenta por cobrar (saldo 12.00 tras el abono)
SET @sql = CONCAT('CALL sp_registrar_devolucion(''', @fc, ''', @caja, 5, 1, ''x'', ''credito'', ''[{"id_producto": 2, "cantidad": 1, "estado": "bueno"}]'', @f, @t)');
CALL t_espera_error(@sql, 'La devolución supera el saldo pendiente del cliente.', 'El abono no puede pasar del saldo');
CALL sp_registrar_devolucion(@fc, @caja, 5, 1, 'Cobro incorrecto', 'credito',
  '[{"id_producto": 2, "cantidad": 0.5, "estado": "bueno"}]', @f, @total_credito);
CALL t_ok(@total_credito = 11.00 AND (SELECT saldo = 1.00 AND estatus = 'pendiente' FROM cuentas_por_cobrar WHERE id_cxc = @cxc),
          'La devolución a crédito baja el saldo del cliente de 12.00 a 1.00');

-- No sale más efectivo del que hay: caja del Administrador con fondo 0
CALL sp_abrir_caja('POS-04', 1, 0.00, @caja_admin);
SET @sql = CONCAT('CALL sp_registrar_devolucion(''', @fd, ''', @caja_admin, 1, 1, ''x'', ''efectivo'', ''[{"id_producto": 3, "cantidad": 1, "estado": "bueno"}]'', @f, @t)');
CALL t_espera_error(@sql, 'No hay suficiente efectivo en la caja para el reembolso.', 'No reembolsa más efectivo del que hay en la caja');

-- -----------------------------------------------------------------------------
-- sp_cerrar_caja (HU-09)
-- -----------------------------------------------------------------------------

CALL t_espera_error('CALL sp_cerrar_caja(@caja, 2, 578.00, NULL, @e, @d)', 'La caja no pertenece al usuario.',
                    'Un cajero no cierra la caja de otro');
CALL t_espera_error('CALL sp_cerrar_caja(@caja, 5, NULL, NULL, @e, @d)', 'Ingrese el efectivo contado.',
                    'Exige el efectivo contado');
CALL t_espera_error('CALL sp_cerrar_caja(@caja, 5, 570.00, ''  '', @e, @d)',
                    'Escriba las observaciones: hay diferencia en el arqueo.', 'Exige observaciones si hay diferencia');
CALL t_ok((SELECT estatus FROM cajas_pos WHERE id_caja = @caja) = 'abierta', 'El corte rechazado deja la caja abierta');

CALL sp_cerrar_caja(@caja, 5, 570.00, 'Faltan 8 pesos, cambio mal entregado', @esperado, @diferencia);
CALL t_ok(@esperado = 578.00 AND @diferencia = -8.00, 'Arqueo: esperado 578.00, contado 570.00, diferencia -8.00');
CALL t_ok((SELECT estatus = 'cerrada' AND fecha_cierre IS NOT NULL AND efectivo_esperado = 578.00
             AND efectivo_contado = 570.00 AND diferencia = -8.00 AND observaciones LIKE 'Faltan 8%'
           FROM cajas_pos WHERE id_caja = @caja),
          'El corte guarda esperado, contado, diferencia y observaciones');

CALL t_espera_error('CALL sp_registrar_venta(@caja, 5, 1, 100.00, NULL, ''[{"id_producto": 2, "cantidad": 1}]'', @a, @b, @c, @d)',
                    'No hay una caja abierta.', 'No se vende en una caja cortada');
CALL t_espera_error('CALL sp_cerrar_caja(@caja, 5, 578.00, NULL, @e, @d)', 'No hay una caja abierta.',
                    'Una caja no se corta dos veces');

-- La terminal queda libre y el mismo cajero abre otro turno; sin diferencia no pide observaciones
CALL sp_abrir_caja('POS-03', 5, 200.00, @caja2);
CALL sp_cerrar_caja(@caja2, 5, 200.00, '', @esperado2, @diferencia2);
CALL t_ok(@diferencia2 = 0.00 AND (SELECT observaciones IS NULL AND estatus = 'cerrada' FROM cajas_pos WHERE id_caja = @caja2),
          'Se reabre la terminal tras el corte y un arqueo exacto cierra sin observaciones');

CALL sp_cerrar_caja(@caja_admin, 1, 0.00, NULL, @e, @d);

SELECT 'Todas las pruebas de corte y devoluciones pasaron' AS resultado;

DROP PROCEDURE t_ok;
DROP PROCEDURE t_espera_error;
