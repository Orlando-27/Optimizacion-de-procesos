"""Proceso 002: RobotPrecia. Descarga diaria de insumos del portal de Precia.

Mapeo al contrato ETL:
  extract   -> planifica: calcula las fechas objetivo (t-1; lunes = fin de
               semana) y expande la lista (insumo x fecha) a descargar.
  transform -> descarga: recorre el plan con el navegador (Selenium) y guarda
               cada insumo en la ruta unica de destino; acumula exitos y fallos.
  validate  -> si hubo fallos, lo marca para que se dispare la alerta por correo.
  load      -> arma el resumen de la corrida (descargados / fallidos).

Se programa en el Programador de Tareas TODOS los dias a las 04:00.

Ejecutable:  python -m procesos.robot_precia.process [flags]
"""

from __future__ import annotations

import argparse
import socket
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from core.contract import (
    Proceso,
    ProcesoSkip,
    ProcessContext,
    ProcessResult,
    RunStatus,
    ValidacionError,
)
from core.run_store import RunStore
from core.runner import ejecutar
from procesos.robot_precia.config_robot import (
    ConfigRobot,
    Insumo,
    cargar_config,
    cargar_insumos,
)
from procesos.robot_precia.fechas import fechas_objetivo, render_nombre
from procesos.robot_precia.navegador import NavegadorError, crear_navegador

RUTA_CONFIG = Path(__file__).parent / "config.yaml"
RUTA_INSUMOS = Path(__file__).parent / "insumos.yaml"


