# database · EC-08

Scripts de MySQL 8.0 (8.0.16 o posterior, por los `CHECK` y `JSON_TABLE`). Historias HU-01 y HU-02.

| Archivo | Contenido |
| --- | --- |
| `schema.sql` | 20 tablas InnoDB con llaves foráneas, `CHECK`, índices, 2 vistas y los triggers de la bitácora |
| `functions/fn_importe_peso.sql` | Función escalar: importe = cantidad × precio vigente, redondeado a 2 decimales |
| `procedures/sp_registrar_venta.sql` | Cobro en una sola transacción con descuento de inventario por lote (FEFO) y rollback |
| `seed.sql` | Datos de prueba para desarrollo; nunca datos reales |
| `tests/test_cobro.sql` | 35 pruebas del esquema, la función y el procedimiento |
| `instalar.sh` | Instala todo en orden |

## Instalar

```bash
MYSQL_ARGS="-h 127.0.0.1 -u root -p" ./database/instalar.sh               # producción: sin datos
MYSQL_ARGS="-h 127.0.0.1 -u root -p" ./database/instalar.sh --con-datos   # desarrollo
MYSQL_ARGS="-h 127.0.0.1 -u root -p" ./database/instalar.sh --con-pruebas # base desechable + pruebas
```

En cada Pull Request que toca `database/`, GitHub Actions levanta MySQL 8.0 y corre `--con-pruebas` (`.github/workflows/database.yml`).

## Tablas

Los nombres van en minúsculas para que el esquema funcione igual en Windows y Linux.

| Módulo | Tablas de la cotización (14) | Soporte propuesto en SC-01 (#2) |
| --- | --- | --- |
| Administración | `usuarios` | `roles`, `permisos`, `auditoria` |
| Proveedores y Compras | `proveedores`, `lotes_compras`, `cuentas_por_pagar` | |
| Catálogo e Inventario | `categorias`, `productos`, `inventario`, `mermas` | `historial_precios` |
| Punto de Venta | `cajas_pos`, `ventas_cabecera`, `ventas_detalle`, `metodos_pago` | `devoluciones` |
| Facturación | `facturas_cfdi` | `clientes_fiscales` |
| Finanzas | `gastos_operativos` | |

## Decisiones de diseño

- **`inventario` es la existencia por lote:** cada fila es un producto dentro de un lote de compra, con su costo, caducidad y cantidad disponible. La existencia total se calcula en `v_existencias`, nunca se captura.
- **`ventas_detalle` lleva un renglón por lote descontado.** Así la utilidad real usa el costo del lote que se vendió.
- **`cajas_pos` es un turno de caja.** Una columna generada impide tener dos cajas abiertas en la misma terminal.
- **Los pagos a proveedores se guardan en `gastos_operativos`** con `tipo = 'pago_proveedor'` y la cuenta por pagar que liquidan. Así entran al flujo de efectivo sin otra tabla, y la utilidad neta los excluye.
- **El estatus "Vencida" se calcula** en `v_cuentas_por_pagar` a partir de la fecha de vencimiento; no se guarda.
- **Un ticket solo tiene una factura vigente.** Una factura cancelada libera el ticket para la factura sustituta.
- **La bitácora `auditoria` es de solo lectura:** triggers rechazan `UPDATE` y `DELETE`.
- **Los precios incluyen IVA.** El procedimiento desglosa el IVA según la tasa de cada producto (0 % o 16 %).

## Pendiente de las solicitudes de cambio

- SC-01 (#2): si el cliente rechaza las 6 tablas de soporte, se quitan del esquema y sus flujos se rediseñan.
- SC-02 (#3): `devoluciones.id_autoriza` acepta cualquier usuario; la regla de qué rol autoriza va en el middleware.
- SC-03 (#4): no hay tabla de cuentas por cobrar hasta que se decida si existe la venta a crédito.

Los cambios a esta carpeta se revisan con la lista del rol Arquitecto.
