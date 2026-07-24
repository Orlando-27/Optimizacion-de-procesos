"""Implementacion de ``Storage`` sobre el filesystem local / rutas UNC.

Es portable (Linux y Windows). En Windows produccion, las rutas destino son
UNC (``\\\\SERVIDOR\\share\\...``), no ``M:\\`` (ver README: el Programador de
Tareas en sesion no interactiva no ve las unidades mapeadas).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from core.adapters.storage_base import Storage


class StorageLocal(Storage):
    def guardar(self, contenido: bytes, destino: Path) -> Path:
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(contenido)
        return destino

    def existe(self, ruta: Path) -> bool:
        return Path(ruta).exists()

    def listar(self, carpeta: Path, patron: str = "*") -> list[Path]:
        carpeta = Path(carpeta)
        if not carpeta.exists():
            return []
        return sorted(carpeta.glob(patron))

    def copiar(self, origen: Path, destino: Path) -> Path:
        origen, destino = Path(origen), Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origen, destino)
        return destino

    def mas_reciente(self, carpeta: Path, patron: str = "*") -> Path | None:
        """Archivo mas reciente por fecha de modificacion (util para INFOVALMER)."""
        archivos = self.listar(carpeta, patron)
        if not archivos:
            return None
        return max(archivos, key=lambda p: p.stat().st_mtime)