class RobotPrecia(Proceso):
    process_id = "robot_precia"
    process_version = "0.1.0"

    def __init__(self, cfg: ConfigRobot, insumos: list[Insumo]) -> None:
        self.cfg = cfg
        self.insumos = insumos
        # MailClient para las ALERTAS ante fallo (lo usa el runner). En la
        # oficina es Outlook COM; el remitente es el owner.
        from core.adapters.mail_factory import crear_emisor
        self.mail = crear_emisor(cfg.backend_correo_activo, cfg.entorno,
                                 remitente=cfg.alertas.owner)

    def _sincronizar_logger(self, ctx: ProcessContext) -> None:
        if hasattr(self.mail, "logger"):
            self.mail.logger = ctx.logger

    # ------------------------------------------------------------------ EXTRACT
    def extract(self, ctx: ProcessContext) -> dict[str, Any]:
        self._sincronizar_logger(ctx)
        hoy: date = ctx.extra.get("fecha_override") or date.today()
        if ctx.extra.get("fechas_forzadas"):
            fechas = ctx.extra["fechas_forzadas"]
        else:
            fechas = fechas_objetivo(hoy)
            if hoy.weekday() == 0 and not self.cfg.fecha.lunes_incluye_fin_de_semana:
                fechas = [hoy - timedelta(days=1)]

        # Filtro opcional (--solo): limita a insumos cuya area/categoria/prefijo
        # contengan el texto, para probar una seccion aislada.
        solo = (ctx.extra.get("solo") or "").lower()
        insumos = self.insumos
        if solo:
            insumos = [i for i in insumos
                       if solo in i.area.lower() or solo in i.categoria.lower()
                       or solo in i.prefijo.lower()]
            ctx.logger.info("filtro_solo", extra={"solo": solo, "insumos": len(insumos)})

        # Plan: (insumo, fecha) por cada combinacion.
        plan = [(ins, f) for f in fechas for ins in insumos]

        # MODO RESPALDO (maquina de las 5 a.m.): antes de abrir el navegador,
        # revisa la ruta de destino. Si la maquina primaria (4 a.m.) ya bajo TODO,
        # se salta sin abrir Selenium. Si falta algo, deja en el plan SOLO lo que
        # falta (la idempotencia igual evita duplicados).
        if ctx.extra.get("respaldo"):
            presentes = [(i, f) for (i, f) in plan if self._ya_en_disco(i, f)]
            faltantes = [(i, f) for (i, f) in plan if (i, f) not in presentes]
            ctx.logger.info(
                "respaldo_revision",
                extra={"total": len(plan), "presentes": len(presentes),
                       "faltantes": len(faltantes),
                       "muestra_faltantes": [i.prefijo for i, _ in faltantes[:10]]},
            )
            if not faltantes:
                # Nada que hacer: avisar (breve) y saltar sin tocar el portal.
                self._reportar(ctx, descargados=[], fallidos=[], fechas=fechas,
                               modo_respaldo=True)
                raise ProcesoSkip(
                    "Respaldo: la maquina primaria ya descargo los "
                    f"{len(presentes)} insumos. No hay nada que hacer.")
            plan = faltantes  # solo re-intentar lo que falta

        ctx.logger.info(
            "plan_construido",
            extra={"hoy": str(hoy), "fechas": [str(f) for f in fechas],
                   "insumos": len(self.insumos), "descargas": len(plan)},
        )
        return {"hoy": hoy, "fechas": fechas, "plan": plan}

    def _ya_en_disco(self, insumo: Insumo, fecha: date) -> bool:
        """True si ya existe en la carpeta un archivo de ese insumo/fecha.

        Mismo criterio que la idempotencia del navegador: un archivo cuenta si su
        nombre EMPIEZA por el nombre renderizado (prefijo + fecha)."""
        carpeta = self.cfg.carpeta_destino
        if not carpeta.exists():
            return False
        objetivo = render_nombre(insumo.patron, fecha)
        for p in carpeta.iterdir():
            if (p.is_file() and p.name.startswith(objetivo)
                    and not p.name.endswith((".crdownload", ".tmp", ".part"))):
                return True
        return False

    def _reportar(self, ctx: ProcessContext, *, descargados, fallidos, fechas,
                  error_global: str | None = None, modo_respaldo: bool = False) -> None:
        """Envia el correo de reporte (descargados + fallidos). Nunca lanza."""
        try:
            from core.notifications import reportar_resumen_descargas
            reportar_resumen_descargas(
                self.cfg, self.mail, ctx.logger,
                descargados=descargados, fallidos=fallidos, fechas=fechas,
                hostname=socket.gethostname(), error_global=error_global,
                modo_respaldo=modo_respaldo,
            )
        except Exception:  # noqa: BLE001 - el reporte no debe romper la corrida
            ctx.logger.exception("reporte_error")

    # ---------------------------------------------------------------- TRANSFORM
    def transform(self, ctx: ProcessContext, data: dict[str, Any]) -> dict[str, Any]:
        plan = data["plan"]
        descargados: list[dict[str, str]] = []
        fallidos: list[dict[str, str]] = []
        error_global: Exception | None = None

        nav = crear_navegador(self.cfg, ctx.logger)
        try:
            nav.abrir()
            for insumo, fecha in plan:
                nombre = render_nombre(insumo.patron, fecha)
                if ctx.dry_run:
                    ctx.logger.info("dry_run_descarga",
                                    extra={"insumo": insumo.prefijo, "fecha": str(fecha),
                                           "archivo": nombre})
                    continue
                try:
                    ruta = nav.descargar(insumo, fecha)
                    descargados.append({"insumo": insumo.prefijo, "fecha": str(fecha),
                                        "archivo": Path(ruta).name})
                except Exception as e:  # noqa: BLE001 - un insumo no debe tumbar los demas
                    ctx.logger.error("insumo_fallido",
                                     extra={"insumo": insumo.prefijo, "fecha": str(fecha),
                                            "categoria": insumo.categoria, "error": str(e)})
                    fallidos.append({"insumo": insumo.prefijo, "fecha": str(fecha),
                                     "categoria": insumo.categoria, "error": str(e)[:200]})
        except Exception as e:  # noqa: BLE001 - fallo global (login, driver, ...)
            error_global = e
            ctx.logger.exception("transform_error_global")
        finally:
            nav.cerrar()

        data.update({"descargados": descargados, "fallidos": fallidos})
        ctx.logger.info("descarga_resumen",
                        extra={"descargados": len(descargados), "fallidos": len(fallidos),
                               "error_global": str(error_global) if error_global else None})

        # Correo de reporte SIEMPRE (exito o fallo), con ambas listas. Se envia
        # aqui (no en load) para que tambien salga cuando validate marca fallo.
        if not ctx.dry_run:
            self._reportar(ctx, descargados=descargados, fallidos=fallidos,
                           fechas=data["fechas"],
                           error_global=str(error_global) if error_global else None)

        # Si hubo fallo global (no pudo ni empezar), propagar -> FAILED.
        if error_global is not None:
            raise error_global
        return data

    # ----------------------------------------------------------------- VALIDATE
    def validate(self, ctx: ProcessContext, data: dict[str, Any]) -> bool:
        fallidos = data.get("fallidos", [])
        if fallidos:
            # Resumen para la alerta (primeros 15 fallos).
            detalle = "; ".join(
                f"{x['insumo']} ({x['fecha']}): {x['error']}" for x in fallidos[:15]
            )
            raise ValidacionError(
                f"{len(fallidos)} de {len(data['plan'])} descargas fallaron. {detalle}"
            )
        return True

    # --------------------------------------------------------------------- LOAD
    def load(self, ctx: ProcessContext, data: dict[str, Any]) -> ProcessResult:
        return ProcessResult(
            run_id=ctx.run_id, process_id=self.process_id,
            process_version=self.process_version, status=RunStatus.SUCCESS,
            filas=len(data.get("descargados", [])),
            outputs={"carpeta": str(self.cfg.carpeta_destino),
                     "descargados": data.get("descargados", [])},
            metrics={"fechas": [str(f) for f in data["fechas"]],
                     "total_plan": len(data["plan"]),
                     "descargados": len(data.get("descargados", [])),
                     "entorno": self.cfg.entorno},
            mensaje=f"{len(data.get('descargados', []))} insumos descargados.",
            trigger=ctx.trigger, disparado_por=ctx.disparado_por,
        )


