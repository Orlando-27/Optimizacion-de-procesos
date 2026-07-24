"""Alertas al owner ante fallos.

Por ahora deja la alerta registrada en el log estructurado (siempre disponible).
Cuando el adaptador de correo este cableado, ``alertar_owner`` reusara el mismo
MailClient para mandar el aviso al owner definido en ``config.alertas.owner``.
"""

from __future__ import annotations

import logging

from core.config import Config
from core.contract import ProcessResult


def alertar_owner(config: Config, res: ProcessResult, logger: logging.Logger) -> None:
    """Notifica al owner un fallo o validacion fallida.

    TODO(load): enviar el correo real via MailClient cuando el adaptador de
    salida este disponible. De momento se garantiza la traza en el log.
    """
    asunto = f"[ALERTA] {res.process_id} -> {res.status.value}"
    logger.error(
        "alerta_owner",
        extra={
            "owner": config.alertas.owner,
            "asunto": asunto,
            "status": res.status.value,
            "mensaje": res.mensaje,
            "run_id": res.run_id,
        },
    )
