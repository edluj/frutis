#!/usr/bin/env bash
# =============================================================================
# Frutis ERP + POS · Instalador del servidor de base de datos en Rocky Linux 10
#
# Instala MySQL 8.4 (AppStream), lo configura, crea la base "frutis" con su
# función y procedimientos, crea los usuarios con el mínimo privilegio, abre el
# firewall solo para la red indicada y programa un respaldo diario.
#
# Se puede ejecutar varias veces: no borra datos. Si la base ya existe, solo
# actualiza la función y los procedimientos.
#
# Uso (como root, desde la copia del repositorio):
#   FRUTIS_MODO=desarrollo FRUTIS_RED_PERMITIDA=192.168.56.0/24 \
#     bash deploy/rocky-linux/instalar_servidor_bd.sh
#
# Variables:
#   FRUTIS_MODO            produccion (predeterminado) | desarrollo
#                          desarrollo = carga datos de prueba y crea el usuario frutis_dev
#   FRUTIS_RED_PERMITIDA   red que puede conectarse al puerto 3306, en formato CIDR
#                          (ej. 192.168.1.0/24). Vacío = solo conexiones locales.
#   FRUTIS_DIR_RESPALDOS   carpeta de respaldos (predeterminado /var/backups/frutis)
#   FRUTIS_DIAS_RESPALDO   días que se conservan los respaldos (predeterminado 30)
#   FRUTIS_ZONA_HORARIA    zona horaria del servidor (predeterminado America/Mexico_City)
# =============================================================================
set -euo pipefail

MODO="${FRUTIS_MODO:-produccion}"
RED="${FRUTIS_RED_PERMITIDA:-}"
DIR_RESPALDOS="${FRUTIS_DIR_RESPALDOS:-/var/backups/frutis}"
DIAS_RESPALDO="${FRUTIS_DIAS_RESPALDO:-30}"
ZONA="${FRUTIS_ZONA_HORARIA:-America/Mexico_City}"

AQUI="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$AQUI/../.." && pwd)"
CREDENCIALES=/root/frutis-credenciales.txt
ROOT_CNF=/root/.my.cnf
RESPALDO_CNF=/root/.frutis-respaldo.cnf
CONF_MYSQL=/etc/my.cnf.d/frutis.cnf

paso()  { printf '\n==> %s\n' "$*"; }
aviso() { printf 'AVISO: %s\n' "$*" >&2; }
falla() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# Contraseña de 24 caracteres con minúscula, mayúscula, número y símbolo
genera_password() { printf '%s-Fr1' "$(openssl rand -hex 10)"; }

sql_root() { mysql --defaults-file="$ROOT_CNF" -N -B -e "$1"; }

# -----------------------------------------------------------------------------
paso "Revisando requisitos"
# -----------------------------------------------------------------------------
[[ $EUID -eq 0 ]] || falla "Ejecuta este script como root (sudo -i)."
[[ -f "$REPO/database/schema.sql" ]] || falla "No encuentro database/schema.sql; ejecuta el script desde la copia del repositorio."
[[ "$MODO" == produccion || "$MODO" == desarrollo ]] || falla "FRUTIS_MODO debe ser produccion o desarrollo."
[[ "$DIAS_RESPALDO" =~ ^[0-9]+$ ]] || falla "FRUTIS_DIAS_RESPALDO debe ser un número de días."
if [[ -n "$RED" && ! "$RED" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}/([0-9]|[12][0-9]|3[0-2])$ ]]; then
  falla "FRUTIS_RED_PERMITIDA debe estar en formato CIDR, por ejemplo 192.168.1.0/24."
fi

# shellcheck source=/dev/null
source /etc/os-release
if [[ "${VERSION_ID%%.*}" != "10" ]]; then
  aviso "Este script está probado para Rocky Linux 10; el sistema es ${PRETTY_NAME:-desconocido}."
fi
if rpm -q mariadb-server &>/dev/null; then
  falla "MariaDB está instalado y no puede convivir con MySQL. Desinstálalo primero."
fi

echo "Modo: $MODO · Red permitida: ${RED:-solo local} · Respaldos: $DIR_RESPALDOS ($DIAS_RESPALDO días)"

# Contraseñas de una ejecución anterior, si existen
if [[ -f "$CREDENCIALES" ]]; then
  # shellcheck source=/dev/null
  source "$CREDENCIALES"
fi
FRUTIS_APP_PASSWORD="${FRUTIS_APP_PASSWORD:-$(genera_password)}"
FRUTIS_RESPALDO_PASSWORD="${FRUTIS_RESPALDO_PASSWORD:-$(genera_password)}"
FRUTIS_DEV_PASSWORD="${FRUTIS_DEV_PASSWORD:-$(genera_password)}"

# -----------------------------------------------------------------------------
paso "Instalando MySQL 8.4"
# -----------------------------------------------------------------------------
dnf -y install mysql8.4-server openssl
command -v mysql &>/dev/null || dnf -y install mysql8.4
mysql --version

timedatectl set-timezone "$ZONA"
echo "Zona horaria: $(timedatectl show -p Timezone --value)"

