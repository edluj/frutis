#!/usr/bin/env bash
# Certificados de la red local (arquitectura, sección 9): una autoridad certificadora propia
# y el certificado del servidor firmado por ella. Las terminales validan el servidor con
# frutis-ca.crt (FRUTIS_CA_PATH o ca_path en frutis.ini).
#
# Uso:
#   ./deploy/generar_certificados.sh                    # IP principal del servidor + localhost
#   ./deploy/generar_certificados.sh 192.168.1.10 caja  # IPs o nombres con que lo buscan las terminales
#
# Resultado en deploy/certificados/ (fuera de Git): frutis-ca.crt, servidor.crt, servidor.key.
# frutis-ca.key firma certificados: guárdela fuera del servidor después de generar.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)/certificados"
mkdir -p "$DIR"
cd "$DIR"
umask 077

nombres=("$@")
if [ ${#nombres[@]} -eq 0 ]; then
  nombres=("$(hostname -I | awk '{print $1}')")
fi
san="DNS:localhost,IP:127.0.0.1"
for n in "${nombres[@]}"; do
  if [[ "$n" =~ ^[0-9]+(\.[0-9]+){3}$ ]]; then san+=",IP:$n"; else san+=",DNS:$n"; fi
done

if [ ! -f frutis-ca.key ]; then
  openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -days 3650 \
    -keyout frutis-ca.key -out frutis-ca.crt -subj "/O=Fruteria Frutis/CN=Frutis CA local" \
    -addext "basicConstraints=critical,CA:TRUE" -addext "keyUsage=critical,keyCertSign,cRLSign" 2>/dev/null
  echo ">> Autoridad certificadora creada: $DIR/frutis-ca.crt"
fi

openssl req -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -keyout servidor.key -out servidor.csr \
  -subj "/O=Fruteria Frutis/CN=${nombres[0]}" 2>/dev/null
openssl x509 -req -in servidor.csr -CA frutis-ca.crt -CAkey frutis-ca.key -CAcreateserial -days 825 \
  -out servidor.crt -extfile <(printf "subjectAltName=%s\nextendedKeyUsage=serverAuth\nbasicConstraints=CA:FALSE\n" "$san") 2>/dev/null
rm -f servidor.csr
chmod 644 frutis-ca.crt servidor.crt

echo ">> Certificado del servidor para: $san"
cat <<FIN

Agregue a deploy/.env:
  FRUTIS_BIND_HOST=0.0.0.0
  FRUTIS_CERT_PATH=$DIR/servidor.crt
  FRUTIS_KEY_PATH=$DIR/servidor.key

Copie $DIR/frutis-ca.crt a cada terminal, junto al ejecutable, y en su frutis.ini:
  api_url = https://${nombres[0]}:8443
  ca_path = frutis-ca.crt
FIN
