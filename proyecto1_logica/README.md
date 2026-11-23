# Proyecto 1 - Investigación de incidentes con lógica proposicional

Implementación propia de los dos algoritmos solicitados:

- inferencia por enumeración de modelos;
- resolución proposicional por refutación.

El caso estudiado es la desaparición de una laptop del laboratorio. La base usa
las 8 variables y las 12 cláusulas CNF del informe corregido (E7 modela los testimonios ¬D, N y D). Los datos están
separados de los algoritmos para que una regla, evidencia o consulta pueda
cambiarse sin modificar el procedimiento de inferencia.

## Estructura

```text
proyecto1_logica/
|-- algoritmos/
|   |-- enumeracion.py
|   `-- resolucion.py
|-- casos_prueba/
|   |-- base_conocimiento.json
|   |-- base_conocimiento_extensiones.json  # Cambios del usuario (separados del original)
|   |-- caso_1_unica_explicacion.json
|   |-- caso_2_varias_explicaciones.json
|   |-- caso_3_contradictorio.json
|   `-- caso_4_nueva_evidencia.json
|-- datos/
|   `-- cargador.py          # Incluye agregar_sospechoso, agregar_regla, validar_consistencia
|-- nucleo/
|   |-- cnf.py
|   |-- estados.py
|   `-- formulas.py
|-- pruebas/
|   |-- test_algoritmos.py
|   |-- test_casos.py
|   `-- test_extensiones.py  # Tests de sospechosos, reglas, consistencia y veredictos
|-- index.html               # Interfaz web interactiva con menú, modelos, trazas y diagnóstico
`-- ejecutar.py              # CLI para ejecución, pruebas y servidor web local
```

No se requieren bibliotecas externas; basta Python 3.10 o posterior.

## Funciones para Extensión y Validación

El módulo `datos.cargador` incorpora las siguientes funciones clave:

* `agregar_sospechoso(base, variable, nombre, actualizar_reglas_culpable=True)`: Registra un nuevo sospechoso y actualiza automáticamente las cláusulas de "al menos uno" ($E1$) y "a lo sumo uno" ($E2$).
* `agregar_regla(base, identificador, descripcion, formula)`: Parsea una fórmula proposicional arbitraria, la convierte a Forma Normal Conjuntiva (FNC) y la agrega a la base.
* `validar_consistencia(base, evidencia=(), metodo="ambos")`: Evalúa si la base es consistente o deriva en contradicción (cláusula vacía $\square$).
* `validar_adicion(base, nuevo_sospechoso=None, nueva_regla=None, evidencia=())`: Agrega sospechosos/reglas y valida inmediatamente la consistencia.
* `diagnosticar_culpabilidad(base, evidencia=(), sospechosos=None)`: Determina explícitamente:
  1. Si la base es consistente y se encontró un culpable único (quién fue).
  2. Si es consistente y no es posible encontrar un culpable único (el estado de la base llega a 2 o más posibles soluciones / indeterminación).
  3. Si se llega a una contradicción (cláusula vacía $\square$) o la base es inconsistente y falta información coherente.

## Interfaz Web (`index.html`)

Se incluye una interfaz web interactiva que no requiere librerías externas. Como la interfaz lee y guarda los JSON mediante una API local, debe iniciarse con el servidor incluido:

```powershell
python ejecutar.py --servidor 8000
```

Luego visite `http://localhost:8000/index.html`. Abrir el HTML con doble clic no habilita la persistencia porque el navegador no puede acceder a la API local.

La interfaz incluye:
* Menú selector de casos (Caso 1, Caso 2, Caso 3, Caso 4 y Modo Personalizado).
* Panel para añadir sospechosos y reglas proposicionales dinámicamente con validación inmediata.
* Persistencia de cambios en `casos_prueba/base_conocimiento_extensiones.json`; `base_conocimiento.json` permanece intacto.
* Botón para eliminar las extensiones y reconstruir la base original.
* Diccionario visible de variables y tabla de enunciados/fórmulas, con etiquetas de origen.
* Visualizador de resolución por enumeración (tabla de modelos y asignaciones de verdad).
* Visualizador de resolución por refutación paso a paso con pivote y resolventes hasta la cláusula vacía $\square$.
* Panel final adaptado a la consulta: culpabilidad para sospechosos, activación de alarma, uso de llave o clasificación lógica general.

## Ejecución en Consola

Desde esta carpeta:

```powershell
python ejecutar.py
```

El comando anterior ejecuta los cuatro casos, compara ambos algoritmos e imprime el diagnóstico explícito de culpabilidad de cada uno.

Para añadir sospechosos o reglas en tiempo de ejecución:

```powershell
python ejecutar.py --caso caso_2 --sospechoso G Gabriel --regla R9 "G -> K" "Gabriel usó llave" --evidencia G
```

Para validar únicamente consistencia:

```powershell
python ejecutar.py --caso caso_3 --validar
```

Para ver los modelos y una secuencia completa de resolución:

```powershell
python ejecutar.py --caso caso_2 --consulta K --traza
```
```

Para simular durante la exposición una consulta o evidencia diferente:

```powershell
python ejecutar.py --caso caso_2 --consulta "F -> ~K" --traza
```

Los literales negativos se escriben con `~`, por ejemplo `~K`. En las consultas
se aceptan `~` (negación), `&` (conjunción), `|` (disyunción), `->`
(implicación), `<->` (bicondicional) y paréntesis.

## Pruebas automáticas

```powershell
python -m unittest discover -s pruebas -v
```

Las pruebas comprueban los conteos esperados de modelos (1, 12, 0 y 4), la
clasificación de todas las consultas, la detección de contradicción y la
coincidencia entre enumeración y resolución.
