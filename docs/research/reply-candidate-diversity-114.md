# PR #114 — Selección offline de variantes contextualmente aprobadas

Fecha: 2026-10-10. Base de inspección: `research/public-reuse-parent`.
Resultado: **implementación experimental y verificable, no conectada a publicaciones reales**.

## Verificación externa: fuente, licencia, mantenimiento y compatibilidad

| Fuente verificada | Commit | Licencia real | Último commit observado | Decisión |
| --- | --- | --- | --- | --- |
| [neural-dialogue-metrics/Distinct-N](https://github.com/neural-dialogue-metrics/Distinct-N) | `e94edcb2e1d2230ff9e0f1821387d7f6d7af0c4f` | MIT (LICENSE y cabeceras del código), **a pesar de un classifier contradictorio en setup.py** | 2023-01-07 | **Reutilizado/adaptado:** `distinct_n/metrics.py` y `distinct_n/utils.py`. MIT íntegra en `tools/vendor/LICENSE.distinct-n.txt`. Se arreglan secuencias cortas, entrada vacía y se añade micro-métrica n-grama. |
| [cshaib/diversity](https://github.com/cshaib/diversity) | `25127ccbe0ce21e5696e15de4ef73f075922d21f` | Apache-2.0 | 2026-05-06 | Compatible por metadatos con Python `>=3.10,<3.13`, pero exige NLTK, transformers y sentence-transformers; no instalar en cada ronda. |
| [GuyTevet/diversity-eval](https://github.com/GuyTevet/diversity-eval) | `c6172997caa04bd8d8c0df12a6faddc2811a726d` | MIT | 2021-02-23 | No integrar: módulos de inglés y rutas `bash` / `bert-sts` rígidas no justifican el coste para Windows. |
| [PAIR-code/llm-comparator](https://github.com/PAIR-code/llm-comparator) | `60edc1eaf96e09f4b9791dbc9bb0fb7bcc82c69c` | Apache-2.0 | 2024-10-18 | Archivado: no incorporar dependencia. Hay comparación ciega local en el oficial. |
| [RasaHQ/paraphraser](https://github.com/RasaHQ/paraphraser) | repositorio inspeccionado | MIT | 2022-01-27 | No usar como generador: envejecido y puede cambiar el sentido. |
| [IBM/diveye](https://github.com/IBM/diveye) | repositorio inspeccionado | NOASSERTION en metadatos | 2026-02-20 | No reutilizar sin licencia aclarada; detector de IA no equivale a naturalidad. |
| [confident-ai/deepeval](https://github.com/confident-ai/deepeval) | repositorio inspeccionado | **Apache-2.0**, no asumir MIT del informe | 2026-10-10 | No integrar sin comparación calibrada; coste innecesario en esta PR. |

La compatibilidad **Windows/Python 3.11 del adaptador local** se apoya en biblioteca estándar (sin llamadas de shell, red, NLTK ni instalación externa); tests ejecutados en Linux/Python **3.13.5**. Windows y Python **3.11** **no han sido probados**; la compatibilidad 3.11 es solo una inferencia estática (anotaciones PEP 604 y biblioteca estándar).

## Revisión de duplicidad: oficial y PR abiertas

Consultada la rama oficial `davidpd89/rrss-davidporto-CODE:integracion/crecimiento-2026-10` y la base del espejo. El oficial ya incluye `reply_writer.py`, `check_language_variety.py`, `reply_corpus_lint.py`, `reply_quality_metrics.py`, `reply_research_eval.py`, `reply_blind_review.py`, `reply_context_trial.py` y `reply_provenance.py`. Estos últimos ya resuelven diagnóstico, ensayo A/B ciego, hipótesis de contexto y enlace de respuestas. Las PR #22, #72, #74, #79, #106/#121 y #119 cubren respectivamente memoria, benchmark, contexto, voz y aplicación de preflight. **No se sustituyen ni duplican**. La PR #116 aborda ranking de acciones, no de alternativas lingüísticas.

## Implementación real de esta PR

- `tools/vendor/distinct_n_compat.py`: reutiliza la semántica de Distinct-N con atribución y licencia MIT, robustez ante corpus vacío y micro-promedio adicional. Ninguna dependencia nueva.
- `tools/reply_candidate_diversity.py`: interfaz pura `select_approved(network, candidates, recent, validator=...)` y `evaluate_cases`; tokenización Unicode con ñ y acentos; antirrepetición entre los candidatos y el historial explícito; novedad bigramas/unigramas para ordenar **solo** variantes ya aprobadas en revisión independiente; `null` si no hay ninguna viable.
- Matriz común para X, Threads, Facebook, Pinterest, Reddit, Bluesky, Mastodon, TikTok e Instagram, más el caso `reddit_micro`. Las ocho redes de `reply_writer.MAX_CHARS/MAX_WORDS` reflejan su límite a fecha de inspección; **Instagram es un perfil propuesto offline**, nunca conectado al publicador.
- Interfaz opcional de preflight `validator(text, network, recent)`, diseñada para recibir el `reply_writer.valid_reply` existente **desde el integrador**, sin importar módulos con efectos externos en la evaluación. No se adjudica a esta selección autoridad para saltarse procedencia, ortografía o QA del publicador.
- CLI con JSON sintético que devuelve índices y métricas, sin eco de autores, posts ni respuestas. Sin redes, credenciales, automatismos ni escritura sobre colas.

**Restricción importante:** las métricas de diversidad miden repetición, **no** verdad, pertinencia, naturalidad ni mejora de seguidores. El campo `context_approved` es una declaración del evaluador independiente; no demuestra que exista una revisión fiable. **No usar la salida automáticamente para publicar**. El resultado de esta PR es un candidato técnico offline para futura integración después de probar revisión real, procedencia y preflight.

## Pruebas y auditoría adversarial

En una copia local del código/test de PR #114 (Linux, Python 3.13.5):

```
python -m unittest discover -s tests -p test_reply_candidate_diversity.py -v
Ran 10 tests ... OK
```

Además: `python -m compileall -q` OK; 1.500 casos sintéticos aleatorios de selección sin excepción y sin escoger respuestas no aprobadas (fuzz local, semilla fija).\n\nCubren las 9 redes + Reddit micro, casos sin aprobación (abstención), normalización con tildes, candidatos duplicados, selección de variante novedosa frente a histórico, preflight opcional que rechaza, rechazo de formato/URLs/hashtags/red desconocida, exactitud de Distinct-N para n-gramas cortos y vacíos, CLI portátil y no filtración de texto en el JSON. Sin claims de rendimiento real.

Segunda pasada adversarial: falsar la hipótesis «Distict-N alto = comentario relevante»; queda prohibido seleccionar por distintividad antes de validar el contexto. Separar la futura conexión a un adaptador distinto evita colisiones con los ejecutores existentes y #106/#121.

## Pendiente para Claude tras integrar dependencias

1. Contrastar límites contra `reply_writer` vigente, y volver a ejecutar tests en **Windows/Python 3.11** y las suites del repositorio privado.
2. Probar revisión contextual humana/automatizada en sombra contra casos reales consentidos y verificar semántica sin introducir frases del corpus público como publicaciones.
3. Verificar los puntos WEB/API/MOBILE en Edge, Android y los nueve adaptadores; **no activar sin evidencia**. Instagram no tiene hoy ruta automática equivalente en `reply_writer`.
4. Antes de cualquier uso productivo: pasar siempre `reply_writer.valid_reply`, QA de voz, procedencia, deduplicación e idempotencia por el punto existente, sin autorizaciones basadas en los campos del JSON.

No se ha hecho merge ni ninguna acción en redes sociales.
