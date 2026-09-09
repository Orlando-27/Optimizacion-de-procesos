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
        # Idempotencia: si el insumo ya esta descargado para esa fecha, no lo
        # vuelve a bajar (evita duplicados y re-descargas al re-ejecutar).
        ya = self._ya_descargado(insumo, fecha, carpeta)
        if ya is not None:
            if self.logger:
                self.logger.info("insumo_ya_existe",
                                 extra={"insumo": insumo.prefijo, "fecha": str(fecha),
                                        "archivo": ya.name})
            return ya

        # Enrutar segun el flujo del area: "agrupador" (Derivados) o "directo" (RF).
        if SECCIONES[insumo.area].get("flujo") == "agrupador":
            return self._descargar_agrupador(insumo, fecha, carpeta)

        ctx_nuevo = (insumo.area, insumo.seccion, fecha)
        # Solo re-navegar si cambio la seccion o la fecha (optimizacion).
        if ctx_nuevo != self._contexto:
            self._abrir_seccion(insumo)
            self._portal._seleccionar_fecha(self._driver, self._wait, fecha)
            if insumo.filtro:
                self._aplicar_filtro(insumo)
            self._contexto = ctx_nuevo

        antes = self._portal._archivos_en(carpeta)
        nombre = render_nombre(insumo.patron, fecha)
        # Busca el insumo recorriendo TODAS las paginas de la tabla (no depende
        # de un numero de pagina fijo: el archivo puede estar en 1, 2, ...).
        link = self._buscar_multipagina(nombre, insumo.prefijo)
        link.click()
        ruta = self._portal._esperar_descarga(carpeta, insumo.prefijo, antes)
        if self.logger:
            self.logger.info("insumo_descargado",
                             extra={"insumo": insumo.prefijo, "fecha": str(fecha),
                                    "archivo": Path(ruta).name})
        return ruta

    # -------------------------------------------------- flujo AGRUPADOR (Derivados)
    def _descargar_agrupador(self, insumo: Insumo, fecha: date, carpeta: Path) -> Path:
        """Flujo de Derivados: menu -> grupo -> fecha (popup) -> Buscar -> filtro
        por columna Prefijo (FWD/SWAPCC) -> ubicar por nombre -> descargar."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC

        cfg = SECCIONES[insumo.area]
        sel = cfg["sel"]
        grupo = cfg["grupos"][insumo.seccion]
        # Cache por (area, grupo, fecha): solo re-selecciona grupo+fecha+Buscar
        # cuando cambian. Todos los insumos de un mismo grupo/fecha comparten la
        # misma tabla, asi que la navegacion pesada se hace una sola vez.
        ctx_nuevo = (insumo.area, grupo, fecha)
        if ctx_nuevo != self._contexto:
            self._abrir_seccion(insumo)  # landing -> #descagrup -> iframe
            self._wait.until(EC.presence_of_element_located((By.ID, sel["agrupador"])))
            self._seleccionar_grupo(sel["agrupador"], grupo)
            self._seleccionar_fecha_popup(sel["fecha"], fecha)
            self._clic(sel["buscar"])
            time.sleep(3)  # cargar la tabla (formDescarga2)
            self._contexto = ctx_nuevo
            # Diagnostico: cuantas filas/enlaces de descarga cargaron para este
            # grupo+fecha. Si es 0, el problema es la seleccion (grupo/fecha) o
            # que ese dia no se publico nada, NO la busqueda de un insumo puntual.
            n = self._contar_descargas_visibles()
            if self.logger:
                self.logger.info("agrupador_tabla_cargada",
                                 extra={"area": insumo.area, "grupo": grupo,
                                        "fecha": str(fecha), "filas_descargables": n})
            self._portal._screenshot(self._driver, f"agrupador_{grupo.replace(' ', '_')}")
            # DIAGNOSTICO opcional: con la variable de entorno ROBOT_DUMP_FILAS=1
            # se vuelca en el log ('agrupador_filas_reales') el prefijo real de
            # todas las filas del grupo. Util para mapear un area nueva o depurar;
            # apagado por defecto para no ralentizar la corrida de las 4 a.m.
            import os
            if os.environ.get("ROBOT_DUMP_FILAS"):
                self._volcar_filas_tabla(sel.get("tabla"))
                # El volcado deja el paginador en la ultima pagina;
                # _buscar_multipagina vuelve a la primera antes de buscar.

        # NOTA: NO se aplica filtro por la columna "Prefijo". La seleccion del
        # grupo ya acota la tabla a unas pocas decenas de archivos y la busqueda
        # multipagina localiza cada insumo por su nombre completo (o prefijo).
        # Un filtro de columna con un valor equivocado (p.ej. 'Matriz_TC_' no
        # empieza por 'FWD') OCULTARIA la fila objetivo y no se descargaria nada.

        antes = self._portal._archivos_en(carpeta)
        nombre = render_nombre(insumo.patron, fecha)
        link = self._buscar_multipagina(nombre, insumo.prefijo)
        link.click()
        ruta = self._portal._esperar_descarga(carpeta, insumo.prefijo, antes)
        if self.logger:
            self.logger.info("insumo_descargado",
                             extra={"insumo": insumo.prefijo, "fecha": str(fecha),
                                    "archivo": Path(ruta).name})
        return ruta

    def _volcar_filas_tabla(self, tabla_id: str | None) -> None:
        """Registra en el log el texto real de TODAS las filas de la tabla,
        recorriendo todas las paginas del paginador.

        Sirve para descubrir como aparecen los archivos en el portal (columna
        Prefijo y nombre) y asi ajustar ``insumos.yaml`` a los valores reales.
        Se limita a 80 filas en total para no saturar el log.
        """
        from selenium.webdriver.common.by import By
        if not self.logger:
            return
        try:
            self._ir_primera_pagina()
            textos: list[str] = []
            paginas = 0
            while True:
                if tabla_id:
                    cuerpo = self._driver.find_element(By.ID, f"{tabla_id}_data")
                    filas = cuerpo.find_elements(By.XPATH, "./tr")
                else:
                    filas = self._driver.find_elements(
                        By.XPATH, "//tr[.//a[.//img[contains(@src,'descargar')]]]")
                for fila in filas:
                    t = " ".join(fila.text.split())
                    if t:
                        textos.append(t)
                paginas += 1
                if len(textos) >= 80 or paginas > 20 or not self._siguiente_pagina():
                    break
            self.logger.warning("agrupador_filas_reales",
                                 extra={"n": len(textos), "filas": textos})
        except Exception as e:  # noqa: BLE001
            self.logger.warning("agrupador_filas_error", extra={"detalle": str(e)})

    def _seleccionar_grupo(self, dropdown_id: str, etiqueta: str) -> None:
        """Selecciona una opcion en un PrimeFaces SelectOneMenu por su etiqueta.

        El menu 'autAgrupador' es filtrable (trae un input '<id>_filter'). Si
        existe, se escribe la etiqueta para acotar la lista antes de clicar el
        item; asi se evita depender del scroll con 13 grupos. Se matchea por
        data-label normalizando espacios (algunas etiquetas traen doble espacio,
        p.ej. 'Insumos Swaps  Internacionales').
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC

        self._esperar_sin_overlay()
        self._wait.until(EC.element_to_be_clickable((By.ID, dropdown_id))).click()
        time.sleep(0.5)
        # Si el SelectOneMenu tiene caja de filtro, escribir para acotar.
        try:
            caja = self._driver.find_element(By.ID, f"{dropdown_id}_filter")
            caja.clear()
            caja.send_keys(etiqueta.split()[1] if len(etiqueta.split()) > 1 else etiqueta)
            time.sleep(0.7)
        except Exception:  # noqa: BLE001 - menu sin filtro: se clica directo
            pass
        # El panel de items es <ul id="<dropdown>_items">.
        xp = (f"//ul[@id='{dropdown_id}_items']"
              f"/li[normalize-space(@data-label)='{etiqueta}']")
        li = self._wait.until(EC.presence_of_element_located((By.XPATH, xp)))
        self._driver.execute_script("arguments[0].scrollIntoView({block:'center'});", li)
        try:
            li.click()
        except Exception:  # noqa: BLE001
            self._driver.execute_script("arguments[0].click();", li)
        time.sleep(1)

    def _contar_descargas_visibles(self) -> int:
        """Cuenta los enlaces de descarga visibles en la tabla actual."""
        from selenium.webdriver.common.by import By
        try:
            return len(self._driver.find_elements(
                By.XPATH, "//a[.//img[contains(@src,'descargar')]]"))
        except Exception:  # noqa: BLE001
            return -1

    def _seleccionar_fecha_popup(self, fecha_span_id: str, fecha: date) -> None:
        """Abre el datepicker popup (boton dentro del span) y selecciona el dia.

        La seleccion del grupo dispara un ajax de PrimeFaces que puede dejar por
        un instante una mascara de bloqueo (.ui-blockui) o el panel del
        desplegable sobre el boton del calendario -> un click normal daria
        'element click intercepted'. Por eso: (1) se espera a que desaparezca
        cualquier overlay, y (2) se pulsa el trigger por JavaScript, que no
        depende de que el elemento este 'despejado' en pantalla.
        """
        from selenium.webdriver.common.by import By

        self._esperar_sin_overlay()
        span = self._driver.find_element(By.ID, fecha_span_id)
        trigger = span.find_element(By.CSS_SELECTOR, ".ui-datepicker-trigger")
        self._driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});", trigger)
        self._driver.execute_script("arguments[0].click();", trigger)
        time.sleep(1)
        # Con el popup abierto (#ui-datepicker-div) reutilizamos el clic de dia.
        self._portal._seleccionar_fecha(self._driver, self._wait, fecha)

    def _esperar_sin_overlay(self, timeout: float = 8.0) -> None:
        """Espera a que no haya mascaras de bloqueo/paneles de PrimeFaces visibles.

        Cubre la mascara de ajax (.ui-blockui) y el overlay generico
        (.ui-widget-overlay) que aparecen mientras el portal procesa una
        peticion; si no hay ninguno, retorna de inmediato.
        """
        overlays = ".ui-blockui, .ui-widget-overlay, .ui-selectonemenu-panel:not([style*='display: none'])"
        fin = time.time() + timeout
        while time.time() < fin:
            visibles = self._driver.execute_script(
                "return Array.from(document.querySelectorAll(arguments[0]))"
                ".some(e => e.offsetParent !== null && e.offsetHeight > 0);",
                overlays,
            )
            if not visibles:
                return
            time.sleep(0.3)

    def _filtrar_columna(self, titulo_columna: str, texto: str) -> None:
        """Escribe (o limpia) el filtro de la columna cuyo titulo es titulo_columna."""
        from selenium.webdriver.common.by import By

        if not titulo_columna:
            return
        xp = (f"//th[.//span[@class='ui-column-title' and "
              f"normalize-space(.)='{titulo_columna}']]//input[contains(@class,'ui-column-filter')]")
        try:
            campo = self._driver.find_element(By.XPATH, xp)
        except Exception:  # noqa: BLE001
            return  # esta seccion no tiene filtro de columna
        campo.clear()
        if texto:
            campo.send_keys(texto)
        time.sleep(2)  # dar tiempo al filtrado ajax

    def _clic(self, elem_id: str) -> None:
        """Clic robusto por ID: espera a que no haya overlay y, si el click
        normal es interceptado, reintenta por JavaScript."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        self._esperar_sin_overlay()
        el = self._wait.until(EC.presence_of_element_located((By.ID, elem_id)))
        self._driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        try:
            el.click()
        except Exception:  # noqa: BLE001 - 'click intercepted' u overlay tardio
            self._driver.execute_script("arguments[0].click();", el)

    def _ya_descargado(self, insumo: Insumo, fecha: date, carpeta: Path):
        """Devuelve la ruta si el insumo ya esta descargado para esa fecha.

        Compara por el nombre renderizado (con la fecha): un archivo cuenta como
        ya descargado si su nombre EMPIEZA por el nombre esperado. Esto sirve
        tanto para nombres con extension conocida (MX090826.txt) como para los
        que solo conocemos el prefijo+fecha (SB090826 -> SB090826.001).
        """
        nombre = render_nombre(insumo.patron, fecha)
        carpeta = Path(carpeta)
        if not carpeta.exists():
            return None
        for p in carpeta.iterdir():
            if (p.is_file() and p.name.startswith(nombre)
                    and not p.name.endswith((".crdownload", ".tmp", ".part"))):
                return p
        return None

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

    def _buscar_multipagina(self, nombre: str, prefijo: str):
        """Busca el insumo en la pagina actual y, si no esta, avanza por el
        paginador de PrimeFaces hasta encontrarlo o agotar las paginas."""
        self._ir_primera_pagina()
        intentos = 0
        while True:
            try:
                return self._buscar_fila_descarga(nombre, prefijo, timeout=6)
            except NavegadorError:
                intentos += 1
                if intentos > 20 or not self._siguiente_pagina():
                    self._portal._screenshot(self._driver, f"fila_no_encontrada_{prefijo}")
                    raise NavegadorError(
                        f"No se encontro '{nombre}' (prefijo '{prefijo}') en ninguna "
                        "pagina de la tabla (¿publicado ese dia? ¿nombre correcto?)."
                    )

    def _ir_primera_pagina(self) -> None:
        from selenium.webdriver.common.by import By
        try:
            btn = self._driver.find_element(By.CSS_SELECTOR, ".ui-paginator-first")
            if "ui-state-disabled" not in (btn.get_attribute("class") or ""):
                btn.click()
                time.sleep(1.5)
        except Exception:  # noqa: BLE001 - sin paginador (una sola pagina): seguir
            pass

    def _siguiente_pagina(self) -> bool:
        """Va a la pagina siguiente. Devuelve False si no hay mas paginas."""
        from selenium.webdriver.common.by import By
        try:
            btn = self._driver.find_element(By.CSS_SELECTOR, ".ui-paginator-next")
            if "ui-state-disabled" in (btn.get_attribute("class") or ""):
                return False
            btn.click()
            time.sleep(1.5)
            return True
        except Exception:  # noqa: BLE001
            return False

    def _buscar_fila_descarga(self, nombre: str, prefijo: str, timeout: int = 20):
        """Ubica el enlace de descarga de la fila del insumo.

        La tabla del agrupador identifica cada archivo por su columna 'Prefijo'
        (p.ej. 'SwapCC_DTF_Diaria_') y NO muestra la fecha en el nombre. Ademas
        la tabla esta en modo 'reflow' (responsive): cada celda antepone el
        titulo de su columna, de modo que el texto de la celda Prefijo es
        'Prefijo SwapCC_DTF_Diaria_'. Por eso se busca con CONTAINS (no
        starts-with) el prefijo dentro de la fila.

        Estrategia (de mas a menos preciso), con timeout CORTO para no colgarse:
          1. Fila cuyo texto CONTIENE el nombre completo (con fecha), por si
             algun archivo si trae la fecha en el nombre.
          2. Fila cuyo texto CONTIENE el prefijo (caso normal del agrupador).
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        # timeout corto: si no esta en esta pagina, falla rapido y prueba la siguiente.
        wait_corto = WebDriverWait(self._driver, timeout)
        candidatos = [
            f"//tr[contains(@data-rk, '{nombre}')]//a[.//img[contains(@src,'descargar')]]",
            f"//tr[.//*[contains(normalize-space(.), '{nombre}')]]"
            f"//a[.//img[contains(@src,'descargar')]]",
            f"//tr[.//*[contains(normalize-space(.), '{prefijo}')]]"
            f"//a[.//img[contains(@src,'descargar')]]",
        ]
        for xp in candidatos:
            try:
                return wait_corto.until(EC.element_to_be_clickable((By.XPATH, xp)))
            except Exception:  # noqa: BLE001
                continue
        raise NavegadorError(f"'{nombre}' no esta en la pagina actual.")

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
