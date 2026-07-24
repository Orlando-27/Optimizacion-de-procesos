"""Proceso 001: ImpugnacionRFL. Ensambla extract/transform/load sobre el motor.

Mapeo al contrato:
  extract   -> pasos 1-3: dia habil, detectar correo (polling), parsear ventanas,
               login + descarga del portal.
  transform -> pasos 4-6: copiar a INFOVALMER, generar Renta Fija.xlsx (paso 5
               PENDIENTE -> placeholder), confirmar la salida.
  load      -> paso 7: componer y enviar el correo con adjunto; archivar copia.
  validate  -> chequeos de la seccion 6.

Ejecutable:  python -m procesos.impugnacion_rfl.process [flags]
"""

from __future__ import annotations

import argparse
import time as _time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from core.adapters.mail_base import Correo, MailClient
from core.adapters.storage_local import StorageLocal
from core.config import Config, cargar_config
from core.contract import (
    PasoPendienteError,
    Proceso,
    ProcesoEsperando,
    ProcesoSkip,
    ProcessContext,
    ProcessResult,
    RunStatus,
)
from core.run_store import RunStore
from core.runner import ejecutar
from core.secrets import secretos_del_portal, secretos_smtp
from procesos.impugnacion_rfl import validacion as val
from procesos.impugnacion_rfl.parser_correo import VentanasImpugnacion, parsear_ventanas
from procesos.impugnacion_rfl.portal_precia import PortalRFL, nombre_archivo_esperado
from procesos.impugnacion_rfl.transform_impugnacion import crear_transformador

RUTA_CONFIG = Path(__file__).parent / "config.yaml"
RUTA_PLANTILLA = Path(__file__).parent / "plantillas" / "cuerpo_correo.html"
FIXTURE_CORREO = Path(__file__).parent / "tests" / "fixtures" / "correo_precia_ejemplo.txt"


