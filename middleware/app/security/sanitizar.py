"""Lista blanca para los textos que llegan al middleware (HU-03).

Comillas, punto y coma y `<` `>` quedan fuera: cubren SQLi y XSS. Las contraseñas
no pasan por aquí porque solo se usan para calcular su hash.
"""

PATRON_TEXTO_SEGURO = r"^[\w .,\-/#()&]+$"
