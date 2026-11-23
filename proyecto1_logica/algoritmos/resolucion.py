"""Resolución proposicional por refutación con traza de cada resolvente."""

from collections import deque
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from nucleo.cnf import (
    Clausula,
    Literal,
    clausula_es_tautologia,
    formula_a_fnc,
)
from nucleo.estados import EstadoConsulta
from nucleo.formulas import Negacion, parsear_formula


@dataclass(frozen=True)
class ClausulaInicial:
    numero: int
    clausula: Clausula
    origen: str


@dataclass(frozen=True)
class PasoResolucion:
    numero: int
    padre_1: int
    padre_2: int
    pivote: Literal
    resolvente: Clausula
    id_resolvente: int


@dataclass(frozen=True)
class Refutacion:
    contradiccion: bool
    iniciales: tuple[ClausulaInicial, ...]
    pasos: tuple[PasoResolucion, ...]
    total_clausulas: int


@dataclass(frozen=True)
class ResultadoConsultaResolucion:
    estado: EstadoConsulta
    intento_demostrar: Refutacion
    intento_refutar: Refutacion | None


@dataclass(frozen=True)
class ResultadoResolucion:
    consistente: bool
    prueba_consistencia: Refutacion
    consultas: Mapping[str, ResultadoConsultaResolucion]


def _resolventes(c1: Clausula, c2: Clausula):
    """Genera todos los resolventes no tautológicos de dos cláusulas."""

    vistos: set[Clausula] = set()
    for literal in sorted(c1):
        complemento = literal.negado()
        if complemento not in c2:
            continue
        resolvente = frozenset((c1 - {literal}) | (c2 - {complemento}))
        if resolvente in vistos or clausula_es_tautologia(resolvente):
            continue
        vistos.add(resolvente)
        yield literal, resolvente


def resolver_por_refutacion(
    clausulas_base: Sequence[Clausula],
    soporte: Sequence[Clausula] | None = None,
    etiquetas_base: Sequence[str] | None = None,
    etiqueta_soporte: str = "Suposición para refutar",
    maximo_clausulas: int = 10_000,
) -> Refutacion:
    """Satura por resolución y se detiene si obtiene la cláusula vacía.

    Si ``soporte`` se proporciona, cada resolución incluye al menos una cláusula
    proveniente de la suposición o derivada de ella. Para comprobar consistencia,
    ``soporte`` debe ser ``None`` y todas las cláusulas entran en la cola.
    """

    clausulas: list[Clausula] = []
    indices: dict[Clausula, int] = {}
    iniciales: list[ClausulaInicial] = []

    def agregar_inicial(clausula: Clausula, origen: str) -> int:
        if clausula in indices:
            return indices[clausula]
        clausulas.append(clausula)
        numero = len(clausulas)
        indices[clausula] = numero
        iniciales.append(ClausulaInicial(numero, clausula, origen))
        return numero

    etiquetas = etiquetas_base or tuple("Base" for _ in clausulas_base)
    if len(etiquetas) != len(clausulas_base):
        raise ValueError("La cantidad de etiquetas no coincide con las cláusulas base.")

    ids_base = [
        agregar_inicial(clausula, etiqueta)
        for clausula, etiqueta in zip(clausulas_base, etiquetas)
    ]

    if soporte is None:
        cola = deque(ids_base)
    else:
        ids_soporte = [
            agregar_inicial(clausula, etiqueta_soporte) for clausula in soporte
        ]
        cola = deque(ids_soporte)

    vacia = frozenset()
    if vacia in indices:
        return Refutacion(True, tuple(iniciales), (), len(clausulas))

    pares_procesados: set[tuple[int, int]] = set()
    pasos: list[PasoResolucion] = []

    while cola:
        id_actual = cola.popleft()
        limite = len(clausulas)
        for id_otro in range(1, limite + 1):
            if id_otro == id_actual:
                continue
            par = tuple(sorted((id_actual, id_otro)))
            if par in pares_procesados:
                continue
            pares_procesados.add(par)

            c1 = clausulas[id_actual - 1]
            c2 = clausulas[id_otro - 1]
            for pivote, resolvente in _resolventes(c1, c2):
                # Subsumición: si ya existe una cláusula igual o más fuerte,
                # agregar este superconjunto no aporta ninguna refutación nueva.
                # La regla conserva completitud y reduce mucho la saturación.
                if any(existente <= resolvente for existente in clausulas):
                    continue
                clausulas.append(resolvente)
                id_nuevo = len(clausulas)
                indices[resolvente] = id_nuevo
                pasos.append(
                    PasoResolucion(
                        len(pasos) + 1,
                        id_actual,
                        id_otro,
                        pivote,
                        resolvente,
                        id_nuevo,
                    )
                )
                if not resolvente:
                    return Refutacion(
                        True, tuple(iniciales), tuple(pasos), len(clausulas)
                    )
                if len(clausulas) >= maximo_clausulas:
                    raise RuntimeError(
                        "Se alcanzó el límite de cláusulas durante la resolución."
                    )
                cola.append(id_nuevo)

    return Refutacion(False, tuple(iniciales), tuple(pasos), len(clausulas))


def inferir_por_resolucion(
    clausulas: Sequence[Clausula],
    consultas: Iterable[str],
    etiquetas: Sequence[str] | None = None,
) -> ResultadoResolucion:
    """Comprueba consistencia y clasifica consultas mediante dos refutaciones."""

    consistencia = resolver_por_refutacion(clausulas, etiquetas_base=etiquetas)
    if consistencia.contradiccion:
        return ResultadoResolucion(False, consistencia, {})

    resultados: dict[str, ResultadoConsultaResolucion] = {}
    for texto in consultas:
        consulta = parsear_formula(texto)

        # KB |= consulta si KB y la negación de la consulta son inconsistentes.
        prueba_demostrar = resolver_por_refutacion(
            clausulas,
            formula_a_fnc(Negacion(consulta)),
            etiquetas,
            f"Negación de la consulta: ~({texto})",
        )
        if prueba_demostrar.contradiccion:
            resultados[texto] = ResultadoConsultaResolucion(
                EstadoConsulta.DEMOSTRADA, prueba_demostrar, None
            )
            continue

        # KB |= ~consulta si KB y la consulta son inconsistentes.
        prueba_refutar = resolver_por_refutacion(
            clausulas,
            formula_a_fnc(consulta),
            etiquetas,
            f"Consulta asumida: {texto}",
        )
        estado = (
            EstadoConsulta.REFUTADA
            if prueba_refutar.contradiccion
            else EstadoConsulta.INDETERMINADA
        )
        resultados[texto] = ResultadoConsultaResolucion(
            estado, prueba_demostrar, prueba_refutar
        )

    return ResultadoResolucion(True, consistencia, resultados)
