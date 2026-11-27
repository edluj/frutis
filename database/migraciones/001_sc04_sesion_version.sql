-- =============================================================================
-- SC-04 (#14) · Cerrar sesión invalida el token (HU-14)
--
-- Solo para bases ya instaladas: schema.sql ya incluye la columna.
-- Se corre una vez:
--   mysql -h 127.0.0.1 -u root -p < database/migraciones/001_sc04_sesion_version.sql
-- =============================================================================

USE frutis;

ALTER TABLE usuarios
  ADD COLUMN sesion_version INT UNSIGNED NOT NULL DEFAULT 0
    COMMENT 'Sube al cerrar sesión e invalida los tokens anteriores (SC-04)'
    AFTER ultimo_acceso;
