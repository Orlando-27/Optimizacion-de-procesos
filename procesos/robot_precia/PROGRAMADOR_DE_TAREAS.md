# Robot Precia — Programador de Tareas (2 máquinas: 04:00 + 05:00 respaldo)

Guía para dejar el robot corriendo solo, con **una máquina primaria a las 04:00**
y **una máquina de respaldo a las 05:00** que solo actúa si la primera falló.

---

## 0. Cómo funciona el respaldo (idea)

- **Máquina A (primaria, 04:00)** ejecuta `run_robot_precia.bat` y descarga los 44
  insumos a la **carpeta de destino**.
- **Máquina B (respaldo, 05:00)** ejecuta `run_robot_precia_respaldo.bat`
  (`--respaldo`). Antes de abrir el navegador **revisa esa misma carpeta**:
  - Si **está todo** → no hace nada (estado `SKIPPED`) y manda un correo
    `[RESPALDO] nada que hacer`.
  - Si **falta algo** (A se apagó, se reinició, o falló) → descarga **solo lo que
    falta**.

> **Requisito clave:** las dos máquinas deben apuntar a la **MISMA carpeta de
> destino** (una ruta de red compartida, p. ej. `\\servidor\insumos\precia`).
> Si cada una guarda en su disco local, el respaldo no puede "ver" lo que bajó la
> primaria. Configúrala en `config.yaml` → `rutas.prod`.

---

## 1. Requisitos en CADA máquina (A y B)

1. **Repo/carpeta** del proyecto copiada (p. ej. `C:\motor-procesos-v2`).
2. **Anaconda + entorno `motor2`** con las dependencias instaladas.
   - Si tu `python.exe` no está en `%USERPROFILE%\anaconda3\envs\motor2\`, edita
     la línea `set "PYEXE=..."` de los `.bat` con la ruta real.
3. **Credenciales del portal** en el archivo `.env` (usuario/clave de Precia).
4. **`config.yaml` en modo producción:** cambia arriba `entorno: prod` para que
   use la ruta real, el correo real (Outlook) y el navegador Selenium.
   - `rutas.prod` = la carpeta de red compartida.
   - `alertas.destinatarios.prod` = los correos que reciben el reporte.
5. **Chrome** instalado (Selenium Manager resuelve el driver solo).

> **Importante (navegador con ventana):** las páginas del portal (JSF) fallan en
> modo *headless*, así que la tarea **debe correr con el usuario conectado**
> (sesión iniciada). Lo más práctico es dejar la máquina con **inicio de sesión
> automático** y que no se cierre la sesión.

---

## 2. Crear la tarea — Máquina A (primaria, 04:00)

**Opción GUI (Programador de tareas):**

1. Abre **Programador de tareas** → **Crear tarea…** (no "tarea básica").
2. **General:**
   - Nombre: `Robot Precia - Primaria 04:00`.
   - Marca **"Ejecutar solo cuando el usuario haya iniciado sesión"**.
   - (Opcional) **"Ejecutar con los privilegios más altos"**.
3. **Desencadenadores** → **Nuevo…**:
   - Diariamente, hora **04:00**, "Repetir cada **1** día". Aceptar.
4. **Acciones** → **Nuevo…**:
   - Acción: *Iniciar un programa*.
   - Programa o script: `C:\motor-procesos-v2\run_robot_precia.bat`
   - **Iniciar en (opcional):** `C:\motor-procesos-v2`  ← (¡importante!)
5. **Condiciones:** desmarca "Iniciar la tarea solo si el equipo está con CA" si
   es un portátil que a veces está con batería.
6. **Configuración:** marca "Permitir ejecutar la tarea a petición" y
   "Si la tarea falla, reiniciarla cada: 5 minutos, hasta 2 veces".
7. Aceptar (pedirá la contraseña del usuario).

**Opción línea de comandos** (una sola línea, en CMD como administrador):

```
schtasks /Create /TN "Robot Precia - Primaria 04:00" /TR "C:\motor-procesos-v2\run_robot_precia.bat" /SC DAILY /ST 04:00 /RL HIGHEST /F
```

---

## 3. Crear la tarea — Máquina B (respaldo, 05:00)

Igual que la sección 2, pero:
- Nombre: `Robot Precia - Respaldo 05:00`.
- Hora del desencadenador: **05:00**.
- Acción → Programa: `C:\motor-procesos-v2\run_robot_precia_respaldo.bat`
  (este ya corre con `--respaldo`).

**Línea de comandos:**

```
schtasks /Create /TN "Robot Precia - Respaldo 05:00" /TR "C:\motor-procesos-v2\run_robot_precia_respaldo.bat" /SC DAILY /ST 05:00 /RL HIGHEST /F
```

> El desfase de 1 hora da margen de sobra: la corrida completa tarda ~15 min, así
> que a las 05:00 la primaria ya terminó (o ya se sabe que no corrió).

---

## 4. Probar sin esperar a la madrugada

- Ejecutar la tarea a demanda: Programador → clic derecho en la tarea →
  **Ejecutar**. O por consola:
  ```
  schtasks /Run /TN "Robot Precia - Primaria 04:00"
  ```
- Ver el log del día en `C:\motor-procesos-v2\logs\robot_precia_YYYYMMDD.log`.
- Prueba del respaldo: **borra 2 o 3 archivos** de la carpeta de destino y ejecuta
  la tarea de respaldo; debe bajar **solo esos** y mandar el correo de reporte.

---

## 5. Qué correo llega

Cada corrida envía **un** correo de reporte a `alertas.destinatarios` con:
- Asunto: `[OK] Robot Precia: N OK / M fallaron (NOMBRE-EQUIPO)` — o `[ALERTA] …`
  si hubo fallos, o `[RESPALDO] …` desde la máquina B.
- Dos listas: **✓ descargados** (insumo, fecha, archivo) y **✗ no descargados**
  (insumo, fecha, motivo).
- El **nombre del equipo** que lo envió, para distinguir A de B.

Así, un día normal recibirás: de A un `[OK] 44/0` (~04:15) y de B un
`[RESPALDO] nada que hacer` (~05:00). Si A no corrió, B mandará el `[OK]` con las
descargas que rescató.

---

## 6. Notas / solución de problemas

- **No abre Chrome / "no interactive session":** la sesión del usuario debe estar
  iniciada (ver nota de la sección 1). Configura inicio de sesión automático.
- **`python` no encontrado:** edita `set "PYEXE=..."` en los dos `.bat` con la
  ruta real al `python.exe` del entorno `motor2`.
- **El respaldo baja todo igual (no ve lo de la primaria):** las dos máquinas no
  están apuntando a la misma carpeta. Revisa `rutas.prod` en `config.yaml`.
- **Reintentos:** cada insumo se reintenta hasta 3 veces recargando la sección
  (resuelve descargas "flaky" como `800149496_Colf_NE`). Si aun así falla, sale
  en la lista de "no descargados" del correo.
- **Fechas:** descarga t-1; **los lunes** baja también sábado y domingo.
