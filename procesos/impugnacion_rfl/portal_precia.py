"""Descarga del archivo de Renta Fija Local desde el portal de Precia (Selenium).

Ruta manual (paso 3):
  Servicios > Renta Fija > Area de clientes renta fija > Archivos Renta Fija
  Local > seleccionar la fecha de hoy > descargar el archivo SXMMDDYY.

Se usa Selenium (pedido del usuario) por ser un WordPress con posible JS/redirects.

IMPORTANTE: los selectores reales del portal AUN NO SE CONOCEN. Estan en el
bloque `# === SELECTORES A VERIFICAR ===` como constantes y hay que capturarlos
corriendo `scripts/explorar_portal.py` en modo headed (page/driver pausado).
Mientras no se confirmen, la descarga real fallara con PortalError explicito.
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


# ===========================================================================
# === SELECTORES A VERIFICAR ===  (capturar con scripts/explorar_portal.py) ==
# ===========================================================================
SEL_LOGIN_USUARIO = "input#user_login"       # WordPress estandar: campo 'log'
SEL_LOGIN_CLAVE = "input#user_pass"          # WordPress estandar: campo 'pwd'
SEL_LOGIN_BOTON = "input#wp-submit"
# TODO(portal): confirmar la cadena de navegacion real hasta la descarga.
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

    def __init__(self, url_login: str, timeout_seg: int = 120, logger=None,
                 carpeta_screenshots: Path = Path("logs")) -> None:
        self.url_login = url_login
        self.timeout_seg = timeout_seg
        self.logger = logger
        self.carpeta_screenshots = Path(carpeta_screenshots)

    def _nuevo_driver(self, carpeta_destino: Path, headless: bool):
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        opts = Options()
        if headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        carpeta_destino.mkdir(parents=True, exist_ok=True)
        opts.add_experimental_option("prefs", {
            "download.default_directory": str(carpeta_destino.resolve()),
            "download.prompt_for_download": False,
            "safebrowsing.enabled": True,
        })
        return webdriver.Chrome(options=opts)

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
            # --- Login (WordPress wp-login.php: campos log/pwd) ---
            driver.get(self.url_login)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, SEL_LOGIN_USUARIO)))
            driver.find_element(By.CSS_SELECTOR, SEL_LOGIN_USUARIO).send_keys(usuario)
            driver.find_element(By.CSS_SELECTOR, SEL_LOGIN_CLAVE).send_keys(clave)
            driver.find_element(By.CSS_SELECTOR, SEL_LOGIN_BOTON).click()

            if "wp-login" in driver.current_url and "action=login" not in driver.current_url:
                self._screenshot(driver, "login_fallido")
                raise PortalError("Login rechazado (credenciales invalidas?).")

            # --- Navegacion hasta el archivo del dia (TODO: cablear con selectores reales) ---
            # driver.find_element(By.CSS_SELECTOR, SEL_MENU_SERVICIOS).click()
            # ... etc, seleccionar fecha, click en SEL_LINK_DESCARGA ...
            raise PortalError(
                "Navegacion/descarga pendiente de cablear con selectores reales."
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
