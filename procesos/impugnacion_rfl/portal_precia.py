"""Descarga del archivo de Renta Fija Local desde el portal de Precia (Selenium).

Ruta manual (paso 3):
  Servicios > Renta Fija > Area de clientes renta fija > Archivos Renta Fija
  Local > seleccionar la fecha de hoy > descargar el archivo SXMMDDYY.

Se usa Selenium (pedido del usuario) por ser un WordPress con posible JS/redirects.

Estado de los selectores:
  - LOGIN: CONFIRMADO contra el DOM real de www.precia.co/wp-login.php
    (campos #user_login/'log', #user_pass/'pwd', boton #wp-submit).
  - NAVEGACION/DESCARGA: el area de clientes esta detras del login, asi que
    esos selectores solo se pueden capturar con credenciales. Estan en el bloque
    `# === SELECTORES A VERIFICAR ===` y se capturan con scripts/explorar_portal.py.
    Mientras no se confirmen, la descarga real falla con PortalError explicito.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.contract import ProcesoError


class PortalError(ProcesoError):
    """Fallo al interactuar con el portal (login, navegacion, descarga)."""


# URLs base del portal (CONFIRMADAS en el sitio publico).
URL_LOGIN = "https://www.precia.co/wp-login.php"
URL_SERVICIOS = "https://www.precia.co/index.php/servicios/"
URL_RENTA_FIJA = "https://www.precia.co/index.php/servicios-renta-fija/"

# --- Selectores de LOGIN: CONFIRMADOS contra el DOM real (2026-07) ---
SEL_LOGIN_USUARIO = "input#user_login"       # WordPress: campo 'log'
SEL_LOGIN_CLAVE = "input#user_pass"          # WordPress: campo 'pwd'
SEL_LOGIN_BOTON = "input#wp-submit"
SEL_LOGIN_ERROR = "#login_error"             # mensaje de credenciales invalidas

# ===========================================================================
# === SELECTORES A VERIFICAR ===  (detras del login: capturar con
#     scripts/explorar_portal.py usando credenciales reales)                 ==
# ===========================================================================
# URL directa del area de clientes RF si existe (preferible a navegar por menu).
URL_AREA_CLIENTES = "TODO: URL de 'Area de clientes renta fija' (tras login)"
SEL_MENU_SERVICIOS = "TODO: selector de 'Servicios'"
SEL_MENU_RENTA_FIJA = "TODO: selector de 'Renta Fija'"
SEL_AREA_CLIENTES = "TODO: selector de 'Area de clientes renta fija'"
SEL_ARCHIVOS_RFL = "TODO: selector de 'Archivos Renta Fija Local'"
SEL_SELECTOR_FECHA = "TODO: selector del control de fecha"
SEL_LINK_DESCARGA = "TODO: selector del enlace/boton de descarga del archivo del dia"
# ===========================================================================


def nombre_archivo_esperado(fecha: datetime) -> str:
    """Nombre del plano segun el patron SXMMDDYY (visto en el correo)."""
    return f"SX{fecha:%m%d%y}"


class PortalRFL(ABC):
    """Interfaz de descarga; permite intercambiar Selenium por un simulado."""

    @abstractmethod
    def descargar_archivo_rfl(
        self,
        fecha: datetime,
        usuario: str,
        clave: str,
        carpeta_destino: Path,
        headless: bool = True,
    ) -> Path:
        ...


class PortalPreciaSelenium(PortalRFL):
    """Implementacion real con Selenium. Requiere selectores confirmados."""

    def __init__(self, url_login: str = URL_LOGIN, timeout_seg: int = 120, logger=None,
                 carpeta_screenshots: Path = Path("logs"),
                 chrome_binary: Optional[str] = None,
                 chromedriver_path: Optional[str] = None,
                 proxy: Optional[str] = None) -> None:
        self.url_login = url_login
        self.timeout_seg = timeout_seg
        self.logger = logger
        self.carpeta_screenshots = Path(carpeta_screenshots)
        # Overrides opcionales (utiles fuera de Windows o con Chrome portable).
        # Tambien se leen de variables de entorno para no tocar codigo.
        import os
        self.chrome_binary = chrome_binary or os.environ.get("CHROME_BINARY")
        self.chromedriver_path = chromedriver_path or os.environ.get("CHROMEDRIVER_PATH")
        self.proxy = proxy or os.environ.get("SELENIUM_PROXY")

    def _nuevo_driver(self, carpeta_destino: Path, headless: bool):
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service

        opts = Options()
        if headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        if self.chrome_binary:
            opts.binary_location = self.chrome_binary
        if self.proxy:
            opts.add_argument(f"--proxy-server={self.proxy}")
        carpeta_destino.mkdir(parents=True, exist_ok=True)
        opts.add_experimental_option("prefs", {
            "download.default_directory": str(carpeta_destino.resolve()),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        })
        if self.chromedriver_path:
            return webdriver.Chrome(service=Service(self.chromedriver_path), options=opts)
        return webdriver.Chrome(options=opts)  # Selenium Manager resuelve el driver

    def login(self, driver, wait, usuario: str, clave: str) -> None:
        """Login en wp-login.php. Selectores CONFIRMADos contra el DOM real."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC

        driver.get(self.url_login)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, SEL_LOGIN_USUARIO)))
        driver.find_element(By.CSS_SELECTOR, SEL_LOGIN_USUARIO).send_keys(usuario)
        driver.find_element(By.CSS_SELECTOR, SEL_LOGIN_CLAVE).send_keys(clave)
        driver.find_element(By.CSS_SELECTOR, SEL_LOGIN_BOTON).click()
        # Credenciales invalidas -> WordPress muestra #login_error y sigue en wp-login.
        if driver.find_elements(By.CSS_SELECTOR, SEL_LOGIN_ERROR):
            self._screenshot(driver, "login_fallido")
            raise PortalError("Login rechazado: credenciales invalidas.")
        if "wp-login" in driver.current_url:
            self._screenshot(driver, "login_sin_redireccion")
            raise PortalError("Login no redirigio (¿credenciales o captcha?).")
        if self.logger:
            self.logger.info("portal_login_ok", extra={"url": driver.current_url})

    def descargar_archivo_rfl(
        self,
        fecha: datetime,
        usuario: str,
        clave: str,
        carpeta_destino: Path,
        headless: bool = True,
    ) -> Path:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        # Guardia: no intentar con selectores TODO sin confirmar.
        pendientes = [s for s in (SEL_MENU_SERVICIOS, SEL_LINK_DESCARGA) if s.startswith("TODO")]
        if pendientes:
            raise PortalError(
                "Selectores del portal sin confirmar. Correr "
                "scripts/explorar_portal.py y completar el bloque "
                "'SELECTORES A VERIFICAR' en portal_precia.py."
            )

        carpeta_destino = Path(carpeta_destino)
        driver = self._nuevo_driver(carpeta_destino, headless)
        try:
            wait = WebDriverWait(driver, self.timeout_seg)

            # --- Login (CONFIRMADO) ---
            self.login(driver, wait, usuario, clave)

            # --- Navegacion hasta el archivo del dia ---
            # PENDIENTE: cablear con los selectores capturados tras el login
            # (bloque SELECTORES A VERIFICAR). Preferir URL_AREA_CLIENTES si existe:
            #   driver.get(URL_AREA_CLIENTES)
            #   driver.find_element(By.CSS_SELECTOR, SEL_ARCHIVOS_RFL).click()
            #   # seleccionar la fecha de hoy en SEL_SELECTOR_FECHA
            #   driver.find_element(By.CSS_SELECTOR, SEL_LINK_DESCARGA).click()
            #   return self._esperar_descarga(carpeta_destino, tam_minimo)
            raise PortalError(
                "Navegacion/descarga pendiente de cablear con selectores reales "
                "(capturarlos con scripts/explorar_portal.py usando credenciales)."
            )
        except PortalError:
            raise
        except Exception as e:  # noqa: BLE001
            self._screenshot(driver, "portal_error")
            raise PortalError(f"Error inesperado en el portal: {e}") from e
        finally:
            driver.quit()

    def _esperar_descarga(self, carpeta: Path, tam_minimo: int = 1024) -> Path:
        """Espera a que aparezca un archivo estable (sin .crdownload) y > umbral."""
        fin = time.time() + self.timeout_seg
        while time.time() < fin:
            candidatos = [p for p in carpeta.iterdir()
                          if p.is_file() and not p.name.endswith(".crdownload")]
            for p in candidatos:
                if p.stat().st_size >= tam_minimo:
                    return p
            time.sleep(1)
        raise PortalError("Timeout esperando la descarga (o archivo corrupto/tam 0).")

    def _screenshot(self, driver, etiqueta: str) -> None:
        try:
            self.carpeta_screenshots.mkdir(parents=True, exist_ok=True)
            ruta = self.carpeta_screenshots / f"{etiqueta}_{datetime.now():%Y%m%d_%H%M%S}.png"
            driver.save_screenshot(str(ruta))
            if self.logger:
                self.logger.warning("portal_screenshot", extra={"ruta": str(ruta)})
        except Exception:  # noqa: BLE001
            pass


class PortalSimulado(PortalRFL):
    """Devuelve un archivo de fixture como si se hubiera descargado.

    Uso en test/offline: evita depender del portal real y de credenciales.
    """

    def __init__(self, archivo_fixture: Path, logger=None) -> None:
        self.archivo_fixture = Path(archivo_fixture)
        self.logger = logger

    def descargar_archivo_rfl(
        self,
        fecha: datetime,
        usuario: str,
        clave: str,
        carpeta_destino: Path,
        headless: bool = True,
    ) -> Path:
        import shutil

        carpeta_destino = Path(carpeta_destino)
        carpeta_destino.mkdir(parents=True, exist_ok=True)
        destino = carpeta_destino / nombre_archivo_esperado(fecha)
        if not self.archivo_fixture.exists():
            # Crea un plano minimo para poder ejercitar el pipeline.
            destino.write_text("SIMULADO|archivo plano de prueba RFL\n", encoding="utf-8")
        else:
            shutil.copy2(self.archivo_fixture, destino)
        if self.logger:
            self.logger.info("portal_simulado", extra={"detalle": f"Archivo simulado en {destino}"})
        return destino
