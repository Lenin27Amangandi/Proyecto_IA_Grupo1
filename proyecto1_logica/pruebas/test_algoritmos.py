import unittest

from algoritmos.enumeracion import inferir_por_enumeracion
from algoritmos.resolucion import inferir_por_resolucion
from datos.cargador import cargar_base, cargar_casos, clausulas_del_escenario
from nucleo.estados import EstadoConsulta


class PruebasAlgoritmos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = cargar_base()
        cls.casos = {caso.identificador: caso for caso in cargar_casos()}

    def test_base_original_tiene_doce_modelos(self):
        caso = self.casos["caso_2"]
        clausulas, _ = clausulas_del_escenario(self.base, caso)
        resultado = inferir_por_enumeracion(
            self.base.variables, clausulas, caso.consultas
        )
        self.assertTrue(resultado.consistente)
        self.assertEqual(12, len(resultado.modelos))
        self.assertEqual(256, resultado.asignaciones_examinadas)
        self.assertEqual(EstadoConsulta.INDETERMINADA, resultado.consultas["D"])
        self.assertEqual(
            EstadoConsulta.DEMOSTRADA, resultado.consultas["N"]
        )

    def test_resolucion_produce_clausula_vacia(self):
        caso = self.casos["caso_2"]
        clausulas, etiquetas = clausulas_del_escenario(self.base, caso)
        resultado = inferir_por_resolucion(clausulas, ["K"], etiquetas)
        detalle = resultado.consultas["K"]
        self.assertEqual(EstadoConsulta.REFUTADA, detalle.estado)
        self.assertIsNotNone(detalle.intento_refutar)
        self.assertTrue(detalle.intento_refutar.contradiccion)
        self.assertEqual(frozenset(), detalle.intento_refutar.pasos[-1].resolvente)

    def test_consulta_nueva_se_demuestra(self):
        caso = self.casos["caso_2"]
        clausulas, etiquetas = clausulas_del_escenario(self.base, caso)
        enumeracion = inferir_por_enumeracion(
            self.base.variables, clausulas, ["F -> ~K"]
        )
        resolucion = inferir_por_resolucion(
            clausulas, ["F -> ~K"], etiquetas
        )
        self.assertEqual(
            EstadoConsulta.DEMOSTRADA, enumeracion.consultas["F -> ~K"]
        )
        self.assertEqual(
            EstadoConsulta.DEMOSTRADA,
            resolucion.consultas["F -> ~K"].estado,
        )


if __name__ == "__main__":
    unittest.main()
