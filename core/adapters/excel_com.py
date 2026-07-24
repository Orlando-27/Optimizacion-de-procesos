"""Fallback: ejecutar la macro VBA original vía Excel COM (solo Windows).

Plan B del PASO 5 si migrar la lógica a Python resulta demasiado costoso. NO es
la ruta preferida (ata prod a Windows + Excel de escritorio). En Linux importa
pero falla al instanciar, por diseño.

Detalles del spec (5.4):
- DispatchEx("Excel.Application") -> instancia aislada, no roba el Excel del usuario.
- DisplayAlerts=False, AutomationSecurity=1 (msoAutomationSecurityLow).
- Application.Run(nombre_macro).
- SIEMPRE cerrar libro y Quit() en finally; matar EXCEL.EXE si queda colgado.
"""

from __future__ import annotations

from pathlib import Path

from core.adapters.excel_base import ExcelRunner, TransformadorImpugnacion


class ExcelRunnerCom(ExcelRunner):
    def __init__(self, logger=None) -> None:
        self.logger = logger

    def correr_macro(
        self,
        ruta_libro: Path,
        nombre_macro: str,
        visible: bool = False,
        timeout_seg: int = 300,
    ) -> None:
        try:
            import win32com.client  # type: ignore
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(
                "ExcelRunnerCom requiere Windows + pywin32 + Excel. "
                "En Linux/GCP migrar la macro a Python (TransformadorImpugnacionPython)."
            ) from e

        xl = win32com.client.DispatchEx("Excel.Application")
        wb = None
        try:
            xl.Visible = visible
            xl.DisplayAlerts = False
            xl.AutomationSecurity = 1  # msoAutomationSecurityLow: no pregunta por macros
            wb = xl.Workbooks.Open(str(Path(ruta_libro).resolve()))
            xl.Application.Run(nombre_macro)
            wb.Save()
            if self.logger:
                self.logger.info("macro_ejecutada", extra={"macro": nombre_macro})
        finally:
            try:
                if wb is not None:
                    wb.Close(SaveChanges=True)
            except Exception:  # noqa: BLE001
                pass
            try:
                xl.Quit()
            except Exception:  # noqa: BLE001
                pass
            self._matar_excel_colgado()

    @staticmethod
    def _matar_excel_colgado() -> None:
        """Best-effort: si quedo un EXCEL.EXE huerfano tras el timeout, matarlo."""
        try:
            import subprocess
            subprocess.run(["taskkill", "/F", "/IM", "EXCEL.EXE"],
                           capture_output=True, check=False)
        except Exception:  # noqa: BLE001
            pass


class TransformadorViaCOM(TransformadorImpugnacion):
    """Envuelve ExcelRunnerCom para cumplir la interfaz de transformación."""

    def __init__(self, ruta_xlsm: Path, nombre_macro: str,
                 archivo_salida: str = "Renta Fija.xlsx", timeout_seg: int = 300,
                 logger=None) -> None:
        self.ruta_xlsm = Path(ruta_xlsm)
        self.nombre_macro = nombre_macro
        self.archivo_salida = archivo_salida
        self.timeout_seg = timeout_seg
        self.logger = logger

    def generar_reporte(self, archivo_entrada: Path, carpeta_salida: Path) -> Path:
        runner = ExcelRunnerCom(self.logger)
        runner.correr_macro(self.ruta_xlsm, self.nombre_macro, timeout_seg=self.timeout_seg)
        return Path(carpeta_salida) / self.archivo_salida
