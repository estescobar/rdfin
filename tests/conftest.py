"""Excel sintético con la estructura del archivo de Crédito Público.

Los datos son inventados: cada fila existe para cubrir un caso de las pruebas.
"""

from datetime import datetime

import httpx
import openpyxl
import pytest

ENCABEZADO = [
    "instrumento",
    "ISIN",
    "Fecha Valor",
    "Fecha Vencimiento",
    "Cupón",
    "Cantidad Títulos",
    "Valor Transado",
    "Días Intereses",
    "Monto Intereses",
    "Monto Limpio",
    "Precio Limpio",
    "Rendimiento al Vencimiento",
    "Moneda",
]


def _fila(instrumento, fecha, vencimiento, cupon, titulos, rendimiento, moneda="Pesos"):
    # Las columnas de montos no entran en los cálculos; basta que sean coherentes.
    valor = titulos * 1000.0
    return [
        instrumento,
        f"XX{instrumento:>10}",
        fecha,
        vencimiento,
        cupon,
        titulos,
        valor,
        100,
        valor * 0.03,
        valor * 0.97,
        0.97,
        rendimiento,
        moneda,
    ]


d = datetime
# En el orden en que aparecen en la hoja: como en el archivo real, lo más
# reciente primero, para que el orden del resultado no venga dado.
FILAS = [
    # Ponderación por títulos: (100 × 10 + 300 × 12) / 400 = 11.5 %.
    _fila("MH12030", d(2026, 11, 17), d(2030, 1, 11), 0.10, 100, 0.10),
    _fila("MH12030", d(2026, 11, 17), d(2030, 1, 11), 0.10, 300, 0.12),
    # Duplicado: con la fila repetida (10 + 10 + 9.6) / 3 = 29.6/3 %; sin ella 9.8 %.
    _fila("MH22041", d(2026, 11, 17), d(2041, 5, 29), 0.12, 100, 0.10),
    _fila("MH22041", d(2026, 11, 17), d(2041, 5, 29), 0.12, 100, 0.10),
    _fila("MH22041", d(2026, 11, 17), d(2041, 5, 29), 0.12, 100, 0.096),
    _fila("MHUS12027", d(2026, 11, 17), d(2027, 3, 5), 0.05, 50, 0.0186, "Dólares"),
    _fila("MHUS12026", d(2026, 11, 17), d(2026, 12, 27), 0.06, 20, -0.0066, "Dólares"),
    # Dato viejo: la última operación de MH12035 es de 7 días antes de la última fecha.
    _fila("MH12035", d(2026, 11, 10), d(2035, 1, 5), 0.105, 200, 0.096835),
    # Bono vencido el 6/3/2026: entra en el snapshot del 5/3/2026, no en el actual.
    _fila("MH12026", d(2026, 3, 4), d(2026, 3, 6), 0.09, 10, 0.09),
    # Fechas como número de serie de Excel: 46000 = 9/12/2025; 49314 = 5/1/2035.
    _fila("MH12035", 46000, 49314, 0.105, 150, 0.095),
    _fila("CDEEE12023", d(2023, 6, 1), d(2023, 10, 30), 0.0725, 5, 0.4856, "Dólares"),
    # Como 14 filas del archivo real: títulos con decimales. Como 273: sin días de
    # interés ni montos. 41803 = 13/6/2014; 42426 = 26/2/2016.
    [
        "ADM12016",
        "XX  ADM12016",
        41803,
        42426,
        0.11,
        748.61,
        69382814.56,
        None,
        None,
        None,
        None,
        0.07,
        "Pesos",
    ],
    # Fila sin instrumento: se descarta.
    [None, None, None, None, None, None, 12345.0, None, None, None, None, None, None],
]

# Como en el archivo real, las columnas N a R traen datos ajenos a la tabla.
BASURA = {"N2": "PX_LAST", "O3": 3.789, "P4": d(2023, 5, 5), "R5": "YLD_YTM_MID"}

# Hoja `Rendimiento Actual` con los valores esperados de los bonos vigentes al
# 17/11/2026, según los casos de FILAS: (vencimiento, moneda, rendimiento en %).
RESUMEN = [
    (d(2030, 1, 11), "DOP", 11.5),  # MH12030
    (d(2035, 1, 5), "DOP", 9.6835),  # MH12035, operado por última vez el 10/11
    (d(2041, 5, 29), "DOP", 29.6 / 3),  # MH22041, con la fila duplicada
    (d(2026, 12, 27), "USD", -0.66),  # MHUS12026
    (d(2027, 3, 5), "USD", 1.86),  # MHUS12027
]


def _escribir_resumen(hoja):
    # Misma disposición que la hoja oficial: título en B4, encabezado en B5:D5.
    hoja["B4"] = "Rendimiento Bonos Domésticos (%)"
    hoja.append([None, "Vencimiento", "DOP", "USD"])
    for vencimiento, moneda, valor in RESUMEN:
        dop, usd = (valor, None) if moneda == "DOP" else (None, valor)
        hoja.append([None, vencimiento, dop, usd])
    hoja.append([None, "* Actualizado al", d(2026, 11, 17)])
    hoja.append([])
    hoja.append([None, "Nota metodológica de ejemplo."])


def escribir_excel(ruta):
    libro = openpyxl.Workbook()
    _escribir_resumen(libro.active)
    libro.active.title = "Rendimiento Actual"
    hoja = libro.create_sheet("Transacciones por instrumento")
    hoja.append(ENCABEZADO)
    for fila in FILAS:
        hoja.append(fila)
    for celda, valor in BASURA.items():
        hoja[celda] = valor
    libro.save(ruta)
    return ruta


def _sin_red(*args, **kwargs):
    raise RuntimeError("Las pruebas normales no usan la red.")


@pytest.fixture(autouse=True)
def _aislar(request, tmp_path, monkeypatch):
    # Ninguna prueba usa la caché del usuario. Salvo las de la marca `red`, tampoco
    # la URL real ni la red: como hay una URL por defecto, un descuido descargaría
    # de la fuente. Las pruebas de descarga usan httpx.MockTransport, que no pasa por
    # HTTPTransport.
    monkeypatch.setenv("RDFIN_CACHE", str(tmp_path / "cache"))
    if request.node.get_closest_marker("red") is None:
        monkeypatch.delenv("RDFIN_URL_CP", raising=False)
        monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _sin_red)


@pytest.fixture
def excel(tmp_path):
    return escribir_excel(tmp_path / "sintetico.xlsx")
