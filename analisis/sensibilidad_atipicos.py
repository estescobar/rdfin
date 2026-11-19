"""Sensibilidad de la marca `atipico` a sus umbrales provisionales.

Uso, desde la raíz del repositorio:

    RDFIN_ARCHIVO_CP=/ruta/al/excel.xlsx uv run python analisis/sensibilidad_atipicos.py

Escribe `analisis/sensibilidad_atipicos.md` solo con agregados: ningún dato de la
fuente se copia al repositorio.
"""

import os
from pathlib import Path

import pandas as pd

from rdfin import creditopublico as cp

# Los pares que pide la guía de v0.1 (sección 5, valores provisionales).
MINIMOS_PCT = [-5, 0, 1]
MAXIMOS_PCT = [20, 30, 50]
MONEDAS = ["DOP", "USD"]
SALIDA = Path(__file__).with_suffix(".md")


def _rendimientos(datos, **kwargs):
    return pd.concat(
        cp.rendimiento_actual(m, datos=datos, **kwargs).set_index("instrumento")[
            "rendimiento_pct"
        ]
        for m in MONEDAS
    )


def main():
    datos = cp.transacciones(os.environ["RDFIN_ARCHIVO_CP"])
    oficial = _rendimientos(datos)
    filas = []
    for minimo in MINIMOS_PCT:
        for maximo in MAXIMOS_PCT:
            marca = (datos["rendimiento_pct"] < minimo) | (
                datos["rendimiento_pct"] > maximo
            )
            sin_atipicos = _rendimientos(
                datos.assign(atipico=marca), excluir_atipicos=True
            )
            # Un bono que se queda sin operaciones al excluir desaparece (NaN).
            cambio = (sin_atipicos.reindex(oficial.index) - oficial).abs()
            filas.append(
                [
                    f"{minimo} / {maximo}",
                    f"{marca.sum():,}",
                    f"{marca.mean():.2%}",
                    f"{datos.loc[marca, 'instrumento'].nunique()}",
                    f"{int(((cambio > 0) | cambio.isna()).sum())}",
                    f"{int(cambio.isna().sum())}",
                    f"{cambio.max():.4f}",
                ]
            )

    encabezado = [
        "Mín. / máx. (%)",
        "Filas marcadas",
        "% de filas",
        "Instrumentos con alguna fila marcada",
        "Bonos vigentes cuyo rendimiento cambia",
        "De ellos, desaparecen",
        "Cambio máximo (pp)",
    ]
    tabla = [encabezado, ["---"] * len(encabezado), *filas]
    texto = "\n".join(
        [
            "# Sensibilidad de la marca de atípico",
            "",
            "Generado por `analisis/sensibilidad_atipicos.py` con el Excel de Crédito "
            f"Público cuya última operación es del {datos['fecha'].max():%d/%m/%Y} "
            f"({len(datos):,} operaciones; {datos['instrumento'].nunique()} "
            f"instrumentos; {len(oficial)} bonos vigentes en DOP y USD).",
            "",
            "Una fila es atípica si su rendimiento está fuera de [mínimo, máximo]. "
            "Los bonos vigentes se comparan entre `rendimiento_actual()` con el "
            "método oficial y con `excluir_atipicos=True`. El umbral vigente en "
            f"rdfin es {cp.RENDIMIENTO_MIN_PCT:g} / {cp.RENDIMIENTO_MAX_PCT:g}.",
            "",
            *("| " + " | ".join(fila) + " |" for fila in tabla),
            "",
        ]
    )
    SALIDA.write_text(texto, encoding="utf-8")
    print(texto)


if __name__ == "__main__":
    main()
