import os
from datetime import date
from io import BytesIO

import openpyxl
import pandas as pd
import pytest
from conftest import ENCABEZADO, FILAS, RESUMEN

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
    # El índice es la fila de Excel: la 1 es el encabezado.
    assert list(crudo.index) == list(range(2, len(FILAS) + 2))
    serial = crudo[crudo["Fecha Valor"] == 46000]
    assert len(serial) == 1
    assert serial["Fecha Vencimiento"].iloc[0] == 49314
    assert crudo["Cupón"].iloc[0] == 0.10


# Errores


def _modificar(excel, tmp_path, cambio, hoja="Transacciones por instrumento"):
    libro = openpyxl.load_workbook(excel)
    cambio(libro[hoja])
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


# Cálculos oficiales

COLUMNAS_SNAPSHOT = [
    "instrumento", "fecha_referencia", "isin", "vencimiento", "plazo_anios",
    "cupon_pct", "rendimiento_pct", "fecha_operacion", "dias_desde_operacion",
    "n_operaciones", "titulos", "valor_transado",
]  # fmt: skip
TOLERANCIA = 1e-9


def test_columnas_y_orden_del_snapshot(df):
    actual = cp.rendimiento_actual(datos=df)
    assert list(actual.columns) == COLUMNAS_SNAPSHOT
    assert list(actual["instrumento"]) == ["MH12030", "MH12035", "MH22041"]
    assert (actual["fecha_referencia"] == pd.Timestamp("2026-11-17")).all()
    esperado = (date(2041, 5, 29) - date(2026, 11, 17)).days / 365
    assert actual["plazo_anios"].iloc[-1] == esperado


def test_ponderacion_por_titulos(df):
    mh12030 = _bono(cp.rendimiento_actual(datos=df), "MH12030").iloc[0]
    assert mh12030["rendimiento_pct"] == pytest.approx(11.5, abs=TOLERANCIA)
    assert mh12030["n_operaciones"] == 2
    assert mh12030["titulos"] == 400
    assert mh12030["valor_transado"] == 400_000


def test_dato_viejo(df):
    mh12035 = _bono(cp.rendimiento_actual(datos=df), "MH12035").iloc[0]
    assert mh12035["fecha_operacion"] == pd.Timestamp("2026-11-10")
    assert mh12035["dias_desde_operacion"] == 7
    # Solo cuenta el último día negociado, no la operación de 2025.
    assert mh12035["rendimiento_pct"] == pytest.approx(9.6835, abs=TOLERANCIA)
    assert mh12035["n_operaciones"] == 1


def test_duplicados(df):
    con = _bono(cp.rendimiento_actual(datos=df), "MH22041").iloc[0]
    assert con["rendimiento_pct"] == pytest.approx(29.6 / 3, abs=TOLERANCIA)
    assert con["n_operaciones"] == 3
    sin = cp.rendimiento_actual(datos=df, excluir_duplicados=True)
    sin = _bono(sin, "MH22041").iloc[0]
    assert sin["rendimiento_pct"] == pytest.approx(9.8, abs=TOLERANCIA)
    assert sin["n_operaciones"] == 2


def test_bono_vencido(df):
    pasado = cp.snapshot("2026-03-05", datos=df)
    mh12026 = _bono(pasado, "MH12026")
    assert len(mh12026) == 1
    assert mh12026["fecha_operacion"].iloc[0] == pd.Timestamp("2026-03-04")
    assert mh12026["plazo_anios"].iloc[0] == 1 / 365
    # El 5/3/2026, MH12035 solo tiene la operación de 2025, guardada como número de
    # serie.
    assert _bono(pasado, "MH12035")["fecha_operacion"].iloc[0] == pd.Timestamp(
        "2025-12-09"
    )
    assert "MH12026" not in set(cp.rendimiento_actual(datos=df)["instrumento"])


def test_dolares(df):
    actual = cp.rendimiento_actual("USD", datos=df)
    assert list(actual["instrumento"]) == ["MHUS12026", "MHUS12027"]


def test_excluir_atipicos(df):
    actual = cp.rendimiento_actual("USD", datos=df, excluir_atipicos=True)
    assert list(actual["instrumento"]) == ["MHUS12027"]


def test_moneda_invalida(df):
    with pytest.raises(ValueError, match="'EUR'"):
        cp.snapshot(moneda="EUR", datos=df)


def test_sin_datos_se_leen_con_kwargs(excel, df):
    pd.testing.assert_frame_equal(
        cp.rendimiento_actual(archivo=excel), cp.rendimiento_actual(datos=df)
    )


