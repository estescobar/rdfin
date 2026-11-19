"""Pruebas contra la fuente real.

Corren solo con `pytest -m red` y requieren la variable RDFIN_URL_CP con el enlace
del Excel de Crédito Público. Sin ella fallan en lugar de omitirse, para que el
canario no salga en verde con la variable mal configurada.
"""

import os

import pytest
from test_creditopublico import comparar_con_oficial

from rdfin import creditopublico as cp

pytestmark = pytest.mark.red


@pytest.fixture(scope="module")
def fuente(tmp_path_factory):
    """Transacciones y hoja oficial de una sola descarga, en una caché temporal."""
    url = os.environ.get("RDFIN_URL_CP")
    if not url:
        pytest.fail(
            "Las pruebas de red requieren RDFIN_URL_CP con el enlace del Excel."
        )
    # La caché temporal de cada prueba todavía no existe al preparar este fixture,
    # que se comparte entre las pruebas del módulo.
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("RDFIN_CACHE", str(tmp_path_factory.mktemp("cache")))
        return cp.transacciones(url=url), cp.resumen_oficial(url=url)


def test_formato(fuente):
    datos, _ = fuente
    assert len(datos) > 100_000
    assert set(datos["moneda"]) == {"DOP", "USD"}
    assert datos["fecha"].notna().all()
    assert datos["vencimiento"].notna().all()


def test_reproduce_la_hoja_oficial(fuente):
    comparar_con_oficial(*fuente)
