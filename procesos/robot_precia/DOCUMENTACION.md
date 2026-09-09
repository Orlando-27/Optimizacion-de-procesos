# Proceso 002 — `robot_precia` (Descarga diaria de insumos de Precia)

Robot de **web scraping con Selenium** que descarga ~43 insumos del portal de
Precia todos los días a las **04:00** (Programador de Tareas). Reutiliza el
motor (`core/`) y el **login del portal ya probado** en `impugnacion_rfl`.

> **Estado: COMPLETO — 44/44 insumos descargados y validados en real** (portal
> de Precia, en el equipo de la oficina). Las 4 áreas quedan cableadas y probadas:
> - ✅ **Renta Fija** Local (`#arlo`) + Internacional (`#arin`) — flujo *directo*
>   (calendario inline + tabla). 12 insumos.
> - ✅ **Derivados** (`#descagrup`) — flujo *agrupador* (grupo + fecha popup +
>   Buscar + tabla, empate por prefijo con `contains`). 24 insumos.
> - ✅ **Renta Variable** (`#arcval` / `#arcvalin`) — flujo *directo*. 4 insumos.
> - ✅ **Productos Estructurados** (`#conpro`) — flujo *consulta* (fecha popup +
>   tabla, sin botón Buscar; con **reintento con recarga** para descargas flaky
>   como `800149496_Colf_NE`). 4 insumos.
>
> Idempotencia (no re-descarga lo ya bajado), fechas t‑1 (+ fin de semana los
> lunes), y **alerta por correo** ante fallos, funcionando.
>
> **Nota:** la curva *TES B en Pesos* ("Histórico betas", `#hisbe`) NO es un
> archivo descargable (es una tabla en pantalla); ese dato ya viene dentro de
> los archivos de valoración de Renta Fija (`SB…`), por eso no se lista aparte.

---

## 1. Qué hace

Descarga insumos de distintas secciones del portal (ver `insumos.yaml`), para la
**fecha t‑1** (día anterior). **Los lunes** descarga **todo el fin de semana**
(sábado y domingo). Guarda todo en una **ruta única** de destino.

- Corre a las 4 a.m. porque a esa hora los insumos de **ayer** ya están publicados.
- El nombre de cada archivo lleva la fecha (`MMDDYY`, `DDMMYY` o `YYYY_MM_DD`).
- Cada insumo se ubica por **prefijo** dentro de su tabla (tras seleccionar la
  fecha, la tabla solo muestra esa fecha).

## 2. Mapeo al contrato ETL

```
extract   -> planifica: fechas objetivo (t-1; lunes = fin de semana) x insumos
transform -> descarga cada insumo con Selenium y lo guarda en la ruta destino
validate  -> si hubo fallos -> alerta por correo a alertas.destinatarios
load      -> resumen (descargados / fallidos)
```

## 3. Archivos del proceso

```
procesos/robot_precia/
├── process.py         ← RobotPrecia(Proceso): planifica, descarga, resume + CLI
├── navegador.py       ← NavegadorSimulado (test) / NavegadorSelenium (real)
├── fechas.py          ← lógica t-1 / lunes=fin de semana + render de nombres
├── config_robot.py    ← modelo de config (pydantic) + carga de insumos
├── config.yaml        ← entorno, ruta única, fecha, backends, alertas
├── insumos.yaml       ← MANIFIESTO: los ~43 insumos (categoría, prefijo, ruta…)
├── manifest.yaml      ← metadatos del proceso
├── tests/             ← tests de fechas y del manifiesto
└── DOCUMENTACION.md   ← este archivo
```

## 4. Cómo se ejecuta

```bat
:: Ver QUÉ se descargaría (sin tocar el portal) — útil para revisar la matriz
python -m procesos.robot_precia.process --plan --fecha 2026-09-08
python -m procesos.robot_precia.process --plan --fecha 2026-09-07   :: lunes (fin de semana)

:: Corrida en test (navegador simulado: crea placeholders en la ruta destino)
python -m procesos.robot_precia.process --entorno test

:: Descarga REAL (cuando esté el Bloque 3), con ventana:
python -m procesos.robot_precia.process --entorno test --portal selenium --headed
```

## 5. Programar la tarea (todos los días 04:00)

```cmd
schtasks /Create ^
  /TN "Motor\robot_precia" ^
  /TR "\"C:\ruta\al\proyecto\run_robot_precia.bat\"" ^
  /SC DAILY ^
  /ST 04:00 ^
  /RU "DOMINIO\usuario" /RP * ^
  /RL HIGHEST /F
```
⚠️ Igual que impugnación: sesión no interactiva **no ve `M:`** → usar UNC; si la
descarga necesita ventana (headless falla en las apps JSF), la tarea debe correr
con sesión de usuario iniciada.

## 6. Lo que queda PENDIENTE (solo para producción)

El scraping de las 44 secciones YA está mapeado, cableado y probado en real.
Lo único que resta es la puesta en producción:

- **Ruta de destino real (prod):** hoy es `./sandbox/robot_precia` en `test`.
  Poner la ruta/UNC definitiva en `config.yaml` (`rutas.prod`).
- **Destinatarios reales de la alerta:** hoy son correos de prueba en
  `config.yaml` (`alertas.prod.destinatarios`). Reemplazar por los reales.
- **Backend de correo/portal en prod:** ya configurados (`outlook_com` /
  `selenium`); confirmar credenciales del portal en `.env` del equipo.
- **Programador de Tareas** a las 04:00 (Lun–Dom) con sesión de usuario
  iniciada (headed; las apps JSF fallan en headless). Ver `run_robot_precia.bat`.

> Diagnóstico opcional: la variable de entorno `ROBOT_DUMP_FILAS=1` hace que el
> robot registre en el log los nombres reales de las filas de cada tabla y el
> HTML del enlace de descarga. Útil para mapear un área nueva o depurar; se deja
> apagada en la corrida diaria.
