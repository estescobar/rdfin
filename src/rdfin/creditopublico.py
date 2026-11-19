"""Mercado secundario de bonos del Ministerio de Hacienda.

Fuente: Dirección General de Crédito Público, con precios de CEVALDOM.
https://www.creditopublico.gob.do/inicio/mercado_de_capitales
"""

from __future__ import annotations

import os
from datetime import datetime
from io import BytesIO
from os import PathLike

import pandas as pd

from . import _cache
from .errores import CambioDeFormato

# El Excel que enlaza la página de mercado de capitales de Crédito Público.
URL_POR_DEFECTO = (
    "https://www.creditopublico.gob.do/Content/archivos/04Nueva%20Metodolog%C3%ADa.xlsx"
)

HOJA_TRANSACCIONES = "Transacciones por instrumento"
HOJA_RESUMEN = "Rendimiento Actual"

# Nombre en la fuente -> nombre en rdfin, en el orden de la hoja.
COLUMNAS = {
    "instrumento": "instrumento",
    "ISIN": "isin",
    "Fecha Valor": "fecha",
    "Fecha Vencimiento": "vencimiento",
    "Cupón": "cupon_pct",
    "Cantidad Títulos": "titulos",
    "Valor Transado": "valor_transado",
    "Días Intereses": "dias_intereses",
    "Monto Intereses": "monto_intereses",
    "Monto Limpio": "monto_limpio",
    "Precio Limpio": "precio_limpio",
    "Rendimiento al Vencimiento": "rendimiento_pct",
    "Moneda": "moneda",
}
MONEDAS = {"Pesos": "DOP", "Dólares": "USD"}

_COLUMNAS_SNAPSHOT = [
    "instrumento",
    "fecha_referencia",
    "isin",
    "vencimiento",
    "plazo_anios",
    "cupon_pct",
    "rendimiento_pct",
    "fecha_operacion",
    "dias_desde_operacion",
    "n_operaciones",
    "titulos",
    "valor_transado",
]

# Provisionales: no tienen respaldo definitivo. Su sensibilidad está en
# analisis/sensibilidad_atipicos.md. Fuera de [mínimo, máximo] la fila se marca
# como atípica.
RENDIMIENTO_MIN_PCT = 0.0
RENDIMIENTO_MAX_PCT = 30.0

# Provisional: falta averiguar a qué hora actualiza la fuente su archivo.
MAX_EDAD_HORAS = 12

# Parte de las filas guarda las fechas como número de serie de Excel: días
# contados desde esta base.
_BASE_EXCEL = pd.Timestamp("1899-12-30")

Archivo = str | PathLike | bytes | BytesIO


def transacciones(
    archivo: Archivo | None = None,
    *,
    url: str | None = None,
    crudo: bool = False,
    refrescar: bool = False,
    max_edad_horas: float = MAX_EDAD_HORAS,
) -> pd.DataFrame:
    """Operaciones del mercado secundario, una fila por operación.

    `archivo` es la ruta, los bytes o un `BytesIO` del Excel de Crédito Público; si
    se pasa, no se usa la caché. Si no, el Excel se descarga de `url`, de la
    variable de entorno `RDFIN_URL_CP` o de `URL_POR_DEFECTO`, en ese orden, y se
    guarda en la caché, que se renueva con `refrescar=True` o cuando la copia tiene
    más de `max_edad_horas`.

    Con `crudo=True` devuelve la hoja tal cual: las 13 columnas con sus nombres y
    valores originales, todas las filas y sin marcas, con el número de fila de
    Excel como índice.

    En el modo normal renombra las columnas, convierte fechas, pasa cupón y
    rendimiento a porcentaje y las monedas a `DOP` y `USD`, y agrega
    `plazo_anios` (ACT/365), `duplicado` y `atipico`. Las filas dudosas se marcan,
    no se borran; solo se descartan las filas sin instrumento.
    """
    if archivo is not None:
        return _leer_transacciones(archivo, crudo=crudo)
    excel = _excel_en_cache(url, refrescar, max_edad_horas)
    if crudo:
        return _leer_transacciones(excel, crudo=True)
    ruta = _cache.parquet(_cache.CREDITOPUBLICO)
    if not ruta.exists():
        _cache.escribir_parquet(_leer_transacciones(excel, crudo=False), ruta)
    # Se lee siempre del parquet para que la primera llamada y las siguientes
    # devuelvan exactamente lo mismo.
    return pd.read_parquet(ruta)


def _excel_en_cache(url: str | None, refrescar: bool, max_edad_horas: float):
    url = url or os.environ.get("RDFIN_URL_CP") or URL_POR_DEFECTO
    return _cache.excel(
        _cache.CREDITOPUBLICO, url, refrescar=refrescar, max_edad_horas=max_edad_horas
    )


