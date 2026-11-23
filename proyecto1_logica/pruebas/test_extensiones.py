import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import datos.cargador as cargador

from datos.cargador import (
    agregar_regla,
    agregar_sospechoso,
    cargar_base,
    diagnosticar_culpabilidad,
    validar_adicion,
    validar_consistencia,
)


class PruebasNuevasFunciones(unittest.TestCase):
    def setUp(self):
        self.base = cargar_base()

    def test_agregar_sospechoso_actualiza_e1_y_e2(self):
        base_nueva = agregar_sospechoso(self.base, "G", "Gabriel")
        self.assertIn("G", base_nueva.variables)
        self.assertIn("G", base_nueva.significados)

        # Verificar que la regla E1 ahora incluye a G
        regla_e1 = next(r for r in base_nueva.reglas if r.identificador == "E1")
        variables_e1 = {lit.variable for lit in regla_e1.fnc[0]}
        self.assertEqual({"D", "E", "F", "G"}, variables_e1)

        # Regla E2 debe tener combinaciones de 4 tomados de a 2 = 6 clausulas
        regla_e2 = next(r for r in base_nueva.reglas if r.identificador == "E2")
        self.assertEqual(6, len(regla_e2.fnc))

        # La base debe ser consistente
        validacion = validar_consistencia(base_nueva)
        self.assertTrue(validacion.consistente)
        self.assertFalse(validacion.clausula_vacia)

    def test_agregar_regla_y_validar_consistencia(self):
        # Agregar una regla compatible
        base_nueva = agregar_regla(
            self.base,
            "R_TEST",
            "Si Diego es inocente entonces Elena o Fabián",
            "~D -> (E | F)",
        )
        self.assertTrue(any(r.identificador == "R_TEST" for r in base_nueva.reglas))
        val_compatible = validar_consistencia(base_nueva)
        self.assertTrue(val_compatible.consistente)

        # Agregar una regla contradictoria directa
        # En la base original E3: N -> A y E6: A -> ~K.
        # Si agregamos regla N & K:
        base_contradictoria = agregar_regla(
            base_nueva, "R_CONTRA", "Noche y llave juntos", "N & K"
        )
        val_inconsistente = validar_consistencia(base_contradictoria)
        self.assertFalse(val_inconsistente.consistente)
        self.assertTrue(val_inconsistente.clausula_vacia)

    def test_validar_adicion(self):
        base_mod, val = validar_adicion(
            self.base,
            nuevo_sospechoso=("G", "Gabriel"),
            nueva_regla=("R_G", "Gabriel estaba en el lab", "G -> N"),
        )
        self.assertIn("G", base_mod.variables)
        self.assertTrue(val.consistente)

    def test_diagnostico_culpable_caso_1(self):
        # Caso 1: Evidencia ~E, ~F, AD, AE -> Diego (D) culpable demostrado
        diag = diagnosticar_culpabilidad(self.base, evidencia=["~E", "~F", "AD", "AE"])
        self.assertTrue(diag.consistente)
        self.assertEqual("CULPABLE_ENCONTRADO", diag.estado)
        self.assertEqual("D", diag.culpable)
        self.assertIn("Diego", diag.mensaje)

    def test_diagnostico_multiples_soluciones_caso_2(self):
        # Caso 2: Sin evidencia adicional -> Tres posibles soluciones (D, E y F)
        diag = diagnosticar_culpabilidad(self.base, evidencia=[])
        self.assertTrue(diag.consistente)
        self.assertEqual("MULTIPLES_SOLUCIONES", diag.estado)
        self.assertIsNone(diag.culpable)
        self.assertEqual(set(diag.posibles_culpables), {"D", "E", "F"})
        self.assertIn("posibles soluciones", diag.mensaje)

    def test_diagnostico_contradiccion_caso_3(self):
        # Caso 3: Evidencia contradictoria K
        diag = diagnosticar_culpabilidad(self.base, evidencia=["K"])
        self.assertFalse(diag.consistente)
        self.assertEqual("CONTRADICCION", diag.estado)
        self.assertTrue(diag.clausula_vacia)
        self.assertIn("contradicción", diag.mensaje.lower())

    def test_diagnostico_culpable_caso_4(self):
        # Caso 4: Evidencia ~D, ~E -> Fabián (F) culpable demostrado
        diag = diagnosticar_culpabilidad(self.base, evidencia=["~D", "~E"])
        self.assertTrue(diag.consistente)
        self.assertEqual("CULPABLE_ENCONTRADO", diag.estado)
        self.assertEqual("F", diag.culpable)
        self.assertIn("Fabián", diag.mensaje)


class PruebasPersistenciaExtensiones(unittest.TestCase):
    def setUp(self):
        self.temporal = TemporaryDirectory()
        self.ruta_anterior = cargador.RUTA_EXTENSIONES
        cargador.RUTA_EXTENSIONES = Path(self.temporal.name) / "extensiones.json"

    def tearDown(self):
        cargador.RUTA_EXTENSIONES = self.ruta_anterior
        self.temporal.cleanup()

    def test_sospechoso_se_guarda_y_se_recarga(self):
        cargador.guardar_sospechoso("G", "Gabriel")
        base = cargador.cargar_base_personalizada()
        extensiones = cargador.cargar_extensiones()

        self.assertIn("G", base.variables)
        self.assertEqual("Gabriel tomó la laptop", base.significados["G"])
        self.assertEqual("G", extensiones["sospechosos"][0]["variable"])
        self.assertIn("G", next(r for r in base.reglas if r.identificador == "E1").formula)

    def test_regla_y_significados_se_guardan_separados(self):
        cargador.guardar_regla(
            "R9",
            "La puerta abierta implica alarma",
            "X -> A",
            {"X": "La puerta estaba abierta"},
        )
        base = cargador.cargar_base_personalizada()
        extensiones = cargador.cargar_extensiones()

        self.assertEqual("La puerta estaba abierta", base.significados["X"])
        self.assertEqual("R9", extensiones["reglas"][0]["id"])
        self.assertFalse(any(r.identificador == "R9" for r in cargador.cargar_base().reglas))

    def test_restablecer_conserva_base_original(self):
        cargador.guardar_sospechoso("G", "Gabriel")
        base = cargador.restablecer_base_original()

        self.assertNotIn("G", base.variables)
        self.assertEqual([], cargador.cargar_extensiones()["sospechosos"])
        self.assertEqual(cargador.cargar_base(), cargador.cargar_base_personalizada())


if __name__ == "__main__":
    unittest.main()
