"""Interfaz generica de cliente de correo.

Implementaciones previstas:
  - mail_smtp.py         -> envio via SMTP (Gmail de prueba / corporativo). Portable, corre en GCP.
  - mail_outlook_com.py  -> Outlook de escritorio via COM (solo Windows, opcional para prod).

La lectura del correo detonante (buscar_correo_precia) hoy depende de Outlook;
al migrar a la nube se implementara con IMAP o Graph detras de esta MISMA interfaz.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class Correo:
    """Representacion neutral de un correo, independiente del backend."""

    asunto: str
    remitente: str
    cuerpo: str                    # texto o HTML
    recibido: Optional[datetime] = None
    es_html: bool = False
    adjuntos: list[Path] = field(default_factory=list)


class MailClient(ABC):
    @abstractmethod
    def buscar_correo_precia(
        self,
        fecha: datetime,
        remitente: str,
        asunto_contiene: str,
        ventana_horas: int = 6,
    ) -> Optional[Correo]:
        """Devuelve el correo detonante del dia o None si aun no llego."""

    @abstractmethod
    def enviar(
        self,
        destinatarios: list[str],
        cc: list[str],
        asunto: str,
        cuerpo_html: str,
        adjuntos: list[Path],
        enviar_de_verdad: bool,
    ) -> None:
        """Envia el correo. Si ``enviar_de_verdad`` es False, lo deja como
        borrador (o no lo envia) y lo registra claramente en el log."""


class MailCompuesto(MailClient):
    """Combina dos backends: uno LEE el correo detonante y otro ENVIA.

    Uso: con ``--simular-correo`` se lee el detonante de un archivo (lector
    simulado) pero se envia por el backend real (p. ej. Outlook COM), sin
    mezclar ambas responsabilidades.
    """

    def __init__(self, lector: MailClient, emisor: MailClient) -> None:
        self.lector = lector
        self.emisor = emisor

    @property
    def logger(self):
        return getattr(self.emisor, "logger", None)

    @logger.setter
    def logger(self, value) -> None:
        for c in (self.lector, self.emisor):
            if hasattr(c, "logger"):
                c.logger = value

    def buscar_correo_precia(self, *args, **kwargs):
        return self.lector.buscar_correo_precia(*args, **kwargs)

    def enviar(self, *args, **kwargs):
        return self.emisor.enviar(*args, **kwargs)
