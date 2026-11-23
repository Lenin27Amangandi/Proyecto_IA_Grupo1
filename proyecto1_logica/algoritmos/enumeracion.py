"""Inferencia proposicional por enumeración exhaustiva de modelos."""

from dataclasses import dataclass
from itertools import product
from typing import Iterable, Mapping, Sequence

from nucleo.cnf import Clausula, evaluar_clausulas
from nucleo.estados import EstadoConsulta
from nucleo.formulas import Formula, parsear_formula


@dataclass(frozen=True)
class ResultadoEnumeracion:
    consistente: bool
    asignaciones_examinadas: int
    modelos: tuple[dict[str, bool], ...]
    consultas: Mapping[str, EstadoConsulta]


def enumerar_modelos(
    variables: Sequence[str], clausulas: Iterable[Clausula]
) -> tuple[dict[str, bool], ...]:
    """Devuelve todas las asignaciones que satisfacen la base de conocimiento."""

    base = tuple(clausulas)
    modelos: list[dict[str, bool]] = []
    for valores in product((False, True), repeat=len(variables)):
        modelo = dict(zip(variables, valores))
        if evaluar_clausulas(base, modelo):
            modelos.append(modelo)
    return tuple(modelos)


def clasificar_en_modelos(
    modelos: Sequence[Mapping[str, bool]], consulta: Formula
) -> EstadoConsulta:
    """Clasifica una fórmula como demostrada, refutada o indeterminada."""

    valores = tuple(consulta.evaluar(modelo) for modelo in modelos)
    if all(valores):
        return EstadoConsulta.DEMOSTRADA
    if not any(valores):
        return EstadoConsulta.REFUTADA
    return EstadoConsulta.INDETERMINADA


def inferir_por_enumeracion(
    variables: Sequence[str],
    clausulas: Iterable[Clausula],
    consultas: Iterable[str],
) -> ResultadoEnumeracion:
    """Verifica consistencia y responde todas las consultas por enumeración."""

    modelos = enumerar_modelos(variables, clausulas)
    total = 2 ** len(variables)
    if not modelos:
        return ResultadoEnumeracion(False, total, (), {})

    resultados = {
        texto: clasificar_en_modelos(modelos, parsear_formula(texto))
        for texto in consultas
    }
    return ResultadoEnumeracion(True, total, modelos, resultados)
