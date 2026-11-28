#!/usr/bin/env bash
# Instala la base de datos de Frutis en orden.
#
# Uso:
#   ./database/instalar.sh                  # esquema, rutinas y catálogos base (producción)
#   ./database/instalar.sh --con-datos      # además carga seed.sql (solo desarrollo)
#   ./database/instalar.sh --con-pruebas    # datos de prueba + pruebas (base desechable)
#   ./database/instalar.sh --solo-rutinas   # actualiza funciones y procedimientos en una base existente
#   ./database/instalar.sh --migraciones    # base existente: migraciones que falten y catálogos base
#
# Conexión: variables estándar del cliente mysql (~/.my.cnf) o MYSQL_ARGS, por ejemplo
#   MYSQL_ARGS="-h 127.0.0.1 -u root -p" ./database/instalar.sh
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
read -r -a ARGS <<< "${MYSQL_ARGS:-}"
run() { echo ">> $1"; mysql "${ARGS[@]}" --default-character-set=utf8mb4 < "$DIR/$1"; }

rutinas() {
  for f in "$DIR"/functions/*.sql;  do run "functions/$(basename "$f")";  done
  for f in "$DIR"/procedures/*.sql; do run "procedures/$(basename "$f")"; done
}

# Cada migración dice en su línea "-- Aplicada si:" una consulta que devuelve 1 cuando ya
# está aplicada; así se puede correr varias veces sin repetir un ALTER.
migraciones() {
  local f consulta aplicada
  # Primero los catálogos: una base de producción anterior a catalogos.sql no tenía roles ni
  # métodos de pago, y la 005 tomaría el id del Efectivo si corriera antes.
  run catalogos.sql
  for f in "$DIR"/migraciones/*.sql; do
    consulta=$(sed -n 's/^-- Aplicada si: //p' "$f")
    if [[ -z "$consulta" ]]; then
      echo "La migración $(basename "$f") no tiene la línea '-- Aplicada si:'" >&2
      exit 1
    fi
    aplicada=$(mysql "${ARGS[@]}" -N -B -e "$consulta")
    if [[ "$aplicada" == "1" ]]; then
      echo "-- migraciones/$(basename "$f") ya está aplicada"
    else
      run "migraciones/$(basename "$f")"
    fi
  done
}

case "${1:-}" in
  --solo-rutinas) rutinas; echo "Rutinas actualizadas."; exit 0 ;;
  --migraciones) migraciones; echo "Migraciones al día."; exit 0 ;;
  ""|--con-datos|--con-pruebas) ;;
  *) echo "Opción desconocida: $1" >&2; exit 2 ;;
esac

run schema.sql
rutinas
run catalogos.sql

case "${1:-}" in
  --con-datos)   run seed.sql ;;
  --con-pruebas)
    run seed.sql
    for f in "$DIR"/tests/*.sql; do run "tests/$(basename "$f")"; done ;;
  "") ;;
  *) echo "Opción desconocida: $1" >&2; exit 2 ;;
esac

echo "Base de datos instalada."
