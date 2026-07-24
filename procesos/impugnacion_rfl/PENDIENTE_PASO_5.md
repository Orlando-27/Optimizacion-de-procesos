# ⏳ PENDIENTE — Paso 5: migrar la macro a Python

Este es **el único paso que queda por desarrollar**. Todo lo demás
(detección de correo, parseo de ventanas, descarga, guardado en INFOVALMER,
validaciones, envío del correo, registro de corridas) ya está construido y
corre end-to-end en modo `test`.

---

## Qué es el paso 5

En el proceso manual, tras descargar el archivo plano `SXMMDDYY` y guardarlo en
INFOVALMER, se abre `Informacion Impugnacion.xlsm` y se **corre una macro VBA**
que:

1. Lee el archivo recién descargado desde INFOVALMER.
2. Arma el reporte de impugnación (cálculos/comparaciones de precios).
3. Guarda el resultado como **`Renta Fija.xlsx`** en la carpeta `Impugnacion`.

**Decisión acordada:** en vez de ejecutar el VBA vía Excel COM (que ataría el
proceso a Windows + Excel de escritorio), se **reimplementa esa lógica en Python**
(`pandas`/`openpyxl`), para que corra portable en Linux/GCP.

---

## Estado en el código

En `transform_impugnacion.py` hay dos implementaciones de la interfaz
`TransformadorImpugnacion`:

| Clase | Qué hace | Uso |
|---|---|---|
| `TransformadorPlaceholder` | Genera un `Renta Fija.xlsx` **mínimo** marcado como PLACEHOLDER (no calcula la impugnación real) | Permite probar el resto del pipeline sin quedar bloqueados. **Activo hoy** (`config.yaml → excel.motor: placeholder`). |
| `TransformadorImpugnacionPython` | La reimplementación **real** de la macro | Hoy lanza `PasoPendienteError`. **Aquí va el trabajo restante.** |

Cuando el paso 5 esté listo, se cambia en `config.yaml`:
```yaml
excel:
  motor: "python"   # deja de usar el placeholder
```

---

## Qué se necesita para completarlo

1. **El archivo `Informacion Impugnacion.xlsm`.** Aún no está en este entorno.
   Súbelo y córrelo por:
   ```bash
   pip install oletools
   python scripts/inspeccionar_macro.py "ruta/Informacion Impugnacion.xlsm" --volcar-vba macro.vba
   ```
   Eso lista los `Sub`/`Function` (candidatos a `nombre_macro`) y vuelca el VBA
   completo para leer la lógica.

2. **Responder, leyendo el VBA:**
   - ¿Qué archivo de INFOVALMER lee? ¿nombre fijo, el más reciente, o `SXMMDDYY`?
   - ¿Qué hojas/rangos toma como entrada?
   - ¿Qué transformación aplica (fórmulas, filtros, comparaciones, umbrales)?
   - ¿Qué estructura tiene exactamente `Renta Fija.xlsx` de salida (hojas, columnas, formato)?

3. **Reimplementar en `TransformadorImpugnacionPython.generar_reporte()`** con
   `pandas`/`openpyxl`, tomando `archivo_entrada` (el plano en INFOVALMER) y
   escribiendo `Renta Fija.xlsx` en `carpeta_salida`.

4. **Validar** contra un `Renta Fija.xlsx` real de referencia (comparar celdas).

---

## Alternativa / fallback documentado

Si la lógica del VBA resulta demasiado costosa de traducir, se puede ejecutar el
VBA original vía Excel COM en Windows: existe la interfaz `ExcelRunner` y el
adaptador `excel_com.py` está previsto (`config.yaml → excel.motor: com`,
`nombre_macro: <el Sub confirmado>`). Esto ata prod a Windows, así que es el
plan B, no el preferido.

---

## Definición de "hecho" para el paso 5

- [ ] `Informacion Impugnacion.xlsm` inspeccionado; `nombre_macro` y lógica documentados.
- [ ] `TransformadorImpugnacionPython.generar_reporte()` implementado.
- [ ] `Renta Fija.xlsx` generado por Python coincide con el de la macro (test de referencia).
- [ ] `config.yaml → excel.motor: "python"`.
- [ ] Tests del transform agregados en `tests/`.