class ImpugnacionRFL(Proceso):
    process_id = "impugnacion_rfl"
    process_version = "0.1.0"

    def __init__(
        self,
        mail: MailClient,
        portal: PortalRFL,
        transformador,
        storage: Optional[StorageLocal] = None,
        plantilla_html: str = "",
    ) -> None:
        self.mail = mail
        self.portal = portal
        self.transformador = transformador
        self.storage = storage or StorageLocal()
        self.plantilla_html = plantilla_html or RUTA_PLANTILLA.read_text(encoding="utf-8")

    def _sincronizar_logger(self, ctx: ProcessContext) -> None:
        """Propaga el logger de la corrida a los adaptadores (un solo run_id)."""
        for comp in (self.mail, self.portal, self.transformador, self.storage):
            if hasattr(comp, "logger"):
                comp.logger = ctx.logger

    # ------------------------------------------------------------------ EXTRACT
    def extract(self, ctx: ProcessContext) -> dict[str, Any]:
        self._sincronizar_logger(ctx)
        cfg: Config = ctx.config
        hoy = datetime.now()

        # (Validacion 1) Dia habil -> si no, SKIPPED sin alertar.
        if not val.es_dia_habil(hoy.date()):
            raise ProcesoSkip(f"{hoy:%Y-%m-%d} no es dia habil en Colombia.")

        # (Pasos 1-2) Detectar el correo detonante (con polling salvo test/sim/dry).
        correo = self._esperar_correo(ctx, hoy)
        val.validar_correo_detonante(correo, cfg.correo_entrada.remitente)
        ctx.logger.info("correo_detectado", extra={"remitente": correo.remitente,
                                                    "asunto": correo.asunto})

        # (Paso 1) Parsear las ventanas del cuerpo.
        ventanas = parsear_ventanas(correo.cuerpo)
        ctx.logger.info("ventanas_parseadas", extra=ventanas.como_texto())

        # (Pasos 2-3) Login + descarga del portal.
        usuario, clave = secretos_del_portal()
        carpeta_descarga = cfg.infovalmer  # se descarga directo hacia INFOVALMER
        ruta_descarga = self.portal.descargar_archivo_rfl(
            fecha=hoy, usuario=usuario or "", clave=clave or "",
            carpeta_destino=carpeta_descarga, headless=cfg.portal.headless,
        )
        ctx.logger.info("archivo_descargado", extra={"ruta": str(ruta_descarga)})

        return {"correo": correo, "ventanas": ventanas, "ruta_descarga": ruta_descarga,
                "inicio": hoy}

    def _esperar_correo(self, ctx: ProcessContext, hoy: datetime) -> Optional[Correo]:
        cfg: Config = ctx.config
        ce = cfg.correo_entrada
        una_pasada = (ctx.entorno == "test" or ctx.dry_run
                      or cfg.backend_correo_activo == "simulado")

        while True:
            correo = self.mail.buscar_correo_precia(
                fecha=hoy,
                remitente=ce.remitente,
                asunto_contiene=ce.asunto_contiene,
            )
            if correo is not None:
                return correo
            if una_pasada:
                raise ProcesoEsperando(
                    "El correo de Precia no esta disponible (modo test/simulado)."
                )
            if datetime.now().time() >= ce.hora_limite_espera:
                # Seccion 7: si a la hora limite no llego -> FAILED con alerta.
                from core.contract import ProcesoError
                raise ProcesoError(
                    "correo de Precia no recibido en la ventana "
                    f"(limite {ce.hora_limite_espera:%H:%M})."
                )
            ctx.logger.info("polling_correo",
                            extra={"reintento_en_seg": ce.intervalo_poll_seg})
            _time.sleep(ce.intervalo_poll_seg)

    # ---------------------------------------------------------------- TRANSFORM
    def transform(self, ctx: ProcessContext, data: dict[str, Any]) -> dict[str, Any]:
        cfg: Config = ctx.config
        ruta_descarga: Path = data["ruta_descarga"]

        # (Validacion 3) Archivo descargado integro.
        val.validar_archivo_descargado(
            ruta_descarga, data["inicio"],
            tam_minimo_bytes=cfg.portal.tam_minimo_bytes,
            # el simulado crea un plano chico; en test relajamos el umbral
            verificar_nombre=True,
        ) if ctx.entorno == "prod" else None

        # (Paso 4) Asegurar que el archivo quede en INFOVALMER.
        destino_infovalmer = cfg.infovalmer / ruta_descarga.name
        if ruta_descarga.resolve() != destino_infovalmer.resolve():
            destino_infovalmer = self.storage.copiar(ruta_descarga, destino_infovalmer)
        ctx.logger.info("guardado_infovalmer", extra={"ruta": str(destino_infovalmer)})

        # (Pasos 5-6) Generar Renta Fija.xlsx  [PASO 5 PENDIENTE -> placeholder].
        ruta_salida = self.transformador.generar_reporte(
            archivo_entrada=destino_infovalmer, carpeta_salida=cfg.impugnacion,
        )
        ctx.logger.info("reporte_generado", extra={"ruta": str(ruta_salida)})

        data.update({"ruta_infovalmer": destino_infovalmer, "ruta_salida": ruta_salida})
        return data

    # ----------------------------------------------------------------- VALIDATE
    def validate(self, ctx: ProcessContext, data: dict[str, Any]) -> bool:
        cfg: Config = ctx.config
        ventanas: VentanasImpugnacion = data["ventanas"]

        # (Validacion 5) Salida correcta y de esta corrida.
        val.validar_salida(data["ruta_salida"], data["inicio"])

        # (Validacion 6) SLA: ahora vs tes_st_fin.
        sla_ok = val.evaluar_sla(datetime.now().time(), ventanas.tes_st_fin)
        data["sla_cumplido"] = sla_ok
        if not sla_ok:
            ctx.logger.warning("sla_incumplido",
                               extra={"tes_st_fin": ventanas.tes_st_fin.strftime("%H:%M"),
                                      "detalle": "Impugnacion fuera de ventana; se envia con alerta."})

        # (Validacion 7) Destinatarios coherentes con el entorno + adjunto existe.
        val.validar_destinatarios_por_entorno(
            cfg.entorno, cfg.destinatarios_activos,
            cfg.correo_salida.destinatarios.get("prod", []),
        )
        val.validar_adjunto(data["ruta_salida"])
        return True

    # --------------------------------------------------------------------- LOAD
    def load(self, ctx: ProcessContext, data: dict[str, Any]) -> ProcessResult:
        cfg: Config = ctx.config
        ventanas: VentanasImpugnacion = data["ventanas"]
        sla_ok = data.get("sla_cumplido", True)

        cuerpo = self._render(self.plantilla_html, ventanas)
        asunto = cfg.prefijo_asunto + cfg.correo_salida.asunto
        if not sla_ok:
            asunto = "[SLA VENCIDO] " + asunto

        if ctx.dry_run:
            ctx.logger.warning("dry_run", extra={"detalle": "No se envia ni se archiva nada."})
        else:
            self.mail.enviar(
                destinatarios=cfg.destinatarios_activos,
                cc=cfg.cc_activos,
                asunto=asunto,
                cuerpo_html=cuerpo,
                adjuntos=[data["ruta_salida"]],
                enviar_de_verdad=cfg.enviar_de_verdad,
            )
            self._archivar(cfg, data["ruta_salida"], data["inicio"], ctx)

        res = ProcessResult(
            run_id=ctx.run_id, process_id=self.process_id,
            process_version=self.process_version, status=RunStatus.SUCCESS,
            sla_cumplido=sla_ok, filas=None,
            outputs={"ruta_salida": str(data["ruta_salida"]),
                     "ruta_infovalmer": str(data.get("ruta_infovalmer", "")),
                     "destinatarios": cfg.destinatarios_activos},
            metrics={"ventanas": ventanas.como_texto(), "entorno": cfg.entorno,
                     "enviado": (not ctx.dry_run) and cfg.enviar_de_verdad},
            mensaje="Correo compuesto correctamente." if not ctx.dry_run else "dry-run: sin envio.",
            trigger=ctx.trigger, disparado_por=ctx.disparado_por,
        )
        return res

    @staticmethod
    def _render(plantilla: str, v: VentanasImpugnacion) -> str:
        t = v.como_texto()
        return plantilla.format(
            tes_st_inicio=t["tes_st_inicio"], tes_st_fin=t["tes_st_fin"],
            demas_inicio=t["demas_inicio"], demas_fin=t["demas_fin"],
        )

    def _archivar(self, cfg: Config, ruta_salida: Path, inicio: datetime, ctx) -> None:
        """Guarda una copia fechada de la salida para trazabilidad."""
        carpeta = cfg.impugnacion / "archivo"
        destino = carpeta / f"Renta Fija_{inicio:%Y%m%d}.xlsx"
        try:
            self.storage.copiar(ruta_salida, destino)
            ctx.logger.info("salida_archivada", extra={"ruta": str(destino)})
        except Exception:  # noqa: BLE001
            ctx.logger.exception("archivar:error")


