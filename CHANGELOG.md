# Registro de cambios

Cada entrada documenta un cambio en seis partes: resumen, situación anterior, cambio y
origen, implicaciones, código tocado y verificación.

## Sin publicar

### Etapa 0: esqueleto del paquete (2026-11-19)

1. **Resumen.** Se crea el paquete `rdfin` vacío pero instalable, con su configuración
   de construcción, lint, pruebas e integración continua.

2. **Antes.** No existía el repositorio.

3. **Cambio y origen.** Sigue las decisiones de diseño y la etapa 0 de
   `INSTRUCCIONES_rdfin_v0.1_desde_cero.md`: Python ≥ 3.10, estructura `src/`, `uv`,
   `hatchling`, `ruff`, `pytest` y licencia MIT. Las cinco dependencias acordadas
   (`httpx`, `openpyxl`, `pandas`, `platformdirs`, `pyarrow`) se declaran sin cotas.
   La versión vive solo en `src/rdfin/__init__.py`. `pytest` excluye por defecto la marca
   `red`; `pytest -m red` la reemplaza. Se agrega `tests/test_paquete.py`, aprobado
   aparte, porque sin pruebas `pytest` termina con código 5.

4. **Implicaciones.** El paquete se instala y se construye, pero todavía no tiene
   funciones. Con el `uv.lock` actual, Python 3.10 resuelve pandas 2.3.3 y numpy 2.2.6, y
   Python 3.13 resuelve pandas 3.1.1. La CI probará las dos ramas de pandas.

5. **Código tocado.**
   - `pyproject.toml`: metadatos, dependencias, grupo `dev` (`pytest`, `ruff`), versión
     dinámica y configuración de `ruff` (reglas `E`, `F`, `I`, `UP`, `B`) y `pytest`
     (marcas `dorada` y `red`).
   - `uv.lock`: 33 paquetes resueltos.
   - `src/rdfin/__init__.py`: `__version__ = "0.1.0.dev0"`.
   - `src/rdfin/py.typed`: marca de paquete con tipos.
   - `tests/test_paquete.py`: comprueba que `__version__` coincide con la versión
     instalada.
   - `.github/workflows/ci.yml`: `ruff check`, `ruff format --check` y `pytest` en
     Linux, Windows y macOS con Python 3.10 y 3.13.
   - `.python-version` (3.13), `.gitignore` (excluye `*.xlsx`, `*.parquet`, `datos/` y
     `data/`), `LICENSE`, `README.md` y este archivo.

6. **Verificación.** En Linux, con Python 3.13.18 y con 3.10.20: `uv sync --locked`,
   `ruff check` ("All checks passed!"), `ruff format --check` ("3 files already
   formatted") y `pytest` (1 prueba pasa). `pytest -m red` deselecciona la prueba, lo que
   confirma que la marca reemplaza el filtro por defecto. `uv build` produce
   `rdfin-0.1.0.dev0.tar.gz` y `rdfin-0.1.0.dev0-py3-none-any.whl`; la rueda contiene
   `__init__.py`, `py.typed` y `LICENSE`. **No se corrió:** `ci.yml`, que se correrá al
   subir el repositorio en la etapa 4; Windows y macOS.
