"""Implementacion portable de MailClient: leer via IMAP, enviar via SMTP.

Es la ruta cloud-native: corre en Linux/GCP sin Outlook. En modo test usa la
cuenta de prueba (joseorlando202014@gmail.com con App Password); en prod, el
SMTP/IMAP corporativo. Gmail requiere un App Password (no la clave normal) y
tener IMAP habilitado.

- ``enviar_de_verdad=False`` -> NO envia: guarda el correo como .eml en la
  carpeta de borradores y lo registra en el log (equivalente portable al
  .Save() de Outlook).
"""

from __future__ import annotations

import imaplib
import email
import smtplib
import ssl
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional

from core.adapters.mail_base import Correo, MailClient


class MailSmtpImap(MailClient):
    def __init__(
        self,
        usuario: str,
        clave: str,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587,
        imap_host: str = "imap.gmail.com",
        imap_port: int = 993,
        carpeta_borradores: Path = Path("sandbox/borradores"),
        logger=None,
    ) -> None:
        self.usuario = usuario
        self._clave = clave
        self.smtp_host, self.smtp_port = smtp_host, smtp_port
        self.imap_host, self.imap_port = imap_host, imap_port
        self.carpeta_borradores = Path(carpeta_borradores)
        self.logger = logger

    # --- Lectura del correo detonante (IMAP) ---
    def buscar_correo_precia(
        self,
        fecha: datetime,
        remitente: str,
        asunto_contiene: str,
        ventana_horas: int = 6,
    ) -> Optional[Correo]:
        desde = (fecha - timedelta(hours=ventana_horas)).strftime("%d-%b-%Y")
        with imaplib.IMAP4_SSL(self.imap_host, self.imap_port) as im:
            im.login(self.usuario, self._clave)
            im.select("INBOX")
            # IMAP SINCE es por dia; afinamos por remitente en el criterio.
            typ, datos = im.search(None, f'(SINCE "{desde}" FROM "{remitente}")')
            if typ != "OK" or not datos or not datos[0]:
                return None
            for num in reversed(datos[0].split()):  # mas reciente primero
                typ, raw = im.fetch(num, "(RFC822)")
                if typ != "OK" or not raw or not raw[0]:
                    continue
                msg = email.message_from_bytes(raw[0][1])
                asunto = str(msg.get("Subject", ""))
                if asunto_contiene.lower() not in asunto.lower():
                    continue
                recibido = None
                try:
                    recibido = parsedate_to_datetime(msg.get("Date"))
                except Exception:  # noqa: BLE001
                    pass
                cuerpo, es_html = self._extraer_cuerpo(msg)
                return Correo(
                    asunto=asunto,
                    remitente=str(msg.get("From", remitente)),
                    cuerpo=cuerpo,
                    recibido=recibido,
                    es_html=es_html,
                )
        return None

    @staticmethod
    def _extraer_cuerpo(msg: email.message.Message) -> tuple[str, bool]:
        if msg.is_multipart():
            # Preferimos text/plain; si no hay, tomamos text/html.
            html_part = None
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype == "text/plain":
                    return part.get_content(), False
                if ctype == "text/html" and html_part is None:
                    html_part = part
            if html_part is not None:
                return html_part.get_content(), True
            return "", False
        return msg.get_content(), msg.get_content_type() == "text/html"

    # --- Envio (SMTP) ---
    def enviar(
        self,
        destinatarios: list[str],
        cc: list[str],
        asunto: str,
        cuerpo_html: str,
        adjuntos: list[Path],
        enviar_de_verdad: bool,
    ) -> None:
        msg = EmailMessage()
        msg["From"] = self.usuario
        msg["To"] = ", ".join(destinatarios)
        if cc:
            msg["Cc"] = ", ".join(cc)
        msg["Subject"] = asunto
        msg.set_content("Este correo requiere un cliente compatible con HTML.")
        msg.add_alternative(cuerpo_html, subtype="html")
        for ad in adjuntos:
            ad = Path(ad)
            msg.add_attachment(
                ad.read_bytes(),
                maintype="application",
                subtype="octet-stream",
                filename=ad.name,
            )

        if not enviar_de_verdad:
            self.carpeta_borradores.mkdir(parents=True, exist_ok=True)
            destino = self.carpeta_borradores / f"borrador_{datetime.now():%Y%m%d_%H%M%S}.eml"
            destino.write_bytes(bytes(msg))
            self._log("correo_borrador", f"NO enviado (test). Guardado en {destino}",
                      destinatarios=destinatarios)
            return

        todos = list(destinatarios) + list(cc)
        ctx = ssl.create_default_context()
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as s:
            s.starttls(context=ctx)
            s.login(self.usuario, self._clave)
            s.send_message(msg, from_addr=self.usuario, to_addrs=todos)
        self._log("correo_enviado", f"Enviado a {len(todos)} destinatario(s)",
                  destinatarios=destinatarios)

    def _log(self, evento: str, msg: str, **extra) -> None:
        if self.logger:
            self.logger.info(evento, extra={"detalle": msg, **extra})