# ============================================================ FABRICA / CLI ===

def construir_proceso(
    cfg: Config, logger=None, ruta_simular_correo: Optional[Path] = None
) -> ImpugnacionRFL:
    """Construye el proceso con los adaptadores segun entorno/config."""
    # --- Correo ---
    backend = "simulado" if ruta_simular_correo else cfg.backend_correo_activo
    if backend == "simulado":
        from core.adapters.mail_simulado import MailSimulado
        ruta = ruta_simular_correo or FIXTURE_CORREO
        mail: MailClient = MailSimulado(ruta_cuerpo=ruta, logger=logger)
    elif backend == "smtp_imap":
        from core.adapters.mail_smtp_imap import MailSmtpImap
        usuario, clave = secretos_smtp(cfg.entorno)
        mail = MailSmtpImap(usuario=usuario or "", clave=clave or "", logger=logger)
    elif backend == "outlook_com":
        from core.adapters.mail_outlook_com import MailOutlookCom
        mail = MailOutlookCom(logger=logger)
    else:
        raise ValueError(f"backend_correo desconocido: {backend}")

    # --- Portal ---
    if cfg.backend_portal_activo == "simulado":
        from procesos.impugnacion_rfl.portal_precia import PortalSimulado
        portal: PortalRFL = PortalSimulado(archivo_fixture=Path("sandbox/INFOVALMER/_fixture_rfl.txt"),
                                           logger=logger)
    else:
        from procesos.impugnacion_rfl.portal_precia import PortalPreciaSelenium
        portal = PortalPreciaSelenium(url_login=cfg.portal.url_login,
                                      timeout_seg=cfg.portal.timeout_seg, logger=logger)

    # --- Transformador (paso 5) ---
    transformador = crear_transformador(cfg.excel.motor, cfg.excel.archivo_salida,
                                        logger, cfg_excel=cfg.excel)

    return ImpugnacionRFL(mail=mail, portal=portal, transformador=transformador)


