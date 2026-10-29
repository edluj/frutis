# database · EC-08

Scripts de MySQL 8.0 (8.0.16 o posterior, por los `CHECK` y `JSON_TABLE`). Historias HU-01 y HU-02.

| Archivo | Contenido |
| --- | --- |
| `schema.sql` | 23 tablas InnoDB con llaves foráneas, `CHECK`, índices, 3 vistas y triggers de la bitácora y de las devoluciones |
| `functions/fn_importe_peso.sql` | Función escalar: importe = cantidad × precio vigente, redondeado a 2 decimales |
| `procedures/sp_registrar_venta.sql` | Cobro en una sola transacción con descuento de inventario por lote (FEFO) y rollback; admite venta a crédito |
| `procedures/sp_registrar_cobro.sql` | Abono de un cliente a una venta a crédito |
| `seed.sql` | Datos de prueba para desarrollo; nunca datos reales |
| `tests/test_cobro.sql` | 50 pruebas del esquema, la función y los procedimientos |
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

| Módulo | Tablas de la cotización (14) | Aprobadas en SC-01 (#2) y SC-03 (#4) |
| --- | --- | --- |
| Administración | `usuarios` | `roles`, `permisos`, `auditoria` |
| Proveedores y Compras | `proveedores`, `lotes_compras`, `cuentas_por_pagar` | |
| Catálogo e Inventario | `categorias`, `productos`, `inventario`, `mermas` | `historial_precios` |
| Punto de Venta | `cajas_pos`, `ventas_cabecera`, `ventas_detalle`, `metodos_pago` | `devoluciones` |
| Facturación | `facturas_cfdi` | `clientes_fiscales` |
| Finanzas | `gastos_operativos` | `clientes_credito`, `cuentas_por_cobrar`, `cobros_clientes` (SC-03) |

## Decisiones de diseño

- **`inventario` es la existencia por lote:** cada fila es un producto dentro de un lote de compra, con su costo, caducidad y cantidad disponible. La existencia total se calcula en `v_existencias`, nunca se captura.
- **`ventas_detalle` lleva un renglón por lote descontado.** Así la utilidad real usa el costo del lote que se vendió.
- **`cajas_pos` es un turno de caja.** Una columna generada impide tener dos cajas abiertas en la misma terminal.
- **Los pagos a proveedores se guardan en `gastos_operativos`** con `tipo = 'pago_proveedor'` y la cuenta por pagar que liquidan. Así entran al flujo de efectivo sin otra tabla, y la utilidad neta los excluye.
- **El estatus "Vencida" se calcula** en `v_cuentas_por_pagar` a partir de la fecha de vencimiento; no se guarda.
- **Un ticket solo tiene una factura vigente.** Una factura cancelada libera el ticket para la factura sustituta.
- **La bitácora `auditoria` es de solo lectura:** triggers rechazan `UPDATE` y `DELETE`.
- **Los precios incluyen IVA.** El procedimiento desglosa el IVA según la tasa de cada producto (0 % o 16 %).

## Solicitudes de cambio aplicadas

| Solicitud | Decisión (29 de octubre de 2026) | Cómo se refleja |
| --- | --- | --- |
| SC-01 (#2) | Las 6 tablas de soporte se quedan, sin costo adicional | `roles`, `permisos`, `auditoria`, `clientes_fiscales`, `devoluciones`, `historial_precios` |
| SC-02 (#3) | Solo el Administrador autoriza devoluciones | Triggers `trg_devoluciones_autoriza_*` rechazan a cualquier otro rol |
| SC-03 (#4) | Sí hay venta a crédito | Método de pago "Crédito", `clientes_credito` con límite y días de crédito, `cuentas_por_cobrar`, `cobros_clientes`, `sp_registrar_cobro` y la vista `v_cuentas_por_cobrar` |

**Venta a crédito.** `sp_registrar_venta` recibe el cliente de crédito, valida que su saldo pendiente más la venta no rebase su límite y crea la cuenta por cobrar con vencimiento a los días de crédito del cliente. Los abonos se registran con `sp_registrar_cobro`; si se reciben en caja, entran al corte de ese turno.

Los cambios a esta carpeta se revisan con la lista del rol Arquitecto.
