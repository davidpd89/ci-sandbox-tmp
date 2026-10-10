# PR #65 — señales explícitas de reciprocidad (10/10/2026)

## Hueco reproducido y alcance

En el espejo el núcleo existente, tools/reciprocity.py, contiene un único FOLLOWBACK_BIO y añade +2,5 a bios con «followback» aunque digan «no hago followback» o «¿qué significa f4f?». No representa reciprocidad de comentarios, cadenas de lectura ni grupos de apoyo. La expansión general de tools/discovery_terms.py depende de términos de configuración, pero no distingue intención expresa de mención casual ni ofrece observaciones etiquetadas por plataforma.

Código oficial consultado **solo en lectura**, rama integracion/crecimiento-2026-10: tools/discovery_ranking.py, tools/discovery_graph.py, tools/discovery_terms.py, tools/reciprocity.py, tools/reciprocity_stats.py, 00_OPERATIVO/REDES/HUBS_RECIPROCIDAD.md y alcance de PR #48 (discovery-hubs). Se verificó que el oficial añade ranking/sources pseudónimos con pruebas de procedencia y snapshots limitados a Bluesky/Mastodon, mientras que esta PR vive en la rama pública y no debe simular que esas evidencias ya están disponibles en las otras redes. No se publicó contenido del privado, ni se cambió su rama.

**Entrega real:** tools/reciprocity_signals.py (pura, stdlib) y conexión mínima a dos interfaces existentes: reciprocity.declares_followback() y discovery_terms.terms(). Los nueve adaptadores que ya consumen terms("red","busquedas"/"hashtags") pueden incluir estas consultas; la adopción por cada escáner se debe comprobar con sus planes. Las bios que ya consumen declared_bonus pasan a separar intención de metacomentario. El módulo NO agrega perfiles a reservas ni modifica colas WEB/API/MOBILE.

## API y contrato

- classify_text(text): listas de indicios de follow_exchange, comment_exchange, reading_chain, support_group. Cada uno conserva clase, coincidencia normalizada, intención explicit/mention y confianza **heurística** (NO calibración estadística).
- search_terms(network, kind): consultas y hashtags por plataforma, con normalización y dedupe a través de discovery_terms. No crea cuentas ni grupos falsos.
- assess_candidate(row, as_of): eligibility explicable por red/superficie, nicho verificado o textual y antigüedad <=7 días para un post. Sin fecha => review, caducado => rejected. Bio/group/list sin fecha de post solo sirve para descubrimiento, nunca autoriza comentar contenido viejo.
- evaluate(rows, as_of): matriz de confusión por red, separa aciertos y fallos etiquetados.
- outcome_report(rows, as_of): tasas descriptivas por red/señal de relation_active, comments y visits cuando el resultado está **verificado y maduro**. Unknown != false. Observaciones no son incrementos causales y se deduplican por origen+actor+red; en caso de varias fuentes el grupo no representa actores únicos entre fuentes.

Datos de evaluación: tests/fixtures/reciprocity_signals_synthetic.json (108 casos etiquetados, 12 por plataforma; nueve redes: X, Threads, Facebook, Pinterest, Reddit, Bluesky, Mastodon, TikTok e Instagram). Todos los textos son sintéticos. Las clases representan biografía, publicación reciente/caducada, hashtag, lista y grupo. Tienen ejemplos positivos y negativos, menciones casuales, contraejemplos, casos sin nicho, ausencia de fecha, comillas y negaciones. Los escenarios se repiten entre redes para comprobar paridad técnica: NO reflejan prevalencias ni rendimiento real de cada comunidad.

**Medición de esta fixture (simulación, no canario):** 5 TP + 7 TN por red; 45 TP, 63 TN, 0 FP y 0 FN sobre los 108 ejemplos diseñados. Precisión y recall 1,00 **solo dentro de la fixture, no promesa de producción**. Regresión específica sobre negación: el bonus heredado habría puntuado la frase «No hago followback»; el adaptador nuevo puntúa 0. Las familias complementarias no estaban cubiertas por la regex histórica.

## Reutilización pública contrastada (GitHub consultado 10/10/2026)