def test_reproduce_la_hoja_sintetica(excel, df):
    oficial = cp.resumen_oficial(excel)
    for moneda in ["DOP", "USD"]:
        calculado = cp.rendimiento_actual(moneda, datos=df)
        esperado = oficial[oficial["moneda"] == moneda].sort_values("vencimiento")
        assert list(calculado["vencimiento"]) == list(esperado["vencimiento"])
        assert list(calculado["rendimiento_pct"]) == pytest.approx(
            list(esperado["rendimiento_pct"]), abs=TOLERANCIA
        )


# Hoja oficial


def test_resumen_oficial(excel):
    oficial = cp.resumen_oficial(excel)
    assert list(oficial.columns) == ["vencimiento", "moneda", "rendimiento_pct"]
    assert list(oficial.itertuples(index=False, name=None)) == [
        (pd.Timestamp(v), m, r) for v, m, r in RESUMEN
    ]
    assert oficial["moneda"].dtype == cp.transacciones(excel)["moneda"].dtype


def test_resumen_encabezado_en_otra_posicion(excel, tmp_path):
    def mover(hoja):
        hoja.insert_rows(1, amount=3)
        hoja.insert_cols(1, amount=2)

    ruta = _modificar(excel, tmp_path, mover, hoja="Rendimiento Actual")
    pd.testing.assert_frame_equal(cp.resumen_oficial(ruta), cp.resumen_oficial(excel))


def test_resumen_sin_encabezado(excel, tmp_path):
    def cambiar(hoja):
        hoja["C5"] = "Pesos"

    ruta = _modificar(excel, tmp_path, cambiar, hoja="Rendimiento Actual")
    with pytest.raises(CambioDeFormato, match="'Vencimiento', 'DOP' y 'USD'"):
        cp.resumen_oficial(ruta)


def test_resumen_fila_con_dos_monedas(excel, tmp_path):
    def cambiar(hoja):
        hoja["D6"] = 5.0

    ruta = _modificar(excel, tmp_path, cambiar, hoja="Rendimiento Actual")
    with pytest.raises(CambioDeFormato, match="fila 6 de Excel"):
        cp.resumen_oficial(ruta)


def test_resumen_valor_no_convertible(excel, tmp_path):
    def cambiar(hoja):
        hoja["D9"] = "n/d"

    ruta = _modificar(excel, tmp_path, cambiar, hoja="Rendimiento Actual")
    with pytest.raises(CambioDeFormato, match="'USD'.*fila 9 de Excel: 'n/d'"):
        cp.resumen_oficial(ruta)


def test_resumen_hoja_faltante(excel, tmp_path):
    def renombrar(hoja):
        hoja.title = "Otra hoja"

    ruta = _modificar(excel, tmp_path, renombrar, hoja="Rendimiento Actual")
    with pytest.raises(CambioDeFormato, match="Falta la hoja 'Rendimiento Actual'"):
        cp.resumen_oficial(ruta)


# Prueba dorada


def comparar_con_oficial(datos, oficial):
    """Cada bono calculado tiene en la hoja oficial una fila con su vencimiento y su
    rendimiento. Una fila oficial que sobre solo se acepta si repite exactamente el
    rendimiento de otra fila oficial que sí cuadró (el caso de MH22034)."""
    for moneda in ["DOP", "USD"]:
        calculado = cp.rendimiento_actual(moneda, datos=datos)
        filas = oficial[oficial["moneda"] == moneda]
        cuadradas = pd.Series(False, index=filas.index)
        sin_fila = []
        for bono in calculado.itertuples():
            coincide = (filas["vencimiento"] == bono.vencimiento) & (
                (filas["rendimiento_pct"] - bono.rendimiento_pct).abs() <= TOLERANCIA
            )
            if not coincide.any():
                sin_fila.append((bono.instrumento, bono.rendimiento_pct))
            cuadradas |= coincide
        assert not sin_fila, f"{moneda}: bonos sin fila oficial: {sin_fila}"
        sobran = filas[~cuadradas]
        rechazadas = sobran[
            ~sobran["rendimiento_pct"].isin(filas.loc[cuadradas, "rendimiento_pct"])
        ]
        assert rechazadas.empty, f"{moneda}: filas oficiales sin bono:\n{rechazadas}"


@pytest.mark.dorada
def test_dorada():
    ruta = os.environ.get("RDFIN_ARCHIVO_CP")
    if not ruta:
        pytest.skip("requiere RDFIN_ARCHIVO_CP con la ruta del Excel real")
    comparar_con_oficial(cp.transacciones(ruta), cp.resumen_oficial(ruta))
