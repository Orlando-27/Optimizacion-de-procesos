# ▶ Continuar en el PC de la oficina

Guía de handoff para retomar el proyecto en el equipo corporativo (con el
**Outlook de escritorio de `jbobadilla@colfondos.com.co`**). Migra toda la
carpeta (el `.zip`) y sigue estos pasos.

---

## 1. Estado actual (qué está hecho y probado)

| Componente | Estado |
|---|---|
| Núcleo (contrato, config, logging, run_store, runner, validaciones) | ✅ Probado (32 tests) |
| Parser de ventanas del correo | ✅ Probado |
| Orquestación (polling, idempotencia, día hábil, SLA) | ✅ Probado |
| **Portal Precia: login + navegación + descarga real** | ✅ **Probado** (descargó `SX072426.001`, 82 MB) |
| Envío de correo — adaptador Outlook COM | ✅ Código listo · ⏳ **falta probarlo en la oficina** |
| **Paso 5: macro → Python** | ⏳ **Pendiente** (lo integras al final) |

> **Único desarrollo que falta: el PASO 5** (migrar la macro). Todo lo demás está
> construido; en la oficina solo hay que **probar el correo por Outlook** y luego
> hacer una **corrida completa real**.

---

## 2. Montaje en el PC de la oficina

```bat
:: 1) Descomprimir el .zip y entrar a la carpeta
cd C:\ruta\donde\descomprimiste\motor-procesos

:: 2) Entorno (Anaconda Prompt)
conda create -n motor python=3.12 -y
conda activate motor
pip install -e ".[windows,macro]"     :: incluye pywin32 (Outlook COM) + oletools

:: 3) Secretos
copy .env.example .env
notepad .env
```
En el `.env` rellena las credenciales del **portal**:
```
PRECIA_USUARIO=...
PRECIA_CLAVE=...
```
(El correo por Outlook COM **no necesita** clave en `.env`: usa la sesión de
Outlook ya abierta con la cuenta de jbobadilla.)

```bat
:: 4) Verificar
python scripts\verificar_entorno.py --entorno test
pytest -q
```

---

## 3. Configuración ya dejada para la oficina (`procesos\impugnacion_rfl\config.yaml`)

- `backend_correo.test` y `.prod` = **`outlook_com`** → envía desde el Outlook de escritorio.
- `correo_salida.remitente` = **`jbobadilla@colfondos.com.co`** (fuerza la cuenta).
- `correo_salida.destinatarios.test` = **`[jbobadilla@colfondos.com.co]`** (te lo envías a ti para probar).
- `backend_portal.prod` = `selenium` (descarga real). En `test` queda `simulado`; para descarga real usa el flag `--portal selenium`.
- `excel.motor` = `placeholder` (hasta terminar el paso 5; luego → `python`).

> Nota Outlook: en `test`, el correo queda como **BORRADOR** en Outlook (no se
> envía). Ábrelo en la carpeta *Borradores* para verificar asunto/adjunto/horarios.
> Para envío real, se usa `entorno: prod`.

---

## 4. Lo que falta probar en la oficina (en orden)

### 4.1 Correo por Outlook (PASO C)
Con Outlook abierto y la cuenta de jbobadilla activa:
```bat
copy procesos\impugnacion_rfl\tests\fixtures\correo_precia_ejemplo.txt correo.txt
python -m procesos.impugnacion_rfl.process --entorno test --paso 7 --simular-correo correo.txt
```
✅ Debe quedar un **borrador en Outlook** con el `Renta Fija.xlsx` (placeholder)
adjunto y los horarios. (En este `--paso 7`, la descarga usa el portal simulado;
para probar TODO real, ver 4.2.)

### 4.2 Corrida COMPLETA real en test (portal real + Outlook)
```bat
del logs\runs.db   :: opcional, por si ya hubo un SUCCESS hoy
python -m procesos.impugnacion_rfl.process --entorno test --portal selenium --headed --fecha AAAA-MM-DD
```
(usar un **día hábil con archivos publicados**). Hace: detecta correo (simulado)
→ descarga real `SX...001` en `sandbox\INFOVALMER` → genera `Renta Fija.xlsx`
placeholder → deja el correo en Borradores de Outlook.

### 4.3 Paso 5 — migrar la macro (ver `procesos\impugnacion_rfl\PENDIENTE_PASO_5.md`)
```bat
python scripts\inspeccionar_macro.py "M:\...\Impugnacion\Informacion Impugnacion.xlsm" --volcar-vba macro.vba
```
Luego se reimplementa la lógica en `TransformadorImpugnacionPython` y se cambia
`config.yaml → excel.motor: python`.

### 4.4 Paso a producción
- `config.yaml`: `entorno: prod`, **rutas UNC reales** (no `M:`), lista real de destinatarios.
- Programar con el Programador de Tareas (`schtasks`, ver `README.md`).
- Recordatorio: la descarga hoy corre **con ventana** (`--headed`); para tarea
  100% desatendida hay que afinar el modo headless (pendiente menor del portal).

---

## 5. Notas y pendientes conocidos

- **Headless del portal:** la descarga se probó con ventana (`--headed`). El modo
  headless falló en la app JSF; queda por afinar para ejecución sin sesión/GCP.
- **Extensión del archivo:** el plano se descarga como `SX{MMDDYY}.001` (~40–80 MB).
- **UNC real de `M:`:** obtener con `net use` y ponerlo en `config.yaml` (prod).
- **Destinatarios reales:** confirmar los correos exactos (hoy son tentativos).
- **Firma del correo:** revisar `plantillas\cuerpo_correo.html`.

Todo lo pendiente está marcado con `TODO`/`PENDIENTE` en el código y la config.
