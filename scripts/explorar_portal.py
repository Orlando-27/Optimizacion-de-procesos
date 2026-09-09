"""Explorador del portal de Precia para capturar los selectores de descarga.

Estado confirmado (2026-07):
  - Login WordPress: #user_login / #user_pass / #wp-submit  (OK)
  - Area de clientes RF: https://www.precia.co/index.php/renta-fija/
  - Esa pagina embebe una app JSF en un iframe (#BranderFrame) servida desde
    otra IP. El boton "Archivos Renta Fija Local" es #arlo y carga en el iframe
    la pagina archivosValoracionRentaFija.xhtml.

Lo que falta capturar esta DENTRO del iframe: el control de fecha y el enlace de
descarga del archivo SXMMDDYY. Por eso este script, ademas de la pagina, VUELCA
el contenido de cada iframe.

Modos:
  HEADED (Windows/Anaconda con pantalla): abre Chrome visible, hace login,
  navega al area de clientes y hace clic en "Archivos Renta Fija Local". Tu
  seleccionas la fecha de hoy si hace falta y presionas ENTER; se guarda el HTML
  del iframe (la pagina de descarga).
        python scripts\\explorar_portal.py

  VOLCAR (headless / Cloud Shell): igual pero sin ventana.
        python scripts/explorar_portal.py --volcar

NOTA: los selectores de descarga YA quedaron confirmados y cableados en
portal_precia.py. Este script se conserva para re-capturar si el portal cambia.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

LOGS = RAIZ / "logs"


def _guardar(driver, etiqueta: str, ts: str) -> None:
    """Guarda page_source + screenshot + enlaces candidatos de la vista actual."""
    from selenium.webdriver.common.by import By

    LOGS.mkdir(parents=True, exist_ok=True)
    base = LOGS / f"portal_{etiqueta}_{ts}"
    base.with_suffix(".html").write_text(driver.page_source, encoding="utf-8", errors="replace")
    try:
        driver.save_screenshot(str(base.with_suffix(".png")))
    except Exception:  # noqa: BLE001
        pass
    print(f"\n=== {etiqueta} | {driver.current_url}")
    print(f"    HTML: {base.with_suffix('.html')}")
    print("    Candidatos (texto -> href / id):")
    for a in driver.find_elements(By.CSS_SELECTOR, "a[href], button, input[type=submit]"):
        txt = (a.text or a.get_attribute("value") or "").strip()
        href = a.get_attribute("href") or ""
        ident = a.get_attribute("id") or ""
        clave = (txt + href + ident).lower()
        if any(k in clave for k in ("archivo", "descarg", "download", ".xls", ".csv",
                                    ".zip", ".txt", "fecha", "sx", "buscar", "consultar")):
            print(f"      {txt[:34]!r:38} id={ident!r:16} -> {href[:70]}")


def _dump_todo(driver, etiqueta: str) -> None:
    """Vuelca la pagina principal y el contenido de cada iframe."""
    from selenium.webdriver.common.by import By

    ts = datetime.now().strftime("%H%M%S")
    _guardar(driver, etiqueta, ts)
    frames = driver.find_elements(By.TAG_NAME, "iframe")
    print(f"\n>> {len(frames)} iframe(s) detectado(s); volcando su contenido...")
    for i, fr in enumerate(frames):
        fid = (fr.get_attribute("id") or fr.get_attribute("name") or f"f{i}")
        try:
            driver.switch_to.frame(fr)
            _guardar(driver, f"{etiqueta}_iframe_{fid}", ts)
        except Exception as e:  # noqa: BLE001
            print(f"   (no se pudo entrar al iframe {fid}: {e})")
        finally:
            driver.switch_to.default_content()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--usuario")
    p.add_argument("--clave")
    p.add_argument("--volcar", action="store_true", help="Headless (Cloud Shell)")
    args = p.parse_args()

    from core.secrets import secretos_del_portal
    from procesos.robot_precia.portal_precia import (
        PortalPreciaSelenium, URL_AREA_CLIENTES, SEL_BTN_ARCHIVOS_RFL,
    )
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    usuario = args.usuario or secretos_del_portal()[0]
    clave = args.clave or secretos_del_portal()[1]
    if not (usuario and clave):
        print("Faltan credenciales. Usar .env/keyring o --usuario/--clave.")
        return 1

    portal = PortalPreciaSelenium(timeout_seg=60)
    driver = portal._nuevo_driver(LOGS, headless=args.volcar)
    try:
        wait = WebDriverWait(driver, 60)
        print(">> Login...")
        portal.login(driver, wait, usuario, clave)
        print(">> Login OK:", driver.current_url)

        print(">> Entrando al area de clientes RF...")
        driver.get(URL_AREA_CLIENTES)
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")

        # Clic en "Archivos Renta Fija Local" (#arlo) -> carga el iframe.
        try:
            btn = wait.until(lambda d: d.find_element(By.CSS_SELECTOR, SEL_BTN_ARCHIVOS_RFL))
            btn.click()
            print(">> Clic en 'Archivos Renta Fija Local'. Esperando el iframe...")
            time.sleep(6)
        except Exception as e:  # noqa: BLE001
            print(f">> No pude hacer clic en {SEL_BTN_ARCHIVOS_RFL} automaticamente: {e}")
            print("   Haz clic tu en 'Archivos Renta Fija Local' en la ventana de Chrome.")

        if not args.volcar:
            print("\n" + "=" * 64)
            print(" En el Chrome: si aparece un control de FECHA, selecciona la de HOY")
            print(" para que se muestre el archivo del dia. Cuando veas el enlace/boton")
            print(" de descarga (o la tabla con el archivo SXMMDDYY), vuelve aqui.")
            print("=" * 64)
            input("\n>> ENTER para capturar la pagina + el iframe...")

        _dump_todo(driver, "archivos")
        print("\n>> Listo. Pasame los archivos logs\\portal_archivos_iframe_*.html")
        print("   (y el .png). De ahi saco el selector de fecha y el de descarga.")
    finally:
        driver.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
