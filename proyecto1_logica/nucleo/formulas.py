"""Árbol de fórmulas proposicionales y analizador de expresiones."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping


class Formula:
    def evaluar(self, modelo: Mapping[str, bool]) -> bool:
        raise NotImplementedError

    def variables(self) -> set[str]:
        raise NotImplementedError


@dataclass(frozen=True)
class Variable(Formula):
    nombre: str

    def evaluar(self, modelo: Mapping[str, bool]) -> bool:
        try:
            return bool(modelo[self.nombre])
        except KeyError as exc:
            raise ValueError(f"La variable {self.nombre!r} no está en el modelo.") from exc

    def variables(self) -> set[str]:
        return {self.nombre}


@dataclass(frozen=True)
class Negacion(Formula):
    operando: Formula

    def evaluar(self, modelo: Mapping[str, bool]) -> bool:
        return not self.operando.evaluar(modelo)

    def variables(self) -> set[str]:
        return self.operando.variables()


@dataclass(frozen=True)
class Conjuncion(Formula):
    izquierda: Formula
    derecha: Formula

    def evaluar(self, modelo: Mapping[str, bool]) -> bool:
        return self.izquierda.evaluar(modelo) and self.derecha.evaluar(modelo)

    def variables(self) -> set[str]:
        return self.izquierda.variables() | self.derecha.variables()


@dataclass(frozen=True)
class Disyuncion(Formula):
    izquierda: Formula
    derecha: Formula

    def evaluar(self, modelo: Mapping[str, bool]) -> bool:
        return self.izquierda.evaluar(modelo) or self.derecha.evaluar(modelo)

    def variables(self) -> set[str]:
        return self.izquierda.variables() | self.derecha.variables()


@dataclass(frozen=True)
class Implicacion(Formula):
    antecedente: Formula
    consecuente: Formula

    def evaluar(self, modelo: Mapping[str, bool]) -> bool:
        return (not self.antecedente.evaluar(modelo)) or self.consecuente.evaluar(modelo)

    def variables(self) -> set[str]:
        return self.antecedente.variables() | self.consecuente.variables()


@dataclass(frozen=True)
class Bicondicional(Formula):
    izquierda: Formula
    derecha: Formula

    def evaluar(self, modelo: Mapping[str, bool]) -> bool:
        return self.izquierda.evaluar(modelo) == self.derecha.evaluar(modelo)

    def variables(self) -> set[str]:
        return self.izquierda.variables() | self.derecha.variables()


_TOKEN = re.compile(r"\s*(<->|->|[()~&|]|[A-Za-z][A-Za-z0-9_]*)")


def _tokenizar(texto: str) -> list[str]:
    tokens: list[str] = []
    posicion = 0
    while posicion < len(texto):
        coincidencia = _TOKEN.match(texto, posicion)
        if not coincidencia:
            if texto[posicion:].strip() == "":
                break
            raise ValueError(
                f"Símbolo inválido en la posición {posicion} de {texto!r}."
            )
        tokens.append(coincidencia.group(1))
        posicion = coincidencia.end()
    if not tokens:
        raise ValueError("La fórmula no puede estar vacía.")
    return tokens


class _Parser:
    def __init__(self, tokens: list[str]):
        self.tokens = tokens
        self.posicion = 0

    def actual(self) -> str | None:
        if self.posicion >= len(self.tokens):
            return None
        return self.tokens[self.posicion]

    def aceptar(self, token: str) -> bool:
        if self.actual() == token:
            self.posicion += 1
            return True
        return False

    def parsear(self) -> Formula:
        formula = self.bicondicional()
        if self.actual() is not None:
            raise ValueError(f"Token inesperado: {self.actual()!r}.")
        return formula

    def bicondicional(self) -> Formula:
        formula = self.implicacion()
        while self.aceptar("<->"):
            formula = Bicondicional(formula, self.implicacion())
        return formula

    def implicacion(self) -> Formula:
        izquierda = self.disyuncion()
        if self.aceptar("->"):
            return Implicacion(izquierda, self.implicacion())
        return izquierda

    def disyuncion(self) -> Formula:
        formula = self.conjuncion()
        while self.aceptar("|"):
            formula = Disyuncion(formula, self.conjuncion())
        return formula

    def conjuncion(self) -> Formula:
        formula = self.negacion()
        while self.aceptar("&"):
            formula = Conjuncion(formula, self.negacion())
        return formula

    def negacion(self) -> Formula:
        if self.aceptar("~"):
            return Negacion(self.negacion())
        return self.primaria()

    def primaria(self) -> Formula:
        if self.aceptar("("):
            formula = self.bicondicional()
            if not self.aceptar(")"):
                raise ValueError("Falta un paréntesis de cierre.")
            return formula
        token = self.actual()
        if token is None or token in {"<->", "->", "&", "|", ")"}:
            raise ValueError(f"Se esperaba una variable y se encontró {token!r}.")
        self.posicion += 1
        return Variable(token)


def parsear_formula(texto: str) -> Formula:
    """Convierte una cadena con operadores ~, &, |, -> y <-> en una fórmula."""

    return _Parser(_tokenizar(texto)).parsear()
