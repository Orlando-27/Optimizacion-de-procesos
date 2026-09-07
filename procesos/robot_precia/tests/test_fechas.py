"""Tests de la logica de fechas y del render de nombres del Robot Precia."""

from __future__ import annotations

from datetime import date

from procesos.robot_precia.fechas import fechas_objetivo, render_nombre


# 2026-09-07 es LUNES; 2026-09-08 es martes; 2026-09-05 sabado; 06 domingo.
def test_dia_normal_martes_descarga_t1():
    assert fechas_objetivo(date(2026, 9, 8)) == [date(2026, 9, 7)]  # lunes


def test_dia_normal_viernes_descarga_t1():
    assert fechas_objetivo(date(2026, 9, 11)) == [date(2026, 9, 10)]  # jueves


def test_lunes_descarga_fin_de_semana():
    # Lunes 07/09 -> sabado 05 y domingo 06.
    assert fechas_objetivo(date(2026, 9, 7)) == [date(2026, 9, 5), date(2026, 9, 6)]


def test_domingo_descarga_t1():
    # Domingo 06/09 -> sabado 05 (t-1).
    assert fechas_objetivo(date(2026, 9, 6)) == [date(2026, 9, 5)]


# --- render_nombre ---
def test_render_mmddyy():
    assert render_nombre("SX{MMDDYY}", date(2026, 9, 6)) == "SX090626"


def test_render_ddmmyy():
    assert render_nombre("800149496_Colf_NE{DDMMYY}.csv", date(2026, 9, 6)) == \
        "800149496_Colf_NE060926.csv"


def test_render_yyyy_mm_dd():
    assert render_nombre("bolvalora_{YYYY_MM_DD}_acciones.xls", date(2026, 9, 6)) == \
        "bolvalora_2026_09_06_acciones.xls"


def test_render_sin_token_devuelve_igual():
    assert render_nombre("Curva de TES B en Pesos", date(2026, 9, 6)) == \
        "Curva de TES B en Pesos"
