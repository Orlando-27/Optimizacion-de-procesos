"""Validaciones obligatorias del proceso (seccion 6 del spec).

Nada se envia sin pasar estos chequeos. Cada funcion lanza ``ValidacionError``
con un mensaje claro si algo no cumple; el proceso las traduce a
VALIDATION_FAILED + alerta.

Se separan en funciones pequeñas y puras para poder testearlas sin Outlook,
portal ni Excel.
"""

from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path
from typing import Optional

import holidays

from core.contract import ValidacionError


def es_dia_habil(dia: date) -> bool:
    """True si es dia habil en Colombia (no fin de semana ni festivo)."""
    if dia.weekday() >= 5:  # 5=sabado, 6=domingo
        return False
    return dia not in holidays.CO(years=dia.year)


def validar_correo_detonante(correo, remitente_esperado: str) -> None:
    if correo is None:
        raise ValidacionError("No llego el correo de Precia dentro de la ventana.")
    if remitente_esperado.lower() not in (correo.remitente or "").lower():
        raise ValidacionError(
            f"Remitente inesperado: {correo.remitente!r} "
            f"(se esperaba contener {remitente_esperado!r})."
        )


def validar_archivo_descargado(
    ruta: Path,
    fecha: datetime,
    tam_minimo_bytes: int = 1024,
    verificar_nombre: bool = True,
) -> None:
    ruta = Path(ruta)
    if not ruta.exists():
        raise ValidacionError(f"El archivo descargado no existe: {ruta}")
    tam = ruta.stat().st_size
    if tam < tam_minimo_bytes:
        raise ValidacionError(
            f"Archivo descargado demasiado pequeño ({tam} bytes < {tam_minimo_bytes})."
        )
    if verificar_nombre:
        esperado = f"SX{fecha:%m%d%y}"
        if esperado.lower() not in ruta.name.lower():
            raise ValidacionError(
                f"El nombre {ruta.name!r} no corresponde a la fecha de hoy "
                f"(se esperaba contener {esperado!r})."
            )


def validar_salida(
    ruta: Path,
    inicio_corrida: datetime,
    tam_minimo_bytes: int = 1,
) -> None:
    """Renta Fija.xlsx existe, es de esta corrida, tam > 0 y abre con openpyxl."""
    ruta = Path(ruta)
    if not ruta.exists():
        raise ValidacionError(f"No se genero la salida esperada: {ruta}")
    st = ruta.stat()
    if st.st_size <= tam_minimo_bytes:
        raise ValidacionError(f"La salida {ruta.name} tiene tamaño 0.")
    mtime = datetime.fromtimestamp(st.st_mtime)
    if mtime < inicio_corrida:
        raise ValidacionError(
            f"La salida {ruta.name} es de una corrida anterior "
            f"(mtime {mtime} < inicio {inicio_corrida}). ¿Es el archivo de ayer?"
        )
    try:
        from openpyxl import load_workbook
        load_workbook(ruta, read_only=True).close()
    except Exception as e:  # noqa: BLE001
        raise ValidacionError(f"La salida {ruta.name} no abre con openpyxl: {e}") from e


def evaluar_sla(ahora: time, tes_st_fin: time) -> bool:
    """True si aun estamos dentro de la ventana (ahora <= tes_st_fin)."""
    return ahora <= tes_st_fin


def validar_destinatarios_por_entorno(
    entorno: str,
    destinatarios: list[str],
    lista_prod: list[str],
) -> None:
    """Evita mandar a la lista real estando en test."""
    if not destinatarios:
        raise ValidacionError("La lista de destinatarios esta vacia.")
    if entorno == "test":
        reales = set(d.lower() for d in lista_prod)
        if any(d.lower() in reales for d in destinatarios):
            raise ValidacionError(
                "En entorno test hay destinatarios de la lista de PROD. Abortado."
            )


def validar_adjunto(ruta: Optional[Path]) -> None:
    if ruta is None or not Path(ruta).exists():
        raise ValidacionError(f"El adjunto no existe: {ruta}")
