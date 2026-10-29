-- =============================================================================
-- sp_registrar_venta · Stored Procedure de la cotización (EC-08, HU-02)
--
-- Registra un cobro completo en una sola transacción (ACID):
--   1. Valida caja abierta, método de pago y carrito.
--   2. Inserta ventas_cabecera.
--   3. Descuenta inventario por lote, primero el que caduca antes (FEFO), y
--      escribe un renglón de ventas_detalle por cada lote usado.
--   4. Calcula subtotal, IVA, total y cambio; valida el monto recibido.
--   5. COMMIT. Ante cualquier error hace ROLLBACK y devuelve el mensaje.
--
-- Entrada:
--   p_carrito  JSON con los renglones: [{"id_producto": 1, "cantidad": 1.250}, ...]
--              cantidad = kg para productos por kilo, piezas para productos por pieza.
--   p_monto_recibido  efectivo entregado por el cliente; se ignora en pagos que no son en efectivo.
--
-- Mensajes de error (SQLSTATE 45000), los mismos del APR flujo C:
--   'El carrito está vacío.' · 'No hay una caja abierta.' · 'Método de pago inválido.'
--   'Cantidad inválida.' · 'Producto no encontrado o inactivo.'
--   'Los productos por pieza se venden en cantidades enteras.'
--   'Producto sin existencia suficiente: <nombre>' · 'El monto recibido es insuficiente.'
-- =============================================================================

USE frutis;

DROP PROCEDURE IF EXISTS sp_registrar_venta;

DELIMITER $$

