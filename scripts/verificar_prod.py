"""Chequeo previo del Robot Precia antes de la primera corrida / puesta en marcha.

Valida, SIN descargar nada ni imprimir secretos:
  1. Que se pueda leer la configuracion (config.yaml + parametros.yaml).
  2. Que la CARPETA DE DESTINO exista y se pueda ESCRIBIR (crea y borra un
     archivo de prueba). Sirve para detectar una ruta de red (UNC) caida o sin
     permisos ANTES de las 4 a.m.
  3. Que esten las CREDENCIALES del portal (PRECIA_USUARIO / PRECIA_CLAVE).
  4. Que Selenium y un navegador Chrome esten disponibles.
  5. Que el backend de correo del entorno este resuelto.

Uso:
    python scripts/verificar_prod.py            # usa el config del robot
    python scripts/verificar_prod.py --config otra/config.yaml

Devuelve codigo 0 si todo lo CRITICO esta OK; 1 si algo critico falla.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

CONFIG_ROBOT = RAIZ / "procesos" / "robot_precia" / "config.yaml"

OK = "[ OK ]"
FALLA = "[FALLA]"
AVISO = "[aviso]"


def _check_config(ruta_config: Path):
    from procesos.robot_precia.config_robot import cargar_config, cargar_insumos
    cfg = cargar_config(ruta_config)
    insumos = cargar_insumos(ruta_config.parent / cfg.manifiesto)
    print(f"{OK} Config cargada. entorno = '{cfg.entorno}' | insumos = {len(insumos)}")
    print(f"       backend_correo = {cfg.backend_correo_activo} | "
          f"backend_portal = {cfg.backend_portal_activo}")
    return cfg


def _check_ruta(cfg) -> bool:
    carpeta = Path(cfg.carpeta_destino)
    try:
        carpeta.mkdir(parents=True, exist_ok=True)
    except Exception as e:  # noqa: BLE001
        print(f"{FALLA} No se pudo crear/abrir la carpeta de destino:\n"
              f"       {carpeta}\n       {e}")
        return False
    # prueba de ESCRITURA real (detecta UNC sin permiso / de solo lectura)
    prueba = carpeta / ".robot_precia_prueba_escritura.tmp"
    try:
        prueba.write_text("ok", encoding="utf-8")
        prueba.unlink()
    except Exception as e:  # noqa: BLE001
        print(f"{FALLA} La carpeta existe pero NO se puede escribir en ella:\n"
              f"       {carpeta}\n       {e}")
        return False
    print(f"{OK} Carpeta de destino escribible: {carpeta}")
    return True


def _check_credenciales() -> bool:
    from core.secrets import secretos_del_portal
    usuario, clave = secretos_del_portal()
    if usuario and clave:
        # NO imprimir los valores; solo confirmar presencia y longitud.
        print(f"{OK} Credenciales del portal presentes "
              f"(usuario de {len(usuario)} car., clave de {len(clave)} car.)")
        return True
    faltan = []
    if not usuario:
        faltan.append("PRECIA_USUARIO")
    if not clave:
        faltan.append("PRECIA_CLAVE")
    print(f"{FALLA} Faltan credenciales del portal: {', '.join(faltan)}.\n"
          f"       Ponlas en el archivo .env o en el Credential Manager de Windows.")
    return False


def _check_selenium() -> bool:
    try:
        import selenium  # noqa: F401
    except Exception:  # noqa: BLE001
        print(f"{FALLA} Selenium no esta instalado (pip install selenium).")
        return False
    # Intentar abrir Chrome headless muy brevemente (no navega a ningun lado).
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        op = Options()
        op.add_argument("--headless=new")
        op.add_argument("--no-sandbox")
        op.add_argument("--disable-gpu")
        d = webdriver.Chrome(options=op)
        d.quit()
        print(f"{OK} Selenium + Chrome disponibles.")
        return True
    except Exception as e:  # noqa: BLE001
        # No es critico para ESTE chequeo (headless puede fallar donde real anda),
        # pero se avisa.
        print(f"{AVISO} Selenium instalado, pero no se pudo abrir Chrome en modo "
              f"headless de prueba:\n       {str(e)[:160]}\n"
              f"       (La corrida real usa ventana; verifica que Chrome este instalado.)")
        return True


def _check_correo(cfg) -> bool:
    dest = cfg.destinatarios_alerta_activos
    if not dest:
        print(f"{AVISO} No hay receptores de correo para el entorno '{cfg.entorno}' "
              f"(receptores.{cfg.entorno} en parametros.yaml). No llegara el reporte.")
        return True
    print(f"{OK} Correo -> remitente: {cfg.alertas.owner} | "
          f"receptores({cfg.entorno}): {', '.join(dest)}")
    return True


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Chequeo previo del Robot Precia")
    p.add_argument("--config", type=Path, default=CONFIG_ROBOT)
    args = p.parse_args(argv)

    print("=" * 64)
    print(" CHEQUEO PREVIO - Robot Precia")
    print("=" * 64)

    try:
        cfg = _check_config(args.config)
    except Exception as e:  # noqa: BLE001
        print(f"{FALLA} No se pudo cargar la configuracion: {e}")
        return 1

    # criticos: ruta escribible + credenciales del portal
    ok_ruta = _check_ruta(cfg)
    ok_cred = _check_credenciales()
    # informativos / no bloqueantes
    _check_selenium()
    _check_correo(cfg)

    print("-" * 64)
    if ok_ruta and ok_cred:
        print(f"{OK} TODO LO CRITICO ESTA LISTO. El robot puede correr.")
        return 0
    print(f"{FALLA} Hay problemas CRITICOS (ver arriba). Corrigelos antes de programar la tarea.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
