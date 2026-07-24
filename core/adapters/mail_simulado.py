"""MailClient simulado, sin red, para pruebas y --simular-correo.

- ``buscar_correo_precia`` devuelve un correo leido de un archivo local
  (el cuerpo guardado), util para probar el parser y el pipeline sin esperar
  a las 4pm ni tener Outlook.
- ``enviar`` nunca manda nada: escribe el .eml en la carpeta de borradores.

Es el backend por defecto en modo test/offline en este entorno Linux.
"""

from __future__ import annotations

from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Optional

from core.adapters.mail_base import Correo, MailClient


class MailSimulado(MailClient):
    def __init__(
        self,
        cuerpo_simulado: Optional[str] = None,
        ruta_cuerpo: Optional[Path] = None,
        remitente_simulado: str = "atencionalcliente@precia.co",
        carpeta_borradores: Path = Path("sandbox/borradores"),
        logger=None,
    ) -> None:
        if ruta_cuerpo is not None:
            cuerpo_simulado = Path(ruta_cuerpo).read_text(encoding="utf-8")
        self.cuerpo_simulado = cuerpo_simulado
        self.remitente_simulado = remitente_simulado
        self.carpeta_borradores = Path(carpeta_borradores)
        self.logger = logger

    def buscar_correo_precia(
        self,
        fecha: datetime,
        remitente: str,
        asunto_contiene: str,
        ventana_horas: int = 6,
    ) -> Optional[Correo]:
        if not self.cuerpo_simulado:
            return None
        return Correo(
            asunto=f"[EXTERNAL]: {asunto_contiene}",
            remitente=self.remitente_simulado,
            cuerpo=self.cuerpo_simulado,
            recibido=fecha,
            es_html="<" in self.cuerpo_simulado and ">" in self.cuerpo_simulado,
        )

    def enviar(
        self,
        destinatarios: list[str],
        cc: list[str],
        asunto: str,
        cuerpo_html: str,
        adjuntos: list[Path],
        enviar_de_verdad: bool,  # ignorado: el simulado nunca envia de verdad
    ) -> None:
        msg = EmailMessage()
        msg["From"] = self.remitente_simulado
        msg["To"] = ", ".join(destinatarios)
        if cc:
            msg["Cc"] = ", ".join(cc)
        msg["Subject"] = asunto
        msg.add_alternative(cuerpo_html, subtype="html")
        for ad in adjuntos:
            ad = Path(ad)
            if ad.exists():
                msg.add_attachment(ad.read_bytes(), maintype="application",
                                   subtype="octet-stream", filename=ad.name)
        self.carpeta_borradores.mkdir(parents=True, exist_ok=True)
        destino = self.carpeta_borradores / f"simulado_{datetime.now():%Y%m%d_%H%M%S}.eml"
        destino.write_bytes(bytes(msg))
        if self.logger:
            self.logger.info(
                "correo_simulado",
                extra={"detalle": f"NO enviado (simulado). Guardado en {destino}",
                       "destinatarios": destinatarios, "adjuntos": [str(a) for a in adjuntos]},
            )
