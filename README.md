# Frutis ERP + POS

Aplicación de escritorio para Frutería Frutis: venta en mostrador con cobro por peso (POS) y administración de compras por lote, inventario, mermas, facturación CFDI, finanzas y usuarios (ERP).

## Arquitectura

Tres capas sobre red local (LAN) privada:

| Capa | Tecnología | Carpeta |
| --- | --- | --- |
| Frontend | Python 3.12 + PySide6 (Qt), empaquetado con PyInstaller | `frontend/` |
| Middleware | FastAPI + Pydantic, tokens por rol, controladores de báscula e impresora | `middleware/` |
| Backend | MySQL 8 (InnoDB), Stored Procedure de cobro y Función escalar | `database/` |

## Estructura del repositorio

```
frutis/
├── frontend/      # App de escritorio PySide6
├── middleware/    # API FastAPI y controladores de hardware
├── database/      # schema.sql, procedures/, functions/, seed.sql
├── deploy/        # Plantilla .env.example e instalación del servidor
├── docs/          # Documentación del proyecto (ver docs/README.md)
├── legacy/        # Prototipo anterior (Tkinter + archivos .txt), solo referencia
└── .github/       # Plantillas de Pull Request y solicitud de cambio
```

## Cómo contribuir

El flujo completo está en el [Plan de Gestión de Configuración](docs/gestion/plan_gestion_configuracion.md). En resumen:

1. Crea una rama desde `develop`: `feature/HU-<número>-<nombre-corto>` (por ejemplo `feature/HU-07-lectura-bascula`).
2. Escribe commits con el formato `<tipo>(<módulo>): <qué cambia> [HU-xx]`, por ejemplo `feat(pos): calcula importe por peso [HU-07]`.
3. Abre un Pull Request hacia `develop` con la plantilla; necesita 1 aprobación de otra persona del equipo.
4. Los cambios a algo que ya está en línea base se piden con un issue de **Solicitud de cambio**.

Nunca subas contraseñas, certificados, CSD, archivos `.env` ni respaldos de la base de datos.

## Estado

Fase de planeación y arquitectura (Sprint 1). Historial de versiones en [CHANGELOG.md](CHANGELOG.md).
