# Historial de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Versionado semántico según el Plan de Gestión de Configuración (sección 6).

## [Sin publicar]

### Agregado
- Estructura del repositorio por capas: `frontend/`, `middleware/`, `database/`, `deploy/` y `docs/`.
- Plan de Gestión de Configuración en `docs/gestion/`.
- Plantillas de Pull Request y de solicitud de cambio.
- `CHANGELOG.md` y nuevo `README.md`.

### Cambiado
- El prototipo anterior (middleware TCP y clientes Tkinter) se movió a `legacy/` como referencia.
- `.gitignore` ampliado para excluir secretos, respaldos y artefactos de empaquetado.

### Eliminado
- `Untitled4.ipynb`: análisis de regresión ajeno al proyecto.
