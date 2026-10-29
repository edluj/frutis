#!/usr/bin/env bash
# Respaldo de la base frutis con mysqldump. Lo ejecuta frutis-respaldo.timer cada día.
# Configuración en /etc/frutis/respaldo.conf (la escribe instalar_servidor_bd.sh).
set -euo pipefail

DESTINO=/var/backups/frutis
DIAS=30
CREDENCIALES=/root/.frutis-respaldo.cnf
if [[ -f /etc/frutis/respaldo.conf ]]; then
  # shellcheck source=/dev/null
  source /etc/frutis/respaldo.conf
fi

install -d -m 700 "$DESTINO"
archivo="$DESTINO/frutis_$(date +%Y%m%d_%H%M%S).sql.gz"

mysqldump --defaults-file="$CREDENCIALES" \
  --single-transaction --routines --triggers --events --no-tablespaces \
  --databases frutis | gzip > "$archivo.tmp"
mv "$archivo.tmp" "$archivo"
chmod 600 "$archivo"

find "$DESTINO" -name 'frutis_*.sql.gz' -type f -mtime +"$DIAS" -delete

echo "Respaldo creado: $archivo ($(du -h "$archivo" | cut -f1))"
