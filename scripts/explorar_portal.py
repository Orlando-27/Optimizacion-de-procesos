"""Explorador del portal de Precia para capturar los selectores post-login.

El LOGIN ya esta confirmado (#user_login/#user_pass/#wp-submit). Falta capturar
lo que esta DETRAS del login: Area de clientes renta fija > Archivos Renta Fija
Local > selector de fecha > boton de descarga.

Dos modos:

  1. HEADED (equipo con pantalla): abre Chrome visible y pausa para que con
     DevTools (F12) copies los selectores.
        python scripts/explorar_portal.py

  2. VOLCAR (Cloud Shell / sin pantalla): headless. Hace login y GUARDA el HTML
     y un screenshot de cada pagina en logs/, e imprime los enlaces candidatos.
     Con eso se extraen los selectores sin DevTools. Se puede profundizar
     pasando --url de una pagina que hayas descubierto en el volcado anterior.
        python scripts/explorar_portal.py --volcar
        python scripts/explorar_portal.py --volcar --url "https://www.precia.co/.../archivos"

Pega lo capturado en el bloque `# === SELECTORES A VERIFICAR ===` de
procesos/impugnacion_rfl/portal_precia.py.

Setup en Cloud Shell (una vez por sesion):
    sudo apt-get update && sudo apt-get install -y chromium chromium-driver
    export CHROME_BINARY=/usr/bin/chromium
    export CHROMEDRIVER_PATH=/usr/bin/chromedriver
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

LOGS = RAIZ / "logs"


def _dump(driver, etiqueta: str) -> None:
    """Guarda page_source + screenshot + lista de enlaces candidatos."""
    from selenium.webdriver.common.by import By

    LOGS.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%H%M%S")
    base = LOGS / f"portal_{etiqueta}_{ts}"
    (base.with_suffix(".html")).write_text(driver.page_source, encoding="utf-8", errors="replace")
    try:
        driver.save_screenshot(str(base.with_suffix(".png")))
    except Exception:  # noqa: BLE001
        pass
    print(f"\n=== {etiqueta} | {driver.current_url}")
    print(f"    HTML: {base.with_suffix('.html')}")
    print(f"    PNG : {base.with_suffix('.png')}")
    print("    Enlaces candidatos (texto -> href):")
    vistos = set()
    for a in driver.find_elements(By.CSS_SELECTOR, "a[href]"):
        txt = (a.text or "").strip()
        href = a.get_attribute("href") or ""
        clave = (txt + href).lower()
        if href in vistos:
            continue
        if any(k in clave for k in ("cliente", "archivo", "renta", "local", "descarg", "area", ".xls", ".csv", ".zip", "download")):
            vistos.add(href)
            print(f"      {txt[:40]!r:44} -> {href}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--usuario")
    p.add_argument("--clave")
    p.add_argument("--volcar", action="store_true",
                   help="Headless: guarda HTML+screenshot+links (Cloud Shell)")
    p.add_argument("--url", action="append", default=[],
                   help="URL(s) extra a visitar y volcar tras el login")
    args = p.parse_args()

    from core.secrets import secretos_del_portal
    from procesos.impugnacion_rfl.portal_precia import PortalPreciaSelenium, URL_RENTA_FIJA
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

        if args.volcar:
            _dump(driver, "post_login")
            driver.get(URL_RENTA_FIJA)
            wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
            _dump(driver, "renta_fija")
            for i, u in enumerate(args.url):
                driver.get(u)
                wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
                _dump(driver, f"url{i}")
            print("\n>> Volcado completo. Revisa los .html/.png en logs/ y pasame")
            print("   los selectores (o el HTML) para cablear la descarga.")
        else:
            driver.get(URL_RENTA_FIJA)
            print("\n" + "=" * 64)
            print(" En la ventana de Chrome que se abrio, navega a mano hasta:")
            print("   Area de clientes renta fija > Archivos Renta Fija Local")
            print("   > (deja a la vista la lista de fechas / el boton de descarga)")
            print(" NO cierres Chrome. Cuando la pagina de descarga este a la vista,")
            print(" vuelve aqui y presiona ENTER: guardare el HTML y un screenshot.")
            print("=" * 64)
            input("\n>> ENTER cuando estes en la pagina de Archivos RFL...")
            # Vuelca la pagina EXACTA donde el usuario navego (la de la descarga).
            _dump(driver, "pagina_descarga")
            print("\n>> Guardado. Pasame el archivo logs\\portal_pagina_descarga_*.html")
            print("   (y el .png si quieres) para extraer los selectores.")
    finally:
        driver.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
