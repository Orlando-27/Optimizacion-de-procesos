"""Configuracion del Robot Precia (config.yaml + insumos.yaml), validada con pydantic.

El robot no necesita correo de entrada/salida: solo descarga insumos.
Reutiliza el mismo estilo de configuracion del motor:
interruptor ``entorno: test | prod`` que cambia rutas, destinatarios de alerta
y efectos secundarios.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field

Entorno = Literal["test", "prod"]


class RutasRobotCfg(BaseModel):
    # Ruta unica de destino de los insumos (una sola por ahora, por pedido).
    test: str
    prod: str


class PortalCfg(BaseModel):
    url_login: str = "https://www.precia.co/wp-login.php"
    headless: bool = False          # las apps JSF suelen fallar headless
    timeout_seg: int = 120
    tam_minimo_bytes: int = 1


class FechaCfg(BaseModel):
    # Dias maximos hacia atras para buscar un insumo si t-1 no esta publicado.
    dias_retroceso_max: int = 7
    # Los lunes, ademas de t-1, descargar el fin de semana (sabado y domingo).
    lunes_incluye_fin_de_semana: bool = True


class AlertasRobotCfg(BaseModel):
    owner: str
    asunto: str = "Robot Precia: fallo en la descarga de insumos"
    destinatarios: dict[str, list[str]] = Field(
        default_factory=lambda: {"test": [], "prod": []}
    )
    cc: dict[str, list[str]] = Field(default_factory=lambda: {"test": [], "prod": []})


class ConfigRobot(BaseModel):
    entorno: Entorno = "test"
    rutas: RutasRobotCfg
    portal: PortalCfg = PortalCfg()
    fecha: FechaCfg = FechaCfg()
    alertas: AlertasRobotCfg
    backend_correo: dict[str, str] = Field(
        default_factory=lambda: {"test": "simulado", "prod": "outlook_com"}
    )
    backend_portal: dict[str, str] = Field(
        default_factory=lambda: {"test": "simulado", "prod": "selenium"}
    )
    manifiesto: str = "insumos.yaml"

    # --- Propiedades resueltas por entorno ---
    @property
    def carpeta_destino(self) -> Path:
        return Path(self.rutas.test if self.entorno == "test" else self.rutas.prod)

    @property
    def prefijo_asunto(self) -> str:
        return "" if self.entorno == "prod" else "[PRUEBA] "

    @property
    def enviar_de_verdad(self) -> bool:
        return self.entorno == "prod"

    @property
    def backend_correo_activo(self) -> str:
        return self.backend_correo.get(self.entorno, "simulado")

    @property
    def backend_portal_activo(self) -> str:
        return self.backend_portal.get(self.entorno, "simulado")

    @property
    def destinatarios_alerta_activos(self) -> list[str]:
        return self.alertas.destinatarios.get(self.entorno, [])

    @property
    def cc_alerta_activos(self) -> list[str]:
        return self.alertas.cc.get(self.entorno, [])


class Insumo(BaseModel):
    categoria: str
    prefijo: str
    patron: str
    area: str
    seccion: str
    pagina: int = 1
    filtro: Optional[str] = None


def _aplicar_parametros(base: dict, params: dict) -> None:
    """Superpone los valores del archivo del usuario (parametros.yaml) sobre la
    config tecnica (config.yaml). Solo toca lo que el usuario debe editar:
    entorno, carpeta de destino, remitente y receptores/CC del correo."""
    if params.get("entorno"):
        base["entorno"] = params["entorno"]

    base.setdefault("rutas", {})
    cd = params.get("carpeta_destino") or {}
    if isinstance(cd, dict):
        for env in ("test", "prod"):
            if cd.get(env):
                base["rutas"][env] = cd[env]

    al = base.setdefault("alertas", {})
    if params.get("remitente"):
        al["owner"] = params["remitente"]
    dest = al.setdefault("destinatarios", {})
    rec = params.get("receptores") or {}
    if isinstance(rec, dict):
        for env in ("test", "prod"):
            if rec.get(env) is not None:
                dest[env] = rec[env]
    ccd = al.setdefault("cc", {})
    cc = params.get("copia_cc") or {}
    if isinstance(cc, dict):
        for env in ("test", "prod"):
            if cc.get(env) is not None:
                ccd[env] = cc[env]


def cargar_config(ruta_yaml: str | Path) -> ConfigRobot:
    """Carga config.yaml (tecnica) y, si existe junto a ella ``parametros.yaml``
    (el archivo que edita el usuario), superpone rutas y correos reales."""
    ruta_yaml = Path(ruta_yaml)
    with ruta_yaml.open("r", encoding="utf-8") as f:
        base = yaml.safe_load(f) or {}

    ruta_params = ruta_yaml.parent / "parametros.yaml"
    if ruta_params.exists():
        with ruta_params.open("r", encoding="utf-8") as f:
            params = yaml.safe_load(f) or {}
        _aplicar_parametros(base, params)

    return ConfigRobot.model_validate(base)


def cargar_insumos(ruta_yaml: str | Path) -> list[Insumo]:
    with Path(ruta_yaml).open("r", encoding="utf-8") as f:
        datos = yaml.safe_load(f)
    return [Insumo.model_validate(x) for x in datos.get("insumos", [])]
