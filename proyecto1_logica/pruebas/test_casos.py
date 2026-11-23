import unittest

from algoritmos.enumeracion import inferir_por_enumeracion
from algoritmos.resolucion import inferir_por_resolucion
from datos.cargador import cargar_base, cargar_casos, clausulas_del_escenario


class PruebasCasosDelInforme(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = cargar_base()
        cls.casos = cargar_casos()

    def test_conteo_de_modelos_de_los_cuatro_casos(self):
        for caso in self.casos:
            with self.subTest(caso=caso.identificador):
                clausulas, _ = clausulas_del_escenario(self.base, caso)
                resultado = inferir_por_enumeracion(
                    self.base.variables, clausulas, caso.consultas
                )
                self.assertEqual(caso.modelos_esperados, len(resultado.modelos))

    def test_resultados_esperados_y_coincidencia(self):
        for caso in self.casos:
            with self.subTest(caso=caso.identificador):
                clausulas, etiquetas = clausulas_del_escenario(self.base, caso)
                enumeracion = inferir_por_enumeracion(
                    self.base.variables, clausulas, caso.consultas
                )
                resolucion = inferir_por_resolucion(
                    clausulas, caso.consultas, etiquetas
                )

                self.assertEqual(enumeracion.consistente, resolucion.consistente)
                if not enumeracion.consistente:
                    self.assertEqual({}, resolucion.consultas)
                    self.assertTrue(resolucion.prueba_consistencia.contradiccion)
                    continue

                for consulta, esperado in caso.esperados.items():
                    self.assertEqual(
                        esperado, enumeracion.consultas[consulta].value
                    )
                    self.assertEqual(
                        esperado, resolucion.consultas[consulta].estado.value
                    )


if __name__ == "__main__":
    unittest.main()