# -----------------------------------------------------------------------------
paso "Configurando MySQL ($CONF_MYSQL)"
# -----------------------------------------------------------------------------
mem_mb=$(( $(awk '/^MemTotal:/ {print $2}' /proc/meminfo) / 1024 ))
pool_mb=$(( mem_mb / 2 ))
(( pool_mb < 256 )) && pool_mb=256
bind=127.0.0.1
[[ -n "$RED" ]] && bind=0.0.0.0

{
  echo "# Generado por deploy/rocky-linux/instalar_servidor_bd.sh. Se reescribe en cada ejecución."
  echo "[mysqld]"
  echo "bind-address = $bind"
  echo "mysqlx-bind-address = 127.0.0.1"
  echo "character-set-server = utf8mb4"
  echo "collation-server = utf8mb4_0900_ai_ci"
  echo "local-infile = OFF"
  echo "max_connections = 100"
  echo "innodb_buffer_pool_size = ${pool_mb}M"
  echo "binlog_expire_logs_seconds = 604800"
  if [[ "$MODO" == desarrollo ]]; then
    echo "# Permite que frutis_dev cree funciones y procedimientos con el binlog activo"
    echo "log_bin_trust_function_creators = ON"
  fi
} > "$CONF_MYSQL"
chmod 644 "$CONF_MYSQL"
cat "$CONF_MYSQL"

systemctl enable mysqld
systemctl restart mysqld
for _ in $(seq 1 30); do
  mysqladmin ping --silent 2>/dev/null && break
  sleep 2
done
mysqladmin ping --silent 2>/dev/null || falla "MySQL no respondió; revisa journalctl -u mysqld."

# -----------------------------------------------------------------------------
paso "Asegurando la cuenta root"
# -----------------------------------------------------------------------------
if [[ -f "$ROOT_CNF" ]] && mysql --defaults-file="$ROOT_CNF" -e 'SELECT 1' &>/dev/null; then
  echo "root ya tiene contraseña (se usa $ROOT_CNF)."
elif mysql -u root -e 'SELECT 1' &>/dev/null; then
  FRUTIS_ROOT_PASSWORD="$(genera_password)"
  mysql -u root -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '${FRUTIS_ROOT_PASSWORD}';"
  ( umask 077; printf '[client]\nuser=root\npassword="%s"\n' "$FRUTIS_ROOT_PASSWORD" > "$ROOT_CNF" )
  echo "Se asignó contraseña a root y se guardó en $ROOT_CNF."
else
  falla "No puedo entrar como root. Crea $ROOT_CNF con [client] user=root password=\"...\" y vuelve a ejecutar."
fi

# Equivalente a mysql_secure_installation
sql_root "DELETE FROM mysql.user WHERE User = '';
          DROP USER IF EXISTS 'root'@'%';
          DROP DATABASE IF EXISTS test;
          FLUSH PRIVILEGES;"

# -----------------------------------------------------------------------------
paso "Instalando la base de datos frutis"
# -----------------------------------------------------------------------------
existe=$(sql_root "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name = 'frutis'")
if [[ "$existe" == "0" ]]; then
  opcion=""
  [[ "$MODO" == desarrollo ]] && opcion="--con-datos"
  MYSQL_ARGS="--defaults-file=$ROOT_CNF" bash "$REPO/database/instalar.sh" $opcion
else
  echo "La base frutis ya existe: no se toca el esquema ni los datos; solo se actualizan las rutinas."
  MYSQL_ARGS="--defaults-file=$ROOT_CNF" bash "$REPO/database/instalar.sh" --solo-rutinas
fi

# -----------------------------------------------------------------------------
paso "Creando usuarios con el mínimo privilegio"
# -----------------------------------------------------------------------------
hosts=("localhost" "127.0.0.1")
[[ -n "$RED" ]] && hosts+=("$RED")

for h in "${hosts[@]}"; do
  # Aplicación (middleware): lee, escribe y ejecuta procedimientos; nunca borra salvo permisos
  sql_root "CREATE USER IF NOT EXISTS 'frutis_app'@'$h' IDENTIFIED BY '${FRUTIS_APP_PASSWORD}';
            ALTER USER 'frutis_app'@'$h' IDENTIFIED BY '${FRUTIS_APP_PASSWORD}';
            GRANT SELECT, INSERT, UPDATE, EXECUTE ON frutis.* TO 'frutis_app'@'$h';
            GRANT DELETE ON frutis.permisos TO 'frutis_app'@'$h';"
  if [[ "$MODO" == desarrollo ]]; then
    # Desarrollo: control total de la base frutis (para MySQL Workbench o DBeaver)
    sql_root "CREATE USER IF NOT EXISTS 'frutis_dev'@'$h' IDENTIFIED BY '${FRUTIS_DEV_PASSWORD}';
              ALTER USER 'frutis_dev'@'$h' IDENTIFIED BY '${FRUTIS_DEV_PASSWORD}';
              GRANT ALL PRIVILEGES ON frutis.* TO 'frutis_dev'@'$h';
              GRANT SHOW_ROUTINE ON *.* TO 'frutis_dev'@'$h';"
  fi
