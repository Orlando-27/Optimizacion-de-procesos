# Proceso 001 — `impugnacion_rfl` (Impugnación de Precios · Renta Fija Local)

Documentación detallada de **qué hace** este proceso, **cómo está construido** y
**qué queda pendiente** (paso 5). Es el primer proceso del *Motor de Optimización
de Procesos*.

> **Estado actual:** ✅ Estructura completa y funcionando end-to-end en modo `test`.
> ⏳ **Único pendiente: PASO 5** (migrar la lógica de la macro a Python). Ver
> [`PENDIENTE_PASO_5.md`](./PENDIENTE_PASO_5.md).

---

## 1. Qué automatiza

Reemplaza el proceso manual que hoy se hace cada tarde: detectar el correo de
Precia, entrar al portal, descargar el archivo de valoración, correr la macro de
impugnación y enviar el resultado por correo **dentro de una ventana de tiempo
muy corta**. Si los precios tienen error y no se reporta a tiempo, quedan en firme.

### Las 7 etapas del proceso manual

| # | Paso manual | Estado |
|---|---|---|
| 1 | Llega el correo detonante de Precia (`atencionalcliente@precia.co`, asunto *Publicación Renta Fija Local*), con las **ventanas de impugnación del día** en el cuerpo | ✅ |
| 2 | Login al portal `www.precia.co` (WordPress) | ✅ (código listo, faltan selectores reales) |
| 3 | Descargar el archivo `SXMMDDYY` (Servicios → Renta Fija → Área de clientes → Archivos RFL → fecha) | ✅ (código listo, faltan selectores reales) |
| 4 | Guardar el archivo en la carpeta **INFOVALMER** | ✅ |
| 5 | **Correr la macro** `Informacion Impugnacion.xlsm` sobre el archivo | ⏳ **PENDIENTE** |
| 6 | La macro genera `Renta Fija.xlsx` | ⏳ (depende del paso 5) |
| 7 | Enviar el correo con `Renta Fija.xlsx` adjunto y los horarios reinyectados | ✅ |

---

## 2. Mapeo al contrato ETL

El proceso hereda de `core.contract.Proceso` e implementa cuatro métodos. El
método `run()` (plantilla, no se sobreescribe) los orquesta, mide duración y
captura errores en un `ProcessResult` homogéneo.

```
extract()   → pasos 1-3:  día hábil → detectar correo (polling) → parsear
                          ventanas → login + descarga del portal
transform() → pasos 4-6:  copiar a INFOVALMER → generar Renta Fija.xlsx
                          (PASO 5: hoy placeholder) → confirmar salida
validate()  → sección 6:  los 7 chequeos obligatorios
load()      → paso 7:     componer y enviar el correo + archivar copia fechada
```

---

## 3. Arquitectura (por qué está partido así)

**Regla de oro:** el proceso depende de **interfaces**, no de tecnologías
concretas. Cambiar de Windows a GCP = cambiar el adaptador que se inyecta, sin
tocar la lógica. Por eso hay tres backends por pieza:

| Pieza | Interfaz | `test` (aquí, Linux) | `prod` portable | `prod` Windows |
|---|---|---|---|---|
| **Correo** | `MailClient` | `MailSimulado` (offline, escribe `.eml`) | `MailSmtpImap` (IMAP+SMTP) | `MailOutlookCom` (COM) |
| **Portal** | `PortalRFL` | `PortalSimulado` (fixture) | `PortalPreciaSelenium` | ídem |
| **Macro** | `TransformadorImpugnacion` | `TransformadorPlaceholder` | `TransformadorImpugnacionPython` ⏳ | `ExcelRunner` (COM, fallback) |
| **Storage** | `Storage` | `StorageLocal` (sandbox) | `StorageLocal` (UNC) | ídem |

El backend se elige en `config.yaml` (`backend_correo`, `backend_portal`,
`excel.motor`) según el entorno activo.

### Archivos del proceso

```
procesos/impugnacion_rfl/
├── process.py               ← clase ImpugnacionRFL + fábrica de adaptadores + CLI
├── parser_correo.py         ← extrae las 4 ventanas del cuerpo (tolerante)
├── portal_precia.py         ← descarga Selenium + PortalSimulado (SELECTORES A VERIFICAR)
├── transform_impugnacion.py ← PASO 5: placeholder + hueco para la macro migrada
├── validacion.py            ← los 7 chequeos de la sección 6
├── config.yaml              ← toda la parametrización (test/prod)
├── manifest.yaml            ← metadatos del proceso
├── plantillas/
│   └── cuerpo_correo.html   ← correo de salida con firma y horarios {…}
├── tests/                   ← 32 tests (parser + validaciones)
└── DOCUMENTACION.md         ← este archivo
```

