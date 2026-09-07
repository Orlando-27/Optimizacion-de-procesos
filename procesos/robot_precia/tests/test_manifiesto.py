"""Tests de carga del manifiesto de insumos y de la config del robot."""

from __future__ import annotations

from pathlib import Path

from procesos.robot_precia.config_robot import cargar_config, cargar_insumos

BASE = Path(__file__).resolve().parents[1]


def test_manifiesto_carga_y_tiene_insumos():
    insumos = cargar_insumos(BASE / "insumos.yaml")
    assert len(insumos) >= 40  # ~43 declarados en el Excel
    # todos traen los campos minimos
    for ins in insumos:
        assert ins.prefijo and ins.area and ins.seccion
        assert ins.pagina in (1, 2)


def test_config_valida_y_resuelve_entorno():
    cfg = cargar_config(BASE / "config.yaml")
    assert cfg.entorno == "test"
    assert str(cfg.carpeta_destino)  # ruta unica resuelta
    assert cfg.backend_portal_activo in ("simulado", "selenium")
    assert cfg.destinatarios_alerta_activos  # hay al menos un correo de alerta


def test_secciones_esperadas_presentes():
    insumos = cargar_insumos(BASE / "insumos.yaml")
    areas = {i.area for i in insumos}
    assert "Clientes Renta Fija Local" in areas
    assert "Clientes Renta Variable" in areas
    assert "Clientes Derivados" in areas
    assert "Clientes Productos Estructurados" in areas
