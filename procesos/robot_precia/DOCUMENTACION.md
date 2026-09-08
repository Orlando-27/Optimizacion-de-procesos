# Proceso 002 — `robot_precia` (Descarga diaria de insumos de Precia)

Robot de **web scraping con Selenium** que descarga ~43 insumos del portal de
Precia todos los días a las **04:00** (Programador de Tareas). Reutiliza el
motor (`core/`) y el **login del portal ya probado** en `impugnacion_rfl`.

> **Estado:**
> - ✅ **Bloque 1:** estructura, manifiesto, lógica de fechas (tests), config,
>   ETL, alertas, modo `--plan`. Corre e2e en `test` (navegador simulado).
> - ✅ **Bloque 3 (framework):** descarga real **genérica** cableada en
>   `NavegadorSelenium` (navegar sección → fecha → filtro → paginación → ubicar
>   por prefijo → descargar), reutilizando el flujo RFL ya probado.
> - ✅ **Renta Fija Local** (pág. 2) y **Renta Fija Internacional** (`#arin`):
>   secciones **cableadas** (usan el área ya mapeada). Listas para probar real.
> - ⏳ **Bloque 2 (pendiente, requiere tu portal):** capturar los selectores de
>   `Renta Variable`, `Derivados` y `Productos Estructurados` con
>   `scripts/explorar_robot.py` y completarlos en `secciones.py`. Hasta entonces,
>   esas secciones fallan con `NavegadorError` explícito ("pendiente de mapear").

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

## 6. Lo que queda PENDIENTE (Bloques 2 y 3)

- **Mapear secciones nuevas** del portal: `Clientes Renta Variable`,
  `Clientes Derivados` (Descargar Archivo Agrupador → Insumos Locales / Swaps /
  Forward Internacionales / Otros Insumos), `Clientes Productos Estructurados`
  (Consulta de productos, Históricos Betas). Capturar selectores con
  `scripts/explorar_portal.py` (headed) — igual que se hizo con RFL.
- **Cablear la descarga** por sección en `NavegadorSelenium.descargar()`:
  entrar al iframe → seleccionar fecha → aplicar **filtro** (`FWD`/`SWAPCC`) →
  ir a la **página** indicada → ubicar la fila por **prefijo** → descargar.
- **Verificar el manifiesto** contra el Excel real: el `--plan` lista 45 filas;
  el Excel declara **43**. Revisar los ítems marcados `CONFIRMAR` en `insumos.yaml`
  (p. ej. los `SwapCC2_*_Colateral_USD` agregados por Teams, y el formato de
  fecha de los archivos `_Diaria_`).
- **Ruta UNC real** de destino (prod) y **destinatarios reales** de alerta.
