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


def reportar_resumen_descargas(
    config,
    mail,
    logger: logging.Logger,
    *,
    descargados: list[dict],
    fallidos: list[dict],
    fechas: list,
    hostname: str = "",
    error_global: Optional[str] = None,
    modo_respaldo: bool = False,
) -> None:
    """Envia UN correo de reporte de la corrida del robot con dos listas:
    los insumos que SI se descargaron y los que NO (con su motivo).

    Se envia siempre (exito o fallo). El asunto refleja el estado. Nunca lanza:
    si el correo falla, se registra y ya. Reusa el MailClient del proceso.
    """
    total = len(descargados) + len(fallidos)
    hay_fallo = bool(fallidos) or bool(error_global)
    etiqueta = "[ALERTA] " if hay_fallo else "[OK] "
    resp = "[RESPALDO] " if modo_respaldo else ""
    asunto = (f"{config.prefijo_asunto}{resp}{etiqueta}Robot Precia: "
              f"{len(descargados)} OK / {len(fallidos)} fallaron"
              + (f" ({hostname})" if hostname else ""))
    dest = config.destinatarios_alerta_activos

    logger.info(
        "reporte_descargas",
        extra={"descargados": len(descargados), "fallidos": len(fallidos),
               "total": total, "hostname": hostname, "asunto": asunto,
               "destinatarios": dest},
    )
    if not mail or not dest:
        logger.warning("reporte_sin_envio",
                       extra={"detalle": "sin MailClient o sin destinatarios; "
                                         "solo queda en el log."})
        return

    cuerpo = _componer_html_reporte(config, descargados, fallidos, fechas,
                                    hostname, error_global, modo_respaldo)
    try:
        mail.enviar(
            destinatarios=dest,
            cc=config.cc_alerta_activos,
            asunto=asunto,
            cuerpo_html=cuerpo,
            adjuntos=[],
            enviar_de_verdad=config.enviar_de_verdad,
        )
        logger.info("reporte_enviado", extra={"destinatarios": dest})
    except Exception:  # noqa: BLE001 - el reporte no debe romper la corrida
        logger.exception("reporte_envio_error")


def _tabla_insumos(filas: list[dict], columnas: list[tuple]) -> str:
    if not filas:
        return "<p style='color:#888'>(ninguno)</p>"
    th = "".join(f"<th style='text-align:left;padding:3px 10px;border-bottom:"
                 f"1px solid #ccc'>{t}</th>" for _, t in columnas)
    trs = []
    for x in filas:
        tds = "".join(
            f"<td style='padding:2px 10px;border-bottom:1px solid #eee'>"
            f"{html.escape(str(x.get(k, '')))}</td>" for k, _ in columnas)
        trs.append(f"<tr>{tds}</tr>")
    return (f"<table style='border-collapse:collapse;font-size:10pt'>"
            f"<tr>{th}</tr>{''.join(trs)}</table>")


def _componer_html_reporte(config, descargados, fallidos, fechas, hostname,
                           error_global, modo_respaldo) -> str:
    fechas_txt = ", ".join(str(f) for f in fechas) if fechas else "-"
    color = "#B00020" if (fallidos or error_global) else "#1B7F3B"
    estado = ("CON FALLOS" if (fallidos or error_global)
              else ("RESPALDO: nada que hacer" if modo_respaldo and not descargados
                    else "OK"))
    aviso_global = (f"<p style='color:#B00020'><b>Fallo global:</b> "
                    f"{html.escape(str(error_global))}</p>" if error_global else "")
    return f"""\
<div style="font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#1f1f1f">
  <p><b style="color:{color}">Robot Precia — {estado}</b></p>
  <table style="border-collapse:collapse;margin-bottom:10px">
    <tr><td style='padding:2px 10px;color:#555'><b>Fechas</b></td><td style='padding:2px 10px'>{fechas_txt}</td></tr>
    <tr><td style='padding:2px 10px;color:#555'><b>Descargados</b></td><td style='padding:2px 10px'>{len(descargados)}</td></tr>
    <tr><td style='padding:2px 10px;color:#555'><b>Fallidos</b></td><td style='padding:2px 10px'>{len(fallidos)}</td></tr>
    <tr><td style='padding:2px 10px;color:#555'><b>Equipo</b></td><td style='padding:2px 10px'>{html.escape(hostname or '-')}</td></tr>
    <tr><td style='padding:2px 10px;color:#555'><b>Entorno</b></td><td style='padding:2px 10px'>{config.entorno}</td></tr>
  </table>
  {aviso_global}
  <p style="margin:12px 0 4px;color:#1B7F3B"><b>✓ Descargados ({len(descargados)})</b></p>
  {_tabla_insumos(descargados, [("insumo","Insumo"),("fecha","Fecha"),("archivo","Archivo")])}
  <p style="margin:12px 0 4px;color:#B00020"><b>✗ No descargados ({len(fallidos)})</b></p>
  {_tabla_insumos(fallidos, [("insumo","Insumo"),("fecha","Fecha"),("error","Motivo")])}
  <p style="color:#888;font-size:9pt;margin-top:14px">Reporte automático del Motor de
     Optimización de Procesos · {datetime.now():%Y-%m-%d %H:%M}</p>
</div>"""


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
