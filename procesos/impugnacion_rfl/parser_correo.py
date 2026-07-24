"""Extrae las ventanas de impugnacion del cuerpo del correo de Precia.

El correo trae dos ventanas que cambian cada dia y hay que leer del texto (no
asumir):
  - TES (ST):        inicio y fin
  - Los demas archivos: inicio y fin

Ejemplo real (correo de Atencion al Cliente <atencionalcliente@precia.co>):
    "El periodo de impugnacion para TES (ST) inicia a las 15:53 y termina a las 16:23.
     El periodo de impugnacion para los demas archivos inicia a las 15:53 y termina a las 16:53."

El texto llega con acentos inconsistentes, saltos de linea en medio de la frase
y a veces HTML. Se normaliza (strip HTML, quita tildes, colapsa espacios,
homogeneiza separadores de hora) ANTES de aplicar el regex. Si no se puede
parsear -> ``ParserError`` (no falla silencioso).
"""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass
from datetime import time

from core.contract import ParserError


@dataclass(frozen=True)
class VentanasImpugnacion:
    """Las cuatro horas parseadas del correo del dia."""

    tes_st_inicio: time
    tes_st_fin: time
    demas_inicio: time
    demas_fin: time

    def como_texto(self) -> dict[str, str]:
        return {
            "tes_st_inicio": self.tes_st_inicio.strftime("%H:%M"),
            "tes_st_fin": self.tes_st_fin.strftime("%H:%M"),
            "demas_inicio": self.demas_inicio.strftime("%H:%M"),
            "demas_fin": self.demas_fin.strftime("%H:%M"),
        }


# --- Normalizacion -----------------------------------------------------------

_RE_TAG = re.compile(r"<[^>]+>")
_RE_ESPACIOS = re.compile(r"\s+")
# Separador de hora: acepta 15:53, 15.53, 15 53, 15h53 -> 15:53
_RE_SEP_HORA = re.compile(r"(?<=\d)\s*[.h:]\s*(?=\d{2}\b)")


def _normalizar(cuerpo: str) -> str:
    """Deja el texto en minusculas, sin tildes, sin HTML y con espacios simples."""
    txt = html.unescape(cuerpo)
    txt = _RE_TAG.sub(" ", txt)                       # strip HTML
    txt = unicodedata.normalize("NFKD", txt)          # descompone acentos
    txt = "".join(c for c in txt if not unicodedata.combining(c))  # quita tildes
    txt = txt.lower()
    txt = _RE_ESPACIOS.sub(" ", txt)                  # colapsa espacios/saltos
    txt = _RE_SEP_HORA.sub(":", txt)                  # homogeneiza separador de hora
    return txt.strip()


# --- Extraccion de horas -----------------------------------------------------

_HORA = r"(\d{1,2}):(\d{2})"
# Tolerante a texto intermedio (a las, la(s), aprox., etc.) entre keyword y hora.
_INTERMEDIO = r"[^0-9]{0,40}?"

_RE_TES = re.compile(
    r"tes\s*\(?\s*st\s*\)?"          # "tes (st)" con o sin parentesis/espacios
    r".*?inicia" + _INTERMEDIO + _HORA +
    r".*?termina" + _INTERMEDIO + _HORA,
    re.DOTALL,
)
_RE_DEMAS = re.compile(
    r"demas"                          # "los demas archivos"
    r".*?inicia" + _INTERMEDIO + _HORA +
    r".*?termina" + _INTERMEDIO + _HORA,
    re.DOTALL,
)


def _a_time(hh: str, mm: str, etiqueta: str) -> time:
    h, m = int(hh), int(mm)
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ParserError(f"Hora invalida para {etiqueta}: {hh}:{mm}")
    return time(h, m)


def parsear_ventanas(cuerpo: str) -> VentanasImpugnacion:
    """Extrae las 4 horas del cuerpo del correo. Lanza ``ParserError`` si falla."""
    if not cuerpo or not cuerpo.strip():
        raise ParserError("Cuerpo de correo vacio: no hay ventanas que parsear.")

    txt = _normalizar(cuerpo)

    m_tes = _RE_TES.search(txt)
    if not m_tes:
        raise ParserError(
            "No se encontro la ventana de TES (ST) en el correo. "
            "Revisar formato del cuerpo o el regex."
        )
    m_demas = _RE_DEMAS.search(txt)
    if not m_demas:
        raise ParserError(
            "No se encontro la ventana de 'los demas archivos' en el correo."
        )

    ventanas = VentanasImpugnacion(
        tes_st_inicio=_a_time(m_tes.group(1), m_tes.group(2), "tes_st_inicio"),
        tes_st_fin=_a_time(m_tes.group(3), m_tes.group(4), "tes_st_fin"),
        demas_inicio=_a_time(m_demas.group(1), m_demas.group(2), "demas_inicio"),
        demas_fin=_a_time(m_demas.group(3), m_demas.group(4), "demas_fin"),
    )

    # Coherencia minima: fin posterior al inicio en cada ventana.
    if ventanas.tes_st_fin <= ventanas.tes_st_inicio:
        raise ParserError(
            f"Ventana TES incoherente: fin {ventanas.tes_st_fin} <= inicio "
            f"{ventanas.tes_st_inicio}."
        )
    if ventanas.demas_fin <= ventanas.demas_inicio:
        raise ParserError(
            f"Ventana 'demas' incoherente: fin {ventanas.demas_fin} <= inicio "
            f"{ventanas.demas_inicio}."
        )
    return ventanas
