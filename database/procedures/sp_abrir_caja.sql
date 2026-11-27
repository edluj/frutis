-- =============================================================================
-- sp_abrir_caja · Apertura de un turno de caja (flujo D, HU-15)
--
-- Registra cajero, terminal, fondo inicial y fecha/hora de apertura.
-- Reglas:
--   * Una sola caja abierta por terminal (índice único uq_cajas_terminal_abierta).
--   * Un cajero no puede tener dos turnos abiertos a la vez: se bloquea su fila
--     en `usuarios` para que dos aperturas simultáneas no pasen las dos.
--
-- Mensajes de error (SQLSTATE 45000):
--   'Ingrese un fondo inicial válido.' · 'Terminal inválida.'
--   'Usuario no encontrado o inactivo.' · 'Ya tiene una caja abierta en la terminal <t>.'
--   'Ya hay una caja abierta en esta terminal.'
-- =============================================================================

USE frutis;

DROP PROCEDURE IF EXISTS sp_abrir_caja;

DELIMITER $$

CREATE PROCEDURE sp_abrir_caja(
  IN  p_terminal    VARCHAR(30),
  IN  p_id_usuario  INT UNSIGNED,
  IN  p_fondo       DECIMAL(12,2),
  OUT p_id_caja     INT UNSIGNED
)
MODIFIES SQL DATA
COMMENT 'Abre un turno de caja con su fondo inicial'
BEGIN
  DECLARE v_activo    BOOLEAN     DEFAULT NULL;
  DECLARE v_terminal  VARCHAR(30) DEFAULT NULL;
  DECLARE v_mensaje   VARCHAR(128) DEFAULT NULL;

  -- Otra terminal ganó la carrera por el índice único de caja abierta
  DECLARE EXIT HANDLER FOR 1062
  BEGIN
    ROLLBACK;
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Ya hay una caja abierta en esta terminal.';
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  SET p_id_caja = NULL;

  IF p_fondo IS NULL OR p_fondo < 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Ingrese un fondo inicial válido.';
  END IF;

  IF p_terminal IS NULL OR CHAR_LENGTH(TRIM(p_terminal)) = 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Terminal inválida.';
  END IF;

  START TRANSACTION;

  SELECT activo INTO v_activo
  FROM usuarios
  WHERE id_usuario = p_id_usuario
  FOR UPDATE;

  IF v_activo IS NULL OR NOT v_activo THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Usuario no encontrado o inactivo.';
  END IF;

  SELECT terminal INTO v_terminal
  FROM cajas_pos
  WHERE id_usuario = p_id_usuario AND estatus = 'abierta'
  LIMIT 1;

  IF v_terminal IS NOT NULL THEN
    SET v_mensaje = LEFT(CONCAT('Ya tiene una caja abierta en la terminal ', v_terminal, '.'), 128);
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_mensaje;
  END IF;

  INSERT INTO cajas_pos (terminal, id_usuario, fondo_inicial)
  VALUES (TRIM(p_terminal), p_id_usuario, p_fondo);

  SET p_id_caja = LAST_INSERT_ID();

  COMMIT;
END$$

DELIMITER ;
