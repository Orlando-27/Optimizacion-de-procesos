"""Interfaz generica de almacenamiento.

``storage_local.py`` la implementa sobre el filesystem (rutas UNC en Windows).
Un futuro ``storage_gcs.py`` la implementaria sobre Google Cloud Storage sin
tocar el proceso.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class Storage(ABC):
    @abstractmethod
    def guardar(self, contenido: bytes, destino: Path) -> Path:
        """Escribe ``contenido`` en ``destino`` y devuelve la ruta final."""

    @abstractmethod
    def existe(self, ruta: Path) -> bool:
        ...

    @abstractmethod
    def listar(self, carpeta: Path, patron: str = "*") -> list[Path]:
        ...

    @abstractmethod
    def copiar(self, origen: Path, destino: Path) -> Path:
        ...
