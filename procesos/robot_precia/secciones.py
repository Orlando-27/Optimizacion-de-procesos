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
        "landing_url": "https://www.precia.co/index.php/renta-variable/",  # CONFIRMADO
        "iframe": "BranderFrame",
        # CONFIRMADO (volcado del portal): flujo "directo" como Renta Fija
        # (calendario inline + tabla reflow con columnas Archivo/Descargar).
        #   #arcval    -> archivosValoracionLocal.xhtml
        #   #arcvalin  -> archivosValoracionInt.xhtml
        "botones": {
            "Archivos De Valoración": "#arcval",
            "Archivos De Valoración Internacional": "#arcvalin",
        },
        "filtros": {},  # estas secciones no llevan filtro de texto
    },
    "Clientes Derivados": {
        "landing_url": "https://www.precia.co/index.php/derivados/",  # CONFIRMADO
        "iframe": "BranderFrame",
        # CONFIRMADO: flujo "agrupador". Boton de menu #descagrup carga
        # descargaArchivosAgrupador.xhtml; ahi se elige el grupo (dropdown),
        # la fecha (popup), se pulsa Buscar y se filtra la tabla por la columna
        # Prefijo (FWD/SWAPCC).
        "flujo": "agrupador",
        "boton_menu": "#descagrup",
        "botones": {  # todas las sub-secciones entran por el mismo boton
            "Descargar Archivo Agrupador > Insumos Locales": "#descagrup",
            "Descargar Archivo Agrupador > Insumos Swaps Internacionales": "#descagrup",
            "Descargar Archivo Agrupador > Insumos Forward Internacionales": "#descagrup",
            "Descargar Archivo Agrupador > Otros Insumos": "#descagrup",
        },
        # seccion -> etiqueta del grupo en el dropdown (espacios normalizados).
        "grupos": {
            "Descargar Archivo Agrupador > Insumos Locales": "Insumos Locales",
            "Descargar Archivo Agrupador > Insumos Swaps Internacionales": "Insumos Swaps Internacionales",
            "Descargar Archivo Agrupador > Insumos Forward Internacionales": "Insumos Forward Internacionales",
            "Descargar Archivo Agrupador > Otros Insumos": "Otros Insumos",
        },
        # El filtro FWD/SWAPCC va en la columna "Prefijo" de la tabla.
        "filtro_columna": "Prefijo",
        # Selectores JSF (By.ID, sin escapar):
        "sel": {
            "agrupador": "formDescarga1:autAgrupador",   # dropdown de grupo
            "fecha": "formDescarga1:popupFecha",         # span calendar (popup)
            "buscar": "formDescarga1:btnBuscar",
            "tabla": "formDescarga2:dtDescargaArchivos",
        },
    },
    "Clientes Productos Estructurados": {
        "landing_url": "https://www.precia.co/index.php/productos-estructurados/",  # CONFIRMADO
        "iframe": "BranderFrame",
        # CONFIRMADO (volcado del portal): flujo "consulta". El boton #conpro
        # carga consultaProductos.xhtml; ahi se elige la fecha en un datepicker
        # POPUP (no inline) y la tabla 'Nombre Archivo / Descargar' se refresca
        # sola (no hay boton Buscar). Se ubica el archivo por su nombre.
        "flujo": "consulta",
        "boton_menu": "#conpro",
        "botones": {
            "Consulta de productos": "#conpro",           # consultaProductos.xhtml
            # NOTA: 'Históricos Betas > Curva de TES B en Pesos' NO existe en el
            # menu de Productos Estructurados. 'Historico betas' (#hisbe) esta en
            # Renta Fija; ese insumo esta pendiente de reubicar (ver insumos.yaml).
            "Históricos Betas > Curva de TES B en Pesos": TODO,
        },
        "sel": {
            "fecha": "formConsultaProductos:fechaIni",        # span datepicker popup
            "tabla": "formConsultaProductos:tblConsultaProductos",
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
