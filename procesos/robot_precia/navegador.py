"""Navegacion y descarga de insumos del portal de Precia (Robot Precia).

Reutiliza el login/driver/datepicker/espera-de-descarga ya PROBADOS en
``impugnacion_rfl.portal_precia.PortalPreciaSelenium`` y agrega la navegacion
por las distintas areas (Clientes Renta Fija Local, Renta Variable, Derivados,
Productos Estructurados) para cada insumo.

Dos implementaciones detras de la misma interfaz:
  - NavegadorSimulado : sin portal; crea archivos placeholder. Para test/offline.
  - NavegadorSelenium : descarga real. La navegacion por area/seccion se cablea
                        en el Bloque 3 con los selectores capturados (Bloque 2).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path

from procesos.robot_precia.config_robot import ConfigRobot, Insumo
from procesos.robot_precia.fechas import render_nombre


class NavegadorError(Exception):
    """Fallo al navegar o descargar un insumo del portal."""


class NavegadorPrecia(ABC):
    """Interfaz de navegacion/descarga de un insumo para una fecha dada."""

    @abstractmethod
    def abrir(self) -> None:
        """Inicia el navegador y hace login (una sola vez por corrida)."""

    @abstractmethod
    def descargar(self, insumo: Insumo, fecha: date) -> Path:
        """Descarga el insumo para la fecha y devuelve la ruta del archivo."""

    @abstractmethod
    def cerrar(self) -> None:
        """Cierra el navegador. Idempotente."""


class NavegadorSimulado(NavegadorPrecia):
    """Crea archivos placeholder como si se hubieran descargado (test/offline)."""

    def __init__(self, carpeta_destino: Path, logger=None) -> None:
        self.carpeta_destino = Path(carpeta_destino)
        self.logger = logger

    def abrir(self) -> None:
        self.carpeta_destino.mkdir(parents=True, exist_ok=True)

    def descargar(self, insumo: Insumo, fecha: date) -> Path:
        nombre = render_nombre(insumo.patron, fecha)
        destino = self.carpeta_destino / nombre
        destino.write_text(
            f"SIMULADO | {insumo.categoria} | {nombre} | {fecha:%Y-%m-%d}\n",
            encoding="utf-8",
        )
        if self.logger:
            self.logger.info("insumo_simulado",
                             extra={"insumo": insumo.prefijo, "fecha": str(fecha),
                                    "archivo": nombre})
        return destino

    def cerrar(self) -> None:
        pass


class NavegadorSelenium(NavegadorPrecia):
    """Descarga real con Selenium. Reutiliza PortalPreciaSelenium para login y
    utilidades; la navegacion por area/seccion se cablea en el Bloque 3.

    NOTA: cada 'area' del portal (Clientes Renta Variable, Clientes Derivados,
    Clientes Productos Estructurados) es una seccion NUEVA que hay que mapear
    (Bloque 2) con scripts/explorar_portal.py; hasta entonces, esas descargas
    fallan con NavegadorError explicito.
    """

    def __init__(self, cfg: ConfigRobot, logger=None) -> None:
        self.cfg = cfg
        self.logger = logger
        self._portal = None
        self._driver = None
        self._wait = None
        self._area_actual: str | None = None

    def abrir(self) -> None:
        from selenium.webdriver.support.ui import WebDriverWait

        from core.secrets import secretos_del_portal
        from procesos.impugnacion_rfl.portal_precia import PortalPreciaSelenium

        usuario, clave = secretos_del_portal()
        if not (usuario and clave):
            raise NavegadorError("Faltan credenciales del portal (PRECIA_USUARIO/CLAVE).")
        self._portal = PortalPreciaSelenium(
            url_login=self.cfg.portal.url_login,
            timeout_seg=self.cfg.portal.timeout_seg,
            logger=self.logger,
        )
        self._driver = self._portal._nuevo_driver(self.cfg.carpeta_destino,
                                                  headless=self.cfg.portal.headless)
        self._portal._forzar_descarga_dir(self._driver, self.cfg.carpeta_destino)
        self._wait = WebDriverWait(self._driver, self.cfg.portal.timeout_seg)
        self._portal.login(self._driver, self._wait, usuario, clave)

    def descargar(self, insumo: Insumo, fecha: date) -> Path:
        # === PENDIENTE (Bloque 3): navegacion real por area/seccion ===
        # Pasos por insumo (reutilizando utilidades de PortalPreciaSelenium):
        #   1. Ir al area de clientes correspondiente (insumo.area) y entrar al
        #      iframe #BranderFrame (como en impugnacion).
        #   2. Abrir la seccion (insumo.seccion) -> boton del menu.
        #   3. Seleccionar la fecha (self._portal._seleccionar_fecha).
        #   4. Si insumo.filtro: escribirlo en el filtro de la tabla.
        #   5. Ir a insumo.pagina (paginador) si != 1.
        #   6. Ubicar la fila cuyo nombre empieza por insumo.prefijo y hacer clic
        #      en su descarga.
        #   7. self._portal._esperar_descarga(carpeta, prefijo, antes).
        raise NavegadorError(
            f"Seccion '{insumo.area} > {insumo.seccion}' pendiente de mapear "
            "(Bloque 2/3). Capturar selectores con scripts/explorar_portal.py."
        )

    def cerrar(self) -> None:
        if self._driver is not None:
            try:
                self._driver.quit()
            except Exception:  # noqa: BLE001
                pass
            self._driver = None


def crear_navegador(cfg: ConfigRobot, logger=None) -> NavegadorPrecia:
    """Fabrica segun backend_portal: 'simulado' | 'selenium'."""
    if cfg.backend_portal_activo == "selenium":
        return NavegadorSelenium(cfg, logger)
    return NavegadorSimulado(cfg.carpeta_destino, logger)