CREATE PROCEDURE sp_registrar_venta(
  IN  p_id_caja         INT UNSIGNED,
  IN  p_id_usuario      INT UNSIGNED,
  IN  p_id_metodo       TINYINT UNSIGNED,
  IN  p_monto_recibido  DECIMAL(12,2),
  IN  p_carrito         JSON,
  OUT p_id_venta        INT UNSIGNED,
  OUT p_folio           VARCHAR(20),
  OUT p_total           DECIMAL(12,2),
  OUT p_cambio          DECIMAL(12,2)
)
MODIFIES SQL DATA
COMMENT 'Cobro POS transaccional con descuento FEFO por lote'
BEGIN
  DECLARE v_estatus_caja  VARCHAR(10)      DEFAULT NULL;
  DECLARE v_es_efectivo   BOOLEAN          DEFAULT NULL;
  DECLARE v_producto      INT UNSIGNED     DEFAULT 0;
  DECLARE v_ultimo        INT UNSIGNED     DEFAULT 0;
  DECLARE v_pendiente     DECIMAL(10,3)    DEFAULT 0;
  DECLARE v_inventario    INT UNSIGNED     DEFAULT NULL;
  DECLARE v_disponible    DECIMAL(10,3)    DEFAULT 0;
  DECLARE v_costo         DECIMAL(12,2)    DEFAULT 0;
  DECLARE v_tomar         DECIMAL(10,3)    DEFAULT 0;
  DECLARE v_precio        DECIMAL(12,2)    DEFAULT 0;
  DECLARE v_tasa          DECIMAL(5,4)     DEFAULT 0;
  DECLARE v_total         DECIMAL(12,2)    DEFAULT 0;
  DECLARE v_iva           DECIMAL(12,2)    DEFAULT 0;
  DECLARE v_recibido      DECIMAL(12,2)    DEFAULT 0;
  DECLARE v_nombre        VARCHAR(120)     DEFAULT NULL;
  DECLARE v_mensaje       VARCHAR(128)     DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    DROP TEMPORARY TABLE IF EXISTS tmp_carrito;
    RESIGNAL;
  END;

  SET p_id_venta = NULL, p_folio = NULL, p_total = NULL, p_cambio = NULL;

  IF p_carrito IS NULL OR JSON_TYPE(p_carrito) <> 'ARRAY' OR JSON_LENGTH(p_carrito) = 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El carrito está vacío.';
  END IF;

  START TRANSACTION;

  -- 1. Caja abierta y método de pago
  SELECT estatus INTO v_estatus_caja
  FROM cajas_pos
  WHERE id_caja = p_id_caja
  FOR SHARE;

  IF v_estatus_caja IS NULL OR v_estatus_caja <> 'abierta' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'No hay una caja abierta.';
  END IF;

  SELECT es_efectivo INTO v_es_efectivo
  FROM metodos_pago
  WHERE id_metodo = p_id_metodo AND activo = TRUE;

  IF v_es_efectivo IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Método de pago inválido.';
  END IF;

  -- 2. Carrito: un renglón por producto (suma cantidades repetidas)
  DROP TEMPORARY TABLE IF EXISTS tmp_carrito;
  CREATE TEMPORARY TABLE tmp_carrito (
    id_producto INT UNSIGNED  NOT NULL PRIMARY KEY,
    cantidad    DECIMAL(10,3) NULL
  ) ENGINE=MEMORY;

  INSERT INTO tmp_carrito (id_producto, cantidad)
  SELECT jt.id_producto, SUM(jt.cantidad)
  FROM JSON_TABLE(
         p_carrito, '$[*]'
         COLUMNS (
           id_producto INT UNSIGNED  PATH '$.id_producto' ERROR ON EMPTY ERROR ON ERROR,
           cantidad    DECIMAL(10,3) PATH '$.cantidad'    ERROR ON EMPTY ERROR ON ERROR
         )
       ) AS jt
  GROUP BY jt.id_producto;

  IF EXISTS (SELECT 1 FROM tmp_carrito WHERE cantidad IS NULL OR cantidad <= 0) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Cantidad inválida.';
  END IF;

  IF EXISTS (
    SELECT 1 FROM tmp_carrito t
    LEFT JOIN productos p ON p.id_producto = t.id_producto AND p.activo = TRUE
    WHERE p.id_producto IS NULL
  ) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Producto no encontrado o inactivo.';
  END IF;

  IF EXISTS (
    SELECT 1 FROM tmp_carrito t
    JOIN productos p ON p.id_producto = t.id_producto
    WHERE p.unidad_venta = 'pieza' AND t.cantidad <> FLOOR(t.cantidad)
  ) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Los productos por pieza se venden en cantidades enteras.';
  END IF;

  -- 3. Cabecera (los importes se completan al final)
  INSERT INTO ventas_cabecera (id_caja, id_usuario, id_metodo)
  VALUES (p_id_caja, p_id_usuario, p_id_metodo);

  SET p_id_venta = LAST_INSERT_ID();
  SET p_folio = CONCAT('V', LPAD(p_id_venta, 8, '0'));

  -- 4. Descuento FEFO por producto, en orden de id para evitar bloqueos cruzados
  productos_loop: LOOP
    SET v_producto = NULL;
    SELECT MIN(id_producto) INTO v_producto FROM tmp_carrito WHERE id_producto > v_ultimo;
    IF v_producto IS NULL THEN
      LEAVE productos_loop;
    END IF;
    SET v_ultimo = v_producto;

    SELECT cantidad INTO v_pendiente FROM tmp_carrito WHERE id_producto = v_producto;
    SELECT precio_venta, tasa_iva, nombre INTO v_precio, v_tasa, v_nombre
    FROM productos WHERE id_producto = v_producto;

    lotes_loop: WHILE v_pendiente > 0 DO
      SET v_inventario = NULL;

      SELECT id_inventario, cantidad_disponible, costo_unitario
        INTO v_inventario, v_disponible, v_costo
      FROM inventario
      WHERE id_producto = v_producto AND cantidad_disponible > 0
      ORDER BY fecha_caducidad, id_inventario
      LIMIT 1
      FOR UPDATE;

      IF v_inventario IS NULL THEN
        SET v_mensaje = LEFT(CONCAT('Producto sin existencia suficiente: ', v_nombre), 128);
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_mensaje;
      END IF;

      SET v_tomar = LEAST(v_disponible, v_pendiente);

      UPDATE inventario
      SET cantidad_disponible = cantidad_disponible - v_tomar
      WHERE id_inventario = v_inventario;

      INSERT INTO ventas_detalle
        (id_venta, id_producto, id_inventario, cantidad, precio_unitario, importe, tasa_iva, costo_unitario)
      VALUES
        (p_id_venta, v_producto, v_inventario, v_tomar, v_precio,
         fn_importe_peso(v_producto, v_tomar), v_tasa, v_costo);

      SET v_pendiente = v_pendiente - v_tomar;
    END WHILE lotes_loop;
  END LOOP productos_loop;

  -- 5. Totales y monto recibido (precios con IVA incluido)
  SELECT COALESCE(SUM(importe), 0),
         COALESCE(ROUND(SUM(importe - importe / (1 + tasa_iva)), 2), 0)
    INTO v_total, v_iva
  FROM ventas_detalle
  WHERE id_venta = p_id_venta;

  IF v_es_efectivo THEN
    IF p_monto_recibido IS NULL OR p_monto_recibido < v_total THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El monto recibido es insuficiente.';
    END IF;
    SET v_recibido = p_monto_recibido;
  ELSE
    SET v_recibido = v_total;
  END IF;

  UPDATE ventas_cabecera
  SET folio          = p_folio,
      subtotal       = v_total - v_iva,
      iva            = v_iva,
      total          = v_total,
      monto_recibido = v_recibido,
      cambio         = v_recibido - v_total
  WHERE id_venta = p_id_venta;

  COMMIT;
  DROP TEMPORARY TABLE IF EXISTS tmp_carrito;

  SET p_total  = v_total;
  SET p_cambio = v_recibido - v_total;
END$$

DELIMITER ;
