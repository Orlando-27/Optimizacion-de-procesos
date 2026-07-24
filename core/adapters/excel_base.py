"""Interfaz del motor de transformacion (la 'macro').

Decision de diseño (pivote acordado): la macro VBA se MIGRA a Python. La
implementacion principal sera ``transform_python.py`` (pandas/openpyxl), que
reimplementa la logica del .xlsm sin depender de Excel de escritorio -> corre
en Linux/GCP.

Se conserva ``ExcelRunner`` + ``excel_com.py`` como fallback documentado para
el caso de que la logica sea demasiado costosa de migrar y haya que ejecutar el
VBA original via COM en Windows.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class TransformadorImpugnacion(ABC):
    """Toma el archivo plano descargado y produce ``Renta Fija.xlsx``."""

    @abstractmethod
    def generar_reporte(self, archivo_entrada: Path, carpeta_salida: Path) -> Path:
        """Devuelve la ruta del ``Renta Fija.xlsx`` generado."""


class ExcelRunner(ABC):
    """Fallback: correr el VBA original via COM (solo Windows)."""

    @abstractmethod
    def correr_macro(
        self,
        ruta_libro: Path,
        nombre_macro: str,
        visible: bool = False,
        timeout_seg: int = 300,
    ) -> None:
        ...
