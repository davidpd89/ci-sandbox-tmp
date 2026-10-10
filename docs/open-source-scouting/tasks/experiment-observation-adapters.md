# Adaptadores de observaciones confirmadas para ensayos multired

Origen: [PR #80](https://github.com/davidpd89/ci-sandbox-tmp/pull/80),
2026-10-10, revisión adversarial del motor de experimentos.
Trabajo **de implementación** independiente. Leer
`docs/open-source-scouting/PROTOCOL.md`, el código final de
`tools/content_comment_experiments.py` de #80 y el repositorio RRSS oficial
privado en modo lectura.

## Hallazgo verificable

#80 aporta la API de asignación, exposición y resultado maduro, pero
**no verifica productores reales** para ninguna de las nueve redes.
En el oficial existen `action_ledger.py`, `content_queue.py`,
`experiment_uplift.py`, `growth_attribution.py` y
`reply_quality_metrics.py`: ninguna de esas piezas, por sí sola,
acredita un par exposición/resultado final de un experimento con
`event_id` estable, ventana completa y vínculo inequívoco a la
asignación. Un snapshot de seguidores agregado no permite deducir
conversiones individuales. Evitar inventar cobertura.

## Encargo para GPT

Implementar código reutilizable y adaptadores **solo de lectura** para
obtener o, cuando falten datos, declarar explícitamente no verificable
los eventos de contenido y comentarios en X, Threads, Facebook, Pinterest,
Reddit, Bluesky, Mastodon, TikTok e Instagram, discriminando WEB/API/MOBILE.

- Normalizar ACK de publicación y comentario a `exposure` solo
  cuando haya fuente e identidad probadas; nunca confundir
  `en cola`, `intento` ni `texto generado` con exposición.
- Normalizar los eventos positivos y negativos a `outcome`
  **solo** tras ventana completa y evidencia suficiente. Un vacío
  de captura, una métrica global o un fallo de red son
  `unknown`, no `False`.
- Preservar deduplicación e identidad de ensayo sin copiar los
  motores de #80 ni el diseño de identidad de #91.
- Modelar `source`, cobertura, caducidad, instantánea completa,
  reloj UTC, atribución y calidad; no introducir bloqueos de volumen
  sin motivo. Exponer métricas de cobertura que permitan priorizar
  productores realmente útiles.
- Crear un recorrido end-to-end con fixtures sintéticos, replays,
  snapshots incompletos, fallos a mitad de lectura y dos redes
  diferentes, sin acciones reales, sin cuentas, sin secretos ni
  modificaciones de estado vivo.
- Comparar proyectos públicos actuales, licencia SPDX, SHA/tag
  inmutable, mantenimiento y compatibilidad Windows/Linux Python 3.11.
  Reutilizar código compatible frente a inventarlo.
- CI Windows/Ubuntu, `docs/research`, pruebas offline y segunda
  revisión adversarial. Un canario supervisado **no** equivale a
  pruebas sintéticas; dejarlo pendiente para Claude.

## Alcance excluido y dependencias

#80 gobierna el ledger y el análisis posterior, #91 la identidad
auditada del experimento, #23 el marco de atribución y análisis.
Esta PR crea **exclusivamente las fuentes/normalizadores de eventos**.
No ampliar motores estadísticos, generar respuestas ni actuar en redes.

Base obligatoria: `research/public-reuse-parent`.
Sin merge: Claude revisará e integrará después de #80/#91.
