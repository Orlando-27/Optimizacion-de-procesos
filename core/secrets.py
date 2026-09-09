"""Lectura de secretos: Windows Credential Manager (keyring) -> .env -> entorno.

Orden de preferencia:
  1. keyring (Windows Credential Manager u otro backend del SO)
  2. variable en el archivo .env
  3. variable de entorno del proceso

Nunca imprime valores. Devuelve ``None`` si no encuentra el secreto, para que
quien lo llame decida si es fatal (p. ej. la clave del portal) o no.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

try:  # keyring es opcional (puede no estar en el contenedor Linux de dev)
    import keyring  # type: ignore
except Exception:  # noqa: BLE001
    keyring = None  # type: ignore

# Servicio bajo el que se guardan los secretos en el Credential Manager.
# Se prueba el nombre actual y, por compatibilidad, el historico (por si ya
# habia credenciales guardadas con el nombre anterior).
_SERVICIOS_KEYRING = ("motor-procesos/precia", "motor-procesos/impugnacion_rfl")
_env_cargado = False


def _cargar_env(ruta_env: Optional[Path] = None) -> None:
    """Carga .env a os.environ una sola vez, sin sobreescribir lo ya presente."""
    global _env_cargado
    if _env_cargado:
        return
    try:
        from dotenv import load_dotenv  # import perezoso
        ruta = ruta_env or Path(".env")
        if ruta.exists():
            load_dotenv(ruta, override=False)
    except Exception:  # noqa: BLE001 - si no hay dotenv, se usa el entorno tal cual
        pass
    _env_cargado = True


def obtener_secreto(nombre: str, ruta_env: Optional[Path] = None) -> Optional[str]:
    """Devuelve el secreto ``nombre`` segun el orden de preferencia, o None."""
    if keyring is not None:
        for servicio in _SERVICIOS_KEYRING:
            try:
                val = keyring.get_password(servicio, nombre)
                if val:
                    return val
            except Exception:  # noqa: BLE001 - backend no disponible -> siguiente fuente
                break
    _cargar_env(ruta_env)
    return os.environ.get(nombre)


def secretos_del_portal(ruta_env: Optional[Path] = None) -> tuple[Optional[str], Optional[str]]:
    return (
        obtener_secreto("PRECIA_USUARIO", ruta_env),
        obtener_secreto("PRECIA_CLAVE", ruta_env),
    )


def secretos_smtp(entorno: str, ruta_env: Optional[Path] = None) -> tuple[Optional[str], Optional[str]]:
    """Credenciales SMTP segun el entorno (test = Gmail de prueba, prod = corp)."""
    suf = "TEST" if entorno == "test" else "PROD"
    return (
        obtener_secreto(f"SMTP_{suf}_USUARIO", ruta_env),
        obtener_secreto(f"SMTP_{suf}_CLAVE", ruta_env),
    )
