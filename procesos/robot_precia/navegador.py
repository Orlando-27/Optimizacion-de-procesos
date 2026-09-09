"""Navegacion y descarga de insumos del portal de Precia (Robot Precia).

Reutiliza el login/driver/datepicker/espera-de-descarga ya PROBADOS en
``impugnacion_rfl.portal_precia.PortalPreciaSelenium`` y agrega la navegacion
por las distintas areas/secciones (segun ``secciones.py``) para cada insumo.

Flujo por insumo (NavegadorSelenium.descargar):
  1. Ir al area de clientes (landing_url) y hacer clic en el boton de la seccion.
  2. Entrar al iframe #BranderFrame (app JSF/PrimeFaces).
  3. Seleccionar la fecha objetivo en el datepicker inline.
  4. Aplicar filtro de texto si la seccion lo requiere (FWD / SWAPCC).
  5. Ir a la pagina indicada (paginador PrimeFaces) si no es la 1.
  6. Ubicar la fila cuyo nombre empieza por el prefijo y hacer clic en su descarga.
  7. Esperar a que termine la descarga (archivo estable en la carpeta destino).

Dos implementaciones:
  - NavegadorSimulado : sin portal; crea placeholders. Para test/offline.
  - NavegadorSelenium : descarga real. Las secciones cuyos selectores aun no se
                        capturaron (ver secciones.py) fallan con NavegadorError
                        explicito ("pendiente de mapear").
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path

from procesos.robot_precia.config_robot import ConfigRobot, Insumo
from procesos.robot_precia.fechas import render_nombre
from procesos.robot_precia.secciones import SECCIONES, seccion_lista


class NavegadorError(Exception):
    """Fallo al navegar o descargar un insumo del portal."""


class NavegadorPrecia(ABC):
    @abstractmethod
    def abrir(self) -> None: ...
    @abstractmethod
    def descargar(self, insumo: Insumo, fecha: date) -> Path: ...
    @abstractmethod
    def cerrar(self) -> None: ...


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
    """Descarga real. Reutiliza PortalPreciaSelenium para login y utilidades."""

    def __init__(self, cfg: ConfigRobot, logger=None) -> None:
        self.cfg = cfg
        self.logger = logger
        self._portal = None
        self._driver = None
        self._wait = None
        # Estado para evitar re-navegar si el insumo es de la misma seccion/fecha.
        self._contexto = (None, None, None)  # (area, seccion, fecha)

    # ------------------------------------------------------------------ abrir
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

    # -------------------------------------------------------------- descargar
    def descargar(self, insumo: Insumo, fecha: date) -> Path:
        if not seccion_lista(insumo.area, insumo.seccion):
            raise NavegadorError(
                f"Seccion '{insumo.area} > {insumo.seccion}' pendiente de mapear "
                "(ver secciones.py / Bloque 2). Capturar con scripts/explorar_portal.py."
            )
        from selenium.webdriver.common.by import By

        carpeta = self.cfg.carpeta_destino
        ctx_nuevo = (insumo.area, insumo.seccion, fecha)
        # Solo re-navegar si cambio la seccion o la fecha (optimizacion).
        if ctx_nuevo != self._contexto:
            self._abrir_seccion(insumo)
            self._portal._seleccionar_fecha(self._driver, self._wait, fecha)
            if insumo.filtro:
                self._aplicar_filtro(insumo)
            if insumo.pagina and insumo.pagina > 1:
                self._ir_a_pagina(insumo.pagina)
            self._contexto = ctx_nuevo

        antes = self._portal._archivos_en(carpeta)
        nombre = render_nombre(insumo.patron, fecha)
        link = self._buscar_fila_descarga(nombre, insumo.prefijo)
        link.click()
        ruta = self._portal._esperar_descarga(carpeta, insumo.prefijo, antes)
        if self.logger:
            self.logger.info("insumo_descargado",
                             extra={"insumo": insumo.prefijo, "fecha": str(fecha),
                                    "archivo": Path(ruta).name})
        return ruta

    # ------------------------------------------------------------ navegacion
    def _abrir_seccion(self, insumo: Insumo) -> None:
        """Va al area de clientes, hace clic en la seccion y entra al iframe."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC

        cfg = SECCIONES[insumo.area]
        boton = cfg["botones"][insumo.seccion]
        self._driver.switch_to.default_content()
        self._driver.get(cfg["landing_url"])
        self._wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
        self._wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, boton))).click()
        # Entrar al iframe con la app JSF y esperar a que cargue el datepicker.
        self._wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, cfg["iframe"])))
        self._wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, ".ui-datepicker-calendar, [id$='_input']")))

    def _aplicar_filtro(self, insumo: Insumo) -> None:
        """Escribe el texto de filtro (FWD/SWAPCC) en el input de la seccion."""
        from selenium.webdriver.common.by import By

        selector = SECCIONES[insumo.area].get("filtros", {}).get(insumo.seccion)
        if not selector or selector == "TODO":
            raise NavegadorError(
                f"Falta el selector del filtro para '{insumo.seccion}' "
                "(capturarlo en secciones.py)."
            )
        campo = self._driver.find_element(By.CSS_SELECTOR, selector)
        campo.clear()
        campo.send_keys(insumo.filtro)
        time.sleep(2)  # dar tiempo al filtrado ajax de PrimeFaces

    def _ir_a_pagina(self, pagina: int) -> None:
        """Hace clic en el numero de pagina del paginador de PrimeFaces."""
        from selenium.webdriver.common.by import By

        try:
            self._driver.find_element(
                By.XPATH,
                f"//a[contains(@class,'ui-paginator-page') and normalize-space(text())='{pagina}']",
            ).click()
            time.sleep(2)
        except Exception as e:  # noqa: BLE001
            raise NavegadorError(f"No se pudo ir a la pagina {pagina}: {e}") from e

    def _buscar_fila_descarga(self, nombre: str, prefijo: str):
        """Ubica el enlace de descarga de la fila del insumo.

        Estrategia (de mas a menos preciso), con timeout CORTO para no colgarse:
          1. Fila cuyo data-rk/texto CONTIENE el nombre completo (con fecha) ->
             desambigua nombres que comparten prefijo (p.ej. los dos 'MX...').
          2. Fila cuyo data-rk/texto EMPIEZA por el prefijo (fallback: prefijos
             unicos como 'Fwd_USDCOP_Diaria_' cuyo formato de fecha no conocemos).
        La imagen de descarga siempre es descargar.png.
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        # timeout corto: si no esta en esta pagina, falla rapido y sigue.
        wait_corto = WebDriverWait(self._driver, 20)
        candidatos = [
            f"//tr[contains(@data-rk, '{nombre}')]//a[.//img[contains(@src,'descargar')]]",
            f"//tr[.//*[contains(normalize-space(.), '{nombre}')]]"
            f"//a[.//img[contains(@src,'descargar')]]",
            f"//tr[starts-with(@data-rk, '{prefijo}')]//a[.//img[contains(@src,'descargar')]]",
            f"//tr[.//*[starts-with(normalize-space(.), '{prefijo}')]]"
            f"//a[.//img[contains(@src,'descargar')]]",
        ]
        for xp in candidatos:
            try:
                return wait_corto.until(EC.element_to_be_clickable((By.XPATH, xp)))
            except Exception:  # noqa: BLE001
                continue
        self._portal._screenshot(self._driver, f"fila_no_encontrada_{prefijo}")
        raise NavegadorError(
            f"No se encontro la fila del insumo '{nombre}' (prefijo '{prefijo}') "
            "en la pagina actual (¿publicado? ¿pagina correcta?)."
        )

    # ------------------------------------------------------------------ cerrar
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
