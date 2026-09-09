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

# --- Area de clientes: CONFIRMADO contra el DOM real (2026-07) ---
# Tras el login de WordPress, el area de clientes RF vive aqui:
URL_AREA_CLIENTES = "https://www.precia.co/index.php/renta-fija/"
# Esa pagina embebe una app JSF (Infovalmer-web) en un iframe, servida desde
# otro host (la "ip transaccional"). El menu lateral son <button> que cambian
# el src del iframe. El de "Archivos Renta Fija Local" es #arlo.
IP_TRANSACCIONAL = "https://52.72.176.166:8443"
IFRAME_CONTENIDO = "BranderFrame"                       # id/name del iframe
SEL_BTN_ARCHIVOS_RFL = "#arlo"                          # boton 'Archivos Renta Fija Local'
SEL_BTN_ARCHIVOS_INTL = "#arin"                         # 'Archivos Renta Fija Internacional'
URL_ARCHIVOS_XHTML = (
    IP_TRANSACCIONAL
    + "/Infovalmer-web/faces/security/RentaFija/archivosValoracionRentaFija.xhtml"
)

# --- Dentro del iframe (app JSF PrimeFaces): CONFIRMADO contra el DOM real ---
# Tabla de archivos (id JSF estable, nombrado por el desarrollador):
SEL_TABLA_ARCHIVOS = "form:TablaValoracionRentaFija"
# Calendario inline de PrimeFaces (clase estable):
SEL_DATEPICKER = ".ui-datepicker-calendar"
SEL_DIA_HOY = ".ui-datepicker-today a"                  # celda del dia de hoy
# Cada fila: <tr data-rk="SX072626.001"> con un <a> de descarga (img descargar.png).
IMG_DESCARGA = "descargar"                              # substring del src de la imagen
EXT_ARCHIVO = ".001"                                    # extension real del plano


