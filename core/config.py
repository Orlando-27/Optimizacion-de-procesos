"""Carga y validacion de configuracion (config.yaml + .env) con pydantic.

Resuelve el interruptor global ``entorno: test | prod`` en propiedades
convenientes (``rutas_activas``, ``destinatarios_activos``, ...) para que el
proceso no tenga que preguntar por el entorno en cada punto.

Los secretos NO viven aqui: esta capa solo describe rutas, destinatarios y
parametros. Las credenciales se leen aparte en ``core.secrets``.
"""

from __future__ import annotations

from datetime import time
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

Entorno = Literal["test", "prod"]


class _PorEntorno(BaseModel):
    """Un valor que cambia entre test y prod."""
    test: object
    prod: object


class RutasCfg(BaseModel):
    test: dict[str, str]
    prod: dict[str, str]


class CorreoEntradaCfg(BaseModel):
    remitente: str
    asunto_contiene: str
    hora_inicio_poll: time
    hora_limite_espera: time
    intervalo_poll_seg: int = 60
    remitente_test: str | None = None  # para simular el detonante en test

    @field_validator("hora_inicio_poll", "hora_limite_espera", mode="before")
    @classmethod
    def _parse_hora(cls, v: object) -> object:
        if isinstance(v, str) and ":" in v:
            hh, mm = v.split(":")[:2]
            return time(int(hh), int(mm))
        return v


class CorreoSalidaCfg(BaseModel):
    asunto: str
    destinatarios: dict[str, list[str]]
    cc: dict[str, list[str]] = Field(default_factory=lambda: {"test": [], "prod": []})
    plantilla: str = "plantillas/cuerpo_correo.html"


class ExcelCfg(BaseModel):
    # Se conserva por compatibilidad y como fallback documentado. La macro se
    # migra a Python (transform nativo), pero dejamos el nombre parametrizado.
    archivo_macro: str = "Informacion Impugnacion.xlsm"
    nombre_macro: str = "<PENDIENTE_CONFIRMAR>"
    archivo_salida: str = "Renta Fija.xlsx"
    timeout_seg: int = 300
    # "python" = macro migrada (paso 5, pendiente) | "placeholder" = salida
    # minima para probar el pipeline | "com" = correr el VBA original (Windows).
    motor: Literal["python", "placeholder", "com"] = "python"


class PortalCfg(BaseModel):
    url_login: str
    headless: bool = True
    timeout_seg: int = 120
    patron_archivo: str = "SX{MMDDYY}"  # SXMMDDYY, ver correo de Precia
    tam_minimo_bytes: int = 1024


class AlertasCfg(BaseModel):
    owner: str


class SlaCfg(BaseModel):
    max_duracion_seg: int = 300


class Config(BaseModel):
    """Configuracion completa del proceso, ya validada."""

    entorno: Entorno = "test"
    rutas: RutasCfg
    correo_entrada: CorreoEntradaCfg
    correo_salida: CorreoSalidaCfg
    excel: ExcelCfg
    portal: PortalCfg
    alertas: AlertasCfg
    sla: SlaCfg
    # Backend de correo por entorno: "simulado" | "smtp_imap" | "outlook_com"
    backend_correo: dict[str, str] = Field(
        default_factory=lambda: {"test": "simulado", "prod": "smtp_imap"}
    )
    # Backend del portal por entorno: "simulado" | "selenium"
    backend_portal: dict[str, str] = Field(
        default_factory=lambda: {"test": "simulado", "prod": "selenium"}
    )

    # --- Propiedades resueltas segun el entorno activo ---
    @property
    def rutas_activas(self) -> dict[str, Path]:
        return {k: Path(v) for k, v in getattr(self.rutas, self.entorno).items()}

    @property
    def infovalmer(self) -> Path:
        return self.rutas_activas["infovalmer"]

    @property
    def impugnacion(self) -> Path:
        return self.rutas_activas["impugnacion"]

    @property
    def destinatarios_activos(self) -> list[str]:
        return self.correo_salida.destinatarios[self.entorno]

    @property
    def cc_activos(self) -> list[str]:
        return self.correo_salida.cc.get(self.entorno, [])

    @property
    def prefijo_asunto(self) -> str:
        return "" if self.entorno == "prod" else "[PRUEBA] "

    @property
    def enviar_de_verdad(self) -> bool:
        """En test se guarda como borrador; en prod se envia."""
        return self.entorno == "prod"

    @property
    def backend_correo_activo(self) -> str:
        return self.backend_correo.get(self.entorno, "simulado")

    @property
    def backend_portal_activo(self) -> str:
        return self.backend_portal.get(self.entorno, "simulado")


def cargar_config(ruta_yaml: str | Path) -> Config:
    """Lee ``config.yaml`` y devuelve un ``Config`` validado.

    Lanza ``pydantic.ValidationError`` si falta o esta mal un campo; es
    intencional fallar temprano y ruidoso antes de tocar produccion.
    """
    ruta = Path(ruta_yaml)
    with ruta.open("r", encoding="utf-8") as f:
        datos = yaml.safe_load(f)
    return Config.model_validate(datos)
