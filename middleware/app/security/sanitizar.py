"""Lista blanca para los textos que llegan al middleware (HU-03).

Comillas, punto y coma y `<` `>` quedan fuera: cubren SQLi y XSS. Las contraseñas
no pasan por aquí porque solo se usan para calcular su hash.
"""

PATRON_TEXTO_SEGURO = r"^[\w .,\-/#()&]+$"

# Notas libres que se guardan (observaciones del corte): además admite saltos de
# línea y la puntuación de una explicación ("faltan $20: cambio mal entregado").
# Siguen fuera comillas, punto y coma y `<` `>`.
PATRON_NOTA = r"^[\w .,\-/#()&:$%+¿?¡!\n]+$"
