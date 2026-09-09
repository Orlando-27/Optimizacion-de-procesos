"""Logica de fechas del Robot Precia.

Regla de negocio (confirmada con el usuario):
  - Siempre se descarga ``t-1`` (el dia anterior).
  - Los LUNES se descarga TODO el fin de semana: sabado y domingo.

El robot corre a las 4:00 a.m., cuando los insumos del dia anterior (t-1) ya
estan publicados en el portal de Precia. El nombre de cada archivo lleva la
fecha embebida (``MMDDYY`` o ``DDMMYY`` o ``YYYY_MM_DD`` segun el insumo), asi
que se genera una lista de fechas objetivo y para cada una se ubica el archivo.
"""

from __future__ import annotations

from datetime import date, timedelta


def fechas_objetivo(hoy: date) -> list[date]:
    """Devuelve las fechas a descargar segun el dia en que corre el robot.

    - Lunes (weekday()==0): sabado y domingo (el fin de semana) -> [t-2, t-1].
    - Cualquier otro dia: solo el dia anterior -> [t-1].

    Se devuelven en orden cronologico ascendente (mas antigua primero).
    """
    if hoy.weekday() == 0:  # lunes
        return [hoy - timedelta(days=2), hoy - timedelta(days=1)]  # sabado, domingo
    return [hoy - timedelta(days=1)]


# --- Formateadores de fecha para el nombre de cada archivo ---
# Los insumos usan distintos patrones de fecha en su nombre. Estas funciones
# arman el fragmento de fecha que se busca dentro del nombre del archivo.

def fmt_mmddyy(f: date) -> str:
    """MMDDYY -> p.ej. 090626 para 06/sep/2026 (mes, dia, anio)."""
    return f.strftime("%m%d%y")


def fmt_ddmmyy(f: date) -> str:
    """DDMMYY -> p.ej. 060926 (dia, mes, anio)."""
    return f.strftime("%d%m%y")


def fmt_yyyy_mm_dd(f: date) -> str:
    """YYYY_MM_DD -> p.ej. 2026_09_06."""
    return f.strftime("%Y_%m_%d")


def fmt_yyyymmdd(f: date) -> str:
    """YYYYMMDD -> p.ej. 20260908 (usado por los archivos del agrupador Derivados)."""
    return f.strftime("%Y%m%d")


# Mapa de patron declarado en el manifiesto -> funcion formateadora.
# IMPORTANTE: el orden importa cuando un token es prefijo de otro. 'YYYY_MM_DD'
# se evalua antes que 'YYYYMMDD' porque llevan claves distintas, pero ambos
# empiezan por 'YYYY'; como el reemplazo es por marca exacta ('{TOKEN}') no hay
# colision. Se listan de mas especifico a menos.
PATRONES_FECHA = {
    "YYYY_MM_DD": fmt_yyyy_mm_dd,
    "YYYYMMDD": fmt_yyyymmdd,
    "MMDDYY": fmt_mmddyy,
    "DDMMYY": fmt_ddmmyy,
}


def render_nombre(patron_nombre: str, fecha: date) -> str:
    """Sustituye el token de fecha en el patron del nombre por la fecha real.

    Ejemplos:
      'SX{MMDDYY}'                 + 06/09/26 -> 'SX090626'
      'MX{MMDDYY}_FormatoLocal.txt'          -> 'MX090626_FormatoLocal.txt'
      'bolvalora_{YYYY_MM_DD}_acciones.xls'  -> 'bolvalora_2026_09_06_acciones.xls'
      '800149496_Colf_NE{DDMMYY}.csv'        -> '800149496_Colf_NE060926.csv'
    Si el patron no trae token de fecha, se devuelve tal cual (se buscara por prefijo).
    """
    salida = patron_nombre
    for token, fn in PATRONES_FECHA.items():
        marca = "{" + token + "}"
        if marca in salida:
            salida = salida.replace(marca, fn(fecha))
    return salida
