"""Fabrica de MailClient (emisor) reutilizable por cualquier proceso.

Centraliza la creacion del backend de correo segun su nombre, para que tanto
impugnacion_rfl como robot_precia (y procesos futuros) envien correos/alertas
sin duplicar la logica.
"""

from __future__ import annotations

from typing import Optional

from core.adapters.mail_base import MailClient


def crear_emisor(
    backend: str,
    entorno: str,
    remitente: Optional[str] = None,
    logger=None,
    fixture_correo=None,
) -> MailClient:
    """Crea el MailClient de ENVIO segun ``backend``.

    - 'simulado'    : escribe .eml en sandbox (sin red). Para test/offline.
    - 'smtp_imap'   : SMTP/IMAP (Gmail de prueba / corporativo).
    - 'outlook_com' : Outlook de escritorio (Windows), remitente configurable.
    """
    if backend == "outlook_com":
        from core.adapters.mail_outlook_com import MailOutlookCom
        return MailOutlookCom(logger=logger, remitente=remitente)
    if backend == "smtp_imap":
        from core.adapters.mail_smtp_imap import MailSmtpImap
        from core.secrets import secretos_smtp
        usuario, clave = secretos_smtp(entorno)
        return MailSmtpImap(usuario=usuario or "", clave=clave or "", logger=logger)
    # simulado (por defecto)
    from core.adapters.mail_simulado import MailSimulado
    return MailSimulado(ruta_cuerpo=fixture_correo, logger=logger)
