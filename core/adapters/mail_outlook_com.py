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
    def __init__(self, logger=None, remitente: str | None = None) -> None:
        self.logger = logger
        self.remitente = remitente  # SMTP de la cuenta desde la que enviar
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

    def _cuenta_por_smtp(self, smtp: str):
        """Devuelve la Account de Outlook cuyo SMTP coincide, o None."""
        try:
            for cuenta in self._app.Session.Accounts:
                if str(getattr(cuenta, "SmtpAddress", "")).lower() == smtp.lower():
                    return cuenta
        except Exception:  # noqa: BLE001
            pass
        return None

    def buscar_correo_precia(
        self,
        fecha: datetime,
        remitente: str,
        asunto_contiene: str,
        ventana_horas: int = 6,
    ) -> Optional[Correo]:
        """Devuelve el correo detonante del dia. EXIGE remitente Y asunto:

        como del mismo remitente llegan muchos correos, un correo solo se acepta
        si (1) el remitente coincide y (2) el asunto CONTIENE el texto esperado.
        La comparacion de asunto es tolerante a tildes/mayusculas/espacios.
        Como los items van ordenados por fecha descendente, se devuelve el MAS
        RECIENTE que cumple ambas condiciones.
        """
        inbox = self._mapi.GetDefaultFolder(_OL_FOLDER_INBOX)
        items = inbox.Items
        items.Sort("[ReceivedTime]", True)
        desde = (fecha - timedelta(hours=ventana_horas)).strftime("%m/%d/%Y %H:%M %p")
        try:
            items = items.Restrict(f"[ReceivedTime] >= '{desde}'")
        except Exception:  # noqa: BLE001 - si Restrict falla, iteramos todo
            pass

        objetivo = self._norm(asunto_contiene)
        candidatos = 0
        for it in items:
            try:
                asunto = str(getattr(it, "Subject", ""))
                remitente_ok = self._remitente_coincide(it, remitente)
                asunto_ok = objetivo in self._norm(asunto)
                # AMBOS son obligatorios.
                if not (remitente_ok and asunto_ok):
                    continue
                candidatos += 1
                cuerpo = str(getattr(it, "HTMLBody", "") or getattr(it, "Body", ""))
                es_html = bool(getattr(it, "HTMLBody", ""))
                self._log(
                    "correo_precia_encontrado",
                    f"Coincide remitente+asunto: '{asunto[:70]}' "
                    f"({getattr(it, 'ReceivedTime', '?')})",
                )
                return Correo(
                    asunto=asunto,
                    remitente=self._smtp_de(it) or remitente,
                    cuerpo=cuerpo,
                    recibido=getattr(it, "ReceivedTime", None),
                    es_html=es_html,
                )
            except Exception:  # noqa: BLE001 - un item raro no debe tumbar la busqueda
                continue
        self._log("correo_precia_no_encontrado",
                  f"Ningun correo cumple remitente '{remitente}' + asunto '{asunto_contiene}' "
                  f"en las ultimas {ventana_horas}h.")
        return None

    @staticmethod
    def _norm(texto: str) -> str:
        """Minusculas, sin tildes, espacios colapsados (para comparar asuntos)."""
        import re
        import unicodedata
        t = unicodedata.normalize("NFKD", texto or "")
        t = "".join(c for c in t if not unicodedata.combining(c))
        return re.sub(r"\s+", " ", t).strip().lower()

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
        # Forzar la cuenta remitente si se configuro (Outlook con varias cuentas).
        if self.remitente:
            cuenta = self._cuenta_por_smtp(self.remitente)
            if cuenta is not None:
                try:
                    mail.SendUsingAccount = cuenta
                except Exception:  # noqa: BLE001
                    pass
            else:
                try:
                    mail.SentOnBehalfOfName = self.remitente
                except Exception:  # noqa: BLE001
                    pass
        if enviar_de_verdad:
            mail.Send()
            self._log("correo_enviado", f"Outlook envio a {len(destinatarios)} dest.")
        else:
            mail.Save()  # queda en Borradores
            self._log("correo_borrador", "Guardado en Borradores de Outlook (NO enviado).")

    def _log(self, evento: str, msg: str) -> None:
        if self.logger:
            self.logger.info(evento, extra={"detalle": msg})
