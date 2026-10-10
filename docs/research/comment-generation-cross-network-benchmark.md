# Benchmark multired de comentarios — PR #72 (10/10/2026)

Fuente primaria: https://github.com/promptfoo/promptfoo/tree/37cfe7146f7abe770867659ad7b01ff57b723033
Fecha de consulta: 2026-10-10
Licencia SPDX: MIT
Referencia inmutable: https://github.com/promptfoo/promptfoo/tree/37cfe7146f7abe770867659ad7b01ff57b723033

## Problema

En el mirror, `tools/reply_writer.py` genera texto por lote, `valid_reply` comprueba
forma y `tools/scan_common.py` y `tools/reply_corpus_lint.py` detectan patrones.
**No hay una comparación pareada, reproducible, entre estrategias en las nueve
redes ni una revisión humana ciega de siete ejes.** La validación formal no
demuestra que el comentario entienda la publicación.

Contexto consultado de `davidpd89/rrss-davidporto-CODE`, rama
`integracion/crecimiento-2026-10`: `tools/reply_writer.py`,
`tools/reply_corpus_lint.py`; y mirror rama de la PR.
El oficial ya contiene refuerzos que no están en el mirror (por ejemplo,
`conversation_context` en el prompt y rechazo de JSON con campos repetidos).
**No se transfieren ni se pisan** esas mejoras. El benchmark es solo de lectura
sobre datos ficticios y reutiliza `valid_reply`, límites editoriales y
`reply_format`; no llama al generador vivo, las colas WEB/API/MOBILE,
sesiones ni publicadores. El flujo real permanece intacto.

## Alternativas