def _leer_transacciones(archivo: Archivo, *, crudo: bool) -> pd.DataFrame:
    hoja = _leer_hoja(archivo, HOJA_TRANSACCIONES, encabezado=True)
    faltan = [c for c in COLUMNAS if c not in hoja.columns]
    if faltan:
        raise CambioDeFormato(
            f"En la hoja {HOJA_TRANSACCIONES!r} faltan las columnas: "
            f"{', '.join(faltan)}."
        )
    hoja = hoja[list(COLUMNAS)]
    if crudo:
        return hoja

    # Se marca sobre los valores crudos y en el orden de la hoja: la primera
    # aparición queda sin marcar.
    duplicado = hoja.duplicated()
    hoja = hoja[hoja["instrumento"].notna()]

    monedas = hoja["Moneda"]
    desconocidas = sorted(map(str, set(monedas[~monedas.isin(list(MONEDAS))])))
    if desconocidas:
        raise CambioDeFormato(
            f"La columna 'Moneda' trae valores desconocidos: {', '.join(desconocidas)}."
        )

    df = hoja.rename(columns=COLUMNAS)
    df["fecha"] = _a_fecha(hoja["Fecha Valor"])
    df["vencimiento"] = _a_fecha(hoja["Fecha Vencimiento"])
    for fuente in [
        "Cupón",
        "Cantidad Títulos",
        "Valor Transado",
        "Monto Intereses",
        "Monto Limpio",
        "Precio Limpio",
        "Rendimiento al Vencimiento",
    ]:
        df[COLUMNAS[fuente]] = _a_numero(hoja[fuente])
    # 273 filas del archivo real no traen días de interés: entero con vacíos.
    df["dias_intereses"] = _a_numero(hoja["Días Intereses"]).astype("Int64")
    df["cupon_pct"] *= 100
    df["rendimiento_pct"] *= 100
    df["moneda"] = monedas.map(MONEDAS)
    # Mismo tipo de texto que `moneda` en cada versión de pandas, sin volver
    # texto los vacíos.
    df["instrumento"] = hoja["instrumento"].infer_objects()
    df["isin"] = hoja["ISIN"].infer_objects()

    df["plazo_anios"] = (df["vencimiento"] - df["fecha"]).dt.days / 365
    df["duplicado"] = duplicado[df.index]
    df["atipico"] = (df["rendimiento_pct"] < RENDIMIENTO_MIN_PCT) | (
        df["rendimiento_pct"] > RENDIMIENTO_MAX_PCT
    )
    return df.sort_values(["fecha", "instrumento"]).reset_index(drop=True)


def snapshot(
    fecha=None,
    *,
    moneda: str = "DOP",
    datos: pd.DataFrame | None = None,
    excluir_duplicados: bool = False,
    excluir_atipicos: bool = False,
    **kwargs,
) -> pd.DataFrame:
    """Rendimiento de cada bono vigente a `fecha`, con el método oficial.

    Para cada bono de `moneda` con operaciones hasta `fecha` y vencimiento
    posterior, toma el último día en que se negoció y promedia los rendimientos de
    ese día ponderando por cantidad de títulos. Así calcula Crédito Público la hoja
    `Rendimiento Actual`: incluye las filas duplicadas y atípicas y no pondera por
    valor transado. `excluir_duplicados` y `excluir_atipicos` quitan esas filas
    antes de buscar el último día de cada bono.

    `fecha=None` es la última fecha con operaciones en cualquier moneda, como el
    "Actualizado al" de la hoja oficial. `datos` es el resultado de
    `transacciones()`; si falta, se llama a `transacciones(**kwargs)`.

    Una fila por bono, ordenada por vencimiento y luego por instrumento, porque hay
    bonos distintos con el mismo vencimiento.
    """
    if moneda not in MONEDAS.values():
        raise ValueError(f"`moneda` debe ser 'DOP' o 'USD', no {moneda!r}.")
    if datos is None:
        datos = transacciones(**kwargs)
    referencia = datos["fecha"].max() if fecha is None else pd.Timestamp(fecha)

    d = datos[
        (datos["moneda"] == moneda)
        & (datos["fecha"] <= referencia)
        & (datos["vencimiento"] > referencia)
    ]
    if excluir_duplicados:
        d = d[~d["duplicado"]]
    if excluir_atipicos:
        d = d[~d["atipico"]]
    d = d[d["fecha"] == d.groupby("instrumento")["fecha"].transform("max")]

    # ISIN, vencimiento y cupón salen del último día del bono: en el archivo real
    # nunca hay dos valores distintos para un mismo instrumento en un mismo día.
    bonos = (
        d.assign(ponderado=d["rendimiento_pct"] * d["titulos"])
        .groupby("instrumento")
        .agg(
            isin=("isin", "first"),
            vencimiento=("vencimiento", "first"),
            cupon_pct=("cupon_pct", "first"),
            fecha_operacion=("fecha", "first"),
            n_operaciones=("fecha", "size"),
            titulos=("titulos", "sum"),
            valor_transado=("valor_transado", "sum"),
            ponderado=("ponderado", "sum"),
        )
        .reset_index()
    )
    bonos["rendimiento_pct"] = bonos["ponderado"] / bonos["titulos"]
    bonos["fecha_referencia"] = referencia
    bonos["plazo_anios"] = (bonos["vencimiento"] - referencia).dt.days / 365
    bonos["dias_desde_operacion"] = (referencia - bonos["fecha_operacion"]).dt.days
    bonos = bonos.sort_values(["vencimiento", "instrumento"]).reset_index(drop=True)
    return bonos[_COLUMNAS_SNAPSHOT]


