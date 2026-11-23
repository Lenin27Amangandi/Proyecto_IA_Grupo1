"""Lectura validada de datos separados de los algoritmos de inferencia y funciones de extensión."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import json
from pathlib import Path
import re
from typing import Iterable

from nucleo.cnf import (
    Clausula,
    Literal,
    clausula_desde_textos,
    formula_a_fnc,
)
from nucleo.estados import EstadoConsulta
from nucleo.formulas import Formula, parsear_formula
from algoritmos.enumeracion import enumerar_modelos
from algoritmos.resolucion import inferir_por_resolucion, resolver_por_refutacion


RAIZ_CASOS = Path(__file__).resolve().parent.parent / "casos_prueba"
RUTA_EXTENSIONES = RAIZ_CASOS / "base_conocimiento_extensiones.json"


@dataclass(frozen=True)
class Regla:
    identificador: str
    descripcion: str
    formula: str
    fnc: tuple[Clausula, ...]


@dataclass(frozen=True)
class BaseConocimiento:
    variables: tuple[str, ...]
    significados: dict[str, str]
    reglas: tuple[Regla, ...]


@dataclass(frozen=True)
class CasoPrueba:
    identificador: str
    nombre: str
    proposito: str
    evidencia: tuple[str, ...]
    consultas: tuple[str, ...]
    esperados: dict[str, str]
    modelos_esperados: int


@dataclass(frozen=True)
class ResultadoValidacion:
    consistente: bool
    total_modelos: int
    asignaciones_examinadas: int
    total_clausulas_resolucion: int
    contradiccion_encontrada: bool
    clausula_vacia: bool
    detalle: str
    diagnostico: str


@dataclass(frozen=True)
class DiagnosticoCulpabilidad:
    consistente: bool
    estado: str  # CULPABLE_ENCONTRADO, MULTIPLES_SOLUCIONES, CONTRADICCION, FALTA_INFORMACION
    culpable: str | None
    culpable_nombre: str | None
    posibles_culpables: tuple[str, ...]
    sospechosos_descartados: tuple[str, ...]
    mensaje: str
    modelos_compatibles: int
    clausula_vacia: bool
    detalle_consultas: dict[str, str]


def _leer_json(ruta: Path) -> dict:
    with ruta.open("r", encoding="utf-8") as archivo:
        return json.load(archivo)


def cargar_base() -> BaseConocimiento:
    datos = _leer_json(RAIZ_CASOS / "base_conocimiento.json")
    reglas = []
    for item in datos["reglas"]:
        reglas.append(
            Regla(
                item["id"],
                item["descripcion"],
                item["formula"],
                tuple(clausula_desde_textos(c) for c in item["fnc"]),
            )
        )
    return BaseConocimiento(
        tuple(datos["variables"]), dict(datos["significados"]), tuple(reglas)
    )


def extensiones_vacias() -> dict:
    """Estructura persistente que mantiene los cambios separados de la base original."""
    return {"version": 1, "sospechosos": [], "reglas": []}


def cargar_extensiones() -> dict:
    if not RUTA_EXTENSIONES.exists():
        return extensiones_vacias()
    datos = _leer_json(RUTA_EXTENSIONES)
    return {
        "version": int(datos.get("version", 1)),
        "sospechosos": list(datos.get("sospechosos", [])),
        "reglas": list(datos.get("reglas", [])),
    }


def _guardar_extensiones(datos: dict) -> None:
    temporal = RUTA_EXTENSIONES.with_suffix(".tmp")
    with temporal.open("w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, ensure_ascii=False, indent=2)
        archivo.write("\n")
    temporal.replace(RUTA_EXTENSIONES)


def cargar_base_personalizada() -> BaseConocimiento:
    """Carga la base original y reproduce, en orden, las extensiones guardadas."""
    base = cargar_base()
    extensiones = cargar_extensiones()
    for item in extensiones["sospechosos"]:
        base = agregar_sospechoso(
            base,
            item["variable"],
            item["nombre"],
            bool(item.get("actualizar_reglas_culpable", True)),
        )
    for item in extensiones["reglas"]:
        base = agregar_regla(
            base,
            item["id"],
            item.get("descripcion", ""),
            item["formula"],
        )
        significados = item.get("significados", {})
        if significados:
            nuevos_significados = dict(base.significados)
            nuevos_significados.update(
                {str(variable): str(significado) for variable, significado in significados.items()}
            )
            base = BaseConocimiento(base.variables, nuevos_significados, base.reglas)
    return base


def guardar_sospechoso(
    variable: str,
    nombre: str,
    actualizar_reglas_culpable: bool = True,
) -> BaseConocimiento:
    """Valida y persiste un sospechoso como extensión, sin modificar el JSON original."""
    variable = variable.strip().upper()
    nombre = nombre.strip()
    if not nombre:
        raise ValueError("El nombre del sospechoso no puede estar vacío.")
    base = cargar_base_personalizada()
    if variable in base.variables:
        raise ValueError(f"La variable {variable!r} ya existe en la base.")
    base_nueva = agregar_sospechoso(
        base, variable, nombre, actualizar_reglas_culpable
    )
    extensiones = cargar_extensiones()
    extensiones["sospechosos"].append(
        {
            "variable": variable,
            "nombre": nombre,
            "actualizar_reglas_culpable": bool(actualizar_reglas_culpable),
        }
    )
    _guardar_extensiones(extensiones)
    return base_nueva


def guardar_regla(
    identificador: str,
    descripcion: str,
    formula: str,
    significados: dict[str, str] | None = None,
) -> BaseConocimiento:
    """Valida y persiste una regla y los significados de sus variables nuevas."""
    identificador = identificador.strip().upper()
    base = cargar_base_personalizada()
    base_nueva = agregar_regla(base, identificador, descripcion, formula)
    significados_limpios = {
        str(variable).strip().upper(): str(significado).strip()
        for variable, significado in (significados or {}).items()
        if str(variable).strip() and str(significado).strip()
    }
    if significados_limpios:
        variables_formula = set(parsear_formula(formula).variables())
        ajenas = set(significados_limpios) - variables_formula
        if ajenas:
            raise ValueError(
                "Los significados contienen variables ajenas a la fórmula: "
                + ", ".join(sorted(ajenas))
            )
        originales = set(significados_limpios) & set(base.variables)
        if originales:
            raise ValueError(
                "Solo puede definir el significado de variables nuevas: "
                + ", ".join(sorted(originales))
            )
        nuevos_significados = dict(base_nueva.significados)
        nuevos_significados.update(significados_limpios)
        base_nueva = BaseConocimiento(
            base_nueva.variables, nuevos_significados, base_nueva.reglas
        )
    extensiones = cargar_extensiones()
    extensiones["reglas"].append(
        {
            "id": identificador,
            "descripcion": descripcion.strip() or f"Regla {identificador}",
            "formula": formula.strip(),
            "significados": significados_limpios,
        }
    )
    _guardar_extensiones(extensiones)
    return base_nueva


def restablecer_base_original() -> BaseConocimiento:
    """Elimina todas las extensiones persistidas y devuelve la base original."""
    _guardar_extensiones(extensiones_vacias())
    return cargar_base()


def base_a_dict(base: BaseConocimiento, extensiones: dict | None = None) -> dict:
    """Serializa una base para la API web, incluyendo el origen de cada elemento."""
    extensiones = extensiones or extensiones_vacias()
    ids_agregados = {item["id"] for item in extensiones["reglas"]}
    variables_agregadas = {
        item["variable"] for item in extensiones["sospechosos"]
    }
    variables_agregadas.update(set(base.variables) - set(cargar_base().variables))
    for item in extensiones["reglas"]:
        variables_agregadas.update(item.get("significados", {}).keys())
    hay_sospechosos = bool(extensiones["sospechosos"])
    reglas = []
    for regla in base.reglas:
        origen = "agregada" if regla.identificador in ids_agregados else "original"
        if hay_sospechosos and regla.identificador in {"E1", "E2"}:
            origen = "original_modificada"
        reglas.append(
            {
                "id": regla.identificador,
                "descripcion": regla.descripcion,
                "formula": regla.formula,
                "fnc": [
                    [str(literal) for literal in sorted(clausula)]
                    for clausula in regla.fnc
                ],
                "origen": origen,
            }
        )
    return {
        "variables": list(base.variables),
        "significados": dict(base.significados),
        "origen_variables": {
            variable: ("agregada" if variable in variables_agregadas else "original")
            for variable in base.variables
        },
        "reglas": reglas,
    }


def casos_a_dict(casos: Iterable[CasoPrueba]) -> list[dict]:
    return [
        {
            "id": caso.identificador,
            "nombre": caso.nombre,
            "proposito": caso.proposito,
            "evidencia": list(caso.evidencia),
            "consultas": list(caso.consultas),
            "modelos_esperados": caso.modelos_esperados,
        }
        for caso in casos
    ]


def cargar_casos() -> tuple[CasoPrueba, ...]:
    casos = []
    for ruta in sorted(RAIZ_CASOS.glob("caso_*.json")):
        datos = _leer_json(ruta)
        casos.append(
            CasoPrueba(
                datos["id"],
                datos["nombre"],
                datos["proposito"],
                tuple(datos["evidencia"]),
                tuple(datos["consultas"]),
                dict(datos["esperados"]),
                int(datos["modelos_esperados"]),
            )
        )
    return tuple(casos)


def clausulas_del_escenario(
    base: BaseConocimiento,
    caso: CasoPrueba,
    evidencia_extra: Iterable[str] = (),
) -> tuple[tuple[Clausula, ...], tuple[str, ...]]:
    clausulas: list[Clausula] = []
    etiquetas: list[str] = []
    for regla in base.reglas:
        for indice, clausula in enumerate(regla.fnc, start=1):
            sufijo = f".{indice}" if len(regla.fnc) > 1 else ""
            clausulas.append(clausula)
            etiquetas.append(f"{regla.identificador}{sufijo}")

    for literal in (*caso.evidencia, *tuple(evidencia_extra)):
        clausulas.append(clausula_desde_textos([literal]))
        etiquetas.append(f"Evidencia {literal}")

    return tuple(clausulas), tuple(etiquetas)


def agregar_sospechoso(
    base: BaseConocimiento,
    variable: str,
    nombre: str,
    actualizar_reglas_culpable: bool = True,
) -> BaseConocimiento:
    """Añade un nuevo sospechoso a la base de conocimiento.

    Si ``actualizar_reglas_culpable`` es True, actualiza las reglas E1 y E2:
      - E1 (al menos uno): s1 | s2 | ... | sN
      - E2 (a lo sumo uno): ~(si & sj) para todo par de sospechosos
    """
    variable = variable.strip()
    if not variable:
        raise ValueError("La variable del sospechoso no puede estar vacía.")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", variable):
        raise ValueError(
            "La variable debe comenzar con una letra y contener solo letras, números o _."
        )

    # Sospechosos actuales a partir de E1 o variables iniciales D, E, F
    sospechosos_actuales: list[str] = []
    regla_e1 = next((r for r in base.reglas if r.identificador == "E1"), None)
    if regla_e1 and regla_e1.fnc:
        for lit in regla_e1.fnc[0]:
            if lit.positivo and lit.variable not in sospechosos_actuales:
                sospechosos_actuales.append(lit.variable)
    else:
        for v in ("D", "E", "F"):
            if v in base.variables and v not in sospechosos_actuales:
                sospechosos_actuales.append(v)

    if variable not in sospechosos_actuales:
        sospechosos_actuales.append(variable)

    nuevas_variables = list(base.variables)
    if variable not in nuevas_variables:
        nuevas_variables.append(variable)

    nuevos_significados = dict(base.significados)
    desc_sospechoso = nombre.strip()
    if not desc_sospechoso.lower().endswith("la laptop"):
        desc_sospechoso = f"{desc_sospechoso} tomó la laptop"
    nuevos_significados[variable] = desc_sospechoso

    nuevas_reglas: list[Regla] = []
    for regla in base.reglas:
        if actualizar_reglas_culpable and regla.identificador == "E1":
            formula_e1 = " | ".join(sorted(sospechosos_actuales))
            fnc_e1 = (frozenset(Literal(s, True) for s in sospechosos_actuales),)
            nuevas_reglas.append(
                Regla(
                    identificador="E1",
                    descripcion=f"Alguien tomó la laptop y fue uno de: {', '.join(sorted(sospechosos_actuales))}.",
                    formula=formula_e1,
                    fnc=fnc_e1,
                )
            )
        elif actualizar_reglas_culpable and regla.identificador == "E2":
            pares = list(combinations(sorted(sospechosos_actuales), 2))
            formula_e2 = " & ".join(f"~({s1} & {s2})" for s1, s2 in pares)
            fnc_e2 = tuple(
                frozenset({Literal(s1, False), Literal(s2, False)})
                for s1, s2 in pares
            )
            nuevas_reglas.append(
                Regla(
                    identificador="E2",
                    descripcion="Fue una sola persona.",
                    formula=formula_e2,
                    fnc=fnc_e2,
                )
            )
        else:
            nuevas_reglas.append(regla)

    return BaseConocimiento(
        variables=tuple(nuevas_variables),
        significados=nuevos_significados,
        reglas=tuple(nuevas_reglas),
    )


def agregar_regla(
    base: BaseConocimiento,
    identificador: str,
    descripcion: str,
    formula: str | Formula,
) -> BaseConocimiento:
    """Añade una regla proposicional a la base de conocimiento."""
    identificador = identificador.strip()
    if not identificador:
        raise ValueError("El identificador de la regla no puede estar vacío.")
    if any(r.identificador == identificador for r in base.reglas):
        raise ValueError(f"Ya existe una regla con identificador {identificador!r}.")

    if isinstance(formula, str):
        formula_arbol = parsear_formula(formula)
        formula_texto = formula.strip()
    else:
        formula_arbol = formula
        formula_texto = str(formula)

    fnc = formula_a_fnc(formula_arbol)

    nuevas_variables = list(base.variables)
    nuevos_significados = dict(base.significados)
    for var in sorted(formula_arbol.variables()):
        if var not in nuevas_variables:
            nuevas_variables.append(var)
        if var not in nuevos_significados:
            nuevos_significados[var] = f"Variable {var}"

    nueva_regla = Regla(
        identificador=identificador,
        descripcion=descripcion.strip() or f"Regla {identificador}",
        formula=formula_texto,
        fnc=fnc,
    )

    return BaseConocimiento(
        variables=tuple(nuevas_variables),
        significados=nuevos_significados,
        reglas=(*base.reglas, nueva_regla),
    )


def validar_consistencia(
    base: BaseConocimiento,
    evidencia: Iterable[str] = (),
    metodo: str = "ambos",
) -> ResultadoValidacion:
    """Valida si la base de conocimiento es consistente o contradictoria."""
    clausulas: list[Clausula] = []
    etiquetas: list[str] = []
    for regla in base.reglas:
        for idx, c in enumerate(regla.fnc, start=1):
            sufijo = f".{idx}" if len(regla.fnc) > 1 else ""
            clausulas.append(c)
            etiquetas.append(f"{regla.identificador}{sufijo}")
    for lit in evidencia:
        clausulas.append(clausula_desde_textos([lit]))
        etiquetas.append(f"Evidencia {lit}")

    clausulas_tupla = tuple(clausulas)
    asignaciones = 2 ** len(base.variables)

    refutacion = resolver_por_refutacion(clausulas_tupla, etiquetas_base=etiquetas)
    resolucion_contradiccion = refutacion.contradiccion

    num_modelos = 0
    if len(base.variables) <= 20 and metodo in ("ambos", "enumeracion"):
        modelos = enumerar_modelos(base.variables, clausulas_tupla)
        num_modelos = len(modelos)
    else:
        num_modelos = 0 if resolucion_contradiccion else -1

    consistente = not resolucion_contradiccion and (num_modelos > 0 if num_modelos != -1 else True)

    if not consistente or resolucion_contradiccion:
        detalle = "Se derivó la cláusula vacía (□) mediante resolución. La base de conocimiento contiene información contradictoria."
        diagnostico = "INCONSISTENTE (Contradicción detectada)"
    else:
        detalle = f"La base es consistente con {num_modelos} modelos compatibles de {asignaciones} asignaciones posibles."
        diagnostico = "CONSISTENTE"

    return ResultadoValidacion(
        consistente=consistente,
        total_modelos=num_modelos,
        asignaciones_examinadas=asignaciones,
        total_clausulas_resolucion=refutacion.total_clausulas,
        contradiccion_encontrada=resolucion_contradiccion,
        clausula_vacia=resolucion_contradiccion,
        detalle=detalle,
        diagnostico=diagnostico,
    )


def validar_adicion(
    base: BaseConocimiento,
    nuevo_sospechoso: tuple[str, str] | None = None,
    nueva_regla: tuple[str, str, str] | None = None,
    evidencia: Iterable[str] = (),
) -> tuple[BaseConocimiento, ResultadoValidacion]:
    """Añade un sospechoso y/o regla a la base y valida de inmediato si la base resultante es consistente."""
    base_actual = base
    if nuevo_sospechoso:
        var, nom = nuevo_sospechoso
        base_actual = agregar_sospechoso(base_actual, var, nom)
    if nueva_regla:
        rid, desc, formula = nueva_regla
        base_actual = agregar_regla(base_actual, rid, desc, formula)
    validacion = validar_consistencia(base_actual, evidencia)
    return base_actual, validacion


def diagnosticar_culpabilidad(
    base: BaseConocimiento,
    evidencia: Iterable[str] = (),
    sospechosos: Iterable[str] | None = None,
) -> DiagnosticoCulpabilidad:
    """Determina explícitamente el estado de la investigación y la existencia o no de culpable."""
    validacion = validar_consistencia(base, evidencia)

    if sospechosos is None:
        lista_sospechosos = []
        regla_e1 = next((r for r in base.reglas if r.identificador == "E1"), None)
        if regla_e1 and regla_e1.fnc:
            for lit in regla_e1.fnc[0]:
                if lit.positivo and lit.variable not in lista_sospechosos:
                    lista_sospechosos.append(lit.variable)
        else:
            for v in ("D", "E", "F"):
                if v in base.variables:
                    lista_sospechosos.append(v)
    else:
        lista_sospechosos = list(sospechosos)

    if not validacion.consistente or validacion.clausula_vacia:
        return DiagnosticoCulpabilidad(
            consistente=False,
            estado="CONTRADICCION",
            culpable=None,
            culpable_nombre=None,
            posibles_culpables=(),
            sospechosos_descartados=tuple(lista_sospechosos),
            mensaje="Se llega a una contradicción (se derivó la cláusula vacía □). La base de conocimiento es inconsistente y la evidencia o reglas son incompatibles.",
            modelos_compatibles=0,
            clausula_vacia=True,
            detalle_consultas={},
        )

    clausulas: list[Clausula] = []
    etiquetas: list[str] = []
    for regla in base.reglas:
        for idx, c in enumerate(regla.fnc, start=1):
            sufijo = f".{idx}" if len(regla.fnc) > 1 else ""
            clausulas.append(c)
            etiquetas.append(f"{regla.identificador}{sufijo}")
    for lit in evidencia:
        clausulas.append(clausula_desde_textos([lit]))
        etiquetas.append(f"Evidencia {lit}")

    resultado_resolucion = inferir_por_resolucion(clausulas, lista_sospechosos, etiquetas)
    estados: dict[str, str] = {
        s: resultado_resolucion.consultas[s].estado.value
        for s in lista_sospechosos
    }

    demostrados = [s for s in lista_sospechosos if estados[s] == EstadoConsulta.DEMOSTRADA.value]
    indeterminados = [s for s in lista_sospechosos if estados[s] == EstadoConsulta.INDETERMINADA.value]
    descartados = [s for s in lista_sospechosos if estados[s] == EstadoConsulta.REFUTADA.value]

    if len(demostrados) == 1:
        culpable_var = demostrados[0]
        nombre = base.significados.get(culpable_var, culpable_var)
        return DiagnosticoCulpabilidad(
            consistente=True,
            estado="CULPABLE_ENCONTRADO",
            culpable=culpable_var,
            culpable_nombre=nombre,
            posibles_culpables=(culpable_var,),
            sospechosos_descartados=tuple(descartados),
            mensaje=f"La base de conocimiento es consistente y se encontró un culpable: {nombre} ({culpable_var}).",
            modelos_compatibles=validacion.total_modelos,
            clausula_vacia=False,
            detalle_consultas=estados,
        )
    elif len(indeterminados) > 1:
        nombres = [f"{base.significados.get(s, s)} ({s})" for s in indeterminados]
        return DiagnosticoCulpabilidad(
            consistente=True,
            estado="MULTIPLES_SOLUCIONES",
            culpable=None,
            culpable_nombre=None,
            posibles_culpables=tuple(indeterminados),
            sospechosos_descartados=tuple(descartados),
            mensaje=(
                f"La base de conocimiento es consistente y no es posible encontrar un único culpable "
                f"(el estado de la base llega a {len(indeterminados)} posibles soluciones: {', '.join(nombres)}). "
                f"Falta información o evidencia para discriminar entre ellos."
            ),
            modelos_compatibles=validacion.total_modelos,
            clausula_vacia=False,
            detalle_consultas=estados,
        )
    elif len(demostrados) == 0 and len(indeterminados) == 1:
        culpable_var = indeterminados[0]
        nombre = base.significados.get(culpable_var, culpable_var)
        return DiagnosticoCulpabilidad(
            consistente=True,
            estado="CULPABLE_ENCONTRADO",
            culpable=culpable_var,
            culpable_nombre=nombre,
            posibles_culpables=(culpable_var,),
            sospechosos_descartados=tuple(descartados),
            mensaje=f"La base de conocimiento es consistente y se determinó el culpable por exclusión: {nombre} ({culpable_var}).",
            modelos_compatibles=validacion.total_modelos,
            clausula_vacia=False,
            detalle_consultas=estados,
        )
    else:
        return DiagnosticoCulpabilidad(
            consistente=True,
            estado="FALTA_INFORMACION",
            culpable=None,
            culpable_nombre=None,
            posibles_culpables=tuple(indeterminados),
            sospechosos_descartados=tuple(descartados),
            mensaje="La base de conocimiento es consistente pero falta información suficiente para deducir al culpable.",
            modelos_compatibles=validacion.total_modelos,
            clausula_vacia=False,
            detalle_consultas=estados,
        )
