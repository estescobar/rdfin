# Registro de cambios

Cada entrada documenta un cambio en seis partes: resumen, situación anterior, cambio y
origen, implicaciones, código tocado y verificación.

## Sin publicar

### Etapa 3: caché y descarga (2026-11-19)

1. **Resumen.** `transacciones()` y `resumen_oficial()` pueden descargar el Excel de
   una URL, con reintentos, y lo guardan en una caché local junto con las transacciones
   limpias en parquet. Así, las llamadas siguientes no vuelven a descargar ni a leer el
   Excel.

2. **Antes.** Solo se podía pasar un archivo ya descargado, y cada llamada leía el Excel
   completo (unos 11 s con pandas 3.1.1).

3. **Cambio y origen.** Sigue las secciones 5 y 6 de
   `INSTRUCCIONES_rdfin_v0.1_desde_cero.md` (descarga, caché y sus pruebas), más cinco
   decisiones aprobadas en esta etapa:
   - una URL distinta de la guardada invalida la caché;
   - si la descarga falla, se lanza `ErrorDeDescarga` y no se usa la copia vieja;
   - el `.xlsx`, el parquet y el json se escriben aparte y se renombran;
   - no hay URL por defecto hasta la etapa 5;
   - las pruebas quedan en `tests/test_creditopublico.py`.
   La fuente se busca en este orden: `archivo` (sin caché), `url` y la variable
   `RDFIN_URL_CP`. `max_edad_horas` vale 12 por defecto, provisional hasta conocer la
   hora de actualización de la fuente.

4. **Implicaciones.** Se descarga de nuevo si no hay copia, con `refrescar=True`, si la
   copia tiene más de `max_edad_horas`, si viene de otra URL o si la guardó otra versión
   de rdfin. Al descargar se borra el parquet. `transacciones()` lee siempre el parquet,
   para que la primera llamada y las siguientes devuelvan exactamente lo mismo.
   `limpiar_cache()` borra solo los archivos `creditopublico.*`, por si `RDFIN_CACHE`
   apunta a una carpeta con otros archivos. La descarga se identifica con
   `User-Agent: rdfin/<versión> (+https://github.com/estescobar/rdfin)`.

5. **Código tocado.**
   - `src/rdfin/_http.py` (nuevo): `descargar()`, con 3 intentos y esperas de 1 s y 2 s
     ante errores de conexión, 429 y 5xx; otro 4xx falla de inmediato.
   - `src/rdfin/_cache.py` (nuevo): directorio, vigencia, escritura por reemplazo y
     `limpiar_cache()`.
   - `src/rdfin/errores.py`: `ErrorDeDescarga`.
   - `src/rdfin/creditopublico.py`: parámetros `url`, `refrescar` y `max_edad_horas`;
     constante `MAX_EDAD_HORAS`; la lectura de transacciones pasa a
     `_leer_transacciones()`; `FuenteNoConfigurada` nombra las tres formas de indicar la
     fuente y se lanza al resolver la URL, por lo que `_leer_hoja()` ya no la comprueba.
   - `src/rdfin/__init__.py`: expone `limpiar_cache`.
   - `tests/conftest.py`: una protección automática hace que cada prueba use una caché
     temporal y corra sin `RDFIN_URL_CP`.
   - `tests/test_creditopublico.py`: 18 pruebas nuevas de caché y descarga; la de
     fuente faltante comprueba que el mensaje nombra las tres formas.

6. **Verificación.** `ruff check` y `ruff format --check` sin errores. Con
   `RDFIN_ARCHIVO_CP`, 54 pruebas pasan con Python 3.13.18 (pandas 3.1.1) y 3.10.20
   (pandas 2.3.3), incluida la dorada (antes 36). Sin la variable, pasan 53 y la dorada
   se omite. Ninguna prueba usa la red: la descarga se simula con un reemplazo de
   `descargar()` en las de caché y con `httpx.MockTransport` en las de descarga. La caché
   real del usuario quedó intacta. Control de punta a punta fuera del repositorio, con el
   Excel real servido por un servidor HTTP local: cuatro llamadas hicieron una sola
   petición; la primera tardó 11.3 s y la segunda 0.02 s desde el parquet (6.1 MB), con
   un resultado idéntico a leer el Excel. **No se corrió:** la descarga desde Crédito
   Público (bloqueado en este entorno; etapa 5), CI, Windows y macOS.

### Etapa 2: cálculos oficiales (2026-11-19)

1. **Resumen.** `snapshot()` y `rendimiento_actual()` reproducen el rendimiento oficial
   por bono a cualquier fecha, y `resumen_oficial()` lee la hoja `Rendimiento Actual`.
   La prueba dorada confirma, con el Excel real, que cada bono calculado tiene su fila
   oficial con tolerancia 1e-9.

2. **Antes.** El paquete entregaba las operaciones limpias, pero no calculaba
   rendimientos por bono ni leía la hoja oficial.

