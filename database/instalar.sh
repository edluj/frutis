#!/usr/bin/env bash
# Instala la base de datos de Frutis en orden.
#
# Uso:
#   ./database/instalar.sh                  # esquema, función y procedimiento
#   ./database/instalar.sh --con-datos      # además carga seed.sql (solo desarrollo)
#   ./database/instalar.sh --con-pruebas    # datos de prueba + pruebas (base desechable)
#
# Conexión: variables estándar del cliente mysql o MYSQL_ARGS, por ejemplo
#   MYSQL_ARGS="-h 127.0.0.1 -u root -p" ./database/instalar.sh
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
read -r -a ARGS <<< "${MYSQL_ARGS:-}"
run() { echo ">> $1"; mysql "${ARGS[@]}" --default-character-set=utf8mb4 < "$DIR/$1"; }

run schema.sql
for f in "$DIR"/functions/*.sql;  do run "functions/$(basename "$f")";  done
for f in "$DIR"/procedures/*.sql; do run "procedures/$(basename "$f")"; done

case "${1:-}" in
  --con-datos)   run seed.sql ;;
  --con-pruebas) run seed.sql; run tests/test_cobro.sql ;;
  "") ;;
  *) echo "Opción desconocida: $1" >&2; exit 2 ;;
esac

echo "Base de datos instalada."
