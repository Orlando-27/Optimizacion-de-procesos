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
