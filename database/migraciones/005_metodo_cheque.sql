-- =============================================================================
-- Método de pago "Cheque" para pagar a proveedores (HU-25)
--
-- La pantalla de cuentas por pagar ofrece Transferencia, Efectivo y Cheque; los pagos
-- se guardan en gastos_operativos con su método. Queda inactivo para que no aparezca
-- en la caja del POS.
--
-- Solo para bases ya instaladas con datos: seed.sql ya lo incluye.
-- Se corre una vez:
--   mysql -h 127.0.0.1 -u root -p < database/migraciones/005_metodo_cheque.sql
-- =============================================================================

-- Aplicada si: SELECT COUNT(*) FROM frutis.metodos_pago WHERE nombre = 'Cheque'
USE frutis;

INSERT INTO metodos_pago (nombre, clave_sat, es_efectivo, es_credito, activo)
SELECT 'Cheque', '02', FALSE, FALSE, FALSE
WHERE NOT EXISTS (SELECT 1 FROM metodos_pago WHERE nombre = 'Cheque');