def nombre_archivo_esperado(fecha: datetime) -> str:
    """Nombre base del plano segun el patron SXMMDDYY (sin extension).

    El portal lo publica como SX{MMDDYY}.001 (p. ej. SX072626.001 para el
    26/07/2026). Aqui devolvemos el prefijo 'SX072626' para buscar la fila.
    """
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
        self._etapa_actual = "init"

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
        opts.add_argument("--window-size=1920,1080")   # que todo quede visible/clicable
        opts.add_argument("--ignore-certificate-errors")  # iframe servido desde una IP (cert)
        opts.set_capability("acceptInsecureCerts", True)
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

        carpeta_destino = Path(carpeta_destino)
        objetivo = nombre_archivo_esperado(fecha)  # p.ej. SX072626
        driver = self._nuevo_driver(carpeta_destino, headless)
        try:
            self._forzar_descarga_dir(driver, carpeta_destino)
            wait = WebDriverWait(driver, self.timeout_seg)

            # 1) Login (CONFIRMADO)
            self._etapa("login")
            self.login(driver, wait, usuario, clave)

            # 2) Area de clientes -> boton 'Archivos Renta Fija Local' (#arlo)
            self._etapa("abrir_area_clientes")
            driver.get(URL_AREA_CLIENTES)
            wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
            self._etapa("click_archivos_rfl")
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, SEL_BTN_ARCHIVOS_RFL))).click()

            # 3) Entrar al iframe con la app JSF (Infovalmer-web)
            self._etapa("entrar_iframe")
            wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, IFRAME_CONTENIDO)))
            self._etapa("esperar_tabla")
            wait.until(EC.presence_of_element_located((By.ID, SEL_TABLA_ARCHIVOS)))

            # 4) Seleccionar la fecha objetivo en el calendario inline
            self._etapa("seleccionar_fecha")
            self._seleccionar_fecha(driver, wait, fecha)

            # 5) Ubicar la fila del archivo SX{MMDDYY} y hacer clic en su descarga
            self._etapa(f"buscar_fila_{objetivo}")
            xpath_link = (
                f"//tr[starts-with(@data-rk, '{objetivo}')]"
                f"//a[.//img[contains(@src, '{IMG_DESCARGA}')]]"
            )
            try:
                link = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_link)))
            except Exception as e:  # noqa: BLE001
                self._screenshot(driver, "archivo_no_encontrado")
                raise PortalError(
                    f"No se encontro el archivo {objetivo}.001 para la fecha "
                    f"{fecha:%d/%m/%Y} (¿aun no publicado?)."
                ) from e

            antes = self._archivos_en(carpeta_destino)
            link.click()

            # 6) Esperar a que TERMINE la descarga del archivo esperado (SX...001).
            #    Ojo: el portal ademas crea un 'downloads.htm' intermedio que se ignora.
            self._etapa("esperar_descarga")
            ruta = self._esperar_descarga(carpeta_destino, objetivo, antes)
            if self.logger:
                self.logger.info("portal_descarga_ok", extra={"ruta": str(ruta)})
            return ruta
        except PortalError:
            raise
        except Exception as e:  # noqa: BLE001
            self._screenshot(driver, f"portal_error_{self._etapa_actual}")
            raise PortalError(
                f"Error en la etapa '{self._etapa_actual}' del portal: "
                f"{type(e).__name__}: {e}"
            ) from e
        finally:
            driver.quit()

    def _etapa(self, nombre: str) -> None:
        """Marca la etapa actual (para logs y para el nombre del screenshot de error)."""
        self._etapa_actual = nombre
        if self.logger:
            self.logger.info("portal_etapa", extra={"etapa": nombre})

    def _seleccionar_fecha(self, driver, wait, fecha: datetime) -> None:
        """Selecciona ``fecha`` en el datepicker inline de PrimeFaces.

        Caso normal (correr el mismo dia): la celda de hoy tiene la clase
        ``ui-datepicker-today``. Para otra fecha del mes visible, se hace clic
        en el numero de dia. La seleccion dispara un ajax que recarga la tabla.
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC

        dia = str(fecha.day)
        # Dia dentro del mes visible, no deshabilitado ni de otro mes.
        xpath_dia = (
            "//table[contains(@class,'ui-datepicker-calendar')]"
            "//td[not(contains(@class,'ui-state-disabled')) "
            "and not(contains(@class,'other-month'))]"
            f"/a[normalize-space(text())='{dia}']"
        )
        try:
            celda = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_dia)))
            celda.click()
            time.sleep(2)  # dar tiempo al ajax que recarga la tabla
        except Exception:  # noqa: BLE001
            # Si el calendario ya trae la fecha correcta por defecto, seguir.
            if self.logger:
                self.logger.warning(
                    "datepicker_sin_click",
                    extra={"detalle": f"No se pudo clicar el dia {dia}; se usa la fecha por defecto."},
                )

    @staticmethod
    def _archivos_en(carpeta: Path) -> set[str]:
        return {p.name for p in Path(carpeta).iterdir() if p.is_file()}

    def _forzar_descarga_dir(self, driver, carpeta: Path) -> None:
        """Refuerza la carpeta de descarga via CDP (necesario en headless)."""
        try:
            driver.execute_cdp_cmd(
                "Page.setDownloadBehavior",
                {"behavior": "allow", "downloadPath": str(Path(carpeta).resolve())},
            )
        except Exception:  # noqa: BLE001
            pass

    def _esperar_descarga(
        self, carpeta: Path, objetivo: str, antes: set[str], tam_minimo: int = 1
    ) -> Path:
        """Espera a que TERMINE la descarga del archivo esperado (``objetivo``).

        El portal descarga el plano como ``SX{MMDDYY}.001`` (archivo grande) y de
        paso crea un ``downloads.htm`` intermedio: se ignora todo lo que no
        empiece por ``objetivo`` y lo que aun este en ``.crdownload/.tmp/.part``.
        Chrome renombra el ``.crdownload`` al nombre final SOLO al completar.
        """
        carpeta = Path(carpeta)
        pref = objetivo.upper()
        temporales = (".crdownload", ".tmp", ".part")
        fin = time.time() + self.timeout_seg
        while time.time() < fin:
            descargando = False
            for p in carpeta.iterdir():
                if not p.is_file() or not p.name.upper().startswith(pref):
                    continue
                if p.name.endswith(temporales):
                    descargando = True  # aun en progreso
                    continue
                if p.name in antes:
                    continue
                if p.stat().st_size >= tam_minimo:
                    self._limpiar_intermedios(carpeta, antes)
                    return p
            if self.logger and descargando:
                self.logger.info("portal_descarga_en_progreso", extra={"objetivo": objetivo})
            time.sleep(1)
        raise PortalError(
            f"Timeout esperando que termine la descarga de '{objetivo}*' "
            f"(¿conexion lenta, o el archivo ya existia y no se genero uno nuevo? "
            f"subir portal.timeout_seg)."
        )

    @staticmethod
    def _limpiar_intermedios(carpeta: Path, antes: set[str]) -> None:
        """Borra archivos intermedios nuevos (p. ej. downloads.htm)."""
        for p in Path(carpeta).iterdir():
            if p.is_file() and p.name not in antes and p.name.lower().endswith((".htm", ".html")):
                try:
                    p.unlink()
                except Exception:  # noqa: BLE001
                    pass

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
