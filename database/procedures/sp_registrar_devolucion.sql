-- =============================================================================
-- sp_registrar_devolucion · Devolución parcial o total de un ticket (flujo E, HU-30)
--
-- En una sola transacción:
--   1. Valida la caja abierta donde se entrega el reembolso y el ticket (vigente:
--      ni cancelado ni devuelto por completo). El ticket queda bloqueado, así que
--      dos devoluciones del mismo ticket no pueden pasar a la vez.
--   2. Valida que no se devuelva más de lo vendido menos lo ya devuelto.
--   3. Reparte cada renglón entre los lotes de los que salió la venta y escribe
--      una fila de `devoluciones` por lote:
--        * buen estado: la cantidad regresa a ese lote del inventario;
--        * mal estado: se registra como merma del lote (el producto ya había
--          salido del inventario con la venta, así que no se descuenta otra vez).
--   4. Reembolso:
--        * efectivo: sale del cajón y se resta en el corte (fn_efectivo_esperado);
--        * credito: descuenta el saldo de la cuenta por cobrar de la venta (SC-03);
--        * tarjeta: solo para tickets pagados con tarjeta (claves SAT 04 y 28).
--   5. Marca el ticket como 'devuelta' o 'devuelta_parcial'.
--
-- Quien autoriza debe ser Administrador activo: lo exigen los triggers
-- trg_devoluciones_autoriza_* (SC-02), no solo el middleware.
--
-- p_renglones: [{"id_producto": 1, "cantidad": 0.500, "estado": "bueno"|"danado"}, ...]
-- Folio de la devolución: D + id de la venta + número de devolución de ese ticket,
-- por ejemplo D00000009-1.
--
-- Mensajes de error (SQLSTATE 45000):
--   'Marque al menos un producto.' · 'Escriba el motivo de la devolución.'
--   'Forma de reembolso inválida.' · 'No hay una caja abierta.'
--   'No existe un ticket con ese número.' · 'El ticket está cancelado.'
--   'El ticket ya se devolvió por completo.'
--   'Una venta a crédito se reembolsa como abono a su cuenta.'
--   'Solo una venta a crédito se reembolsa como abono.'
--   'El ticket no se pagó con tarjeta.' · 'Cantidad inválida.'
--   'Estado del producto inválido.' · 'La cantidad a devolver de <producto> no es válida.'
--   'No hay suficiente efectivo en la caja para el reembolso.'
--   'La devolución supera el saldo pendiente del cliente.'
--   'Solo un Administrador puede autorizar devoluciones.' (trigger)
-- =============================================================================

USE frutis;

DROP PROCEDURE IF EXISTS sp_registrar_devolucion;

DELIMITER $$

