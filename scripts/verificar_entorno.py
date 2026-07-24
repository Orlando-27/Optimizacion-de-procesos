"""Diagnostico de entorno antes de la primera corrida.

Chequea Python, dependencias, rutas configuradas, credenciales presentes
(sin imprimirlas) y disponibilidad de los backends segun el entorno.

Uso:  python scripts/verificar_entorno.py [--config ruta] [--entorno test|prod]
"""

from __future__ import annotations

import argparse
import importlib
import platform
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

OK, WARN, FAIL = "[ OK ]", "[WARN]", "[FALLA]"


def _chk(cond: bool, ok_msg: str, fail_msg: str, critico: bool = True) -> bool:
    print(f"{OK if cond else (FAIL if critico else WARN)} "
          f"{ok_msg if cond else fail_msg}")
    return cond or not critico


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path,
                   default=RAIZ / "procesos/impugnacion_rfl/config.yaml")
    p.add_argument("--entorno", choices=["test", "prod"])
    args = p.parse_args()

    todo_ok = True
    print("=" * 60)
    print(" DIAGNOSTICO DE ENTORNO - impugnacion_rfl")
    print("=" * 60)

    # Python
    v = sys.version_info
    todo_ok &= _chk(v >= (3, 11), f"Python {platform.python_version()}",
                    f"Python {platform.python_version()} (se requiere >= 3.11)")
    print(f"       SO: {platform.system()} {platform.release()}")

    # Dependencias
    deps = {
        "pydantic": True, "yaml": True, "holidays": True, "openpyxl": True,
        "dotenv": False, "selenium": False, "keyring": False,
    }
    for mod, critico in deps.items():
        try:
            importlib.import_module(mod)
            print(f"{OK} dep: {mod}")
        except Exception:  # noqa: BLE001
            print(f"{FAIL if critico else WARN} dep: {mod} no instalada"
                  f"{'' if critico else ' (opcional)'}")
            todo_ok &= not critico

    # pywin32 / Outlook / Excel COM (solo Windows)
    if platform.system() == "Windows":
        for mod in ("win32com.client",):
            try:
                importlib.import_module(mod)
                print(f"{OK} dep Windows: {mod}")
            except Exception:  # noqa: BLE001
                print(f"{WARN} dep Windows: {mod} no disponible (necesaria para COM)")
    else:
        print(f"{WARN} No es Windows: los backends COM (Outlook/Excel) no aplican aqui.")

    # Config + rutas
    try:
        from core.config import cargar_config
        cfg = cargar_config(args.config)
        if args.entorno:
            cfg.entorno = args.entorno
        print(f"{OK} config.yaml valida | entorno activo: {cfg.entorno}")
        print(f"       INFOVALMER : {cfg.infovalmer}")
        print(f"       Impugnacion: {cfg.impugnacion}")
        for etiqueta, ruta in (("INFOVALMER", cfg.infovalmer), ("Impugnacion", cfg.impugnacion)):
            existe = Path(ruta).exists()
            _chk(existe, f"ruta {etiqueta} accesible",
                 f"ruta {etiqueta} NO accesible: {ruta}"
                 + ("" if cfg.entorno == "test" else "  (¿UNC correcto? ¿sesion ve la unidad?)"),
                 critico=(cfg.entorno == "prod"))
        print(f"       backend correo: {cfg.backend_correo_activo} | "
              f"backend portal: {cfg.backend_portal_activo} | motor macro: {cfg.excel.motor}")
        if cfg.excel.motor == "placeholder":
            print(f"{WARN} motor macro = 'placeholder': PASO 5 pendiente (ver PENDIENTE_PASO_5.md)")
    except Exception as e:  # noqa: BLE001
        print(f"{FAIL} No se pudo cargar config: {e}")
        todo_ok = False
        cfg = None

    # Credenciales (presencia, NUNCA el valor)
    try:
        from core.secrets import secretos_del_portal, secretos_smtp
        u_p, c_p = secretos_del_portal()
        _chk(bool(u_p and c_p), "credenciales de portal presentes",
             "faltan PRECIA_USUARIO/PRECIA_CLAVE (.env o keyring)", critico=False)
        if cfg is not None:
            u_s, c_s = secretos_smtp(cfg.entorno)
            _chk(bool(u_s and c_s), f"credenciales SMTP ({cfg.entorno}) presentes",
                 f"faltan SMTP_{cfg.entorno.upper()}_* (solo necesario si backend=smtp_imap)",
                 critico=False)
    except Exception as e:  # noqa: BLE001
        print(f"{WARN} No se pudieron chequear credenciales: {e}")

    print("=" * 60)
    print(("TODO OK: listo para correr en test." if todo_ok
           else "HAY FALLAS CRITICAS: revisar antes de correr."))
    print("=" * 60)
    return 0 if todo_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
