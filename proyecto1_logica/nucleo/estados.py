"""Estados comunes devueltos por ambos algoritmos."""

from enum import Enum


class EstadoConsulta(str, Enum):
    DEMOSTRADA = "DEMOSTRADA"
    REFUTADA = "REFUTADA"
    INDETERMINADA = "INDETERMINADA"
