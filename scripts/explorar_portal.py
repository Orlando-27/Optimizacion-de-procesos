"""Explorador headed del portal de Precia para capturar los selectores post-login.

El LOGIN ya esta confirmado (campos #user_login/#user_pass/#wp-submit). Lo que
falta capturar esta DETRAS del login: Area de clientes renta fija > Archivos
Renta Fija Local > selector de fecha > boton de descarga.

Este script:
  1. Abre Chrome VISIBLE y hace login con tus credenciales (de .env/keyring o --usuario/--clave).
  2. Navega a la seccion de Renta Fija.
  3. Vuelca los enlaces/candidatos que ve para ayudarte a identificar la ruta.
  4. PAUSA para que con DevTools (F12) copies los selectores CSS exactos.

Pega lo capturado en el bloque `# === SELECTORES A VERIFICAR ===` de
procesos/impugnacion_rfl/portal_precia.py (URL_AREA_CLIENTES, SEL_ARCHIVOS_RFL,
SEL_SELECTOR_FECHA, SEL_LINK_DESCARGA).

Uso:
  python scripts/explorar_portal.py
  # con Chromium portable (Linux/sandbox):
  CHROME_BINARY=/ruta/chrome CHROMEDRIVER_PATH=/ruta/chromedriver python scripts/explorar_portal.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--usuario")
    p.add_argument("--clave")
    p.add_argument("--headless", action="store_true",
                   help="Correr sin ventana (para diagnostico; para capturar usar headed)")
    args = p.parse_args()

    from core.secrets import secretos_del_portal
    from procesos.impugnacion_rfl.portal_precia import (
        PortalPreciaSelenium, URL_RENTA_FIJA,
    )
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    usuario = args.usuario or secretos_del_portal()[0]
    clave = args.clave or secretos_del_portal()[1]
    if not (usuario and clave):
        print("Faltan credenciales. Usar .env/keyring o --usuario/--clave.")
        return 1

    portal = PortalPreciaSelenium(timeout_seg=60)
    driver = portal._nuevo_driver(RAIZ / "logs", headless=args.headless)
    try:
        wait = WebDriverWait(driver, 60)
        print(">> Haciendo login...")
        portal.login(driver, wait, usuario, clave)
        print(">> Login OK. URL actual:", driver.current_url)

        print(">> Navegando a Renta Fija...")
        driver.get(URL_RENTA_FIJA)
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")

        # Volcado de candidatos: enlaces con palabras clave de la ruta.
        print("\n=== ENLACES CANDIDATOS (texto -> href) ===")
        for a in driver.find_elements(By.CSS_SELECTOR, "a[href]"):
            txt = (a.text or "").strip()
            href = a.get_attribute("href") or ""
            clave_txt = (txt + href).lower()
            if any(k in clave_txt for k in ("cliente", "archivo", "renta", "local", "descarg", "area")):
                print(f"  {txt[:40]!r:44} -> {href}")

        print("\n" + "=" * 64)
        print(" NAVEGA A MANO: Area de clientes renta fija > Archivos Renta Fija")
        print(" Local > (fecha de hoy) > descarga.")
        print(" Con DevTools (F12) copia el selector CSS de cada elemento y")
        print(" pegalo en portal_precia.py -> bloque SELECTORES A VERIFICAR.")
        print("=" * 64)
        if not args.headless:
            input("\n>> ENTER para cerrar cuando termines de capturar...")
    finally:
        driver.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
