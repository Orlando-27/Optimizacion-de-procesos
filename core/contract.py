"""Contrato generico que todo proceso del motor debe cumplir.

Define el patron ETL (extract -> transform -> load -> validate) mas el metodo
plantilla ``run`` que orquesta el ciclo, mide duracion y captura errores en un
``ProcessResult`` homogeneo. Los procesos concretos (p. ej. ``ImpugnacionRFL``)
heredan de ``Proceso`` e implementan los pasos; NO deben sobreescribir ``run``.

Este modulo es 100% agnostico del SO y de la nube: no importa nada de Windows,
Outlook, Excel ni Selenium. Esa dependencia vive en los adaptadores.
"""

from __future__ import annotations

import time
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class RunStatus(str, Enum):
    """Estado final de una corrida. Hereda de ``str`` para serializar directo a
    SQLite/BigQuery/JSON sin conversiones."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    SKIPPED = "SKIPPED"          # p. ej. dia no habil o ya hubo un SUCCESS hoy
    WAITING = "WAITING"          # el correo detonante aun no llega


class ProcesoError(Exception):
    """Base de errores de negocio del motor. Los subtipos permiten mapear a un
    ``RunStatus`` especifico sin depender del texto del mensaje."""


class ValidacionError(ProcesoError):
    """Una validacion obligatoria fallo -> RunStatus.VALIDATION_FAILED."""


class ParserError(ProcesoError):
    """No se pudo parsear informacion critica (p. ej. las ventanas del correo)."""


class ProcesoSkip(ProcesoError):
    """Senal de que la corrida debe saltarse SIN alertar (dia no habil,
    ya hubo un SUCCESS hoy, ...). -> RunStatus.SKIPPED."""


class ProcesoEsperando(ProcesoError):
    """El insumo aun no esta disponible (p. ej. el correo no ha llegado dentro
    de la ventana). -> RunStatus.WAITING/FAILED segun el caso."""


class PasoPendienteError(ProcesoError):
    """Un paso aun no esta implementado (p. ej. paso 5: macro por migrar).
    Se usa para fallar de forma explicita y trazable, nunca en silencio."""


@dataclass
class ProcessContext:
    """Todo lo que un proceso necesita para correr, inyectado desde afuera.

    Se pasa por parametro (no se lee de globales) para que el mismo proceso
    corra en test, en prod o en GCP solo cambiando lo que se inyecta aqui.
    """

    run_id: str
    process_id: str
    process_version: str
    entorno: str                       # "test" | "prod"
    config: Any                        # objeto de configuracion validado (core.config)
    logger: Any                        # logging.Logger ya contextualizado
    trigger: str = "manual"            # "scheduler" | "manual" | "cli"
    disparado_por: str = "desconocido"
    dry_run: bool = False
    paso_aislado: Optional[int] = None  # --paso N: correr un solo paso
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessResult:
    """Resultado homogeneo de una corrida. Sus campos calzan 1:1 con la tabla
    ``runs`` de ``run_store`` (y con el esquema futuro de BigQuery)."""

    run_id: str
    process_id: str
    process_version: str
    status: RunStatus = RunStatus.WAITING
    inicio: Optional[datetime] = None
    fin: Optional[datetime] = None
    duracion_seg: Optional[float] = None
    filas: Optional[int] = None
    sla_cumplido: Optional[bool] = None
    outputs: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    mensaje: str = ""
    traceback: Optional[str] = None
    trigger: str = "manual"
    disparado_por: str = "desconocido"

    def marcar_fin(self) -> None:
        """Cierra tiempos y calcula duracion. Idempotente."""
        if self.fin is None:
            self.fin = datetime.now(timezone.utc)
        if self.inicio is not None and self.duracion_seg is None:
            self.duracion_seg = (self.fin - self.inicio).total_seconds()


class Proceso(ABC):
    """Clase base de un proceso automatizable.

    Implementa ``extract``, ``transform``, ``load`` y opcionalmente ``validate``.
    ``run`` es una plantilla: NO sobreescribir.
    """

    process_id: str = "proceso_base"
    process_version: str = "0.0.0"

    @abstractmethod
    def extract(self, ctx: ProcessContext) -> Any:
        """Obtiene los insumos externos (correo, descarga del portal, ...)."""

    @abstractmethod
    def transform(self, ctx: ProcessContext, data: Any) -> Any:
        """Aplica la logica de negocio (macro migrada a Python, etc.)."""

    @abstractmethod
    def load(self, ctx: ProcessContext, result: Any) -> ProcessResult:
        """Publica el resultado (envia el correo, archiva la salida)."""

    def validate(self, ctx: ProcessContext, result: Any) -> bool:
        """Chequeos de integridad. Por defecto no valida nada.

        Debe lanzar ``ValidacionError`` si algo no cumple, para diferenciar un
        VALIDATION_FAILED de un FAILED tecnico.
        """
        return True

    def run(self, ctx: ProcessContext) -> ProcessResult:
        """Metodo plantilla: orquesta extract -> transform -> validate -> load.

        Captura tiempos y excepciones y siempre devuelve un ``ProcessResult``.
        No relanza: el runner decide que hacer con el status.
        """
        res = ProcessResult(
            run_id=ctx.run_id,
            process_id=self.process_id,
            process_version=self.process_version,
            inicio=datetime.now(timezone.utc),
            trigger=ctx.trigger,
            disparado_por=ctx.disparado_por,
        )
        inicio_orig = res.inicio
        t0 = time.perf_counter()
        try:
            ctx.logger.info("extract:inicio")
            data = self.extract(ctx)

            ctx.logger.info("transform:inicio")
            transformado = self.transform(ctx, data)

            ctx.logger.info("validate:inicio")
            self.validate(ctx, transformado)  # lanza ValidacionError si falla

            ctx.logger.info("load:inicio")
            res = self.load(ctx, transformado)
            if res.status == RunStatus.WAITING:
                res.status = RunStatus.SUCCESS

        except ProcesoSkip as e:
            res.status = RunStatus.SKIPPED
            res.mensaje = str(e)
            ctx.logger.info("proceso_saltado", extra={"detalle": str(e)})
        except ProcesoEsperando as e:
            res.status = RunStatus.WAITING
            res.mensaje = str(e)
            ctx.logger.warning("proceso_esperando", extra={"detalle": str(e)})
        except ValidacionError as e:
            res.status = RunStatus.VALIDATION_FAILED
            res.mensaje = str(e)
            res.traceback = traceback.format_exc()
            ctx.logger.error("validacion_fallida", extra={"detalle": str(e)})
        except ParserError as e:
            res.status = RunStatus.FAILED
            res.mensaje = f"ParserError: {e}"
            res.traceback = traceback.format_exc()
            ctx.logger.error("parser_error", extra={"detalle": str(e)})
        except ProcesoError as e:
            res.status = RunStatus.FAILED
            res.mensaje = str(e)
            res.traceback = traceback.format_exc()
            ctx.logger.error("proceso_error", extra={"detalle": str(e)})
        except Exception as e:  # noqa: BLE001 - frontera: cualquier fallo -> FAILED
            res.status = RunStatus.FAILED
            res.mensaje = f"Error inesperado: {e}"
            res.traceback = traceback.format_exc()
            ctx.logger.exception("error_inesperado")
        finally:
            # load() puede devolver un ProcessResult nuevo sin inicio: se preserva.
            if res.inicio is None:
                res.inicio = inicio_orig
            res.metrics.setdefault("duracion_perf_seg", round(time.perf_counter() - t0, 3))
            res.marcar_fin()
            ctx.logger.info("run:fin", extra={"status": res.status.value})
        return res
