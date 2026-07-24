"""Explorador headed del portal de Precia para capturar los selectores reales.

Abre Chrome VISIBLE, hace el login y PAUSA para que navegues a mano la ruta
Servicios > Renta Fija > Area de clientes > Archivos Renta Fija Local, y con las
DevTools (F12) copies los selectores CSS de cada elemento. Luego pegalos en el
bloque `# === SELECTORES A VERIFICAR ===` de procesos/impugnacion_rfl/portal_precia.py.

Uso:
  # credenciales via .env / keyring (recomendado):
  python scripts/explorar_portal.py
  # o pasandolas explicitamente (evitar en equipos compartidos):
  python scripts/explorar_portal.py --usuario XXX --clave YYY

Requiere: pip install selenium  (y un Chrome/Chromedriver disponible).
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
    p.add_argument("--url", default="https://www.precia.co/wp-login.php")
    args = p.parse_args()

    from core.secrets import secretos_del_portal
    usuario = args.usuario or secretos_del_portal()[0]
    clave = args.clave or secretos_del_portal()[1]
    if not (usuario and clave):
        print("Faltan credenciales. Usar .env/keyring o --usuario/--clave.")
        return 1

    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By

    opts = Options()
    opts.add_argument("--start-maximized")
    driver = webdriver.Chrome(options=opts)  # headed a proposito
    try:
        driver.get(args.url)
        # WordPress estandar: campos 'log' y 'pwd'.
        try:
            driver.find_element(By.ID, "user_login").send_keys(usuario)
            driver.find_element(By.ID, "user_pass").send_keys(clave)
            driver.find_element(By.ID, "wp-submit").click()
        except Exception as e:  # noqa: BLE001
            print(f"No se pudo autocompletar el login (revisar IDs): {e}")

        print("\n" + "=" * 64)
        print(" NAVEGADOR ABIERTO. Haz login si hace falta y navega a:")
        print("   Servicios > Renta Fija > Area de clientes renta fija >")
        print("   Archivos Renta Fija Local > (fecha de hoy) > descarga")
        print(" Abre DevTools (F12) y copia el selector CSS de cada elemento.")
        print("=" * 64)
        input("\n>> Cuando termines de capturar los selectores, ENTER para cerrar...")
    finally:
        driver.quit()
    print("Pega los selectores en portal_precia.py -> bloque SELECTORES A VERIFICAR.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
