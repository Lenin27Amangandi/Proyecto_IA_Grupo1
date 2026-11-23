"""Interfaz de consola para ejecutar y demostrar el Proyecto 1."""

from __future__ import annotations

import argparse
import http.server
import json
import sys
from pathlib import Path
from typing import Iterable

from algoritmos.enumeracion import ResultadoEnumeracion, inferir_por_enumeracion
from algoritmos.resolucion import (
    Refutacion,
    ResultadoResolucion,
    inferir_por_resolucion,
)
from datos.cargador import (
    CasoPrueba,
    agregar_regla,
    agregar_sospechoso,
    base_a_dict,
    cargar_base_personalizada,
    cargar_base,
    cargar_casos,
    cargar_extensiones,
    casos_a_dict,
    clausulas_del_escenario,
    diagnosticar_culpabilidad,
    guardar_regla,
    guardar_sospechoso,
    restablecer_base_original,
    validar_consistencia,
)
from nucleo.cnf import clausula_a_texto


def _crear_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inferencia por enumeración y resolución por refutación."
    )
    parser.add_argument(
        "--caso",
        default="todos",
        help="caso_1, caso_2, caso_3, caso_4 o todos (predeterminado)",
    )
    parser.add_argument(
        "--metodo",
        choices=("ambos", "enumeracion", "resolucion"),
        default="ambos",
    )
    parser.add_argument(
        "--consulta",
        action="append",
        help="Reemplaza las consultas del JSON; puede repetirse.",
    )
    parser.add_argument(
        "--evidencia",
        action="append",
        default=[],
        help="Agrega un literal, por ejemplo K o ~K; puede repetirse.",
    )
    parser.add_argument(
        "--sospechoso",
        nargs=2,
        action="append",
        metavar=("VAR", "NOMBRE"),
        help="Añade un sospechoso (ej: --sospechoso G Gabriel)",
    )
    parser.add_argument(
        "--regla",
        nargs="+",
        action="append",
        metavar="PARAM",
        help="Añade una regla (ej: --regla R9 'G -> K' 'Gabriel tenía la llave')",
    )
    parser.add_argument(
        "--validar",
        action="store_true",
        help="Solo valida consistencia de la base con las modificaciones indicadas.",
    )
    parser.add_argument(
        "--traza",
        action="store_true",
        help="Muestra modelos y la prueba de resolución de la primera consulta.",
    )
    parser.add_argument(
        "--servidor",
        nargs="?",
        const=8000,
        type=int,
        metavar="PUERTO",
        help="Inicia un servidor local para abrir index.html (predeterminado: 8000).",
    )
    return parser.parse_args()


def _imprimir_modelos(resultado: ResultadoEnumeracion, variables: Iterable[str]) -> None:
    variables = tuple(variables)
    print("\n  Modelos compatibles (1=verdadero, 0=falso):")
    print("  #  " + " ".join(f"{variable:>2}" for variable in variables))
    for numero, modelo in enumerate(resultado.modelos, start=1):
        valores = " ".join(f"{int(modelo[variable]):>2}" for variable in variables)
        print(f"  {numero:>2} {valores}")


def _imprimir_refutacion(prueba: Refutacion) -> None:
    print("\n  Cláusulas iniciales:")
    for inicial in prueba.iniciales:
        print(
            f"  C{inicial.numero:<3} {clausula_a_texto(inicial.clausula):<25} "
            f"[{inicial.origen}]"
        )
    print("\n  Pasos de resolución:")
    if not prueba.pasos:
        print("  (no se generaron resolventes nuevos)")
    for paso in prueba.pasos:
        print(
            f"  R{paso.numero:<3} C{paso.padre_1} + C{paso.padre_2} "
            f"(pivote {paso.pivote.variable}) -> C{paso.id_resolvente}: "
            f"{clausula_a_texto(paso.resolvente)}"
        )
    final = "se obtuvo □" if prueba.contradiccion else "saturación sin □"
    print(f"\n  Resultado de la refutación: {final}.")


