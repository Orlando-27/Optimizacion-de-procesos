"""Inspecciona el .xlsm de la macro y lista sus procedimientos VBA.

Sirve para desbloquear el PASO 5 (migrar la macro a Python): identifica el
nombre de la macro a ejecutar y ayuda a entender que lee y que produce.

Requiere ``oletools`` (pip install oletools).

Uso:
  python scripts/inspeccionar_macro.py "ruta/Informacion Impugnacion.xlsm"
  python scripts/inspeccionar_macro.py "ruta.xlsm" --volcar-vba salida.vba
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_RE_PROC = re.compile(r"^\s*(?:Public\s+|Private\s+)?(Sub|Function)\s+([A-Za-z0-9_]+)",
                      re.MULTILINE)


def main() -> int:
    p = argparse.ArgumentParser(description="Inspecciona el VBA de un .xlsm")
    p.add_argument("xlsm", type=Path, help="Ruta al archivo .xlsm")
    p.add_argument("--volcar-vba", type=Path, help="Guarda todo el VBA a un archivo")
    args = p.parse_args()

    if not args.xlsm.exists():
        print(f"No existe: {args.xlsm}")
        return 1

    try:
        from oletools.olevba import VBA_Parser
    except Exception:  # noqa: BLE001
        print("Falta 'oletools'. Instalar con:  pip install oletools")
        return 2

    vba = VBA_Parser(str(args.xlsm))
    if not vba.detect_vba_macros():
        print("El archivo no contiene macros VBA.")
        return 0

    modulos: list[tuple[str, str]] = []
    todo_vba: list[str] = []
    for _fn, _stream, nombre_modulo, codigo in vba.extract_macros():
        modulos.append((nombre_modulo, codigo))
        todo_vba.append(f"'==== MODULO: {nombre_modulo} ====\n{codigo}\n")

    print("=" * 64)
    print(f" MACROS EN: {args.xlsm.name}")
    print("=" * 64)
    candidatos: list[str] = []
    for nombre_modulo, codigo in modulos:
        procs = _RE_PROC.findall(codigo)
        print(f"\nMODULO: {nombre_modulo}  ({len(procs)} procedimientos)")
        for tipo, nombre in procs:
            publico = "Private" not in codigo.split(nombre)[0][-40:]
            marca = "  <- candidato" if (tipo == "Sub" and publico) else ""
            print(f"   {tipo:8} {nombre}{marca}")
            if tipo == "Sub" and publico:
                candidatos.append(f"{nombre_modulo}.{nombre}")

    print("\n" + "-" * 64)
    print("CANDIDATOS a 'nombre_macro' (Subs publicos):")
    for c in candidatos:
        print(f"   - {c}")
    print("\nPistas de I/O (buscar en el VBA): Workbooks.Open, Range(...).Value,")
    print("SaveAs 'Renta Fija', Dir(), rutas INFOVALMER, nombres de hoja.")

    if args.volcar_vba:
        args.volcar_vba.write_text("\n".join(todo_vba), encoding="utf-8", errors="replace")
        print(f"\nVBA completo volcado en: {args.volcar_vba}")

    vba.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
