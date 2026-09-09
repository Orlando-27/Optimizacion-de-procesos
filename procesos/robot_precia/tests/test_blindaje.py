"""Tests del blindaje del Robot Precia: reporte de correo (OK + fallidos) y
modo respaldo (revisar la ruta y bajar solo lo que falta)."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import pytest

from core.contract import ProcesoSkip, ProcessContext
from procesos.robot_precia.config_robot import cargar_config, cargar_insumos
from procesos.robot_precia.fechas import render_nombre
from procesos.robot_precia.process import RobotPrecia

BASE = Path(__file__).resolve().parents[1]


class _MailFake:
    """Captura la llamada a enviar() sin mandar nada."""
    def __init__(self):
        self.enviado = None
        self.logger = None

    def enviar(self, **kw):
        self.enviado = kw


def _cfg(tmp: Path):
    cfg = cargar_config(BASE / "config.yaml")
    cfg.entorno = "test"
    cfg.rutas.test = str(tmp)          # carpeta_destino -> tmp
    # asegurar que haya destinatarios para que el reporte intente enviar
    cfg.alertas.destinatarios["test"] = ["prueba@colfondos.com.co"]
    return cfg


def _ctx(cfg) -> ProcessContext:
    return ProcessContext(
        run_id="test-run", process_id="robot_precia", process_version="t",
        entorno="test", config=cfg, logger=logging.getLogger("test"),
        extra={},
    )


def test_reporte_asunto_ok_y_alerta(tmp_path):
    from core.notifications import reportar_resumen_descargas
    cfg = _cfg(tmp_path)

    # Caso OK: sin fallidos -> [OK]
    m = _MailFake()
    reportar_resumen_descargas(
        cfg, m, logging.getLogger("t"),
        descargados=[{"insumo": "SB", "fecha": "2026-09-08", "archivo": "SB080926"}],
        fallidos=[], fechas=[date(2026, 9, 8)], hostname="PC-A")
    assert m.enviado is not None
    assert "[OK]" in m.enviado["asunto"] and "PC-A" in m.enviado["asunto"]
    assert "SB" in m.enviado["cuerpo_html"]

    # Caso con fallo -> [ALERTA] y aparece el motivo
    m2 = _MailFake()
    reportar_resumen_descargas(
        cfg, m2, logging.getLogger("t"),
        descargados=[], fallidos=[{"insumo": "MX", "fecha": "2026-09-08",
                                   "error": "timeout"}],
        fechas=[date(2026, 9, 8)], hostname="PC-B")
    assert "[ALERTA]" in m2.enviado["asunto"]
    assert "timeout" in m2.enviado["cuerpo_html"]


def test_respaldo_salta_si_todo_esta(tmp_path):
    cfg = _cfg(tmp_path)
    insumos = cargar_insumos(BASE / "insumos.yaml")
    proc = RobotPrecia(cfg, insumos)
    fecha = date(2026, 9, 8)

    # Simular que la primaria ya bajo TODO (crear los archivos esperados).
    tmp_path.mkdir(parents=True, exist_ok=True)
    for ins in insumos:
        (tmp_path / render_nombre(ins.patron, fecha)).write_text("x", encoding="utf-8")

    ctx = _ctx(cfg)
    ctx.extra["fechas_forzadas"] = [fecha]
    ctx.extra["respaldo"] = True
    with pytest.raises(ProcesoSkip):
        proc.extract(ctx)


def test_respaldo_deja_solo_faltantes(tmp_path):
    cfg = _cfg(tmp_path)
    insumos = cargar_insumos(BASE / "insumos.yaml")
    proc = RobotPrecia(cfg, insumos)
    fecha = date(2026, 9, 8)

    # Bajar todos menos 2 (simula que la primaria fallo a mitad).
    tmp_path.mkdir(parents=True, exist_ok=True)
    faltan = {insumos[0].prefijo, insumos[5].prefijo}
    for ins in insumos:
        if ins.prefijo in faltan:
            continue
        (tmp_path / render_nombre(ins.patron, fecha)).write_text("x", encoding="utf-8")

    ctx = _ctx(cfg)
    ctx.extra["fechas_forzadas"] = [fecha]
    ctx.extra["respaldo"] = True
    data = proc.extract(ctx)
    # el plan debe quedar SOLO con los que faltan
    prefijos_plan = {ins.prefijo for ins, _ in data["plan"]}
    assert prefijos_plan == faltan