def _parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Proceso impugnacion_rfl")
    p.add_argument("--entorno", choices=["test", "prod"], help="Sobreescribe config.entorno")
    p.add_argument("--dry-run", action="store_true", help="Corre todo pero no envia ni escribe en prod")
    p.add_argument("--paso", type=int, help="Corre un paso aislado (1..7) para depurar")
    p.add_argument("--simular-correo", type=Path, help="Usa un cuerpo de correo de archivo")
    p.add_argument("--config", type=Path, default=RUTA_CONFIG)
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    cfg = cargar_config(args.config)
    if args.entorno:
        cfg.entorno = args.entorno

    # Idempotencia (seccion 7): si ya hubo SUCCESS hoy -> SKIPPED.
    store = RunStore()
    if store.existe_success_hoy(ImpugnacionRFL.process_id):
        print("SKIPPED: ya hubo una corrida SUCCESS hoy (idempotencia).")
        return 0

    if args.paso is not None:
        from core.logging_config import configurar_logging
        from core.runner import nuevo_run_id
        run_id = nuevo_run_id(ImpugnacionRFL.process_id)
        logger = configurar_logging(run_id, ImpugnacionRFL.process_id, Path("logs"))
        proceso = construir_proceso(cfg, logger=logger, ruta_simular_correo=args.simular_correo)
        return _correr_paso(proceso, cfg, logger, args)

    # Ruta normal: el runner crea el logger/run_id y el proceso lo propaga a
    # sus adaptadores (ver _sincronizar_logger).
    proceso = construir_proceso(cfg, logger=None, ruta_simular_correo=args.simular_correo)
    res = ejecutar(
        proceso, cfg, trigger="cli",
        disparado_por="cli", dry_run=args.dry_run, store=store,
        secretos=tuple(x for x in (secretos_del_portal() + secretos_smtp(cfg.entorno)) if x),
    )
    print(f"STATUS: {res.status.value} | duracion={res.duracion_seg}s | {res.mensaje}")
    # exit code: 0 si SUCCESS/SKIPPED/WAITING, 1 si fallo (para el Programador de Tareas).
    return 0 if res.status in (RunStatus.SUCCESS, RunStatus.SKIPPED, RunStatus.WAITING) else 1


def _correr_paso(proceso: ImpugnacionRFL, cfg: Config, logger, args) -> int:
    """Ejecuta un paso aislado para depuracion (--paso N)."""
    ctx = ProcessContext(
        run_id="paso-aislado", process_id=ImpugnacionRFL.process_id,
        process_version=ImpugnacionRFL.process_version, entorno=cfg.entorno,
        config=cfg, logger=logger, trigger="cli-paso", dry_run=args.dry_run,
        paso_aislado=args.paso,
    )
    try:
        if args.paso in (1, 2, 3):
            data = proceso.extract(ctx)
            print("VENTANAS:", data["ventanas"].como_texto())
            print("DESCARGA:", data["ruta_descarga"])
        elif args.paso in (4, 5, 6):
            data = proceso.extract(ctx)
            data = proceso.transform(ctx, data)
            print("SALIDA:", data["ruta_salida"])
        elif args.paso == 7:
            data = proceso.extract(ctx)
            data = proceso.transform(ctx, data)
            proceso.validate(ctx, data)
            proceso.load(ctx, data)
            print("CORREO compuesto/enviado segun entorno.")
        else:
            print(f"Paso {args.paso} no reconocido (usar 1..7).")
            return 2
        return 0
    except PasoPendienteError as e:
        print(f"PASO PENDIENTE: {e}")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
