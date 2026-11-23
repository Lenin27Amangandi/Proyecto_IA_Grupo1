"""Literales, cláusulas y conversión propia de fórmulas a CNF."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .formulas import (
    Bicondicional,
    Conjuncion,
    Disyuncion,
    Formula,
    Implicacion,
    Negacion,
    Variable,
)


@dataclass(frozen=True, order=True)
class Literal:
    variable: str
    positivo: bool = True

    def negado(self) -> "Literal":
        return Literal(self.variable, not self.positivo)

    @classmethod
    def desde_texto(cls, texto: str) -> "Literal":
        limpio = texto.strip()
        if limpio.startswith(("~", "¬")):
            return cls(limpio[1:].strip(), False)
        return cls(limpio, True)

    def __str__(self) -> str:
        return self.variable if self.positivo else f"~{self.variable}"


Clausula = frozenset[Literal]


def clausula_desde_textos(literales: Iterable[str]) -> Clausula:
    return frozenset(Literal.desde_texto(literal) for literal in literales)


def clausula_es_tautologia(clausula: Clausula) -> bool:
    return any(literal.negado() in clausula for literal in clausula)


def clausula_a_texto(clausula: Clausula) -> str:
    if not clausula:
        return "□"
    return " ∨ ".join(str(literal) for literal in sorted(clausula))


def evaluar_clausulas(
    clausulas: Iterable[Clausula], modelo: Mapping[str, bool]
) -> bool:
    return all(
        any(modelo[lit.variable] == lit.positivo for lit in clausula)
        for clausula in clausulas
    )


def _sin_implicaciones(formula: Formula) -> Formula:
    if isinstance(formula, Variable):
        return formula
    if isinstance(formula, Negacion):
        return Negacion(_sin_implicaciones(formula.operando))
    if isinstance(formula, Conjuncion):
        return Conjuncion(
            _sin_implicaciones(formula.izquierda),
            _sin_implicaciones(formula.derecha),
        )
    if isinstance(formula, Disyuncion):
        return Disyuncion(
            _sin_implicaciones(formula.izquierda),
            _sin_implicaciones(formula.derecha),
        )
    if isinstance(formula, Implicacion):
        return Disyuncion(
            Negacion(_sin_implicaciones(formula.antecedente)),
            _sin_implicaciones(formula.consecuente),
        )
    if isinstance(formula, Bicondicional):
        izquierda = _sin_implicaciones(formula.izquierda)
        derecha = _sin_implicaciones(formula.derecha)
        return Conjuncion(
            Disyuncion(Negacion(izquierda), derecha),
            Disyuncion(Negacion(derecha), izquierda),
        )
    raise TypeError(f"Tipo de fórmula no soportado: {type(formula).__name__}")


def _a_nnf(formula: Formula, negar: bool = False) -> Formula:
    if isinstance(formula, Variable):
        return Negacion(formula) if negar else formula
    if isinstance(formula, Negacion):
        return _a_nnf(formula.operando, not negar)
    if isinstance(formula, Conjuncion):
        clase = Disyuncion if negar else Conjuncion
        return clase(
            _a_nnf(formula.izquierda, negar),
            _a_nnf(formula.derecha, negar),
        )
    if isinstance(formula, Disyuncion):
        clase = Conjuncion if negar else Disyuncion
        return clase(
            _a_nnf(formula.izquierda, negar),
            _a_nnf(formula.derecha, negar),
        )
    raise ValueError("Primero deben eliminarse implicaciones y bicondicionales.")


def _unicas(clausulas: Iterable[Clausula]) -> list[Clausula]:
    resultado: list[Clausula] = []
    vistas: set[Clausula] = set()
    for clausula in clausulas:
        if clausula_es_tautologia(clausula) or clausula in vistas:
            continue
        vistas.add(clausula)
        resultado.append(clausula)
    return resultado


def _distribuir(
    izquierda: Iterable[Clausula], derecha: Iterable[Clausula]
) -> list[Clausula]:
    return _unicas(
        frozenset(set(c1) | set(c2)) for c1 in izquierda for c2 in derecha
    )


def _nnf_a_fnc(formula: Formula) -> list[Clausula]:
    if isinstance(formula, Variable):
        return [frozenset({Literal(formula.nombre)})]
    if isinstance(formula, Negacion) and isinstance(formula.operando, Variable):
        return [frozenset({Literal(formula.operando.nombre, False)})]
    if isinstance(formula, Conjuncion):
        return _unicas(
            _nnf_a_fnc(formula.izquierda) + _nnf_a_fnc(formula.derecha)
        )
    if isinstance(formula, Disyuncion):
        return _distribuir(
            _nnf_a_fnc(formula.izquierda), _nnf_a_fnc(formula.derecha)
        )
    raise ValueError("La fórmula no está en forma normal negativa.")


def formula_a_fnc(formula: Formula) -> tuple[Clausula, ...]:
    """Convierte una fórmula arbitraria a una tupla de cláusulas CNF."""

    return tuple(_nnf_a_fnc(_a_nnf(_sin_implicaciones(formula))))
