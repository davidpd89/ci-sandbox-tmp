# Integración de QA lingüística en salidas de texto no cubiertas

Origen comprobado: PR #79 (auditor compartido en `tools/spanish_voice_quality.py`). El escritor `reply_writer.py` y siete publicadores de `content_publisher.py` emiten avisos de voz no destructivos. Persisten rutas de texto propias/fuera del escritor común, como X banco, Reddit/TikTok con entrada manual o workflows específicos y publicación a través de herramientas directas. El objetivo NO es recrear el corrector ni reescribir comentarios.

## Encargo de implementación

1. Inspeccionar en el espejo y el repo oficial cada punto de **salida final de texto** que aún no llama al auditor de #79. Inventariar nueve redes, canales WEB/API/MOBILE, responsabilidad del productor y si usa el motor de respuestas común; no afirmar cobertura sin trazabilidad.
2. Integrar **una sola API** de QA de #79, preferiblemente en los preflights comunes de salida o en un adaptador compartido; no copiar regex. Diagnósticos sin autocorrecciones ni bloqueos editoriales nuevos, sin alterar tildes de títulos, URLs, citas, hashtags ni formato nativo.
3. Tests offline sintéticos que demuestren, por cada ruta integrada, que se llama al auditor antes del punto irreversible y que su excepción no publica nada accidental, no duplica contenido ni modifica el texto. Verificar que el constructor de un post/reply que ya usa el escritor no ejecuta auditorías repetidas. Comparar cobertura antes/después.
4. Buscar bibliotecas públicas mantenidas al 10/10/2026, registrar licencia, commit fijo, Windows/Python 3.11 y dependencias; reutilizar #79 y comparar cualquier alternativa.
5. Entregar implementación, pruebas Ubuntu/Windows Python 3.11, documentación de alcance y limitaciones, evaluación adversarial, reversión e informe en esta misma PR. No tocar datos reales, credenciales ni cuentas, no publicar/responder, no hacer merge.

## Criterio de aceptación

Tabla auditable por red y cola indicando **conectado / no aplicable / pendiente**, puntos de llamada antes de la acción, pruebas de no-mutación y de errores controlados y sin acción social real. No duplicar #79 (calidad del auditor), #72 (benchmark de comentarios), #50 (Unicode), #51 (evaluación ciega), #20 (planificador de publicaciones). Claude integrará #79 antes de esta PR.

Ver también `docs/open-source-scouting/PROTOCOL.md`; crear `docs/research/` con fuentes SPDX e informes de regresión. Toda investigación deberá traducirse en código probado.
