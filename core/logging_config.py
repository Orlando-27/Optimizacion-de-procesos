"""Logging estructurado en JSON con contexto de corrida.

Cada linea de log es un objeto JSON con ``run_id`` y ``process_id`` fijos, lo
que hace trivial filtrar una corrida entera despues (y cargar los logs a un
sink en la nube sin reparsear texto). Incluye un enmascarador de secretos:
ningun valor sensible debe aparecer nunca en los logs.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

# Campos estandar de LogRecord que NO queremos duplicar dentro de "extra".
_RESERVADOS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "taskName",
}


class _EnmascararSecretos(logging.Filter):
    """Reemplaza en el mensaje cualquier valor sensible conocido por ``***``.

    Se registran los secretos vivos (clave del portal, del SMTP, etc.) al
    cargarlos, de modo que aunque un modulo los loguee por error queden ocultos.
    """

    _valores: set[str] = set()

    @classmethod
    def registrar(cls, *secretos: Optional[str]) -> None:
        for s in secretos:
            if s and len(s) >= 4:  # evita enmascarar cadenas triviales
                cls._valores.add(s)

    def filter(self, record: logging.LogRecord) -> bool:
        if self._valores:
            msg = record.getMessage()
            for secreto in self._valores:
                if secreto in msg:
                    msg = msg.replace(secreto, "***")
            record.msg = msg
            record.args = ()
        return True


class _JsonFormatter(logging.Formatter):
    def __init__(self, run_id: str, process_id: str) -> None:
        super().__init__()
        self.run_id = run_id
        self.process_id = process_id

    def format(self, record: logging.LogRecord) -> str:
        base = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "nivel": record.levelname,
            "run_id": self.run_id,
            "process_id": self.process_id,
            "evento": record.getMessage(),
            "modulo": record.module,
        }
        # Cualquier kwarg pasado via logger.info(..., extra={...}) se agrega plano.
        for k, v in record.__dict__.items():
            if k not in _RESERVADOS and k not in base and not k.startswith("_"):
                base[k] = v
        if record.exc_info:
            base["traceback"] = self.formatException(record.exc_info)
        return json.dumps(base, ensure_ascii=False, default=str)


def configurar_logging(
    run_id: str,
    process_id: str,
    carpeta_logs: Path,
    nivel: int = logging.INFO,
    secretos: Iterable[Optional[str]] = (),
) -> logging.Logger:
    """Configura y devuelve un logger contextualizado para la corrida.

    Escribe a stdout (para que el .bat lo capture) y a un archivo JSONL diario.
    """
    carpeta_logs.mkdir(parents=True, exist_ok=True)
    _EnmascararSecretos.registrar(*secretos)

    logger = logging.getLogger(f"{process_id}.{run_id}")
    logger.setLevel(nivel)
    logger.handlers.clear()
    logger.propagate = False

    fmt = _JsonFormatter(run_id, process_id)
    filtro = _EnmascararSecretos()

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    sh.addFilter(filtro)
    logger.addHandler(sh)

    hoy = datetime.now(timezone.utc).strftime("%Y%m%d")
    fh = logging.FileHandler(carpeta_logs / f"{process_id}_{hoy}.jsonl", encoding="utf-8")
    fh.setFormatter(fmt)
    fh.addFilter(filtro)
    logger.addHandler(fh)

    return logger


def enmascarar(texto: str) -> str:
    """Utilidad para enmascarar a mano (p. ej. antes de imprimir una URL)."""
    return re.sub(r"(clave|pwd|password|token)=([^&\s]+)", r"\1=***", texto, flags=re.I)
