"""Tests de las validaciones obligatorias (seccion 6)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path

import pytest
from openpyxl import Workbook

from core.adapters.mail_base import Correo
from core.contract import ValidacionError
from procesos.impugnacion_rfl import validacion as val


# --- dia habil ---
def test_sabado_no_es_habil():
    assert val.es_dia_habil(date(2026, 7, 25)) is False  # sabado


def test_domingo_no_es_habil():
    assert val.es_dia_habil(date(2026, 7, 26)) is False  # domingo


def test_festivo_colombiano_no_es_habil():
    # 20 de julio de 2026: Dia de la Independencia (lunes).
    assert val.es_dia_habil(date(2026, 7, 20)) is False


def test_dia_habil_normal():
    assert val.es_dia_habil(date(2026, 7, 24)) is True  # viernes normal


# --- correo detonante ---
def test_correo_none_falla():
    with pytest.raises(ValidacionError):
        val.validar_correo_detonante(None, "atencionalcliente@precia.co")


def test_correo_remitente_incorrecto_falla():
    c = Correo(asunto="x", remitente="otro@dominio.com", cuerpo="")
    with pytest.raises(ValidacionError):
        val.validar_correo_detonante(c, "atencionalcliente@precia.co")


def test_correo_ok():
    c = Correo(asunto="x", remitente="Atencion <atencionalcliente@precia.co>", cuerpo="")
    val.validar_correo_detonante(c, "atencionalcliente@precia.co")  # no lanza


# --- archivo descargado ---
def test_archivo_inexistente_falla(tmp_path):
    with pytest.raises(ValidacionError):
        val.validar_archivo_descargado(tmp_path / "nope", datetime.now())


def test_archivo_muy_pequeno_falla(tmp_path):
    f = tmp_path / "SX072426"
    f.write_text("x")
    with pytest.raises(ValidacionError):
        val.validar_archivo_descargado(f, datetime(2026, 7, 24), tam_minimo_bytes=1024)


def test_archivo_nombre_no_corresponde_falla(tmp_path):
    f = tmp_path / "OTRONOMBRE.txt"
    f.write_text("x" * 2000)
    with pytest.raises(ValidacionError):
        val.validar_archivo_descargado(f, datetime(2026, 7, 24), tam_minimo_bytes=10)


def test_archivo_ok(tmp_path):
    f = tmp_path / "SX072426.txt"
    f.write_text("x" * 2000)
    val.validar_archivo_descargado(f, datetime(2026, 7, 24), tam_minimo_bytes=10)


# --- salida ---
def _xlsx(ruta: Path) -> Path:
    wb = Workbook()
    wb.active["A1"] = "ok"
    wb.save(ruta)
    return ruta


def test_salida_inexistente_falla(tmp_path):
    with pytest.raises(ValidacionError):
        val.validar_salida(tmp_path / "Renta Fija.xlsx", datetime.now())


def test_salida_de_ayer_falla(tmp_path):
    f = _xlsx(tmp_path / "Renta Fija.xlsx")
    inicio_corrida = datetime.now() + timedelta(hours=1)  # el archivo es anterior
    with pytest.raises(ValidacionError):
        val.validar_salida(f, inicio_corrida)


def test_salida_ok(tmp_path):
    inicio = datetime.now() - timedelta(seconds=5)
    f = _xlsx(tmp_path / "Renta Fija.xlsx")
    val.validar_salida(f, inicio)


# --- SLA ---
def test_sla_dentro_de_ventana():
    assert val.evaluar_sla(time(16, 0), time(16, 23)) is True


def test_sla_fuera_de_ventana():
    assert val.evaluar_sla(time(16, 30), time(16, 23)) is False


# --- destinatarios por entorno ---
def test_test_con_destinatario_de_prod_falla():
    with pytest.raises(ValidacionError):
        val.validar_destinatarios_por_entorno(
            "test", ["real@colfondos.com.co"], ["real@colfondos.com.co"],
        )


def test_test_con_destinatario_seguro_ok():
    val.validar_destinatarios_por_entorno(
        "test", ["joseorlando202014@gmail.com"], ["real@colfondos.com.co"],
    )


def test_destinatarios_vacios_falla():
    with pytest.raises(ValidacionError):
        val.validar_destinatarios_por_entorno("prod", [], [])


# --- adjunto ---
def test_adjunto_inexistente_falla():
    with pytest.raises(ValidacionError):
        val.validar_adjunto(Path("/no/existe.xlsx"))
