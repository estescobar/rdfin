from importlib.metadata import version

import rdfin


def test_version_coincide_con_la_instalada():
    # La versión vive solo en __init__.py; hatchling la copia a los metadatos.
    assert rdfin.__version__ == version("rdfin")