| Alternativa | Referencia fija, licencia, mantenimiento | Compatibilidad y coste | Decisión |
|---|---|---|---|
| RapidFuzz | https://github.com/rapidfuzz/RapidFuzz/commit/db6e504539a9c895180b266a06b36a32cb6029ee — MIT, commit septiembre 2026, no archivado, push septiembre 2026 | Python >=3.11, Windows/Linux wheels, CRT Visual C++ en Windows; resuelve similitud difusa pero no intenciones/negación | No introducir dependencia ni falsos positivos por aproximación |
| pyahocorasick | https://github.com/WojciechMula/pyahocorasick/commit/4e28d29898f1019d9706485b2a06026466814d9d — BSD-3-Clause, versión 2.3.1 abril 2026, no archivado | CPython 3.11 Windows/Linux con wheel; búsqueda exacta acelerada, extensión nativa | Útil si el vocabulario escala a miles de patrones; cuatro familias no amortizan carga |
| FlashText | https://github.com/vi3k6i5/flashtext/commit/f49274459bc9879789c6e6bb64bf05af755de0b3 — MIT, último commit consultado mayo 2022 (pese a fecha de push del repositorio más reciente) | Implementación Python, palabra/frase exacta sin contexto de negación | No integrar: mantenimiento relativamente bajo y requiere reglas contextuales adicionales |
| Núcleo RRSS existente + re stdlib | tools/reciprocity.py, tools/discovery_terms.py del espejo; Python estándar bajo licencia del repositorio | Python 3.11 Windows/Linux sin wheel nuevo. Evita dependencia y mantiene contratos | **Elegido**: reutilización local explícita, detector pequeño y datos de prueba independientes |

Fuentes adicionales: https://github.com/rapidfuzz/RapidFuzz/blob/main/pyproject.toml (Python y MIT), https://pypi.org/project/pyahocorasick/ (wheel CPython 3.11 Windows), https://github.com/WojciechMula/pyahocorasick (BSD-3-Clause). No se copió código de terceros ni se introduce su licencia al árbol. Se reutilizan interfaces RRSS y técnicas públicas básicas (normalización Unicode, patrones exactos y validación de contexto). La compatibilidad Windows 3.11 se valida en GitHub Actions, no en el Edge/Android reales.

## Riesgos técnicos, segunda revisión adversarial y correcciones

1. **Falso positivo léxico:** «no hago followback» y «¿qué significa f4f?» no son ofertas. Se corrigió el bonus de bios existente para usar intent=explicit y se introdujeron negativos en cada plataforma. «En mi novela…» y «prefiero no recomendar…» también están excluidos. No existe clasificación semántica perfecta: el texto ambiguo puede requerir revisión manual.
2. **Sesgo de edades:** un post antiguo o sin timestamp jamás obtiene eligible. Superficies bio/grupo/lista no equivalen a autorización de publicar o responder; ejecutores mantienen su guard de antigüedad.
3. **Identidad y métricas:** desconocido no se contabiliza como fracaso; actor/superficie de redes distintas no colapsan. La función outcome_report recibe verificaciones suministradas por el caller, **no puede demostrar por sí sola** que el conector verificó la acción real. No utilizar sus tasas para priorizar producción sin atribución y coortes completas (ver PR #21/#23/#48/#50).
4. **Interferencia entre PR:** no se importó código nuevo del oficial para no crear conflictos con discovery_graph/discovery_ranking ni con PR #57/#59 (ciclo y memoria de follow-back) y #63 (expansión de hashtags).
5. **Higiene pública:** el texto heredado modificado contenía un identificador real en el docstring; se sustituyó por un ejemplo sin cuenta. No se tocaron registros, ni estados ni secretos.
6. **Portabilidad y reversión:** rollback = revertir exclusivamente cambios en tools/reciprocity.py, tools/discovery_terms.py y borrar tools/reciprocity_signals.py + tests/fixture/workflow. No hay migración de SQLite ni cambios persistentes.
7. **Cobertura real pendiente:** un canario supervisado por Claude debe comprobar la captación de términos en cada adaptador, coste de consultas, ranking de prospectos y conversiones medidas con lectores reales, sin activar acciones en este entorno. No afirmar medición efectiva de followers, comentarios o visitas de todas las redes.

## Pruebas reproducibles

Comando sin paquetes adicionales: python -m unittest discover -s tests -p test_reciprocity_signals.py -v

Workflow nuevo .github/workflows/reciprocity-signals-offline.yml, matriz ubuntu-latest/windows-latest Python 3.11 y compilación de los módulos; también queda el workflow general validate-social-tools. Deben comprobarse ejecuciones y HEAD final antes de integrar. Fixture únicamente sintética; ninguna cuenta social se consultó ni modificó.

## Integración futura / criterios de canario

1. Conectar assess_candidate a las observaciones reales de cada escáner por adaptador (sin saltarse filtros de idioma, nicho, identidad, consentimiento de lectura y edad). Guardar **señal, superficie, timestamp, origen, actor canónico** para atribución; priorizar uso de esquema de source keys de PR #23/#48 y el ranking validado del oficial.
2. A/B por red entre conjunto sin señales y conjunto con señales; antes/después en la misma ventana: candidatos nuevos por lectura, relevancia humana muestreada, relaciones activas a 7/14 días, comentarios de vuelta y visitas verificadas. No contar exposición como resultado. Separar muestra de exploración y controles.
3. Distinguir resultados de pruebas simuladas (ya incluidos) y canario en Edge/Android real (pendiente Claude). Esta rama no modifica los ejecutores ni crea follow/reply/like.
