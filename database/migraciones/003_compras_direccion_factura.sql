-- =============================================================================
-- Datos de Compras que captura la pantalla (HU-23, HU-11)
--
-- La pantalla de proveedores pide la dirección y la de registrar lote pide la
-- factura del proveedor; sin estas columnas se perdían.
--
-- Solo para bases ya instaladas: schema.sql ya incluye las columnas.
-- Se corre una vez:
--   mysql -h 127.0.0.1 -u root -p < database/migraciones/003_compras_direccion_factura.sql
-- =============================================================================

USE frutis;

ALTER TABLE proveedores
  ADD COLUMN direccion VARCHAR(200) NULL AFTER correo;

ALTER TABLE lotes_compras
  ADD COLUMN factura_proveedor VARCHAR(40) NULL COMMENT 'Folio de la factura o nota del proveedor' AFTER total;
