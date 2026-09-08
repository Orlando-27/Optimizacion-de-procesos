"""Mapa de navegacion de cada AREA/SECCION del portal de Precia.

El portal es una app JSF/PrimeFaces embebida en un iframe (#BranderFrame). Cada
"area de clientes" es una pagina de WordPress con su propio iframe; dentro, un
menu de <button> cambia el contenido del iframe a cada seccion.

Para cada area se necesita:
  landing_url : URL de la pagina del area de clientes (tras el login).
  iframe      : id/name del iframe con la app JSF (normalmente "BranderFrame").
  botones     : {nombre_seccion -> selector CSS del boton del menu}.
  filtros     : {nombre_seccion -> selector CSS del input de filtro} (opcional).

ESTADO:
  - "Clientes Renta Fija Local": CONFIRMADO (mismo login/area de impugnacion).
  - Las demas areas: PENDIENTES de mapear (Bloque 2) -> valores "TODO:".
    Se capturan con:  python scripts/explorar_portal.py --volcar --area <landing_url>
"""

from __future__ import annotations

# Marcador para selectores/URLs aun no capturados.
TODO = "TODO"


SECCIONES: dict[str, dict] = {
    # ---- CONFIRMADO: es la misma area que ya automatizamos en impugnacion_rfl ----
    "Clientes Renta Fija Local": {
        "landing_url": "https://www.precia.co/index.php/renta-fija/",
        "iframe": "BranderFrame",
        "botones": {
            "Archivos Renta Fija Local": "#arlo",          # confirmado
            "Archivos Renta Fija Internacional": "#arin",  # confirmado
        },
        "filtros": {},  # estas secciones no llevan filtro de texto
    },

    # ---- PENDIENTES DE MAPEAR (capturar landing_url + selectores) ----
    "Clientes Renta Variable": {
        "landing_url": TODO,   # p.ej. https://www.precia.co/index.php/renta-variable/
        "iframe": "BranderFrame",
        "botones": {
            "Archivos De Valoración": TODO,
            "Archivos De Valoración Internacional": TODO,
        },
        "filtros": {},
    },
    "Clientes Derivados": {
        "landing_url": TODO,   # p.ej. https://www.precia.co/index.php/derivados/
        "iframe": "BranderFrame",
        "botones": {
            # La ruta real es "Descargar Archivo Agrupador" y dentro se elige el
            # grupo (Insumos Locales / Swaps Internacionales / Forward Intl / Otros).
            "Descargar Archivo Agrupador > Insumos Locales": TODO,
            "Descargar Archivo Agrupador > Insumos Swaps Internacionales": TODO,
            "Descargar Archivo Agrupador > Insumos Forward Internacionales": TODO,
            "Descargar Archivo Agrupador > Otros Insumos": TODO,
        },
        # Estas secciones SI llevan filtro de texto ("FWD" / "SWAPCC").
        "filtros": {
            "Descargar Archivo Agrupador > Insumos Locales": TODO,  # input del filtro
            "Descargar Archivo Agrupador > Insumos Forward Internacionales": TODO,
        },
    },
    "Clientes Productos Estructurados": {
        "landing_url": TODO,
        "iframe": "BranderFrame",
        "botones": {
            "Consulta de productos": TODO,
            "Históricos Betas > Curva de TES B en Pesos": TODO,
        },
        "filtros": {},
    },
}


def seccion_lista(area: str, seccion: str) -> bool:
    """True si el area/seccion tiene todos los selectores capturados (sin TODO)."""
    cfg = SECCIONES.get(area)
    if not cfg or cfg.get("landing_url", TODO) == TODO:
        return False
    boton = cfg.get("botones", {}).get(seccion, TODO)
    return boton != TODO
