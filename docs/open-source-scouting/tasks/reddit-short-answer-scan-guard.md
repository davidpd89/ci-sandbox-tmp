# Reddit — activar el filtro de respuestas cortas en el escáner

**Hallazgo reproducido por inspección (10/10/2026):** en el oficial `davidpd89/rrss-davidporto-CODE`, `integracion/crecimiento-2026-10` HEAD `5449513d9b545d0a6a72abf066ab6a779bfdad71`, `tools/reddit_scan.py` define `is_short_answer_thread(title)`, pero `scan()` **jamás la invoca**: filtra política e identidad, luego incorpora cualquier título, incluso solicitudes de opinión larga. Contradice `SISTEMA_DIARIO_REDDIT/REGLAS.md` (scope 03/10, solo microrrespuestas 1–5 palabras) y el propio docstring del escáner.

## Encargo para GPT

1. Revisar el código oficial actualizado, y PR abiertas/fusionadas del sandbox/privado antes de tocarlo; no duplicar un fix concurrente. Conservar `r/libros` y `r/filosofia_en_espanol` (con sus permisos editoriales individuales) y el historial confirmado/incierto.
2. Introducir el veto al seleccionar hilos, **antes** de presentar `[RESPUESTA: 1-5 palabras]`. Reutilizar `is_short_answer_thread` existente, sin copiar ni alterar el sistema global de ranking. Un título no determina contexto suficiente: mantener revisión humana de todo candidato.
3. Incluir tests herméticos que invoquen `scan()` con fakes `_extract_threads` y casos positivos (listas/preguntas breves), negativos (petición de reseña u opinión de un manuscrito, textos expositivos), tildes/Unicode y URL dudosa. Confirmar que no se conecta Edge ni se publican comentarios/votos durante tests.
4. Añadir breve informe `docs/research/`, referencias de HEAD/procedencia, resultados de tests Ubuntu/Windows Python 3.11 y segunda pasada adversarial. No copiar ficheros privados de estado ni secretos al mirror. No ejecutar acciones en Reddit.
5. La norma global y adaptadores siguen en #117, #100 y #116; aquí **solo** se corrige el veto específico de Reddit. Tras integración, Claude revisará la suite/Edge/PC real. **Sin merge por GPT.**

**Base:** `research/public-reuse-parent`. **Motivo de PR independiente:** fallo del escáner existente, distinto del lector opcional PRAW de [#126](https://github.com/davidpd89/ci-sandbox-tmp/pull/126). Verificación de duplicados: búsqueda de PR abiertas/cerradas sobre «reddit scan», «short answer reddit» y «respuesta corta» el 10/10/2026; ninguna PR contiene este arreglo específico (la PR oficial #57 es una planificación general de comunidades).
