-- =============================================================================
-- Motivo "Plaga u hongo" en las mermas (HU-17)
--
-- La pantalla de mermas (CAT-08) ofrece ese motivo y la base no lo tenía.
-- Agregar un valor al final del ENUM no cambia los registros existentes.
--
-- Solo para bases ya instaladas: schema.sql ya incluye el valor.
-- Se corre una vez:
--   mysql -h 127.0.0.1 -u root -p < database/migraciones/004_mermas_motivo_plaga.sql
-- =============================================================================

-- Aplicada si: SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = 'frutis' AND table_name = 'mermas' AND column_name = 'motivo' AND column_type LIKE '%''plaga''%'

USE frutis;

ALTER TABLE mermas
  MODIFY COLUMN motivo ENUM('maduracion','golpe','caducidad','devolucion','otro','plaga') NOT NULL;
