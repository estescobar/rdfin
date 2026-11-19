"""Caché local de los archivos descargados.

Cada fuente guarda en el directorio de caché su archivo descargado, un parquet con
los datos limpios y un json con la hora de descarga, la URL y la versión de rdfin.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import platformdirs

from . import _http

CREDITOPUBLICO = "creditopublico"
# Nombres de archivo de cada fuente; limpiar_cache() borra solo estos.
FUENTES = (CREDITOPUBLICO,)


def directorio() -> Path:
    return Path(os.environ.get("RDFIN_CACHE") or platformdirs.user_cache_dir("rdfin"))


def excel(fuente: str, url: str, *, refrescar: bool, max_edad_horas: float) -> Path:
    """Ruta del Excel de `fuente` en la caché, descargado de nuevo si hace falta.

    Se descarga si no hay copia, si `refrescar`, si la copia tiene más de
    `max_edad_horas`, si viene de otra URL o si la guardó otra versión de rdfin,
    porque la limpieza pudo cambiar. Al descargar se borra el parquet anterior.
    """
    # Se importa aquí para leer la versión al usarla; el paquete importa este
    # módulo al iniciarse.
    from . import __version__

    base = directorio()
    ruta, meta = base / f"{fuente}.xlsx", base / f"{fuente}.json"
    vigente = (
        not refrescar
        and ruta.exists()
        and meta.exists()
        and _vigente(
            json.loads(meta.read_text("utf-8")), url, __version__, max_edad_horas
        )
    )
    if not vigente:
        contenido = _http.descargar(url)
        base.mkdir(parents=True, exist_ok=True)
        parquet(fuente).unlink(missing_ok=True)
        _reemplazar(ruta, lambda temporal: temporal.write_bytes(contenido))
        datos = {
            "hora_descarga": datetime.now(timezone.utc).isoformat(),
            "url": url,
            "version_rdfin": __version__,
        }
        _reemplazar(
            meta, lambda temporal: temporal.write_text(json.dumps(datos), "utf-8")
        )
    return ruta


def _vigente(datos: dict, url: str, version: str, max_edad_horas: float) -> bool:
    edad = datetime.now(timezone.utc) - datetime.fromisoformat(datos["hora_descarga"])
    return (
        datos["url"] == url
        and datos["version_rdfin"] == version
        and edad <= timedelta(hours=max_edad_horas)
    )


def parquet(fuente: str) -> Path:
    return directorio() / f"{fuente}.parquet"


def escribir_parquet(df: pd.DataFrame, ruta: Path) -> None:
    _reemplazar(ruta, df.to_parquet)


def _reemplazar(ruta: Path, escribir) -> None:
    # Se escribe aparte y se renombra: una escritura interrumpida no deja en la
    # caché un archivo a medias.
    temporal = ruta.with_name(ruta.name + ".tmp")
    escribir(temporal)
    os.replace(temporal, ruta)


def limpiar_cache() -> None:
    """Borra los archivos que rdfin guardó en la caché."""
    for fuente in FUENTES:
        for ruta in directorio().glob(f"{fuente}.*"):
            ruta.unlink()
