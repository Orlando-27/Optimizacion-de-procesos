# Motor de Optimización de Procesos

Plataforma de automatización de procesos operativos. Cada proceso se escribe una
vez sobre un **contrato común** (`extract → transform → load → validate`) y se
ejecuta desatendido, con registro de corridas, validaciones y alertas.

**Proceso 001:** [`impugnacion_rfl`](procesos/impugnacion_rfl/DOCUMENTACION.md) —
Impugnación de Precios de Renta Fija Local.

> Diseñado para correr hoy en Windows (Programador de Tareas) pero **portable a
> GCP sin reescribir**: todo el I/O específico está detrás de adaptadores
> intercambiables (correo, portal, macro, storage).

---

## Estructura

```
core/                 ← genérico y reutilizable por procesos futuros
├── contract.py       ← Proceso(ABC), ProcessContext/Result, RunStatus, run()
├── config.py         ← carga config.yaml + .env (pydantic)
├── secrets.py        ← keyring (Windows Credential Manager) → .env
├── logging_config.py ← logs JSON con run_id/process_id + enmascarado de secretos
├── run_store.py      ← registro de corridas (SQLite, esquema listo para BigQuery)
├── runner.py         ← ejecuta un proceso, persiste y alerta
├── notifications.py  ← alerta al owner ante fallo
└── adapters/         ← MailClient / Storage / Transformador (+ implementaciones)

procesos/impugnacion_rfl/   ← ver procesos/impugnacion_rfl/DOCUMENTACION.md
scripts/                    ← verificar_entorno / inspeccionar_macro / explorar_portal
run_impugnacion.bat         ← entrypoint para el Programador de Tareas
```

---

## Instalación

```bash
# 1. Crear entorno virtual
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 2. Instalar
pip install -e .
# En el equipo Windows de producción, además:
pip install -e ".[windows,macro]"     # pywin32 (COM) + oletools (inspección VBA)

# 3. Configurar secretos
copy .env.example .env                 # (cp en Linux) y rellenar credenciales
```

---

## Uso

```bash
# Diagnóstico previo (¡correr esto primero!)
python scripts/verificar_entorno.py --entorno test

# Corrida completa en test (no toca producción, correo queda en borrador)
python -m procesos.impugnacion_rfl.process --entorno test

# Depuración
python -m procesos.impugnacion_rfl.process --dry-run
python -m procesos.impugnacion_rfl.process --paso 3
python -m procesos.impugnacion_rfl.process --simular-correo cuerpo.txt

# Tests
pytest -q
```

---

## Pasar de `test` a `prod`

Editar `procesos/impugnacion_rfl/config.yaml`:

1. `entorno: prod`
2. **Rutas UNC** en `rutas.prod` — reemplazar `SERVIDOR` por el host real
   (ver abajo). **Nunca usar `M:\`** (el Programador de Tareas en sesión no
   interactiva no ve las unidades mapeadas).
3. `backend_correo.prod` y `backend_portal.prod` (`smtp_imap`/`outlook_com`, `selenium`).
4. `correo_salida.destinatarios.prod` — confirmar la lista real.
5. `excel.motor: python` **(requiere completar el PASO 5)**.
6. Cargar credenciales reales en `.env` o Windows Credential Manager.

### Obtener el UNC real de `M:`
En el equipo, con `M:` mapeada:
```cmd
net use
```
Copiar la columna *Recurso remoto* (`\\servidor\share`) y componer las rutas UNC
completas en `config.yaml`.

---

## Programar la tarea (Windows)

El proceso se dispara **una vez** a las 15:45 y hace *polling* del correo hasta
las 16:20. Crear la tarea (L-V, corre aunque el usuario no haya iniciado sesión):

```cmd
schtasks /Create ^
  /TN "Motor\impugnacion_rfl" ^
  /TR "\"C:\ruta\al\proyecto\run_impugnacion.bat\"" ^
  /SC WEEKLY /D MON,TUE,WED,THU,FRI ^
  /ST 15:45 ^
  /RU "DOMINIO\usuario" /RP * ^
  /RL HIGHEST /F
```

⚠️ **Advertencias de sesión no interactiva:**
- Marcar *"Ejecutar aunque el usuario no haya iniciado sesión"* (implícito con `/RU`+`/RP`).
- Con esa opción, **las unidades mapeadas (`M:`) NO están disponibles** → usar UNC.
- Si se usa el backend `outlook_com`, Outlook debe poder abrirse en esa sesión
  (COM en sesión no interactiva es frágil; por eso el backend portable
  `smtp_imap` es el recomendado para desatendido).

---

## Qué revisar cuando algo falle

| Síntoma | Dónde mirar |
|---|---|
| ¿Qué pasó en la corrida? | `logs/impugnacion_YYYYMMDD.log` (stdout) y `logs/impugnacion_rfl_YYYYMMDD.jsonl` (estructurado) |
| Historial y estados | `logs/runs.db` → `RunStore.consultar_recientes()` (status, duración, traceback) |
| "No llegó el correo de Precia" | ¿llegó a Outlook? ¿remitente/asunto correctos en `config.yaml`? |
| Falla el login/descarga del portal | screenshot en `logs/` + selectores en `portal_precia.py` (¿capturados?) |
| `PASO PENDIENTE` / `PasoPendienteError` | el paso 5 aún no está migrado — ver `PENDIENTE_PASO_5.md` |
| Rutas UNC no accesibles en prod | sesión no interactiva no ve `M:`; validar UNC con `net use` |
| El correo se envió a quien no debía | revisar `entorno` y `destinatarios`; en `test` está bloqueado mandar a la lista de prod |

---

## Seguridad

- Ningún secreto en código, logs ni en el `.bat`. Se leen de `.env` o Windows
  Credential Manager; los logs enmascaran cualquier valor sensible.
- `.gitignore` excluye `.env`, `sandbox/`, `logs/`, `*.xlsx` y las bases `*.db`.

---

## Estado

- ✅ Núcleo (`core/`), parser, validaciones, orquestación, registro y envío: **funcionando en test**.
- ✅ 32 tests en verde (`pytest`).
- ⏳ **Pendiente: PASO 5** (migrar la macro a Python) — ver
  [`procesos/impugnacion_rfl/PENDIENTE_PASO_5.md`](procesos/impugnacion_rfl/PENDIENTE_PASO_5.md).