3. **Cambio y origen.** El método es el de la sección 4 de
   `INSTRUCCIONES_rdfin_v0.1_desde_cero.md`: el último día en que se negoció cada bono,
   con promedio ponderado por cantidad de títulos y sin excluir duplicados ni atípicos.
   Las decisiones aprobadas en esta etapa son siete:
   - Sin `fecha`, la referencia es la última fecha con operaciones en cualquier moneda,
     como el "Actualizado al" de la hoja oficial.
   - `excluir_duplicados` y `excluir_atipicos` quitan filas antes de buscar el último
     día de cada bono.
   - El snapshot se ordena por vencimiento y luego por instrumento, porque COV2040 e
     INF2040 vencen ambos el 28/2/2040.
   - ISIN, vencimiento y cupón se toman del último día del bono. En el archivo real
     cuatro instrumentos tienen dos cupones en su historia (MH12022 por redondeo;
     MH12031, MH22028 y SEH12017 por filas sueltas), pero nunca dos en un mismo día.
   - Una `moneda` distinta de `DOP` y `USD` lanza `ValueError`.
   - La hoja leída usa la fila de Excel como índice, para que los mensajes de error de
     las dos hojas nombren la fila correcta.
   - El análisis de sensibilidad de los umbrales de atípico se versiona en `analisis/`.

4. **Implicaciones.** El snapshot entrega, por bono, el rendimiento, la fecha de la
   última operación y los días desde entonces. Así queda visible lo que la hoja oficial
   no indica: en el archivo del 17/11/2026, 17 de los 30 bonos vigentes no se negociaron
   ese día y el dato más viejo es de MH12038, del 27/5/2026. `transacciones(crudo=True)`
   usa ahora la fila de Excel como índice (2, 3, …) en lugar de 0, 1, …; el resultado
   limpio no cambia.
   La sensibilidad muestra que en DOP ningún bono vigente cambia su rendimiento actual
   al excluir atípicos con ninguno de los 9 pares de umbrales. En USD cambian MHUS12026
   y MHUS12027 cuando el mínimo es 0 o 1, porque sus rendimientos recientes son negativos
   o muy bajos. Con el umbral vigente (0 / 30) se marcan 1,586 filas de 15 instrumentos.

5. **Código tocado.**
   - `src/rdfin/creditopublico.py`: `snapshot()`, `rendimiento_actual()`,
     `resumen_oficial()`, constante `HOJA_RESUMEN`; `_leer_hoja()` recibe `encabezado`
     y pone la fila de Excel como índice; `_exigir()` ya no suma 2 a la fila.
   - `tests/conftest.py`: hoja `Rendimiento Actual` sintética con la disposición de la
     oficial y los valores esperados de los 5 bonos vigentes (`RESUMEN`).
   - `tests/test_creditopublico.py`: 17 pruebas nuevas de snapshot, hoja oficial y
     prueba dorada; la del modo crudo comprueba el índice; `_modificar()` acepta la hoja.
   - `analisis/sensibilidad_atipicos.py` (nuevo) y su salida
     `analisis/sensibilidad_atipicos.md` (nuevo, solo agregados).

6. **Verificación.** Tolerancia de 1e-9, fijada en la guía antes de correr. `ruff check`
   y `ruff format --check` sin errores. Con Python 3.13.18 (pandas 3.1.1) y 3.10.20
   (pandas 2.3.3), y `RDFIN_ARCHIVO_CP` apuntando al Excel del 17/11/2026: 36 pruebas
   pasan, incluida la dorada (antes 19). Sin la variable, la dorada se omite y pasan 35.
   Para comprobar que la comparación dorada detecta errores, se corrió dos veces fuera
   del repositorio con la hoja oficial alterada: al sumar 1e-8 a un rendimiento falla
   (`MH22028` sin fila oficial) y al agregar una fila con un vencimiento y un rendimiento
   inventados también falla. Sin alterar, pasa. La tabla de sensibilidad está en
   `analisis/sensibilidad_atipicos.md`. **No se corrió:** CI, Windows y macOS.

### Mismo tipo de texto en `instrumento`, `isin` y `moneda` (2026-11-19)

1. **Resumen.** Las tres columnas de texto de `transacciones()` tienen ahora el mismo
   tipo dentro de cada versión de pandas.

2. **Antes.** Con pandas 3, `moneda` salía como `str` y `instrumento` e `isin` como
   `object`, porque las dos últimas conservaban el tipo de lectura. Con pandas 2 las tres
   eran `object`. La diferencia no cambiaba valores, pero podía confundir al usuario y a
   la caché en parquet de la etapa 3.

3. **Cambio y origen.** Aprobado tras la etapa 1. `instrumento` e `isin` pasan por
   `infer_objects()`, que da el tipo de texto por defecto de cada versión y conserva los
   vacíos. Se descartó `astype(str)` porque con pandas 2 convierte un vacío en el texto
   `'None'`.

4. **Implicaciones.** Con pandas 3 las tres columnas son `str`; con pandas 2, `object`.
   Los valores no cambian. Las fechas siguen con la resolución de cada versión
   (`datetime64[us]` con pandas 3, `datetime64[ns]` con pandas 2).

5. **Código tocado.**
   - `src/rdfin/creditopublico.py`: `transacciones()` convierte `instrumento` e `isin`.
   - `tests/test_creditopublico.py`: prueba nueva
     `test_columnas_de_texto_con_el_mismo_tipo`.

6. **Verificación.** La prueba nueva falla con el código anterior en pandas 3.1.1
   (`dtype('O')` frente a `StringDtype`) y pasa con el cambio. `ruff` sin errores;
   `pytest`, 19 pruebas pasan con Python 3.13 y 3.10 (antes 18). Con el Excel real y
   pandas 3, las tres columnas son `str` y siguen 168,021 filas, 19,283 duplicados y
   1,586 atípicos, como antes.

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