| Solución | Puntos fuertes | Coste y ajuste | Decisión |
| --- | --- | --- | --- |
| [promptfoo](https://github.com/promptfoo/promptfoo/tree/37cfe7146f7abe770867659ad7b01ff57b723033) | matrices de prompts/modelos, assertions y CI | Node >=22.22 según `package.json` consultado; un segundo runtime no necesario para un test offline pequeño en Python 3.11 | patrón de pruebas declarativas y resultados comparables; **no** integrar runtime |
| [DeepEval](https://github.com/confident-ai/deepeval/tree/4598fe8eb7be713637fbc803b9f127b5b83de69a) | métricas personalizadas, jueces LLM G-Eval | juez externo, coste y variabilidad de evaluación; dependencias nuevas para tareas sin secretos | posible segunda fase supervisada, **no** sustituye juicio humano |
| [Argilla](https://github.com/argilla-io/argilla/tree/5338519accb13ae422f8bf9c0642651c249c49af) | etiquetado y datasets de evaluación humana | infraestructura de anotación adicional para solo 72 respuestas | inspira CSV ciego; no instalar |
| [Hugging Face Transformers](https://github.com/huggingface/transformers/tree/536ecc007387a50e77603bb5d92100e9b07514cc) | generadores locales, modelos y prompts configurables desde Python | instalar modelos y comparar latencia/memoria/calidad por hardware y licencia del peso | candidato futuro; no introducir modelo no medido |
| [llama.cpp](https://github.com/ggml-org/llama.cpp/tree/10a60cf303566e10d6a7a2774c17d2085503d87b) | inferencia local con modelos cuantizados, también posible en Windows | binarios, recursos, licencia del modelo independiente del motor; benchmarking de hardware ausente | no integrar sin resultados de calidad y capacidad |
| **Herramientas existentes + stdlib Python** | `valid_reply`, tipología común de respuestas, compatible con tres colas | no estima significado de forma automática | **seleccionada** para evitar divergencia por red |

Repositorios y licencias consultados en GitHub el **10/10/2026**.
Las referencias fijas de arriba identifican el código contrastado.
No se copia código externo. La lógica de par anónimo, métricas y CLI
es implementación original; se reutiliza **directamente** la validación
existente, sin copiarla. Mantenimiento: estos proyectos presentan
commits accesibles en las referencias fijadas; no se ha probado
su calendario de releases, soporte comercial ni la instalación Windows
de sus dependencias completas. El módulo elegido solo añade stdlib a las
dependencias ya instaladas.

**Prompts/modelos comparados:** el baseline genérico y el candidato
contextual del fixture no son LLMs ni salidas de proveedores;
son textos sintéticos escritos para ejercitar el comparador.
La generación real continúa en el prompt del proyecto (`reply_writer.PROMPT`).
No se ha medido una superioridad entre GPT, Claude, modelos locales,
promptfoo o DeepEval; esa afirmación exigiría ejecutar un mismo corpus
con múltiples modelos y juicio humano independiente.

## Licencias y procedencia

- **promptfoo**: MIT, [licencia](https://github.com/promptfoo/promptfoo/blob/37cfe7146f7abe770867659ad7b01ff57b723033/LICENSE).
- **DeepEval**: Apache-2.0, [licencia](https://github.com/confident-ai/deepeval/blob/4598fe8eb7be713637fbc803b9f127b5b83de69a/LICENSE.md).
- **Argilla**: Apache-2.0, [licencia](https://github.com/argilla-io/argilla/blob/5338519accb13ae422f8bf9c0642651c249c49af/LICENSE).
- **Transformers**: Apache-2.0, [licencia](https://github.com/huggingface/transformers/blob/536ecc007387a50e77603bb5d92100e9b07514cc/LICENSE).
- **llama.cpp**: MIT, [licencia](https://github.com/ggml-org/llama.cpp/blob/10a60cf303566e10d6a7a2774c17d2085503d87b/LICENSE).
- No se traen dependencias, datos personales, imágenes, transcripciones
  auténticas ni código externo al mirror. Si en el futuro se importa
  código, conservar licencia y avisos atribuidos.

## Decisión

Se añade `tools/comment_benchmark.py` y
`tests/fixtures/comment_benchmark_synthetic.json`.

**Contrato de evaluación:**
1. Dataset `cases` con `id,network,kind,post,anchors,published_at,as_of`
   y `thread` opcional, y `candidates` con `case_id,strategy,reply`.
   9 redes × 4 tipos (literatura/noticia/premio/conversación) × 2
   estrategias = **36 casos/72 candidatos sintéticos**.
2. Rechaza casos sin fecha con zona, futuros, con más de 72 horas,
   identidades repetidas, redes desconocidas y respuestas de tipo inválido.
   72 horas es presupuesto **del benchmark**, no una relajación de ningún
   límite operativo existente.
3. Califica automáticamente **solo señales observables**: válido según
   `valid_reply`, anclas textuales presentes, pregunta, formato, duplicados
   exactos y abstenciones. No las denomina «naturalidad» ni «aportación»:
   coincidencia de palabras puede engañar y no es un juez semántico.
4. `prepare` exporta `blind.csv` (post, hilo, respuesta, siete ejes 0–4,
   nombre de evaluador vacío) y un `key.csv` **separado** que vincula
   identificador opaco ↔ estrategia/caso. No se muestra la estrategia al
   evaluador. Para evitar sesgos, no entregar `key.csv` al evaluador.
   Identificadores derivados de sal local, **no cifrado**: no usar
   con datos sensibles ni publicar juicios privados.
5. `evaluate --ratings` exige **dos evaluadores distintos por texto**.
   Solo compara estrategias puntuadas sobre los mismos casos. Para sugerir
   preferencia por red exige las cuatro categorías pareadas, dos evaluadores,
   al menos dos estrategias **idénticas en los cuatro casos**, textos válidos de la estrategia ganadora y diferencia de nota media >=0,05. Una
   preferencia así **no altera el generador real**: antes es precisa una
   validación supervisada, con muestras reales autorizadas.
6. `prompt --case` permite inspeccionar el suplemento editorial ajustado
   a la red y el hilo. Es **texto diagnóstico, nunca una llamada de red**.
   La única variación específica por red es el límite editorial; la
   rúbrica y los siete ejes son comunes.

## Pruebas

Ejecutar en Windows/Ubuntu con Python 3.11:

```sh
python -m pytest tests/test_comment_benchmark.py -q
python tools/comment_benchmark.py evaluate --input tests/fixtures/comment_benchmark_synthetic.json
python tools/comment_benchmark.py prepare --input tests/fixtures/comment_benchmark_synthetic.json --blind blind.csv --key key.csv
# Copiar blind.csv por separado a dos evaluadores; recibir sus filas con judge único:
python tools/comment_benchmark.py evaluate --input tests/fixtures/comment_benchmark_synthetic.json --ratings ratings.csv --output result.json
```

Usar la misma opción `--salt` en `prepare` y `evaluate`
si se cambia la sal predeterminada. `prepare` rechaza sobrescrituras
y rutas coincidentes. El CLI no crea archivos salvo con nombres de
salida explícitos. Los tests usan directorios temporales.

**Antes (HEAD original):** 0 pares comparables con anotación ciega en
las nueve redes. **Después (fixtures):** 36 pares, 72 ejemplos;
12 pruebas unitarias específicas; las pruebas de revisión ficticia
demuestran el funcionamiento del cálculo, **no una preferencia real**.
Evidencia del HEAD de código `9830eddd79bca6336d5357f7c876cff1077d9cb3`:
[Actions de pruebas 38016943031](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/38016943031),
**Ubuntu 1700 passed, 8 skipped, 8 deselected; Windows 1703 passed,
5 skipped, 8 deselected**, 681 subtests en cada runner; ninguna regresión
fallida. [Control público 38016945765](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/38016945765):
**Ubuntu y Windows correctos**. Los resultados reflejan
fixtures ficticios y pruebas offline, no sesiones ni comentarios reales.

La auditoría encontró un falso positivo preexistente en
`tools/spellcheck_es.py` al evaluar la forma verbal `borren`.
Se corrigió solo la oración sintética del fixture de esta PR, y se
abrió [#105](https://github.com/davidpd89/ci-sandbox-tmp/pull/105)
para implementar una solución morfológica común sin cambiar
los ejecutores dentro de #72.

## Segunda revisión adversarial

- **Fuga de etiqueta:** el CSV ciego no exporta `strategy` ni `case_id`.
  Conservar el archivo de clave separado. Un evaluador podría reconocer
  el estilo; la anonimización no garantiza cegamiento absoluto.
- **Juez engañado por keyword:** `anchor_hit` no se interpreta como
  calidad semántica; un comentario copiado puede obtenerlo.
- **Efecto «muchas notas, pocos posts»:** no se comparan estrategias sin
  la misma cobertura pareada; la preferencia exige los 4 tipos de caso.
- **Sesgo de rater / pseudo-independencia:** dos identificadores distintos
  de `judge` no prueban independencia humana; no hay verificación de identidad.
- **Cambio de fecha / DST:** se comparan instantes con zona explícita en UTC;
  se descartan fechas ingenuas, negativas y >72 h.
- **Pareado adversarial:** una versión inicial permitía comparar una estrategia evaluada en cuatro posts con otra evaluada solo en uno. Ahora exige el mismo conjunto de estrategias y la misma cobertura en todos los casos, y excluye ganadores con respuestas inválidas; hay una regresión sintética específica.
- **Repetición:** informe por red de duplicados exactos, no detector
  semántico de paráfrasis; el corpus puede mejorar con revisión humana.
- **Desbordamiento:** límites editoriales comunes, incluido Instagram,
  sin cambiar límites de publicación en producción.
- **No se tocó ningún estado real.** No se invoca navegador, móvil,
  SDK ni API. El canario supervisado y la evaluación de comentarios
  reales son trabajos pendientes de Claude; no hay garantía del 100 %.

## Retirada

Sin migración ni cambios de formato del sistema real. Reversión:
retirar `tools/comment_benchmark.py`,
`tests/test_comment_benchmark.py`,
`tests/fixtures/comment_benchmark_synthetic.json` y este informe.
No existe estado persistido del benchmark dentro de producción.

## Siguientes pasos para Claude

1. Obtener un corpus de publicaciones y comentarios recientes **autorizado
   y minimizado**, representativo de las nueve redes, sin incluir perfiles
   ni identificadores reales en este espejo. Etiquetarlo por tipo e hilo.
2. Conservar en el repositorio privado las mejoras recientes del parser y
   de `conversation_context`; no traer desde el mirror versiones viejas.
3. Ejecutar una evaluación ciega auténtica, comparar dos estrategias
   de prompt y al menos dos proveedores/modelos si existe presupuesto.
   Medir diversidad global, respuestas de cierre, falsos supuestos,
   naturalidad, cobertura y longitud.
4. Solo entonces seleccionar un perfil editorial por red y probarlo con
   un canario supervisado en su respectiva cola, sin mezclar API/WEB/MOBILE.
   Coordinar con #22 (memoria) y #51 (evaluación ciega); no duplicarlos.
