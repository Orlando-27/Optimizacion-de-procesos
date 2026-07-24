"""MailClient sobre Outlook de escritorio via COM (solo Windows).

Ruta de PRODUCCION opcional si se decide seguir usando el Outlook del equipo en
lugar de SMTP/IMAP. Requiere ``pywin32`` y Outlook instalado; en Linux este
modulo importa pero falla al instanciar (por diseño).

Notas de implementacion (del .md):
- Bandeja de entrada = GetDefaultFolder(6).
- Restrict por [ReceivedTime] para eficiencia, luego filtrar en Python.
- SenderEmailAddress en Exchange puede venir como /O=EXCHANGE...; intentar
  Sender.GetExchangeUser().PrimarySmtpAddress con try/except.
- enviar_de_verdad=False -> .Save() (queda en Borradores), no .Send().
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from core.adapters.mail_base import Correo, MailClient

_OL_FOLDER_INBOX = 6


class MailOutlookCom(MailClient):
    def __init__(self, logger=None) -> None:
        self.logger = logger
        try:
            import win32com.client  # type: ignore
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(
                "MailOutlookCom requiere Windows + pywin32 + Outlook. "
                "En Linux/GCP usar MailSmtpImap."
            ) from e
        self._win32com = win32com.client
        self._app = win32com.client.Dispatch("Outlook.Application")
        self._mapi = self._app.GetNamespace("MAPI")

    def buscar_correo_precia(
        self,
        fecha: datetime,
        remitente: str,
        asunto_contiene: str,
        ventana_horas: int = 6,
    ) -> Optional[Correo]:
        inbox = self._mapi.GetDefaultFolder(_OL_FOLDER_INBOX)
        items = inbox.Items
        items.Sort("[ReceivedTime]", True)
        desde = (fecha - timedelta(hours=ventana_horas)).strftime("%m/%d/%Y %H:%M %p")
        try:
            items = items.Restrict(f"[ReceivedTime] >= '{desde}'")
        except Exception:  # noqa: BLE001 - si Restrict falla, iteramos todo
            pass
        for it in items:
            try:
                asunto = str(getattr(it, "Subject", ""))
                if asunto_contiene.lower() not in asunto.lower():
                    continue
                if not self._remitente_coincide(it, remitente):
                    continue
                cuerpo = str(getattr(it, "HTMLBody", "") or getattr(it, "Body", ""))
                es_html = bool(getattr(it, "HTMLBody", ""))
                return Correo(
                    asunto=asunto,
                    remitente=self._smtp_de(it) or remitente,
                    cuerpo=cuerpo,
                    recibido=getattr(it, "ReceivedTime", None),
                    es_html=es_html,
                )
            except Exception:  # noqa: BLE001 - un item raro no debe tumbar la busqueda
                continue
        return None

    @staticmethod
    def _smtp_de(item) -> Optional[str]:
        try:
            addr = str(getattr(item, "SenderEmailAddress", ""))
            if addr and "@" in addr:
                return addr
            return item.Sender.GetExchangeUser().PrimarySmtpAddress
        except Exception:  # noqa: BLE001
            return None

    def _remitente_coincide(self, item, remitente: str) -> bool:
        smtp = self._smtp_de(item) or ""
        return remitente.lower() in smtp.lower()

    def enviar(
        self,
        destinatarios: list[str],
        cc: list[str],
        asunto: str,
        cuerpo_html: str,
        adjuntos: list[Path],
        enviar_de_verdad: bool,
    ) -> None:
        mail = self._app.CreateItem(0)  # olMailItem
        mail.To = "; ".join(destinatarios)
        if cc:
            mail.CC = "; ".join(cc)
        mail.Subject = asunto
        mail.HTMLBody = cuerpo_html
        for ad in adjuntos:
            mail.Attachments.Add(str(Path(ad).resolve()))
        if enviar_de_verdad:
            mail.Send()
            self._log("correo_enviado", f"Outlook envio a {len(destinatarios)} dest.")
        else:
            mail.Save()  # queda en Borradores
            self._log("correo_borrador", "Guardado en Borradores de Outlook (NO enviado).")

    def _log(self, evento: str, msg: str) -> None:
        if self.logger:
            self.logger.info(evento, extra={"detalle": msg})
