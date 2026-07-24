"""Registro de corridas en SQLite, con esquema listo para BigQuery.

La tabla ``runs`` tiene exactamente las columnas que despues se replicaran en
BigQuery, de modo que el dashboard futuro consuma ``consultar_recientes`` sin
cambios. La implementacion es intercambiable: manana un ``RunStoreBigQuery``
puede implementar la misma interfaz publica.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from core.contract import ProcessResult

_DDL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id           TEXT PRIMARY KEY,
    process_id       TEXT NOT NULL,
    process_version  TEXT,
    trigger          TEXT,
    status           TEXT NOT NULL,
    inicio           TEXT,
    fin              TEXT,
    duracion_seg     REAL,
    filas            INTEGER,
    sla_cumplido     INTEGER,
    outputs          TEXT,   -- JSON
    metrics          TEXT,   -- JSON
    mensaje          TEXT,
    traceback        TEXT,
    disparado_por    TEXT
);
"""


class RunStore:
    """Almacen de corridas sobre SQLite local."""

    def __init__(self, ruta_db: str | Path = "logs/runs.db") -> None:
        self.ruta_db = Path(ruta_db)
        self.ruta_db.parent.mkdir(parents=True, exist_ok=True)
        with self._con() as con:
            con.executescript(_DDL)

    def _con(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.ruta_db)
        con.row_factory = sqlite3.Row
        return con

    def guardar(self, res: ProcessResult) -> None:
        """Inserta o reemplaza el registro de una corrida."""
        fila = {
            "run_id": res.run_id,
            "process_id": res.process_id,
            "process_version": res.process_version,
            "trigger": res.trigger,
            "status": res.status.value,
            "inicio": res.inicio.isoformat() if res.inicio else None,
            "fin": res.fin.isoformat() if res.fin else None,
            "duracion_seg": res.duracion_seg,
            "filas": res.filas,
            "sla_cumplido": None if res.sla_cumplido is None else int(res.sla_cumplido),
            "outputs": json.dumps(res.outputs, ensure_ascii=False, default=str),
            "metrics": json.dumps(res.metrics, ensure_ascii=False, default=str),
            "mensaje": res.mensaje,
            "traceback": res.traceback,
            "disparado_por": res.disparado_por,
        }
        cols = ", ".join(fila)
        marc = ", ".join(f":{k}" for k in fila)
        with self._con() as con:
            con.execute(f"INSERT OR REPLACE INTO runs ({cols}) VALUES ({marc})", fila)

    def consultar_recientes(self, limite: int = 20) -> list[dict[str, Any]]:
        """Ultimas corridas, mas recientes primero. Base del dashboard futuro."""
        with self._con() as con:
            cur = con.execute(
                "SELECT * FROM runs ORDER BY COALESCE(inicio, '') DESC LIMIT ?",
                (limite,),
            )
            return [self._deserializar(dict(r)) for r in cur.fetchall()]

    def existe_success_hoy(self, process_id: str, fecha: datetime | None = None) -> bool:
        """Idempotencia: ¿ya hubo un SUCCESS para este proceso hoy?"""
        dia = (fecha or datetime.now()).strftime("%Y-%m-%d")
        with self._con() as con:
            cur = con.execute(
                "SELECT 1 FROM runs WHERE process_id = ? AND status = 'SUCCESS' "
                "AND substr(inicio, 1, 10) = ? LIMIT 1",
                (process_id, dia),
            )
            return cur.fetchone() is not None

    @staticmethod
    def _deserializar(fila: dict[str, Any]) -> dict[str, Any]:
        for campo in ("outputs", "metrics"):
            if isinstance(fila.get(campo), str):
                try:
                    fila[campo] = json.loads(fila[campo])
                except (ValueError, TypeError):
                    pass
        if fila.get("sla_cumplido") is not None:
            fila["sla_cumplido"] = bool(fila["sla_cumplido"])
        return fila