def rendimiento_actual(
    moneda: str = "DOP", *, datos: pd.DataFrame | None = None, **kwargs
) -> pd.DataFrame:
    """`snapshot()` a la última fecha con operaciones: replica la hoja oficial."""
    return snapshot(moneda=moneda, datos=datos, **kwargs)


def resumen_oficial(
    archivo: Archivo | None = None,
    *,
    url: str | None = None,
    refrescar: bool = False,
    max_edad_horas: float = MAX_EDAD_HORAS,
) -> pd.DataFrame:
    """La hoja `Rendimiento Actual` tal como la publica Crédito Público.

    Una fila por fila de la tabla, en el orden de la hoja, con `vencimiento`,
    `moneda` y `rendimiento_pct`. La hoja no trae el nombre del instrumento. El
    encabezado se busca por sus celdas `Vencimiento`, `DOP` y `USD`, no por
    posición; la tabla termina en la primera fila cuyo vencimiento no es fecha.

    La fuente y la caché funcionan como en `transacciones()`.
    """
    if archivo is None:
        archivo = _excel_en_cache(url, refrescar, max_edad_horas)
    hoja = _leer_hoja(archivo, HOJA_RESUMEN, encabezado=False)
    celdas = {nombre: hoja.eq(nombre) for nombre in ("Vencimiento", "DOP", "USD")}
    filas = pd.concat([c.any(axis=1) for c in celdas.values()], axis=1).all(axis=1)
    if not filas.any():
        raise CambioDeFormato(
            f"En la hoja {HOJA_RESUMEN!r} no hay una fila con las celdas "
            "'Vencimiento', 'DOP' y 'USD'."
        )
    fila = filas.idxmax()
    tabla = hoja.loc[fila + 1 :, [c.loc[fila].idxmax() for c in celdas.values()]]
    tabla.columns = list(celdas)
    es_fecha = tabla["Vencimiento"].map(lambda v: isinstance(v, datetime))
    tabla = tabla[(~es_fecha).cumsum() == 0]

    con_valor = tabla[["DOP", "USD"]].notna()
    mal = con_valor.sum(axis=1) != 1
    if mal.any():
        raise CambioDeFormato(
            f"En la hoja {HOJA_RESUMEN!r}, la fila {mal.idxmax()} de Excel debe traer "
            "el rendimiento en una sola moneda."
        )
    return pd.DataFrame(
        {
            "vencimiento": pd.to_datetime(tabla["Vencimiento"]),
            "moneda": con_valor["USD"].map({False: "DOP", True: "USD"}),
            "rendimiento_pct": _a_numero(tabla["DOP"]).fillna(_a_numero(tabla["USD"])),
        }
    ).reset_index(drop=True)


def _leer_hoja(archivo: Archivo, nombre: str, *, encabezado: bool) -> pd.DataFrame:
    """Lee una hoja con el número de fila de Excel como índice."""
    if isinstance(archivo, bytes):
        archivo = BytesIO(archivo)
    with pd.ExcelFile(archivo, engine="openpyxl") as libro:
        if nombre not in libro.sheet_names:
            raise CambioDeFormato(
                f"Falta la hoja {nombre!r}. Hojas en el archivo: "
                f"{', '.join(libro.sheet_names)}."
            )
        hoja = pd.read_excel(
            libro, sheet_name=nombre, dtype=object, header=0 if encabezado else None
        )
    # Con encabezado, la primera fila de datos es la 2 de Excel.
    hoja.index += 2 if encabezado else 1
    return hoja


def _a_fecha(serie: pd.Series) -> pd.Series:
    es_fecha = serie.map(lambda v: isinstance(v, datetime))
    es_serial = serie.map(lambda v: type(v) is int)
    _exigir(es_fecha | es_serial | serie.isna(), serie)
    fechas = pd.to_datetime(serie.where(es_fecha))
    seriales = _BASE_EXCEL + pd.to_timedelta(
        pd.to_numeric(serie.where(es_serial)), unit="D"
    )
    return fechas.where(es_fecha, seriales)


def _a_numero(serie: pd.Series) -> pd.Series:
    numeros = pd.to_numeric(serie, errors="coerce")
    _exigir(numeros.notna() | serie.isna(), serie)
    return numeros.astype("float64")


def _exigir(validos: pd.Series, serie: pd.Series) -> None:
    if not validos.all():
        fila = validos.idxmin()
        raise CambioDeFormato(
            f"La columna {serie.name!r} trae un valor que no se puede convertir en la "
            f"fila {fila} de Excel: {serie[fila]!r}."
        )