def _ejecutar_caso(caso: CasoPrueba, args: argparse.Namespace) -> None:
    base = cargar_base_personalizada()

    # Aplicar sospechosos y reglas extras si se pasaron por CLI
    if args.sospechoso:
        for var, nom in args.sospechoso:
            base = agregar_sospechoso(base, var, nom)
    if args.regla:
        for item in args.regla:
            rid = item[0]
            formula = item[1]
            desc = item[2] if len(item) > 2 else f"Regla {rid}"
            base = agregar_regla(base, rid, desc, formula)

    clausulas, etiquetas = clausulas_del_escenario(base, caso, args.evidencia)
    consultas = tuple(args.consulta) if args.consulta else caso.consultas
    evidencia = (*caso.evidencia, *tuple(args.evidencia))

    print("\n" + "=" * 78)
    print(f"{caso.identificador.upper()}: {caso.nombre}")
    print(f"Propósito: {caso.proposito}")
    print(f"Evidencia: {', '.join(evidencia) if evidencia else '(ninguna)'}")

    if args.validar:
        val = validar_consistencia(base, evidencia)
        print(f"\nValidación de consistencia: {val.diagnostico}")
        print(f"Detalle: {val.detalle}")
        return

    enumeracion = None
    resolucion = None
    if args.metodo in ("ambos", "enumeracion"):
        enumeracion = inferir_por_enumeracion(
            base.variables, clausulas, consultas
        )
        estado = "CONSISTENTE" if enumeracion.consistente else "INCONSISTENTE"
        print(
            f"\nEnumeración: {estado}; {len(enumeracion.modelos)} modelos de "
            f"{enumeracion.asignaciones_examinadas} asignaciones."
        )

    if args.metodo in ("ambos", "resolucion"):
        resolucion = inferir_por_resolucion(clausulas, consultas, etiquetas)
        estado = "CONSISTENTE" if resolucion.consistente else "INCONSISTENTE"
        print(
            f"Resolución: {estado}; "
            f"{resolucion.prueba_consistencia.total_clausulas} cláusulas al saturar."
        )

    diagnostico = diagnosticar_culpabilidad(base, evidencia)
    print("\nDIAGNÓSTICO EXPLICITO:")
    print(f"  * {diagnostico.mensaje}")

    if (enumeracion and not enumeracion.consistente) or (
        resolucion and not resolucion.consistente
    ):
        print("La base es contradictoria; no se clasifican consultas.")
        if args.traza and resolucion:
            _imprimir_refutacion(resolucion.prueba_consistencia)
        return

    if consultas:
        print("\nConsultas:")
        for consulta in consultas:
            e = enumeracion.consultas[consulta].value if enumeracion else "-"
            r = resolucion.consultas[consulta].estado.value if resolucion else "-"
            coincide = "sí" if not enumeracion or not resolucion or e == r else "NO"
            print(
                f"  {consulta:<16} enumeración={e:<14} "
                f"resolución={r:<14} coinciden={coincide}"
            )

    if args.traza and enumeracion:
        _imprimir_modelos(enumeracion, base.variables)
    if args.traza and resolucion and consultas:
        detalle = resolucion.consultas[consultas[0]]
        if detalle.estado.value == "DEMOSTRADA":
            prueba = detalle.intento_demostrar
        else:
            prueba = detalle.intento_refutar or detalle.intento_demostrar
        print(f"\nTraza para la consulta {consultas[0]!r} ({detalle.estado.value}):")
        _imprimir_refutacion(prueba)


def _iniciar_servidor(puerto: int) -> None:
    directorio = Path(__file__).resolve().parent

    class Manejador(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directorio), **kwargs)

        def _enviar_json(self, datos: dict, estado: int = 200) -> None:
            contenido = json.dumps(datos, ensure_ascii=False).encode("utf-8")
            self.send_response(estado)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(contenido)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(contenido)

        def _leer_cuerpo_json(self) -> dict:
            longitud = int(self.headers.get("Content-Length", "0"))
            if longitud <= 0:
                return {}
            return json.loads(self.rfile.read(longitud).decode("utf-8"))

        def _estado(self) -> dict:
            extensiones = cargar_extensiones()
            return {
                "base_original": base_a_dict(cargar_base()),
                "base_activa": base_a_dict(
                    cargar_base_personalizada(), extensiones
                ),
                "extensiones": extensiones,
                "casos": casos_a_dict(cargar_casos()),
            }

        def do_GET(self) -> None:
            if self.path.split("?", 1)[0] == "/api/estado":
                self._enviar_json(self._estado())
                return
            super().do_GET()

        def do_POST(self) -> None:
            ruta = self.path.split("?", 1)[0]
            try:
                datos = self._leer_cuerpo_json()
                if ruta == "/api/sospechosos":
                    guardar_sospechoso(
                        str(datos.get("variable", "")),
                        str(datos.get("nombre", "")),
                        bool(datos.get("actualizar_reglas_culpable", True)),
                    )
                elif ruta == "/api/reglas":
                    guardar_regla(
                        str(datos.get("id", "")),
                        str(datos.get("descripcion", "")),
                        str(datos.get("formula", "")),
                        dict(datos.get("significados", {})),
                    )
                elif ruta == "/api/restablecer":
                    restablecer_base_original()
                else:
                    self._enviar_json(
                        {"ok": False, "error": "Ruta de API desconocida."}, 404
                    )
                    return
                self._enviar_json({"ok": True, **self._estado()})
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
                self._enviar_json({"ok": False, "error": str(error)}, 400)

        def log_message(self, formato: str, *args: object) -> None:
            if self.path.startswith("/api/"):
                return
            super().log_message(formato, *args)

    print(f"Servidor web iniciado en http://localhost:{puerto}/index.html")
    print("Presione Ctrl+C para detener el servidor.")
    with http.server.ThreadingHTTPServer(("", puerto), Manejador) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor detenido.")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = _crear_argumentos()

    if args.servidor is not None:
        _iniciar_servidor(args.servidor)
        return

    casos = cargar_casos()
    seleccionados = casos if args.caso == "todos" else tuple(
        caso for caso in casos if caso.identificador == args.caso
    )
    if not seleccionados:
        disponibles = ", ".join(caso.identificador for caso in casos)
        raise SystemExit(f"Caso desconocido. Use uno de: {disponibles}, todos.")
    for caso in seleccionados:
        _ejecutar_caso(caso, args)


if __name__ == "__main__":
    main()
