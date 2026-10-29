-- =============================================================================
-- sp_registrar_cobro · Abono de un cliente a una venta a crédito (SC-03, flujo N, HU-38)
--
-- En una sola transacción:
--   1. Bloquea la cuenta por cobrar y valida que el abono no supere el saldo.
--   2. Valida el método de pago (no puede ser crédito) y, si se indica, la caja abierta.
--   3. Registra el cobro en cobros_clientes y descuenta el saldo.
--   4. Cuando el saldo llega a cero, la cuenta pasa a "pagada".
--
-- p_id_caja es opcional: si el cobro se recibe en mostrador, se indica la caja
-- para que el efectivo entre al corte de ese turno.
--
-- Mensajes de error (SQLSTATE 45000):
--   'Ingrese un monto válido.' · 'Cuenta por cobrar no encontrada.'
--   'El cobro no puede ser mayor al saldo.' · 'Método de pago inválido para un cobro.'
--   'No hay una caja abierta.'
-- =============================================================================

USE frutis;

DROP PROCEDURE IF EXISTS sp_registrar_cobro;

DELIMITER $$

CREATE PROCEDURE sp_registrar_cobro(
  IN  p_id_cxc      INT UNSIGNED,
  IN  p_monto       DECIMAL(12,2),
  IN  p_id_metodo   TINYINT UNSIGNED,
  IN  p_id_caja     INT UNSIGNED,
  IN  p_id_usuario  INT UNSIGNED,
  OUT p_saldo       DECIMAL(12,2)
)
MODIFIES SQL DATA
COMMENT 'Abono a una cuenta por cobrar'
BEGIN
  DECLARE v_saldo         DECIMAL(12,2) DEFAULT NULL;
  DECLARE v_es_credito    BOOLEAN       DEFAULT NULL;
  DECLARE v_estatus_caja  VARCHAR(10)   DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  SET p_saldo = NULL;

  IF p_monto IS NULL OR p_monto <= 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Ingrese un monto válido.';
  END IF;

  START TRANSACTION;

  SELECT saldo INTO v_saldo
  FROM cuentas_por_cobrar
  WHERE id_cxc = p_id_cxc
  FOR UPDATE;

  IF v_saldo IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Cuenta por cobrar no encontrada.';
  END IF;

  IF p_monto > v_saldo THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El cobro no puede ser mayor al saldo.';
  END IF;

  SELECT es_credito INTO v_es_credito
  FROM metodos_pago
  WHERE id_metodo = p_id_metodo AND activo = TRUE;

  IF v_es_credito IS NULL OR v_es_credito THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Método de pago inválido para un cobro.';
  END IF;

  IF p_id_caja IS NOT NULL THEN
    SELECT estatus INTO v_estatus_caja
    FROM cajas_pos
    WHERE id_caja = p_id_caja
    FOR SHARE;

    IF v_estatus_caja IS NULL OR v_estatus_caja <> 'abierta' THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'No hay una caja abierta.';
    END IF;
  END IF;

  INSERT INTO cobros_clientes (id_cxc, monto, id_metodo, id_caja, id_usuario)
  VALUES (p_id_cxc, p_monto, p_id_metodo, p_id_caja, p_id_usuario);

  -- MySQL evalúa las asignaciones en orden: estatus ya ve el saldo nuevo
  UPDATE cuentas_por_cobrar
  SET saldo   = saldo - p_monto,
      estatus = IF(saldo = 0, 'pagada', 'pendiente')
  WHERE id_cxc = p_id_cxc;

  COMMIT;

  SET p_saldo = v_saldo - p_monto;
END$$

DELIMITER ;
