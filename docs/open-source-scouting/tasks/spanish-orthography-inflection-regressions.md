# Evitar falsos positivos morfológicos en el corrector español común

Origen verificable: [PR #72](https://github.com/davidpd89/ci-sandbox-tmp/pull/72),
benchmark sintético de comentarios de nueve redes ejecutado en Ubuntu Python 3.11.
Un comentario sintético perfectamente ortográfico:
«¿Hay alguna regla para que se borren esos mapas?» no superó
`tools/reply_writer.valid_reply()` porque
`tools/x_interact._check_spanish_orthography` notificó
`posible tilde/ene perdida en: borren`.
La forma **borren** es válida del presente de subjuntivo/imperativo de
`borrar`; el detector por diccionario de `tools/spellcheck_es.py` ya
reconoce que no cubre bien conjugaciones, y mantiene una lista manual
`_VALID_UNACCENTED` para otros falsos positivos (`publica`, `londres`).

## Encargo para GPT

**Implementar, no solo investigar.** Leer
`docs/open-source-scouting/PROTOCOL.md`,
`tools/spellcheck_es.py`,
`tools/x_interact.py`, `tools/reply_writer.py` y el contexto del
repositorio privado `rrss-davidporto-CODE` en rama
`integracion/crecimiento-2026-10` (solo lectura).
Comparar código público mantenido para morfología, lematización y
correctores en español (por ejemplo LanguageTool, spaCy,
`wordfreq`, diccionarios de conjugaciones), verificar commits
inmutables/licencia/dependencias y compatibilidad Windows/Python 3.11.
Preferir conservar el detector con una mejora ligera verificada si gana
frente a un runtime pesado.

Entregar **código real en esta PR** y regresiones sintéticas que demuestren
que verbos correctamente flexionados (incluido `borren`) no se bloquean
por posibles tildes, pero `capitulo` por `capítulo` cuando es inequívoco
sigue detectándose. Medir falsos positivos/falsos negativos en un corpus
editorial ES-ES con casos ambiguos de contexto (`publico/publicó`,
`publica/publicá`), nombres propios y vocabulario de fantasía.
Preferir avisos revisables si hay incertidumbre lingüística a bloquear
una respuesta correcta. No eliminar en bloque la guardia; mantener
compatibilidad con el validador de respuestas utilizado por las nueve
redes. Valorar relación con #50 (Unicode) sin duplicar su trabajo.

Pruebas offline y workflow Ubuntu/Windows Python 3.11, fixtures ficticios,
`docs/research` con alternativa/licencia/medición antes-después,
revisión adversarial, rollback sin cambios irreversibles. Sin cuentas,
tokens, publicación, seguimiento, acceso móvil, secretos, merge ni estados
reales. Integración final sujeta a Claude. Base
`research/public-reuse-parent`.

**Criterio de aceptación:** reproducir el fallo sin servicios externos,
corregirlo, conservar la regresión positiva y verificar cobertura de
cada consumidor de `valid_reply` sin añadir una excepción específica
por red. Esta PR nace de un fallo real de test, no de una mejora estética.