CREATE PROCEDURE sp_registrar_devolucion(
  IN  p_folio_venta  VARCHAR(20),
  IN  p_id_caja      INT UNSIGNED,
  IN  p_id_usuario   INT UNSIGNED,
  IN  p_id_autoriza  INT UNSIGNED,
  IN  p_motivo       VARCHAR(200),
  IN  p_reembolso    VARCHAR(15),
  IN  p_renglones    JSON,
  OUT p_folio        VARCHAR(20),
  OUT p_total        DECIMAL(12,2)
)
MODIFIES SQL DATA
COMMENT 'Devolución con reingreso al inventario o merma y reembolso'
BEGIN
  DECLARE v_estatus_caja   VARCHAR(10)     DEFAULT NULL;
  DECLARE v_id_venta       INT UNSIGNED    DEFAULT NULL;
  DECLARE v_estatus_venta  VARCHAR(20)     DEFAULT NULL;
  DECLARE v_es_credito     BOOLEAN         DEFAULT FALSE;
  DECLARE v_clave_sat      CHAR(2)         DEFAULT NULL;
  DECLARE v_motivo         VARCHAR(200)    DEFAULT NULL;
  DECLARE v_numero         INT UNSIGNED    DEFAULT 0;
  DECLARE v_renglon        INT UNSIGNED    DEFAULT NULL;
  DECLARE v_ultimo         INT UNSIGNED    DEFAULT 0;
  DECLARE v_producto       INT UNSIGNED    DEFAULT NULL;
  DECLARE v_pendiente      DECIMAL(10,3)   DEFAULT 0;
  DECLARE v_estado         VARCHAR(10)     DEFAULT NULL;
  DECLARE v_detalle        BIGINT UNSIGNED DEFAULT NULL;
  DECLARE v_inventario     INT UNSIGNED    DEFAULT NULL;
  DECLARE v_restante       DECIMAL(10,3)   DEFAULT 0;
  DECLARE v_importe_rest   DECIMAL(12,2)   DEFAULT 0;
  DECLARE v_precio         DECIMAL(12,2)   DEFAULT 0;
  DECLARE v_costo          DECIMAL(12,2)   DEFAULT 0;
  DECLARE v_tomar          DECIMAL(10,3)   DEFAULT 0;
  DECLARE v_importe        DECIMAL(12,2)   DEFAULT 0;
  DECLARE v_total          DECIMAL(12,2)   DEFAULT 0;
  DECLARE v_id_cxc         INT UNSIGNED    DEFAULT NULL;
  DECLARE v_saldo          DECIMAL(12,2)   DEFAULT NULL;
  DECLARE v_nombre         VARCHAR(120)    DEFAULT NULL;
  DECLARE v_mensaje        VARCHAR(128)    DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    DROP TEMPORARY TABLE IF EXISTS tmp_devolucion;
    RESIGNAL;
  END;

  SET p_folio = NULL, p_total = NULL;
  SET v_motivo = NULLIF(TRIM(p_motivo), '');

  IF p_renglones IS NULL OR JSON_TYPE(p_renglones) <> 'ARRAY' OR JSON_LENGTH(p_renglones) = 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Marque al menos un producto.';
  END IF;

  IF v_motivo IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Escriba el motivo de la devolución.';
  END IF;

  IF p_reembolso IS NULL OR p_reembolso NOT IN ('efectivo', 'tarjeta', 'transferencia', 'credito') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Forma de reembolso inválida.';
  END IF;

  START TRANSACTION;

  -- 1. Caja y ticket
  SELECT estatus INTO v_estatus_caja
  FROM cajas_pos
  WHERE id_caja = p_id_caja
  FOR SHARE;

  IF v_estatus_caja IS NULL OR v_estatus_caja <> 'abierta' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'No hay una caja abierta.';
  END IF;

  SELECT v.id_venta, v.estatus, m.es_credito, m.clave_sat
    INTO v_id_venta, v_estatus_venta, v_es_credito, v_clave_sat
  FROM ventas_cabecera v
  JOIN metodos_pago m ON m.id_metodo = v.id_metodo
  WHERE v.folio = p_folio_venta
  FOR UPDATE OF v;

  IF v_id_venta IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'No existe un ticket con ese número.';
  END IF;

  IF v_estatus_venta = 'cancelada' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El ticket está cancelado.';
  END IF;

  IF v_estatus_venta = 'devuelta' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El ticket ya se devolvió por completo.';
  END IF;

  -- 2. Forma de reembolso según cómo se pagó el ticket
  IF v_es_credito AND p_reembolso <> 'credito' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Una venta a crédito se reembolsa como abono a su cuenta.';
  END IF;

  IF NOT v_es_credito AND p_reembolso = 'credito' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Solo una venta a crédito se reembolsa como abono.';
  END IF;

  IF p_reembolso = 'tarjeta' AND v_clave_sat NOT IN ('04', '28') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El ticket no se pagó con tarjeta.';
  END IF;

  -- 3. Renglones
  DROP TEMPORARY TABLE IF EXISTS tmp_devolucion;
  CREATE TEMPORARY TABLE tmp_devolucion (
    n            INT UNSIGNED  NOT NULL AUTO_INCREMENT PRIMARY KEY,
    id_producto  INT UNSIGNED  NOT NULL,
    cantidad     DECIMAL(10,3) NULL,
    estado       VARCHAR(10)   NULL
  ) ENGINE=MEMORY;

  INSERT INTO tmp_devolucion (id_producto, cantidad, estado)
  SELECT jt.id_producto, jt.cantidad, jt.estado
  FROM JSON_TABLE(
         p_renglones, '$[*]'
         COLUMNS (
           id_producto INT UNSIGNED  PATH '$.id_producto' ERROR ON EMPTY ERROR ON ERROR,
           cantidad    DECIMAL(10,3) PATH '$.cantidad'    ERROR ON EMPTY ERROR ON ERROR,
           estado      VARCHAR(10)   PATH '$.estado'      ERROR ON EMPTY ERROR ON ERROR
         )
       ) AS jt;

  IF EXISTS (SELECT 1 FROM tmp_devolucion WHERE cantidad IS NULL OR cantidad <= 0) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Cantidad inválida.';
  END IF;

  IF EXISTS (SELECT 1 FROM tmp_devolucion WHERE estado IS NULL OR estado NOT IN ('bueno', 'danado')) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Estado del producto inválido.';
  END IF;

  -- Por producto: lo pedido no puede pasar de lo vendido menos lo ya devuelto,
  -- y las piezas van enteras. Un producto que no está en el ticket tiene 0 vendido.
  SELECT COALESCE(p.nombre, CONCAT('el producto ', t.id_producto)) INTO v_nombre
  FROM (SELECT id_producto, SUM(cantidad) AS cantidad FROM tmp_devolucion GROUP BY id_producto) t
  LEFT JOIN productos p ON p.id_producto = t.id_producto
  LEFT JOIN (
    SELECT id_producto, SUM(cantidad) AS vendido
    FROM ventas_detalle WHERE id_venta = v_id_venta GROUP BY id_producto
  ) s ON s.id_producto = t.id_producto
  LEFT JOIN (
    SELECT d.id_producto, SUM(x.cantidad) AS devuelto
    FROM devoluciones x JOIN ventas_detalle d ON d.id_detalle = x.id_detalle
    WHERE x.id_venta = v_id_venta GROUP BY d.id_producto
  ) r ON r.id_producto = t.id_producto
  WHERE t.cantidad > COALESCE(s.vendido, 0) - COALESCE(r.devuelto, 0)
     OR (p.unidad_venta = 'pieza' AND t.cantidad <> FLOOR(t.cantidad))
  ORDER BY t.id_producto
  LIMIT 1;

  IF v_nombre IS NOT NULL THEN
    SET v_mensaje = LEFT(CONCAT('La cantidad a devolver de ', v_nombre, ' no es válida.'), 128);
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_mensaje;
  END IF;

  SELECT COUNT(DISTINCT folio) + 1 INTO v_numero FROM devoluciones WHERE id_venta = v_id_venta;
  SET p_folio = CONCAT('D', LPAD(v_id_venta, 8, '0'), '-', v_numero);

  -- 4. Una fila por lote; primero el último renglón de la venta
  renglones_loop: LOOP
    SET v_renglon = NULL;
    SELECT MIN(n) INTO v_renglon FROM tmp_devolucion WHERE n > v_ultimo;
    IF v_renglon IS NULL THEN
      LEAVE renglones_loop;
    END IF;
    SET v_ultimo = v_renglon;

    SELECT id_producto, cantidad, estado INTO v_producto, v_pendiente, v_estado
    FROM tmp_devolucion WHERE n = v_renglon;

    lotes_loop: WHILE v_pendiente > 0 DO
      SET v_detalle = NULL;

      SELECT d.id_detalle, d.id_inventario, d.precio_unitario, d.costo_unitario,
             d.cantidad - COALESCE(SUM(x.cantidad), 0) AS restante,
             d.importe - COALESCE(SUM(x.importe), 0) AS importe_restante
        INTO v_detalle, v_inventario, v_precio, v_costo, v_restante, v_importe_rest
      FROM ventas_detalle d
      LEFT JOIN devoluciones x ON x.id_detalle = d.id_detalle
      WHERE d.id_venta = v_id_venta AND d.id_producto = v_producto
      GROUP BY d.id_detalle
      HAVING restante > 0
      ORDER BY d.id_detalle DESC
      LIMIT 1;

      IF v_detalle IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Cantidad inválida.';
      END IF;

      SET v_tomar = LEAST(v_restante, v_pendiente);
      -- Si se devuelve todo lo que queda del renglón, se regresa justo lo que falta
      -- del importe; así una devolución total cuadra al centavo con el ticket.
      SET v_importe = IF(v_tomar = v_restante, v_importe_rest, ROUND(v_tomar * v_precio, 2));

      INSERT INTO devoluciones
        (folio, id_venta, id_detalle, id_caja, cantidad, importe, motivo, estado_producto, reembolso,
         id_usuario, id_autoriza)
      VALUES
        (p_folio, v_id_venta, v_detalle, p_id_caja, v_tomar, v_importe, v_motivo, v_estado, p_reembolso,
         p_id_usuario, p_id_autoriza);

      IF v_estado = 'bueno' THEN
        UPDATE inventario
        SET cantidad_disponible = cantidad_disponible + v_tomar
        WHERE id_inventario = v_inventario;
      ELSE
        INSERT INTO mermas (id_inventario, cantidad, motivo, costo_total, observaciones, id_usuario)
        VALUES (v_inventario, v_tomar, 'devolucion', ROUND(v_tomar * v_costo, 2),
                LEFT(CONCAT('Devolución ', p_folio, ': ', v_motivo), 255), p_id_usuario);
      END IF;

      SET v_total = v_total + v_importe;
      SET v_pendiente = v_pendiente - v_tomar;
    END WHILE lotes_loop;
  END LOOP renglones_loop;

  -- 5. Reembolso
  IF p_reembolso = 'efectivo' AND fn_efectivo_esperado(p_id_caja) < 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'No hay suficiente efectivo en la caja para el reembolso.';
  END IF;

  IF p_reembolso = 'credito' THEN
    SELECT id_cxc, saldo INTO v_id_cxc, v_saldo
    FROM cuentas_por_cobrar
    WHERE id_venta = v_id_venta
    FOR UPDATE;

    IF v_saldo IS NULL OR v_saldo < v_total THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La devolución supera el saldo pendiente del cliente.';
    END IF;

    -- MySQL evalúa las asignaciones en orden: estatus ya ve el saldo nuevo
    UPDATE cuentas_por_cobrar
    SET saldo   = saldo - v_total,
        estatus = IF(saldo = 0, 'pagada', 'pendiente')
    WHERE id_cxc = v_id_cxc;
  END IF;

  -- 6. Estatus del ticket
  UPDATE ventas_cabecera
  SET estatus = IF(
        (SELECT SUM(cantidad) FROM ventas_detalle WHERE id_venta = v_id_venta)
          <= (SELECT SUM(cantidad) FROM devoluciones WHERE id_venta = v_id_venta),
        'devuelta', 'devuelta_parcial')
  WHERE id_venta = v_id_venta;

  COMMIT;
  DROP TEMPORARY TABLE IF EXISTS tmp_devolucion;

  SET p_total = v_total;
END$$

DELIMITER ;
