"""Descarga de archivos de la fuente, con reintentos."""

import time

import httpx

from .errores import ErrorDeDescarga

REPOSITORIO = "https://github.com/estescobar/rdfin"
INTENTOS = 3
TIEMPO_DE_ESPERA_S = 60


def descargar(url: str) -> bytes:
    """Contenido de `url`.

    Reintenta ante errores de conexión y respuestas 429 o 5xx, con esperas de 1 s y
    2 s. Cualquier otro 4xx falla de inmediato.
    """
    # Se importa aquí porque el paquete importa este módulo al iniciarse.
    from . import __version__

    # Identifica a rdfin ante el servidor de la fuente y dice dónde averiguar más.
    agente = f"rdfin/{__version__} (+{REPOSITORIO})"
    with httpx.Client(
        headers={"User-Agent": agente},
        follow_redirects=True,
        timeout=TIEMPO_DE_ESPERA_S,
    ) as cliente:
        for intento in range(1, INTENTOS + 1):
            try:
                respuesta = cliente.get(url)
            except httpx.TransportError as error:
                causa = f"{type(error).__name__}: {error}"
            else:
                if respuesta.is_success:
                    return respuesta.content
                causa = f"HTTP {respuesta.status_code}"
                if respuesta.status_code != 429 and respuesta.status_code < 500:
                    raise ErrorDeDescarga(f"{url} respondió {causa}.")
            if intento < INTENTOS:
                time.sleep(2 ** (intento - 1))
    raise ErrorDeDescarga(
        f"No se pudo descargar {url} tras {INTENTOS} intentos. Último error: {causa}."
    )
