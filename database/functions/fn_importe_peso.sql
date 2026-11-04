-- =============================================================================
-- fn_importe_peso · Función escalar de la cotización (EC-08)
--
-- Devuelve el importe de una cantidad de producto al precio vigente:
--   importe = ROUND(cantidad x precio_venta, 2)
-- La cantidad es el peso en kg para productos por kilo o el número de piezas.
-- El precio incluye IVA. La usan sp_registrar_venta y los reportes, para que el
-- cálculo exista en un solo lugar.
-- =============================================================================

USE frutis;

DROP FUNCTION IF EXISTS fn_importe_peso;

DELIMITER $$

CREATE FUNCTION fn_importe_peso(p_id_producto INT UNSIGNED, p_cantidad DECIMAL(10,3))
RETURNS DECIMAL(12,2)
NOT DETERMINISTIC
READS SQL DATA
COMMENT 'Importe = cantidad x precio vigente, redondeado a 2 decimales'
BEGIN
  DECLARE v_precio DECIMAL(12,2) DEFAULT NULL;

  IF p_cantidad IS NULL OR p_cantidad <= 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Cantidad inválida.';
  END IF;

  SELECT precio_venta INTO v_precio
  FROM productos
  WHERE id_producto = p_id_producto AND activo = TRUE;

  IF v_precio IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Producto no encontrado o inactivo.';
  END IF;

  RETURN ROUND(p_cantidad * v_precio, 2);
END$$

DELIMITER ;
