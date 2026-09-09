"""Test del overlay de parametros.yaml sobre config.yaml (archivo editable por
el usuario para rutas y correos)."""

from __future__ import annotations

from pathlib import Path

import yaml

from procesos.robot_precia.config_robot import cargar_config

BASE = Path(__file__).resolve().parents[1]


def test_parametros_superpone_rutas_y_correos(tmp_path):
    # config tecnica minima
    (tmp_path / "config.yaml").write_text(yaml.safe_dump({
        "entorno": "test",
        "rutas": {"test": "./x", "prod": "\\\\viejo\\ruta"},
        "alertas": {"owner": "viejo@x.com",
                    "destinatarios": {"test": ["a@x.com"], "prod": ["viejo@x.com"]},
                    "cc": {"test": [], "prod": []}},
    }), encoding="utf-8")

    # el usuario edita parametros.yaml
    (tmp_path / "parametros.yaml").write_text(yaml.safe_dump({
        "entorno": "prod",
        "carpeta_destino": {"prod": "\\\\SERVIDOR\\INSUMOS"},
        "remitente": "jbobadilla@colfondos.com.co",
        "receptores": {"prod": ["riesgos@colfondos.com.co", "cuant@colfondos.com.co"]},
        "copia_cc": {"prod": ["jefe@colfondos.com.co"]},
    }), encoding="utf-8")

    cfg = cargar_config(tmp_path / "config.yaml")
    # parametros.yaml mando:
    assert cfg.entorno == "prod"
    assert str(cfg.carpeta_destino) == "\\\\SERVIDOR\\INSUMOS"
    assert cfg.alertas.owner == "jbobadilla@colfondos.com.co"
    assert cfg.destinatarios_alerta_activos == ["riesgos@colfondos.com.co",
                                                "cuant@colfondos.com.co"]
    assert cfg.cc_alerta_activos == ["jefe@colfondos.com.co"]


def test_sin_parametros_usa_config(tmp_path):
    # si no hay parametros.yaml, se usa config.yaml tal cual
    (tmp_path / "config.yaml").write_text(yaml.safe_dump({
        "entorno": "test",
        "rutas": {"test": "./x", "prod": "./y"},
        "alertas": {"owner": "o@x.com",
                    "destinatarios": {"test": ["a@x.com"], "prod": []},
                    "cc": {"test": [], "prod": []}},
    }), encoding="utf-8")
    cfg = cargar_config(tmp_path / "config.yaml")
    assert cfg.entorno == "test"
    assert cfg.alertas.owner == "o@x.com"


def test_parametros_real_del_repo_es_valido():
    # el parametros.yaml versionado debe cargar sin romper config.yaml real
    cfg = cargar_config(BASE / "config.yaml")
    assert cfg.entorno in ("test", "prod")
    assert cfg.destinatarios_alerta_activos  # hay al menos un receptor
