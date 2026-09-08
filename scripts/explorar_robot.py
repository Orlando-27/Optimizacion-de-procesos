"""Explorador para MAPEAR las secciones nuevas del Robot Precia (Bloque 2).

Hace login y navega a un area de clientes; opcionalmente hace clic en un boton
del menu; luego vuelca el HTML + screenshot + enlaces/inputs candidatos de la
pagina y de su iframe. Con eso se completan los selectores en
``procesos/robot_precia/secciones.py``.

Uso (headed, en el equipo de la oficina con credenciales en .env):
  # 1) Ver la pagina del area (para hallar landing_url y el boton de la seccion):
  python scripts/explorar_robot.py --url "https://www.precia.co/index.php/renta-variable/"

  # 2) Entrar a una seccion (clic en su boton) y volcar su iframe:
  python scripts/explorar_robot.py --url "https://www.precia.co/index.php/derivados/" --boton "#idBoton"

Setup Chromium en Cloud Shell (si aplica): ver scripts/explorar_portal.py.
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
    from selenium.webdriver.common.by import By

    LOGS.mkdir(parents=True, exist_ok=True)
    base = LOGS / f"robot_{etiqueta}_{ts}"
    base.with_suffix(".html").write_text(driver.page_source, encoding="utf-8", errors="replace")
    try:
        driver.save_screenshot(str(base.with_suffix(".png")))
    except Exception:  # noqa: BLE001
        pass
    print(f"\n=== {etiqueta} | {driver.current_url}")
    print(f"    HTML: {base.with_suffix('.html')}")
    print("    Botones / enlaces / inputs candidatos (id | texto):")
    for el in driver.find_elements(By.CSS_SELECTOR, "button, a[href], input"):
        ident = el.get_attribute("id") or ""
        txt = (el.text or el.get_attribute("value") or el.get_attribute("placeholder") or "").strip()
        if ident or txt:
            print(f"      id={ident!r:22} {txt[:48]!r}")


def _dump_todo(driver, etiqueta: str) -> None:
    from selenium.webdriver.common.by import By

    ts = datetime.now().strftime("%H%M%S")
    _guardar(driver, etiqueta, ts)
    for i, fr in enumerate(driver.find_elements(By.TAG_NAME, "iframe")):
        fid = fr.get_attribute("id") or fr.get_attribute("name") or f"f{i}"
        try:
            driver.switch_to.frame(fr)
            _guardar(driver, f"{etiqueta}_iframe_{fid}", ts)
        except Exception as e:  # noqa: BLE001
            print(f"   (no se pudo entrar al iframe {fid}: {e})")
        finally:
            driver.switch_to.default_content()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True, help="Landing URL del area de clientes")
    p.add_argument("--boton", help="Selector CSS del boton de la seccion a abrir")
    p.add_argument("--volcar", action="store_true", help="Headless (Cloud Shell)")
    args = p.parse_args()

    from core.secrets import secretos_del_portal
    from procesos.impugnacion_rfl.portal_precia import PortalPreciaSelenium
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    usuario, clave = secretos_del_portal()
    if not (usuario and clave):
        print("Faltan credenciales (PRECIA_USUARIO/PRECIA_CLAVE en .env).")
        return 1

    portal = PortalPreciaSelenium(timeout_seg=60)
    driver = portal._nuevo_driver(LOGS, headless=args.volcar)
    try:
        wait = WebDriverWait(driver, 60)
        print(">> Login..."); portal.login(driver, wait, usuario, clave)
        print(">> Login OK:", driver.current_url)
        driver.get(args.url)
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
        if args.boton:
            print(f">> Clic en {args.boton} ...")
            wait.until(lambda d: d.find_element(By.CSS_SELECTOR, args.boton)).click()
            time.sleep(6)
        _dump_todo(driver, "seccion")
        print("\n>> Volcado en logs/. Pasame los .html/.png para completar secciones.py")
        if not args.volcar:
            input(">> ENTER para cerrar...")
    finally:
        driver.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
