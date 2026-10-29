# Servidor de base de datos en Rocky Linux 10

Instala y deja funcionando la base de datos de Frutis en una máquina virtual (o en el servidor local) con Rocky Linux 10. El script `instalar_servidor_bd.sh` hace todo en un solo paso y se puede volver a ejecutar sin perder datos.

**Qué hace el script:**

1. Instala MySQL 8.4, la versión que trae Rocky Linux 10 en AppStream.
2. Configura la zona horaria (America/Mexico_City), `utf8mb4` y la memoria de InnoDB según la RAM.
3. Asigna contraseña a `root` y aplica lo mismo que `mysql_secure_installation`.
4. Crea la base `frutis` con sus 23 tablas, la función y los 2 procedimientos.
5. Crea usuarios con el mínimo privilegio (`frutis_app`, `frutis_respaldo` y, en desarrollo, `frutis_dev`).
6. Abre el puerto 3306 solo para la red que indiques.
7. Programa un respaldo diario a las 23:30 y hace el primero.
8. Verifica que todo quedó bien.

## 1. Crear la máquina virtual

| Recurso | Desarrollo | Producción (cotización) |
| --- | --- | --- |
| CPU | 2 vCPU | Multinúcleo |
| RAM | 4 GB | 16 GB |
| Disco | 25 GB | SSD |
| Red | Adaptador puente o solo anfitrión | Red LAN de la frutería, IP fija |

