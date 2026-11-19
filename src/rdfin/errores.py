"""Excepciones de rdfin."""


class RdfinError(Exception):
    """Base de todos los errores de rdfin."""


class CambioDeFormato(RdfinError):
    """El archivo de la fuente no tiene la estructura esperada."""


class ErrorDeDescarga(RdfinError):
    """La fuente no respondió o rechazó la descarga."""
