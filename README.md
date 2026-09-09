# Robot Precia — Descarga diaria de insumos

Robot de **web scraping (Selenium)** que descarga los insumos del portal de
**Precia** todos los días de forma desatendida (Programador de Tareas de Windows).

Está construido sobre un **contrato común** (`extract → transform → load →
validate`) con registro de corridas, reintentos, idempotencia y alertas por
correo. Diseñado para Windows pero **portable a GCP** (todo el I/O específico
—portal, correo, almacenamiento— está detrás de adaptadores intercambiables).

> Proceso: [`procesos/robot_precia/DOCUMENTACION.md`](procesos/robot_precia/DOCUMENTACION.md)
> · Puesta en marcha en 2 máquinas: [`PROGRAMADOR_DE_TAREAS.md`](procesos/robot_precia/PROGRAMADOR_DE_TAREAS.md)

---

## Estructura

```
core/                 ← motor genérico, reutilizable
├── contract.py       ← Proceso(ABC), ProcessContext/Result, RunStatus, run()
├── config.py         ← carga config.yaml + .env (pydantic)
├── secrets.py        ← keyring (Windows Credential Manager) → .env
├── logging_config.py ← logs JSON con run_id/process_id + enmascarado de secretos
├── run_store.py      ← registro de corridas (SQLite, listo para BigQuery)
├── runner.py         ← ejecuta un proceso, persiste y notifica
├── notifications.py  ← correo de reporte (descargados/fallidos) y alertas
└── adapters/         ← MailClient / Storage / Portal (+ implementaciones)

procesos/robot_precia/      ← el robot (ver su DOCUMENTACION.md)
├── process.py        ← contrato ETL + CLI
├── navegador.py      ← navegación/descarga (3 flujos: directo/agrupador/consulta)
├── portal_precia.py  ← login/driver/datepicker/espera de descarga (Selenium)
├── secciones.py      ← mapa de áreas/secciones del portal
├── insumos.yaml      ← catálogo de insumos a descargar
├── fechas.py         ← lógica t-1 (+ fin de semana los lunes)
├── parametros.yaml   ← ⭐ RUTAS y CORREOS reales (lo edita el usuario)
└── config.yaml       ← ajustes técnicos (backends, timeouts)

scripts/                    ← explorar_robot / explorar_portal (mapear/depurar)
run_robot_precia.bat        ← entrypoint máquina PRIMARIA (04:00)
run_robot_precia_respaldo.bat ← entrypoint máquina RESPALDO (05:00, --respaldo)
```

---

## Instalación

```bash
# Con Anaconda (recomendado en la oficina)
conda create -n motor2 python=3.12 -y
conda activate motor2
pip install -e .            # o: pip install -e ".[dev]" para correr tests
```

Credenciales del portal en un archivo `.env` (o Windows Credential Manager):

```
PRECIA_USUARIO=tu_usuario
PRECIA_CLAVE=tu_clave
```

---

## Uso

```bash
# Ver el plan (qué se descargaría) sin tocar el portal
python -m procesos.robot_precia.process --plan --fecha 2026-09-09

# Corrida real (entorno se toma de config.yaml; --headed = con ventana)
python -m procesos.robot_precia.process --entorno test --portal selenium --headed

# Solo una sección (para probar aislado)
python -m procesos.robot_precia.process --solo "Clientes Derivados" --headed

# Modo respaldo (máquina de las 5 a.m.): baja solo lo que falte
python -m procesos.robot_precia.process --respaldo
```

Diagnóstico opcional: `set ROBOT_DUMP_FILAS=1` hace que el log liste los nombres
reales de las filas de cada tabla (útil para mapear un área nueva o depurar).

---

## Producción

1. **`parametros.yaml`** (único archivo que editas): `entorno: prod`, la
   `carpeta_destino.prod` (carpeta de red compartida) y los `receptores.prod`
   (correos reales). El remitente ya es el buzón de Outlook.
2. `.env` con las credenciales del portal en cada máquina.
3. Crear las tareas del Programador siguiendo
   [`PROGRAMADOR_DE_TAREAS.md`](procesos/robot_precia/PROGRAMADOR_DE_TAREAS.md)
   (primaria 04:00 + respaldo 05:00, ambas apuntando a la misma carpeta).

## Tests

```bash
python -m pytest -q
```
