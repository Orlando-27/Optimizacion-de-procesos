"""Tests del parser de ventanas de impugnacion.

Cubre el correo real de ejemplo y variantes deformadas: sin tildes, con HTML,
con saltos de linea en medio de la frase, separadores raros de hora y casos
que deben fallar ruidosamente con ParserError.
"""

from __future__ import annotations

from datetime import time
from pathlib import Path

import pytest

from core.contract import ParserError
from procesos.impugnacion_rfl.parser_correo import parsear_ventanas

FIXTURE = Path(__file__).parent / "fixtures" / "correo_precia_ejemplo.txt"


def test_correo_real_de_ejemplo():
    cuerpo = FIXTURE.read_text(encoding="utf-8")
    v = parsear_ventanas(cuerpo)
    assert v.tes_st_inicio == time(15, 53)
    assert v.tes_st_fin == time(16, 23)
    assert v.demas_inicio == time(15, 53)
    assert v.demas_fin == time(16, 53)


def test_como_texto():
    v = parsear_ventanas(FIXTURE.read_text(encoding="utf-8"))
    assert v.como_texto() == {
        "tes_st_inicio": "15:53",
        "tes_st_fin": "16:23",
        "demas_inicio": "15:53",
        "demas_fin": "16:53",
    }


def test_sin_tildes_ni_mayusculas():
    cuerpo = (
        "el periodo de impugnacion para tes (st) inicia a las 14:05 y termina a las 14:35. "
        "el periodo de impugnacion para los demas archivos inicia a las 14:05 y termina a las 15:05."
    )
    v = parsear_ventanas(cuerpo)
    assert (v.tes_st_inicio, v.tes_st_fin) == (time(14, 5), time(14, 35))
    assert (v.demas_inicio, v.demas_fin) == (time(14, 5), time(15, 5))


def test_con_html_y_entidades():
    cuerpo = (
        "<p>El per&iacute;odo de impugnaci&oacute;n para <b>TES (ST)</b> "
        "inicia a las <strong>16:00</strong> y termina a las 16:30.</p>"
        "<p>El periodo para los dem&aacute;s archivos inicia a las 16:00 "
        "y termina a las 17:00.</p>"
    )
    v = parsear_ventanas(cuerpo)
    assert (v.tes_st_inicio, v.tes_st_fin) == (time(16, 0), time(16, 30))
    assert (v.demas_inicio, v.demas_fin) == (time(16, 0), time(17, 0))


def test_saltos_de_linea_en_medio_de_la_frase():
    cuerpo = (
        "El periodo de impugnacion para TES\n(ST) inicia a las\n15:50 y termina\n"
        "a las 16:20.\nEl periodo de impugnacion para los demas\narchivos inicia "
        "a las 15:50 y\ntermina a las 16:50."
    )
    v = parsear_ventanas(cuerpo)
    assert v.tes_st_fin == time(16, 20)
    assert v.demas_fin == time(16, 50)


def test_separadores_de_hora_raros():
    # 15.53 y 16h23 deben normalizarse a 15:53 / 16:23
    cuerpo = (
        "impugnacion para TES (ST) inicia a las 15.53 y termina a las 16h23. "
        "para los demas archivos inicia a las 15.53 y termina a las 16.53."
    )
    v = parsear_ventanas(cuerpo)
    assert v.tes_st_inicio == time(15, 53)
    assert v.tes_st_fin == time(16, 23)
    assert v.demas_fin == time(16, 53)


def test_tes_sin_parentesis():
    cuerpo = (
        "impugnacion para TES ST inicia a las 15:53 y termina a las 16:23. "
        "los demas archivos inicia a las 15:53 y termina a las 16:53."
    )
    v = parsear_ventanas(cuerpo)
    assert v.tes_st_inicio == time(15, 53)


def test_cuerpo_vacio_falla():
    with pytest.raises(ParserError):
        parsear_ventanas("")


def test_sin_ventana_tes_falla():
    cuerpo = "los demas archivos inicia a las 15:53 y termina a las 16:53."
    with pytest.raises(ParserError):
        parsear_ventanas(cuerpo)


def test_sin_ventana_demas_falla():
    cuerpo = "para TES (ST) inicia a las 15:53 y termina a las 16:23."
    with pytest.raises(ParserError):
        parsear_ventanas(cuerpo)


def test_ventana_incoherente_falla():
    # fin antes que inicio -> ParserError
    cuerpo = (
        "para TES (ST) inicia a las 16:30 y termina a las 16:00. "
        "los demas archivos inicia a las 15:53 y termina a las 16:53."
    )
    with pytest.raises(ParserError):
        parsear_ventanas(cuerpo)


def test_hora_invalida_falla():
    cuerpo = (
        "para TES (ST) inicia a las 25:99 y termina a las 16:00. "
        "los demas archivos inicia a las 15:53 y termina a las 16:53."
    )
    with pytest.raises(ParserError):
        parsear_ventanas(cuerpo)
