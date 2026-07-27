"""Ejecuta un proceso end-to-end: arma contexto, corre, persiste y notifica.

Es el pegamento entre ``Proceso.run`` (logica pura), ``RunStore`` (persistencia)
y ``notifications`` (alertas al owner). No conoce nada especifico de
impugnacion_rfl: cualquier proceso del motor se ejecuta por aca.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from core.config import Config
from core.contract import Proceso, ProcessContext, ProcessResult, RunStatus
from core.logging_config import configurar_logging
from core.run_store import RunStore


def nuevo_run_id(process_id: str) -> str:
    """ID legible + unico: <process_id>-YYYYMMDD-HHMMSS-<8hex>."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{process_id}-{ts}-{uuid.uuid4().hex[:8]}"


def ejecutar(
    proceso: Proceso,
    config: Config,
    *,
    trigger: str = "manual",
    disparado_por: str = "desconocido",
    dry_run: bool = False,
    paso_aislado: Optional[int] = None,
    carpeta_logs: Path = Path("logs"),
    store: Optional[RunStore] = None,
    secretos: tuple[Optional[str], ...] = (),
    notificar_fallo: bool = True,
    extra: Optional[dict] = None,
) -> ProcessResult:
    """Orquesta una corrida completa y devuelve el resultado ya persistido."""
    run_id = nuevo_run_id(proceso.process_id)
    logger = configurar_logging(
        run_id=run_id,
        process_id=proceso.process_id,
        carpeta_logs=carpeta_logs,
        secretos=secretos,
    )
    logger.info("runner:inicio", extra={"entorno": config.entorno, "dry_run": dry_run})

    ctx = ProcessContext(
        run_id=run_id,
        process_id=proceso.process_id,
        process_version=proceso.process_version,
        entorno=config.entorno,
        config=config,
        logger=logger,
        trigger=trigger,
        disparado_por=disparado_por,
        dry_run=dry_run,
        paso_aislado=paso_aislado,
        extra=extra or {},
    )

    store = store or RunStore()
    res = proceso.run(ctx)

    try:
        store.guardar(res)
    except Exception:  # noqa: BLE001 - no perder la corrida por un fallo de persistencia
        logger.exception("run_store:error_guardando")

    if notificar_fallo and res.status in (RunStatus.FAILED, RunStatus.VALIDATION_FAILED):
        try:
            from core.notifications import alertar_owner
            # Reusa el MailClient del proceso para enviar el aviso (Outlook, etc.).
            alertar_owner(config, res, logger, mail=getattr(proceso, "mail", None))
        except Exception:  # noqa: BLE001
            logger.exception("notificacion:error")

    return res