El núcleo genérico reutilizable vive en `core/` (contrato, config, logging,
run_store, runner, secrets, notifications, adapters).

---

## 4. Cómo se ejecuta

```bash
# Diagnóstico previo (dependencias, rutas, credenciales)
python scripts/verificar_entorno.py --entorno test

# Corrida completa end-to-end en test (no toca prod, deja el correo como borrador)
python -m procesos.impugnacion_rfl.process --entorno test

# Flags de depuración
python -m procesos.impugnacion_rfl.process --dry-run              # corre pero no envía/escribe
python -m procesos.impugnacion_rfl.process --paso 1               # solo detecta correo + parsea
python -m procesos.impugnacion_rfl.process --paso 3               # hasta la descarga
python -m procesos.impugnacion_rfl.process --simular-correo cuerpo.txt   # usa un cuerpo guardado
```

En `test`, el proceso:
- usa `./sandbox/INFOVALMER` y `./sandbox/Impugnacion` (no las rutas de red);
- lee el correo simulado del fixture (no espera a las 4pm);
- genera un `Renta Fija.xlsx` **placeholder**;
- **no envía**: deja el `.eml` en `./sandbox/borradores/`;
- solo permite el destinatario de prueba `joseorlando202014@gmail.com`.

---

## 5. Validaciones obligatorias (sección 6)

Nada se envía sin pasar estos chequeos (`validacion.py`). Si alguno falla →
`VALIDATION_FAILED` + alerta, y **no** se envía.

1. **Día hábil** — fin de semana o festivo CO (`holidays.CO`) → `SKIPPED` sin alertar.
2. **Correo detonante** — recibido hoy, del remitente esperado.
3. **Archivo descargado** — existe, tamaño > umbral, nombre corresponde a la fecha.
4. **Macro** — termina sin excepción (hoy: placeholder).
5. **Salida** — `Renta Fija.xlsx` existe, es de **esta** corrida (mtime), tam > 0, abre con `openpyxl`.
6. **SLA** — compara la hora actual con `tes_st_fin`. Si ya pasó → `sla_cumplido=False`, envía igual pero con **alerta destacada** y prefijo `[SLA VENCIDO]`.
7. **Antes de enviar** — el adjunto existe y los destinatarios corresponden al entorno (no mandar a la lista real estando en `test`).

---

## 6. Orquestación temporal (sección 7)

- El `.bat` se programa **una vez** a las 15:45 (L-V) y el proceso hace *polling*
  de Outlook cada `intervalo_poll_seg` (60s) hasta `hora_limite_espera` (16:20).
- Al detectar el correo, arranca el pipeline (objetivo < 5 min).
- Si a las 16:20 no llegó → alerta + `FAILED`.
- **Reintentos:** hasta 2 con backoff en pasos de red (login/descarga). La macro
  y el envío **no se reintentan** (riesgo de duplicar el correo).
- **Idempotencia:** si ya hubo un `SUCCESS` hoy → `SKIPPED` (evita doble envío).

---

## 7. Registro de corridas

Cada corrida se persiste en `logs/runs.db` (SQLite) con el esquema exacto que
irá a BigQuery: `run_id, process_id, process_version, trigger, status, inicio,
fin, duracion_seg, filas, sla_cumplido, outputs, metrics, mensaje, traceback,
disparado_por`. Consultable con `RunStore.consultar_recientes(limite)` — base
del dashboard futuro sin cambios.

---

## 8. Lo que queda PENDIENTE

### ⏳ PASO 5 — migrar la macro a Python (único desarrollo restante)
Detalle completo en [`PENDIENTE_PASO_5.md`](./PENDIENTE_PASO_5.md). En resumen:
falta inspeccionar `Informacion Impugnacion.xlsm`, entender qué lee y cómo arma
`Renta Fija.xlsx`, y reimplementarlo en `TransformadorImpugnacionPython`.

### Otros puntos parametrizados (no bloquean test, sí prod)
- **Selectores reales del portal** — capturar con `scripts/explorar_portal.py` y
  pegarlos en `portal_precia.py` (bloque `SELECTORES A VERIFICAR`).
- **Nombre/extensión exactos del archivo `SXMMDDYY`** — confirmar al descargar.
- **Ruta UNC real** que corresponde a `M:` — reemplazar `SERVIDOR` en `config.yaml`.
- **Lista real de destinatarios/CC** — confirmar los correos en `config.yaml`.
- **Firma corporativa** — validar la de `plantillas/cuerpo_correo.html`.
- **Credenciales** — cargar `PRECIA_*` y `SMTP_*` en `.env` o Windows Credential Manager.

Todos están marcados como `TODO`/`<PENDIENTE_...>` en el código y la config; no se
adivinó ninguno.
