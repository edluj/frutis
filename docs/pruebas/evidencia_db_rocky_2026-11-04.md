# Evidencia · Instalación y pruebas de la base de datos en Rocky Linux

| Dato | Valor |
| --- | --- |
| Elemento de configuración | EC-08 Base de datos (`database/`) |
| Historias y solicitudes | HU-01, HU-02, SC-02 (#3), SC-03 (#4) |
| Fecha | 4 de noviembre de 2026 |
| Equipo | Máquina virtual de desarrollo, Rocky Linux 10.2 (kernel 6.12.0-211.68.1.el10_2.x86_64) |
| Servidor de base de datos | MySQL Community Server 8.0.46 |
| Versión del repositorio | `develop` en `0ff5f5e` |
| Resultado | **50 de 50 pruebas pasaron; verificación de usuarios y respaldo correcta** |

Las contraseñas no aparecen en esta evidencia. Las de `frutis_app` y `frutis_respaldo` están solo en el servidor (`deploy/.env` y `~/.frutis_respaldo.cnf`, con permisos 600) y no entran al repositorio.

## 1. Instalación y pruebas automáticas

Comando, ejecutado sobre un servidor sin la base `frutis` (terminó a las 10:41 CST):

```bash
./database/instalar.sh --con-pruebas
```

Es el mismo comando que corre GitHub Actions (`.github/workflows/database.yml`). Instala `schema.sql`, la función, los procedimientos y `seed.sql`, y luego corre `tests/test_cobro.sql`. El instalador terminó con código de salida 0.

Salida completa. Se omitieron solo los 51 renglones `resultado`, que son el encabezado de columna que imprime el cliente `mysql` antes de cada mensaje:

```text
>> schema.sql
>> functions/fn_importe_peso.sql
>> procedures/sp_registrar_cobro.sql
>> procedures/sp_registrar_venta.sql
>> seed.sql
>> tests/test_cobro.sql
OK   El esquema tiene 23 tablas (14 de la cotización + 6 de SC-01 + 3 de SC-03)
OK   Todas las tablas usan InnoDB
OK   fn_importe_peso redondea a 2 decimales (1.255 kg x 28.50 = 35.77)
OK   fn_importe_peso calcula productos por pieza (3 x 35.00)
OK   fn_importe_peso rechaza cantidad cero
OK   fn_importe_peso rechaza producto inexistente
OK   El primer ticket recibe el folio V00000001
OK   Total 135.00 y cambio 65.00 sobre 200.00 recibidos
OK   La venta usa 2 lotes
OK   FEFO: toma primero los 2 kg del lote que caduca antes
OK   El inventario queda en 0 y 9 kg
OK   La cabecera cuadra: total = subtotal + IVA
OK   Tarjeta: 2 kg de plátano + 2 piñas = 114.00, sin cambio
OK   Un producto repetido en el carrito se registra en un solo renglón
OK   En pagos sin efectivo el monto recibido es igual al total
OK   Rechaza monto recibido menor al total
OK   Rollback: el aguacate conserva sus 8 kg
OK   Rechaza producto sin existencia suficiente
OK   Rollback: no descuenta la manzana ya procesada ni el limón
OK   Rechaza piezas fraccionadas
OK   Rechaza carrito vacío
OK   Rechaza producto inexistente
OK   Rechaza cantidad negativa
OK   Rechaza método de pago inexistente
OK   Rechaza cobro en caja cerrada
OK   Ningún cobro fallido deja ventas o renglones a medias
OK   Venta a crédito de 68.00 sin cambio
OK   La venta a crédito crea la cuenta por cobrar con vencimiento a 15 días
OK   Rechaza venta a crédito sin cliente
OK   Rechaza venta que rebasa el límite de crédito
OK   Rollback: la venta rechazada por límite no descuenta inventario
OK   Un abono parcial deja saldo de 18.00 pendiente
OK   Rechaza un cobro mayor al saldo
OK   Rechaza cobrar con el método Crédito
OK   Rechaza cobro en caja cerrada
OK   El abono final liquida la cuenta y la marca como pagada
OK   Los cobros registrados suman el total de la venta
OK   v_cuentas_por_cobrar muestra la cuenta como Pagada
OK   Un cajero no puede autorizar devoluciones
OK   El Administrador sí autoriza devoluciones
OK   No se puede cambiar el autorizador a otro rol
OK   Solo una caja abierta por terminal
OK   No se cierra caja con diferencia sin observaciones
OK   La existencia por lote no puede ser negativa
OK   Rechaza correo con formato inválido
OK   La bitácora no se puede editar
OK   La bitácora no se puede borrar
OK   Un ticket no se factura dos veces
OK   v_existencias marca "Bajo" la manzana (9 kg con mínimo de 10)
OK   v_cuentas_por_pagar calcula el estatus del adeudo
Todas las pruebas pasaron
Base de datos instalada.
```

## 2. Verificación de objetos, usuarios y respaldo

Se crearon dos usuarios con el mínimo de permisos necesario:

| Usuario | Uso | Permisos |
| --- | --- | --- |
| `frutis_app@localhost` | Middleware (FastAPI) | `SELECT, INSERT, UPDATE, EXECUTE` sobre `frutis.*`. Sin `DELETE`, porque el diseño usa bajas lógicas con la columna `activo` |
| `frutis_respaldo@localhost` | Respaldos con `mysqldump` | `SELECT, SHOW VIEW, TRIGGER, LOCK TABLES, EVENT` sobre `frutis.*` y `SHOW_ROUTINE` global |

Cada usuario se conectó con su propia credencial: `frutis_app` con `--no-defaults` y `frutis_respaldo` con `--defaults-file`, para que no se mezclen con las credenciales de `root`. El respaldo de prueba se generó fuera del repositorio y se borró.

Salida completa:

```text
$ date
2026-11-04 10:56:22 CST

# Servidor
+---------+------------------------------+
| version | edicion                      |
+---------+------------------------------+
| 8.0.46  | MySQL Community Server - GPL |
+---------+------------------------------+

# Objetos instalados en frutis
+------------+-------+
| tipo       | total |
+------------+-------+
| BASE TABLE |    23 |
| VIEW       |     3 |
+------------+-------+
+-----------+--------------------+
| tipo      | nombre             |
+-----------+--------------------+
| FUNCTION  | fn_importe_peso    |
| PROCEDURE | sp_registrar_cobro |
| PROCEDURE | sp_registrar_venta |
+-----------+--------------------+
+----------------------------------+--------------+
| trigger_nombre                   | tabla        |
+----------------------------------+--------------+
| trg_auditoria_sin_borrado        | auditoria    |
| trg_auditoria_sin_cambios        | auditoria    |
| trg_devoluciones_autoriza_alta   | devoluciones |
| trg_devoluciones_autoriza_cambio | devoluciones |
+----------------------------------+--------------+

# Permisos de los usuarios
+---------------------------------------------------------------------------------+
| Grants for frutis_app@localhost                                                 |
+---------------------------------------------------------------------------------+
| GRANT USAGE ON *.* TO `frutis_app`@`localhost`                                  |
| GRANT SELECT, INSERT, UPDATE, EXECUTE ON `frutis`.* TO `frutis_app`@`localhost` |
+---------------------------------------------------------------------------------+
+-----------------------------------------------------------------------------------------------------+
| Grants for frutis_respaldo@localhost                                                                |
+-----------------------------------------------------------------------------------------------------+
| GRANT USAGE ON *.* TO `frutis_respaldo`@`localhost`                                                 |
| GRANT SHOW_ROUTINE ON *.* TO `frutis_respaldo`@`localhost`                                          |
| GRANT SELECT, LOCK TABLES, SHOW VIEW, EVENT, TRIGGER ON `frutis`.* TO `frutis_respaldo`@`localhost` |
+-----------------------------------------------------------------------------------------------------+

# frutis_app (credenciales de deploy/.env): lee y ejecuta la función
+----------------------+
| usuario              |
+----------------------+
| frutis_app@localhost |
+----------------------+
+-----------+
| productos |
+-----------+
|         6 |
+-----------+
+--------------------------+
| fn_importe_peso_1_1500kg |
+--------------------------+
|                    67.50 |
+--------------------------+

# frutis_app: DROP TABLE debe ser rechazado
ERROR 1142 (42000) at line 1: DROP command denied to user 'frutis_app'@'localhost' for table 'mermas'
código de salida: 1

# frutis_app: DELETE debe ser rechazado (bajas lógicas)
ERROR 1142 (42000) at line 1: DELETE command denied to user 'frutis_app'@'localhost' for table 'mermas'
código de salida: 1

# frutis_respaldo (credenciales de ~/.frutis_respaldo.cnf): solo lectura
+---------------------------+
| usuario                   |
+---------------------------+
| frutis_respaldo@localhost |
+---------------------------+
ERROR 1142 (42000) at line 1: UPDATE command denied to user 'frutis_respaldo'@'localhost' for table 'productos'
código de salida: 1

# frutis_respaldo: mysqldump con rutinas, triggers y eventos
código de salida: 0
líneas de error: 0
Tablas (CREATE TABLE): 23
Vistas: 3
Funciones: 1
Procedimientos: 2
Triggers: 4
-- Dump completed on 2026-11-04 10:56:23
```

## 3. Conclusión

| Verificación | Esperado | Obtenido |
| --- | --- | --- |
| Pruebas de `tests/test_cobro.sql` | 50 OK | 50 OK |
| Tablas / vistas | 23 / 3 | 23 / 3 |
| Función / procedimientos / triggers | 1 / 2 / 4 | 1 / 2 / 4 |
| `frutis_app` lee y ejecuta `fn_importe_peso` | Sí | Sí (67.50) |
| `frutis_app` hace `DROP` o `DELETE` | Rechazado | ERROR 1142 |
| `frutis_respaldo` escribe | Rechazado | ERROR 1142 |
| `mysqldump` con `frutis_respaldo` | Sin errores, con rutinas y triggers | Código 0; 23 tablas, 3 vistas, 1 función, 2 procedimientos, 4 triggers |

**Observación.** La base `frutis` de esta máquina conserva los datos de `seed.sql` y los que generaron las pruebas. Es una instalación de desarrollo; producción se instala con `./database/instalar.sh` sin opciones.
