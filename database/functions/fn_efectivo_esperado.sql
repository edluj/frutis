-- =============================================================================
-- fn_efectivo_esperado · Efectivo que debe haber en el cajón de un turno (HU-09)
--
--   fondo inicial
--   + ventas en efectivo (las canceladas no cuentan; las devueltas sí, porque la
--     devolución se resta aparte)
--   + cobros a clientes de crédito recibidos en efectivo en esa caja (SC-03)
--   - devoluciones reembolsadas en efectivo desde esa caja
--
-- La usan sp_cerrar_caja, sp_registrar_devolucion y el resumen del corte en el
-- middleware, para que el cálculo exista en un solo lugar.
-- =============================================================================

USE frutis;

DROP FUNCTION IF EXISTS fn_efectivo_esperado;

DELIMITER $$

CREATE FUNCTION fn_efectivo_esperado(p_id_caja INT UNSIGNED)
RETURNS DECIMAL(12,2)
NOT DETERMINISTIC
READS SQL DATA
COMMENT 'Fondo + ventas y cobros en efectivo - devoluciones en efectivo'
BEGIN
  DECLARE v_fondo       DECIMAL(12,2) DEFAULT NULL;
  DECLARE v_ventas      DECIMAL(12,2) DEFAULT 0;
  DECLARE v_cobros      DECIMAL(12,2) DEFAULT 0;
  DECLARE v_devuelto    DECIMAL(12,2) DEFAULT 0;

  SELECT fondo_inicial INTO v_fondo FROM cajas_pos WHERE id_caja = p_id_caja;

  IF v_fondo IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'No hay una caja abierta.';
  END IF;

  SELECT COALESCE(SUM(v.total), 0) INTO v_ventas
  FROM ventas_cabecera v
  JOIN metodos_pago m ON m.id_metodo = v.id_metodo
  WHERE v.id_caja = p_id_caja AND m.es_efectivo = TRUE AND v.estatus <> 'cancelada';

  SELECT COALESCE(SUM(c.monto), 0) INTO v_cobros
  FROM cobros_clientes c
  JOIN metodos_pago m ON m.id_metodo = c.id_metodo
  WHERE c.id_caja = p_id_caja AND m.es_efectivo = TRUE;

  SELECT COALESCE(SUM(importe), 0) INTO v_devuelto
  FROM devoluciones
  WHERE id_caja = p_id_caja AND reembolso = 'efectivo';

  RETURN v_fondo + v_ventas + v_cobros - v_devuelto;
END$$

DELIMITER ;