done

# Respaldos: solo lectura y solo desde el propio servidor
sql_root "CREATE USER IF NOT EXISTS 'frutis_respaldo'@'localhost' IDENTIFIED BY '${FRUTIS_RESPALDO_PASSWORD}';
          ALTER USER 'frutis_respaldo'@'localhost' IDENTIFIED BY '${FRUTIS_RESPALDO_PASSWORD}';
          GRANT SELECT, SHOW VIEW, TRIGGER, LOCK TABLES, EVENT ON frutis.* TO 'frutis_respaldo'@'localhost';
          GRANT SHOW_ROUTINE ON *.* TO 'frutis_respaldo'@'localhost';
          FLUSH PRIVILEGES;"

( umask 077; printf '[client]\nuser=frutis_respaldo\npassword="%s"\n' "$FRUTIS_RESPALDO_PASSWORD" > "$RESPALDO_CNF" )

(
  umask 077
  {
    echo "# Credenciales de Frutis ERP · $(date '+%Y-%m-%d %H:%M') · NO subir al repositorio"
    [[ -n "${FRUTIS_ROOT_PASSWORD:-}" ]] && echo "FRUTIS_ROOT_PASSWORD='${FRUTIS_ROOT_PASSWORD}'"
    echo "FRUTIS_APP_PASSWORD='${FRUTIS_APP_PASSWORD}'"
    echo "FRUTIS_RESPALDO_PASSWORD='${FRUTIS_RESPALDO_PASSWORD}'"
    echo "FRUTIS_DEV_PASSWORD='${FRUTIS_DEV_PASSWORD}'"
  } > "$CREDENCIALES"
)

# -----------------------------------------------------------------------------
paso "Configurando el firewall"
# -----------------------------------------------------------------------------
if [[ -z "$RED" ]]; then
  echo "Sin red permitida: MySQL solo escucha en 127.0.0.1; no se abre ningún puerto."
elif systemctl is-active --quiet firewalld; then
  regla="rule family=\"ipv4\" source address=\"$RED\" port port=\"3306\" protocol=\"tcp\" accept"
  if firewall-cmd --permanent --query-rich-rule="$regla" &>/dev/null; then
    echo "La regla para $RED ya existe."
  else
    firewall-cmd --permanent --add-rich-rule="$regla"
    firewall-cmd --reload
    echo "Puerto 3306 abierto solo para $RED."
  fi
else
  aviso "firewalld no está activo: el puerto 3306 queda expuesto a cualquier red. Actívalo con: systemctl enable --now firewalld"
fi

# -----------------------------------------------------------------------------
paso "Programando el respaldo diario"
# -----------------------------------------------------------------------------
install -d -m 755 /etc/frutis
printf 'DESTINO=%q\nDIAS=%q\nCREDENCIALES=%q\n' "$DIR_RESPALDOS" "$DIAS_RESPALDO" "$RESPALDO_CNF" > /etc/frutis/respaldo.conf
install -m 750 "$AQUI/frutis-respaldo.sh" /usr/local/sbin/frutis-respaldo
install -m 644 "$AQUI/frutis-respaldo.service" /etc/systemd/system/frutis-respaldo.service
install -m 644 "$AQUI/frutis-respaldo.timer" /etc/systemd/system/frutis-respaldo.timer
systemctl daemon-reload
systemctl enable --now frutis-respaldo.timer
/usr/local/sbin/frutis-respaldo

# -----------------------------------------------------------------------------
paso "Verificando"
# -----------------------------------------------------------------------------
tablas=$(sql_root "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'frutis' AND table_type = 'BASE TABLE'")
rutinas=$(sql_root "SELECT COUNT(*) FROM information_schema.routines WHERE routine_schema = 'frutis'")
triggers=$(sql_root "SELECT COUNT(*) FROM information_schema.triggers WHERE trigger_schema = 'frutis'")
productos=$(MYSQL_PWD="$FRUTIS_APP_PASSWORD" mysql -u frutis_app -h 127.0.0.1 -N -B -e "SELECT COUNT(*) FROM frutis.productos")
ip=$(hostname -I | awk '{print $1}')

cat <<RESUMEN

Servidor de base de datos listo.
  MySQL ............ $(mysql --version | awk '{print $3}')
  Tablas ........... $tablas (esperadas: 23)
  Rutinas .......... $rutinas (esperadas: 3)
  Triggers ......... $triggers (esperados: 4)
  frutis_app ....... se conecta; ve $productos productos
  Conexión ......... ${ip}:3306 $( [[ -n "$RED" ]] && echo "desde $RED" || echo "(solo local)")
  Respaldos ........ $DIR_RESPALDOS, diario a las 23:30, $DIAS_RESPALDO días
  Credenciales ..... $CREDENCIALES (solo root puede leerlo)
RESUMEN

[[ "$tablas" == "23" && "$rutinas" == "3" && "$triggers" == "4" ]] || falla "La verificación no coincide con lo esperado."
