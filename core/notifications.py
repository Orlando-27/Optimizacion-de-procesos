"""Alertas por correo cuando el proceso NO se puede ejecutar.

Si una corrida termina en FAILED o VALIDATION_FAILED, se envia un correo a la
lista ``alertas.destinatarios`` (distinta de los destinatarios del correo de
salida) explicando las razones: estado, etapa, mensaje y traceback.

Reusa el mismo MailClient del proceso (Outlook COM en la oficina). Respeta el
entorno: en ``test`` el aviso queda como BORRADOR (para verificar); en ``prod``
se envia. Nunca lanza excepcion: si el aviso falla, se registra y ya.
"""

from __future__ import annotations

import html
import logging
from datetime import datetime
from typing import Optional

from core.config import Config
from core.contract import ProcessResult


def alertar_owner(
    config: Config,
    res: ProcessResult,
    logger: logging.Logger,
    mail=None,
) -> None:
    """Registra y (si hay MailClient) envia el correo de alerta de fallo."""
    dest = config.destinatarios_alerta_activos
    asunto = f"{config.prefijo_asunto}[ALERTA] {config.alertas.asunto} ({res.status.value})"

    # Siempre dejar la traza (aunque no haya correo configurado).
    logger.error(
        "alerta_owner",
        extra={
            "owner": config.alertas.owner,
            "destinatarios_alerta": dest,
            "asunto": asunto,
            "status": res.status.value,
            "mensaje": res.mensaje,
            "run_id": res.run_id,
        },
    )

    if not mail:
        logger.warning("alerta_sin_mailclient",
                       extra={"detalle": "No hay MailClient para enviar la alerta."})
        return
    if not dest:
        logger.warning(
            "alerta_sin_destinatarios",
            extra={"detalle": f"alertas.destinatarios[{config.entorno}] esta vacio; "
                              "configurar los correos que deben recibir el aviso."},
        )
        return

    cuerpo = _componer_html(config, res)
    try:
        mail.enviar(
            destinatarios=dest,
            cc=config.cc_alerta_activos,
            asunto=asunto,
            cuerpo_html=cuerpo,
            adjuntos=[],
            enviar_de_verdad=config.enviar_de_verdad,
        )
        logger.info("alerta_enviada", extra={"destinatarios": dest})
    except Exception:  # noqa: BLE001 - el fallo del aviso no debe romper nada
        logger.exception("alerta_envio_error")


def _componer_html(config: Config, res: ProcessResult) -> str:
    """Arma el cuerpo HTML del aviso con las razones del fallo."""
    etapa = res.metrics.get("etapa") or res.outputs.get("etapa") or "-"
    tb = (res.traceback or "").strip()
    tb_corto = html.escape(tb[-1500:]) if tb else "(sin traceback)"
    inicio = res.inicio.strftime("%Y-%m-%d %H:%M:%S") if res.inicio else "-"
    filas = [
        ("Proceso", res.process_id),
        ("Estado", res.status.value),
        ("Motivo", html.escape(res.mensaje or "-")),
        ("Etapa", html.escape(str(etapa))),
        ("Inicio", inicio),
        ("Run ID", res.run_id),
        ("Entorno", config.entorno),
    ]
    tabla = "".join(
        f"<tr><td style='padding:2px 10px;color:#555'><b>{k}</b></td>"
        f"<td style='padding:2px 10px'>{v}</td></tr>"
        for k, v in filas
    )
    return f"""\
<div style="font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#1f1f1f">
  <p><b style="color:#B00020">El proceso de Impugnación RFL NO se pudo ejecutar.</b></p>
  <table style="border-collapse:collapse">{tabla}</table>
  <p style="margin-top:12px;color:#555">Detalle técnico:</p>
  <pre style="background:#f6f6f6;border:1px solid #ddd;padding:8px;
              font-size:9pt;white-space:pre-wrap">{tb_corto}</pre>
  <p style="color:#888;font-size:9pt">Aviso automático del Motor de Optimización
     de Procesos · {datetime.now():%Y-%m-%d %H:%M}</p>
</div>"""
