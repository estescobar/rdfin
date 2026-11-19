# Registro de cambios

Cada entrada documenta un cambio en seis partes: resumen, situación anterior, cambio y
origen, implicaciones, código tocado y verificación.

## Sin publicar

### Etapa 1: lectura y limpieza de transacciones (2026-11-19)

1. **Resumen.** `creditopublico.transacciones()` lee la hoja de transacciones del Excel
   de Crédito Público y entrega las operaciones limpias, con marcas de duplicado y
   atípico en lugar de borrar filas.

2. **Antes.** El paquete no leía datos.

3. **Cambio y origen.** Sigue las secciones 4 a 6 de
   `INSTRUCCIONES_rdfin_v0.1_desde_cero.md` y cinco decisiones aprobadas en esta etapa:
   la firma lleva solo `archivo` y `crudo` (los parámetros de descarga y caché llegan en
   la etapa 3); `titulos` es decimal y `dias_intereses` es entero con vacíos; un valor que
   no se puede convertir en una columna de fecha o numérica lanza `CambioDeFormato` con
   la columna y la fila de Excel; `ErrorDeDescarga` se define en la etapa 3; la hoja
   `Rendimiento Actual` sintética se agrega en la etapa 2.
   La revisión del Excel real del 17/11/2026 encontró tres hechos que la guía no
   menciona y que el código y el Excel sintético cubren: las columnas N a R traen un
   bloque ajeno a la tabla (filas 118,931 a 119,195 de Excel, con encabezados tipo
   `PX_LAST` y `YLD_YTM_MID` de mayo de 2023); 14 filas tienen `Cantidad Títulos` con
   decimales; 273 filas no traen `Días Intereses`, `Monto Intereses`, `Monto Limpio` ni
   `Precio Limpio`.

4. **Implicaciones.** Las fechas guardadas como número de serie de Excel se convierten
   desde la base 1899-12-30. Cupón y rendimiento quedan en porcentaje y las monedas como
   `DOP` y `USD`. `duplicado` se calcula sobre los 13 valores crudos en el orden de la
   hoja; `atipico` marca rendimientos fuera de [0, 30] %, umbrales provisionales. El
   resultado se ordena por `fecha` e `instrumento`. Las validaciones de formato ocurren
   una sola vez, al leer. El modo crudo solo valida la hoja y las columnas, para poder
   auditar un archivo con valores inesperados.

5. **Código tocado.**
   - `src/rdfin/errores.py` (nuevo): `RdfinError`, `FuenteNoConfigurada` y
     `CambioDeFormato`.
   - `src/rdfin/creditopublico.py` (nuevo): `transacciones()`, el mapa de columnas, el
     mapa de monedas y los umbrales `RENDIMIENTO_MIN_PCT` y `RENDIMIENTO_MAX_PCT`.
   - `src/rdfin/__init__.py`: expone `creditopublico` y `errores`.
   - `tests/conftest.py` (nuevo): Excel sintético con la hoja de transacciones, los
     casos de la sección 6 de la guía y los tres hechos anteriores, más una fila sin
     instrumento.
   - `tests/test_creditopublico.py` (nuevo): 17 pruebas de limpieza, modo crudo y
     errores.

6. **Verificación.** En Linux con Python 3.13.18 (pandas 3.1.1) y 3.10.20 (pandas
   2.3.3): `ruff check` y `ruff format --check` sin errores; `pytest`, 18 pruebas pasan
   (antes 1). Control fuera del repositorio con el Excel real, idéntico en las dos
   versiones: 168,021 operaciones, 61 instrumentos, del 30/3/2009 al 17/11/2026, ninguna
   fecha vacía ni plazo negativo, 19,283 duplicados, 1,586 atípicos (1,460 negativos y
   126 mayores de 30 %), 129,565 operaciones en DOP y 38,456 en USD. Son las cifras de
   la guía. La lectura tardó 10.7 s con pandas 3.1.1 y 16.5 s con pandas 2.3.3. Los
   tipos difieren entre versiones: con pandas 3 las fechas son `datetime64[us]` y
   `moneda` es `str`; con pandas 2, `datetime64[ns]` y `object`. **No se corrió:** CI,
   Windows y macOS.

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
