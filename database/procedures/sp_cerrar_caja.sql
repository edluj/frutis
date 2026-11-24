-- =============================================================================
-- sp_cerrar_caja · Corte de caja con arqueo (flujo D, HU-09)
--
-- En una sola transacción:
--   1. Bloquea el turno. Los cobros y devoluciones en curso lo leen con FOR SHARE,
--      así que el corte espera a que terminen y después ya no entra ninguno.
--   2. Calcula el efectivo esperado con fn_efectivo_esperado y la diferencia
--      contra lo contado.
--   3. Exige observaciones si hay diferencia y cierra la caja.
--
-- Mensajes de error (SQLSTATE 45000):
--   'Ingrese el efectivo contado.' · 'No hay una caja abierta.'
--   'La caja no pertenece al usuario.'
--   'Escriba las observaciones: hay diferencia en el arqueo.'
-- =============================================================================

USE frutis;

DROP PROCEDURE IF EXISTS sp_cerrar_caja;

DELIMITER $$

CREATE PROCEDURE sp_cerrar_caja(
  IN  p_id_caja        INT UNSIGNED,
  IN  p_id_usuario     INT UNSIGNED,
  IN  p_contado        DECIMAL(12,2),
  IN  p_observaciones  VARCHAR(255),
  OUT p_esperado       DECIMAL(12,2),
  OUT p_diferencia     DECIMAL(12,2)
)
MODIFIES SQL DATA
COMMENT 'Arqueo y cierre de un turno de caja'
BEGIN
  DECLARE v_estatus        VARCHAR(10)  DEFAULT NULL;
  DECLARE v_usuario        INT UNSIGNED DEFAULT NULL;
  DECLARE v_observaciones  VARCHAR(255) DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  SET p_esperado = NULL, p_diferencia = NULL;

  IF p_contado IS NULL OR p_contado < 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Ingrese el efectivo contado.';
  END IF;

  START TRANSACTION;

  SELECT estatus, id_usuario INTO v_estatus, v_usuario
  FROM cajas_pos
  WHERE id_caja = p_id_caja
  FOR UPDATE;

  IF v_estatus IS NULL OR v_estatus <> 'abierta' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'No hay una caja abierta.';
  END IF;

  IF v_usuario <> p_id_usuario THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La caja no pertenece al usuario.';
  END IF;

  SET p_esperado = fn_efectivo_esperado(p_id_caja);
  SET p_diferencia = p_contado - p_esperado;
  SET v_observaciones = NULLIF(TRIM(p_observaciones), '');

  IF p_diferencia <> 0 AND v_observaciones IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Escriba las observaciones: hay diferencia en el arqueo.';
  END IF;

  UPDATE cajas_pos
  SET fecha_cierre      = NOW(),
      efectivo_esperado = p_esperado,
      efectivo_contado  = p_contado,
      diferencia        = p_diferencia,
      observaciones     = v_observaciones,
      estatus           = 'cerrada'
  WHERE id_caja = p_id_caja;

  COMMIT;
END$$

DELIMITER ;