- Descarga la ISO de Rocky Linux 10 (x86_64, *Minimal* o *DVD*) desde [rockylinux.org](https://rockylinux.org/download).
- En la instalación elige **Minimal Install**, crea un usuario con permisos de administrador y deja activo el firewall.
- **Red:** con *adaptador puente* la VM recibe una IP de tu red y cualquier equipo de la LAN puede llegar a ella. Con *solo anfitrión* (host-only) solo tu PC puede conectarse, suficiente para desarrollar.

Para ver la IP y la red de la VM:

```bash
ip -4 addr show | grep inet
# ejemplo: inet 192.168.56.10/24  ->  la red es 192.168.56.0/24
```

Para fijar la IP (recomendado en producción), con el nombre de tu conexión:

```bash
sudo nmcli con mod "enp0s3" ipv4.method manual ipv4.addresses 192.168.1.50/24 \
  ipv4.gateway 192.168.1.1 ipv4.dns 192.168.1.1
sudo nmcli con up "enp0s3"
```

## 2. Descargar el repositorio en la VM

```bash
sudo dnf -y update
sudo dnf -y install git
git clone https://github.com/edluj/frutis.git
cd frutis
git checkout develop
```

## 3. Ejecutar el instalador

**Desarrollo** (con datos de prueba y acceso desde tu PC). Cambia la red por la tuya:

```bash
sudo FRUTIS_MODO=desarrollo FRUTIS_RED_PERMITIDA=192.168.56.0/24 \
  bash deploy/rocky-linux/instalar_servidor_bd.sh
```

**Producción** (sin datos de prueba ni usuario `frutis_dev`). Si el middleware corre en el mismo servidor, no indiques red: MySQL solo escuchará en el propio equipo.

```bash
sudo FRUTIS_MODO=produccion bash deploy/rocky-linux/instalar_servidor_bd.sh
```

| Variable | Valor predeterminado | Para qué sirve |
| --- | --- | --- |
| `FRUTIS_MODO` | `produccion` | `desarrollo` carga datos de prueba y crea `frutis_dev` |
| `FRUTIS_RED_PERMITIDA` | vacío (solo local) | Red en formato CIDR que puede conectarse al puerto 3306 |
| `FRUTIS_DIR_RESPALDOS` | `/var/backups/frutis` | Carpeta de respaldos; en producción, el disco externo |
| `FRUTIS_DIAS_RESPALDO` | `30` | Días que se conservan los respaldos |
| `FRUTIS_ZONA_HORARIA` | `America/Mexico_City` | Zona horaria del servidor |

Al terminar verás un resumen como este:

```
Servidor de base de datos listo.
  MySQL ............ 8.4.x
  Tablas ........... 23 (esperadas: 23)
  Rutinas .......... 3 (esperadas: 3)
  Triggers ......... 4 (esperados: 4)
  frutis_app ....... se conecta; ve 6 productos
  Conexión ......... 192.168.56.10:3306 desde 192.168.56.0/24
  Respaldos ........ /var/backups/frutis, diario a las 23:30, 30 días
  Credenciales ..... /root/frutis-credenciales.txt (solo root puede leerlo)
```

## 4. Usuarios y contraseñas

El script genera contraseñas aleatorias y las guarda en `/root/frutis-credenciales.txt`, que solo `root` puede leer. Si lo vuelves a ejecutar, conserva las mismas.

```bash
sudo cat /root/frutis-credenciales.txt
```

| Usuario | Desde dónde | Permisos | Uso |
| --- | --- | --- | --- |
| `root` | Solo el servidor | Todos | Administración; su contraseña está en `/root/.my.cnf` |
| `frutis_app` | Servidor y red permitida | Leer, insertar, actualizar y ejecutar procedimientos; borrar solo en `permisos` | Middleware |
| `frutis_respaldo` | Solo el servidor | Solo lectura | Respaldos diarios |
| `frutis_dev` | Servidor y red permitida | Todos sobre `frutis` | Solo en desarrollo: MySQL Workbench o DBeaver |

Nunca subas estas contraseñas al repositorio. El middleware las leerá de su archivo `.env` (ver `deploy/.env.example`).

## 5. Conectarse desde tu PC

En MySQL Workbench o DBeaver crea una conexión con:

- **Host:** la IP de la VM. **Puerto:** 3306.
- **Usuario:** `frutis_dev`. **Contraseña:** la de `FRUTIS_DEV_PASSWORD`.
- **Base de datos:** `frutis`.

Para probar el cobro desde la consola de la VM:

```sql
CALL sp_registrar_venta(1, 2, 1, 200.00, NULL, '[{"id_producto": 1, "cantidad": 1.5}]', @venta, @folio, @total, @cambio);
SELECT @folio, @total, @cambio;
```

## 6. Respaldos

```bash
systemctl list-timers frutis-respaldo.timer   # próxima ejecución
sudo frutis-respaldo                           # respaldo manual inmediato
ls -lh /var/backups/frutis                     # respaldos existentes
```

Para restaurar un respaldo (reemplaza las tablas existentes por las del respaldo):

```bash
gunzip < /var/backups/frutis/frutis_AAAAMMDD_HHMMSS.sql.gz | sudo mysql --defaults-file=/root/.my.cnf
```

El plan de gestión de configuración pide probar una restauración antes de la entrega (riesgo R-10) y guardar los respaldos fuera del servidor: monta el disco externo y vuelve a ejecutar el instalador con `FRUTIS_DIR_RESPALDOS` apuntando a él.

## 7. Actualizar después de un cambio en el repositorio

```bash
cd ~/frutis && git pull
sudo FRUTIS_MODO=desarrollo FRUTIS_RED_PERMITIDA=192.168.56.0/24 \
  bash deploy/rocky-linux/instalar_servidor_bd.sh
```

Si la base ya existe, el script no toca tablas ni datos: solo actualiza la función y los procedimientos. Un cambio de tablas en una base con datos necesita un script de migración aparte.

Para empezar de cero en desarrollo (borra todos los datos):

```bash
sudo mysql --defaults-file=/root/.my.cnf -e "DROP DATABASE frutis"
```

## 8. Solución de problemas

| Síntoma | Qué revisar |
| --- | --- |
| MySQL no arranca | `sudo journalctl -u mysqld -n 50` y `sudo cat /var/log/mysql/mysqld.log` |
| No conecta desde la PC | Que la PC esté en la red permitida; `sudo firewall-cmd --list-rich-rules`; `ss -tlnp \| grep 3306` debe mostrar `0.0.0.0:3306` |
| `Access denied` desde la PC | El usuario solo existe para la red indicada; vuelve a ejecutar con la red correcta |
| `MariaDB está instalado` | MySQL y MariaDB no pueden convivir: `sudo dnf remove mariadb-server` |
| Las fechas salen con horas de diferencia | `timedatectl` debe mostrar America/Mexico_City |

Referencia: [Red Hat Enterprise Linux 10, Using MySQL](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/10/html/configuring_and_using_database_servers/using-mysql).
