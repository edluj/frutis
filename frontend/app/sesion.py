"""Perfil del usuario en sesión y consulta de su matriz de permisos (flujos B y U)."""
from dataclasses import dataclass, field

# Módulos del enum `permisos.modulo` en el orden del menú del diseño.
MODULOS = [
    ("pos", "Punto de Venta", "pos"),
    ("compras", "Proveedores y Compras", "compras"),
    ("facturacion", "Facturación", "facturacion"),
    ("finanzas", "Finanzas", "finanzas"),
    ("inventario", "Catálogo e Inventario", "inventario"),
    ("reportes", "Reportes", "reportes"),
    ("admin", "Administración", "admin"),
]
NOMBRE_MODULO = {clave: nombre for clave, nombre, _ in MODULOS}


@dataclass
class Sesion:
    id_usuario: int
    usuario: str
    nombre_completo: str
    rol: str
    permisos: dict[str, dict[str, bool]] = field(default_factory=dict)
    caja: str | None = None
    # Módulos del menú: los que el rol puede ver y que tienen al menos una pantalla abrible.
    modulos_menu: list[tuple[str, str, str]] = field(default_factory=list)

    @classmethod
    def desde_perfil(cls, perfil: dict) -> "Sesion":
        permisos = {
            p["modulo"]: {
                "ver": p["puede_ver"], "crear": p["puede_crear"],
                "editar": p["puede_editar"], "eliminar": p["puede_eliminar"],
            }
            for p in perfil.get("permisos", [])
        }
        return cls(perfil["id_usuario"], perfil["usuario"], perfil["nombre_completo"], perfil["rol"], permisos)

    def puede(self, modulo: str, accion: str = "ver") -> bool:
        return bool(self.permisos.get(modulo, {}).get(accion))

    @property
    def es_admin(self) -> bool:
        return self.rol == "Administrador"

    def modulos_visibles(self) -> list[tuple[str, str, str]]:
        """Solo los módulos que el rol puede ver (HU-14)."""
        return [m for m in MODULOS if self.puede(m[0])]

    @property
    def primer_nombre(self) -> str:
        return self.nombre_completo.split()[0] if self.nombre_completo else self.usuario

    @property
    def descripcion(self) -> str:
        return f"{self.rol} · {self.caja}" if self.caja else self.rol