# ============================================================ FABRICA / CLI ===

def construir_proceso(cfg: ConfigRobot) -> RobotPrecia:
    insumos = cargar_insumos(RUTA_INSUMOS)
    return RobotPrecia(cfg, insumos)


def _parse_fecha(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Robot Precia - descarga de insumos")
    p.add_argument("--entorno", choices=["test", "prod"])
    p.add_argument("--plan", action="store_true",
                   help="Solo muestra QUE se descargaria (no toca el portal)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--portal", choices=["simulado", "selenium"],
                   help="Sobreescribe el backend del portal")
    p.add_argument("--headed", action="store_true", help="Navegador con ventana")
    p.add_argument("--fecha", type=_parse_fecha,
                   help="Forzar 'hoy' (YYYY-MM-DD) para el calculo de fechas")
    p.add_argument("--solo", help="Filtrar insumos por area/categoria/prefijo "
                   "(p.ej. --solo \"Renta Fija\") para probar una seccion aislada")
    p.add_argument("--respaldo", action="store_true",
                   help="Modo respaldo (maquina de las 5 a.m.): si la ruta ya "
                        "tiene todos los insumos, se salta; si falta algo, solo "
                        "descarga lo que falta.")
    p.add_argument("--config", type=Path, default=RUTA_CONFIG)
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    cfg = cargar_config(args.config)
    if args.entorno:
        cfg.entorno = args.entorno
    if args.portal:
        cfg.backend_portal[cfg.entorno] = args.portal
    if args.headed:
        cfg.portal.headless = False

    proceso = construir_proceso(cfg)

    # --plan: listar el plan sin descargar nada (util para revisar la matriz).
    if args.plan:
        hoy = args.fecha or date.today()
        fechas = fechas_objetivo(hoy)
        solo = (args.solo or "").lower()
        insumos = [i for i in proceso.insumos
                   if not solo or solo in i.area.lower() or solo in i.categoria.lower()
                   or solo in i.prefijo.lower()]
        print(f"HOY: {hoy} ({hoy.strftime('%A')}) | fechas objetivo: "
              f"{', '.join(str(f) for f in fechas)}")
        print(f"Insumos{(' (filtro=' + args.solo + ')') if args.solo else ''}: "
              f"{len(insumos)} | descargas totales: {len(insumos) * len(fechas)}")
        print("-" * 70)
        for f in fechas:
            for ins in insumos:
                print(f"  [{f}] {ins.categoria:32.32} -> {render_nombre(ins.patron, f)}"
                      f"{('  (filtro=' + ins.filtro + ')') if ins.filtro else ''}")
        return 0

    extra = {}
    if args.fecha:
        extra["fecha_override"] = args.fecha
    if args.solo:
        extra["solo"] = args.solo
    if args.respaldo:
        extra["respaldo"] = True

    # notificar_fallo=False: el propio proceso envia UN correo de reporte
    # (descargados + fallidos) al final del transform, asi que no delegamos la
    # alerta generica al runner (evita correos duplicados).
    res = ejecutar(
        proceso, cfg, trigger="cli", disparado_por="cli",
        dry_run=args.dry_run, store=RunStore(), extra=extra,
        notificar_fallo=False,
    )
    print(f"STATUS: {res.status.value} | {res.mensaje}")
    return 0 if res.status in (RunStatus.SUCCESS, RunStatus.SKIPPED) else 1


if __name__ == "__main__":
    raise SystemExit(main())
