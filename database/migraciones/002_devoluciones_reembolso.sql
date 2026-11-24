-- =============================================================================
-- Forma de reembolso de las devoluciones (HU-09, HU-30)
--
-- El corte de caja resta las devoluciones pagadas en efectivo; sin esta columna
-- no se sabe cuáles fueron en efectivo.
--
-- Solo para bases ya instaladas: schema.sql ya incluye la columna.
-- Se corre una vez y después se instalan la función y los procedimientos nuevos:
--   mysql -h 127.0.0.1 -u root -p < database/migraciones/002_devoluciones_reembolso.sql
--   mysql -h 127.0.0.1 -u root -p < database/functions/fn_efectivo_esperado.sql
--   mysql -h 127.0.0.1 -u root -p < database/procedures/sp_abrir_caja.sql
--   mysql -h 127.0.0.1 -u root -p < database/procedures/sp_cerrar_caja.sql
--   mysql -h 127.0.0.1 -u root -p < database/procedures/sp_registrar_devolucion.sql
--
-- Las devoluciones que ya existían quedan como "efectivo", que era lo único que
-- se podía registrar en caja.
-- =============================================================================

USE frutis;

ALTER TABLE devoluciones
  ADD COLUMN reembolso ENUM('efectivo','tarjeta','transferencia','credito') NOT NULL DEFAULT 'efectivo'
    COMMENT 'efectivo sale de la caja y entra al corte; credito descuenta la cuenta por cobrar'
    AFTER estado_producto,
  ADD INDEX idx_devoluciones_caja (id_caja, reembolso);

ALTER TABLE devoluciones ALTER COLUMN reembolso DROP DEFAULT;
