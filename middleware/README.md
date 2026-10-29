# middleware · EC-09, EC-10

API FastAPI sobre HTTPS en la red local. Es la única puerta a la base de datos.

- Autenticación con token por rol y matriz de permisos por módulo.
- Validación y sanitización con Pydantic (SQLi / XSS) y consultas siempre parametrizadas.
- Reglas de negocio y bitácora de auditoría.
- Controladores de báscula e impresora de tickets en `app/hardware/` (EC-10).
- Integración con el proveedor de timbrado CFDI en `app/integrations/`.

Estructura prevista: `app/{api,security,schemas,services,repositories,hardware,integrations}/`, `tests/`, `requirements.txt`.

Del prototipo en `legacy/middleware.py` se reutilizan el hash PBKDF2, el límite de 5 intentos fallidos y el enmascarado de contraseñas en la bitácora.
