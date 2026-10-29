# database · EC-08

Scripts de MySQL 8 (InnoDB).

| Archivo | Contenido |
| --- | --- |
| `schema.sql` | Las 14 tablas transaccionales, índices y llaves foráneas |
| `procedures/sp_registrar_venta.sql` | Cobro en una sola transacción: venta, detalle y descuento de inventario con rollback |
| `functions/fn_importe_peso.sql` | Importe = peso × precio por kg vigente |
| `seed.sql` | Datos de prueba para desarrollo; nunca datos reales |

Los cambios a esta carpeta los aprueba el Arquitecto de Software.
