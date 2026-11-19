from datetime import date
from io import BytesIO

import openpyxl
import pandas as pd
import pytest
from conftest import ENCABEZADO, FILAS

from rdfin import creditopublico as cp
from rdfin.errores import CambioDeFormato, FuenteNoConfigurada

COLUMNAS_LIMPIAS = [
    "instrumento", "isin", "fecha", "vencimiento", "cupon_pct", "titulos",
    "valor_transado", "dias_intereses", "monto_intereses", "monto_limpio",
    "precio_limpio", "rendimiento_pct", "moneda", "plazo_anios", "duplicado", "atipico",
]  # fmt: skip


@pytest.fixture
def df(excel):
    return cp.transacciones(excel)


def _bono(df, instrumento):
    return df[df["instrumento"] == instrumento]


# Lectura y limpieza


def test_columnas_y_filas(df):
    assert list(df.columns) == COLUMNAS_LIMPIAS
    # Se descarta solo la fila sin instrumento; las columnas N a R se ignoran.
    assert len(df) == len(FILAS) - 1
    assert df["instrumento"].notna().all()


def test_orden_por_fecha_e_instrumento(df):
    ordenado = df.sort_values(["fecha", "instrumento"])
    assert ordenado.index.equals(df.index)
    assert df.index.equals(pd.RangeIndex(len(df)))


def test_fechas_como_numero_de_serie(df):
    mh12035 = _bono(df, "MH12035")
    assert list(mh12035["fecha"]) == [
        pd.Timestamp("2025-12-09"),
        pd.Timestamp("2026-11-10"),
    ]
    assert list(mh12035["vencimiento"]) == [pd.Timestamp("2035-01-05")] * 2
    assert pd.api.types.is_datetime64_dtype(df["fecha"])
    assert pd.api.types.is_datetime64_dtype(df["vencimiento"])


def test_unidades_en_porcentaje(df):
    mh12030 = _bono(df, "MH12030")
    assert list(mh12030["cupon_pct"]) == pytest.approx([10.0, 10.0], abs=1e-12)
    assert list(mh12030["rendimiento_pct"]) == pytest.approx([10.0, 12.0], abs=1e-12)
    assert _bono(df, "MHUS12026")["rendimiento_pct"].iloc[0] == pytest.approx(
        -0.66, abs=1e-12
    )


def test_monedas(df):
    assert set(df["moneda"]) == {"DOP", "USD"}
    assert set(_bono(df, "MHUS12027")["moneda"]) == {"USD"}
    assert set(_bono(df, "MH12030")["moneda"]) == {"DOP"}


def test_plazo_exacto(df):
    fila = _bono(df, "MH12030").iloc[0]
    esperado = (date(2030, 1, 11) - date(2026, 11, 17)).days / 365
    assert fila["plazo_anios"] == esperado


def test_marca_de_duplicado(df):
    marcados = df[df["duplicado"]]
    assert len(marcados) == 1
    assert marcados["instrumento"].iloc[0] == "MH22041"
    assert marcados["rendimiento_pct"].iloc[0] == pytest.approx(10.0, abs=1e-12)
    # La fila se marca, no se borra: MH22041 conserva sus tres operaciones.
    assert len(_bono(df, "MH22041")) == 3


def test_marca_de_atipico(df):
    assert set(df.loc[df["atipico"], "instrumento"]) == {"CDEEE12023", "MHUS12026"}
    assert df["atipico"].sum() == 2


def test_columnas_de_texto_con_el_mismo_tipo(df):
    assert df["instrumento"].dtype == df["isin"].dtype == df["moneda"].dtype


def test_tipos_con_decimales_y_vacios(df):
    adm = _bono(df, "ADM12016").iloc[0]
    assert adm["titulos"] == 748.61
    assert df["dias_intereses"].dtype == "Int64"
    assert pd.isna(adm["dias_intereses"])
    assert pd.isna(adm["precio_limpio"])


def test_formas_de_pasar_el_archivo(excel, df):
    contenido = excel.read_bytes()
    pd.testing.assert_frame_equal(cp.transacciones(str(excel)), df)
    pd.testing.assert_frame_equal(cp.transacciones(contenido), df)
    pd.testing.assert_frame_equal(cp.transacciones(BytesIO(contenido)), df)


def test_modo_crudo(excel):
    crudo = cp.transacciones(excel, crudo=True)
    assert list(crudo.columns) == ENCABEZADO
    assert len(crudo) == len(FILAS)
    serial = crudo[crudo["Fecha Valor"] == 46000]
    assert len(serial) == 1
    assert serial["Fecha Vencimiento"].iloc[0] == 49314
    assert crudo["Cupón"].iloc[0] == 0.10


# Errores


def _modificar(excel, tmp_path, cambio):
    libro = openpyxl.load_workbook(excel)
    cambio(libro["Transacciones por instrumento"])
    ruta = tmp_path / "modificado.xlsx"
    libro.save(ruta)
    return ruta


def test_sin_fuente():
    with pytest.raises(FuenteNoConfigurada, match="archivo"):
        cp.transacciones()


def test_columna_faltante(excel, tmp_path):
    ruta = _modificar(excel, tmp_path, lambda hoja: hoja.delete_cols(6))
    with pytest.raises(CambioDeFormato, match="faltan las columnas: Cantidad Títulos"):
        cp.transacciones(ruta)


def test_hoja_faltante(excel, tmp_path):
    def renombrar(hoja):
        hoja.title = "Otra hoja"

    ruta = _modificar(excel, tmp_path, renombrar)
    with pytest.raises(
        CambioDeFormato, match="Falta la hoja 'Transacciones por instrumento'"
    ):
        cp.transacciones(ruta)


def test_moneda_desconocida(excel, tmp_path):
    def euros(hoja):
        hoja["M3"] = "Euros"

    ruta = _modificar(excel, tmp_path, euros)
    with pytest.raises(CambioDeFormato, match="desconocidos: Euros"):
        cp.transacciones(ruta)


def test_valor_no_convertible(excel, tmp_path):
    def texto(hoja):
        hoja["G4"] = "n/d"

    ruta = _modificar(excel, tmp_path, texto)
    with pytest.raises(
        CambioDeFormato, match="'Valor Transado'.*fila 4 de Excel: 'n/d'"
    ):
        cp.transacciones(ruta)


def test_fecha_no_convertible(excel, tmp_path):
    def texto(hoja):
        hoja["C5"] = "17/11/2026"

    ruta = _modificar(excel, tmp_path, texto)
    with pytest.raises(CambioDeFormato, match="'Fecha Valor'.*fila 5 de Excel"):
        cp.transacciones(ruta)
