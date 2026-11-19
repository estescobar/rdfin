"""Mercado secundario de bonos del Ministerio de Hacienda.

Fuente: Dirección General de Crédito Público, con precios de CEVALDOM.
https://www.creditopublico.gob.do/inicio/mercado_de_capitales
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from os import PathLike

import pandas as pd

from .errores import CambioDeFormato, FuenteNoConfigurada

HOJA_TRANSACCIONES = "Transacciones por instrumento"

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

# Provisionales: no tienen respaldo definitivo y se someten a análisis de
# sensibilidad. Fuera de [mínimo, máximo] la fila se marca como atípica.
RENDIMIENTO_MIN_PCT = 0.0
RENDIMIENTO_MAX_PCT = 30.0

# Parte de las filas guarda las fechas como número de serie de Excel: días
# contados desde esta base.
_BASE_EXCEL = pd.Timestamp("1899-12-30")

Archivo = str | PathLike | bytes | BytesIO


def transacciones(
    archivo: Archivo | None = None, *, crudo: bool = False
) -> pd.DataFrame:
    """Operaciones del mercado secundario, una fila por operación.

    `archivo` es la ruta, los bytes o un `BytesIO` del Excel de Crédito Público.
    Con `crudo=True` devuelve la hoja tal cual: las 13 columnas con sus nombres y
    valores originales, todas las filas y sin marcas.

    En el modo normal renombra las columnas, convierte fechas, pasa cupón y
    rendimiento a porcentaje y las monedas a `DOP` y `USD`, y agrega
    `plazo_anios` (ACT/365), `duplicado` y `atipico`. Las filas dudosas se marcan,
    no se borran; solo se descartan las filas sin instrumento.
    """
    hoja = _leer_hoja(archivo, HOJA_TRANSACCIONES)
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


def _leer_hoja(archivo: Archivo | None, nombre: str) -> pd.DataFrame:
    if archivo is None:
        raise FuenteNoConfigurada(
            "No se indicó la fuente: pase en `archivo` la ruta, los bytes o un BytesIO "
            "del Excel de Crédito Público."
        )
    if isinstance(archivo, bytes):
        archivo = BytesIO(archivo)
    with pd.ExcelFile(archivo, engine="openpyxl") as libro:
        if nombre not in libro.sheet_names:
            raise CambioDeFormato(
                f"Falta la hoja {nombre!r}. Hojas en el archivo: "
                f"{', '.join(libro.sheet_names)}."
            )
        return pd.read_excel(libro, sheet_name=nombre, dtype=object)


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
        indice = validos.idxmin()
        # El índice 0 es la fila 2 de Excel: la fila 1 es el encabezado.
        raise CambioDeFormato(
            f"La columna {serie.name!r} trae un valor que no se puede convertir en la "
            f"fila {indice + 2} de Excel: {serie[indice]!r}."
        )
