"""Algoritmos de inferencia desarrollados para el Proyecto 1."""

from .enumeracion import ResultadoEnumeracion, inferir_por_enumeracion
from .resolucion import ResultadoResolucion, inferir_por_resolucion

__all__ = [
    "ResultadoEnumeracion",
    "ResultadoResolucion",
    "inferir_por_enumeracion",
    "inferir_por_resolucion",
]
