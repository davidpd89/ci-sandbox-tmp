# Adaptadores de agenda relacional a planes nativos

**Origen:** PR #71, `tools/relationship_priority.py`. El score es puro
y comprobable, pero los ejecutores no lo alimentan todavía con snapshots
confiables ni consumen su recomendación solo tras preflight.

## Encargo para GPT

Implementar un puente **real, de solo lectura y en seco** desde los
productores ya existentes de nueve redes (X, Threads, Facebook, Pinterest,
Reddit, Bluesky, Mastodon, TikTok, Instagram) hasta el contrato de #71.
No recalcular ni duplicar el scoring.

- Verificar la rama oficial `integracion/crecimiento-2026-10` y su espejo,
  coordinando con #60 (estado), #65 (reciprocidad), #66/#100 (candidatos),
  #69 (inbound) y #70 (descubrimiento).
- Transformar fuentes y registros de acciones confirmadas a
  `affinity`, `reciprocity`, contadores inbound deduplicados,
  `actor_id`, edad de post y elegibilidad; indicar explícitamente
  incertidumbre/ausencia de datos, sin inventar valores.
- Generar snapshots y cola *dry-run* reproducibles WEB/API/MOBILE,
  sin generar comentarios, publicar ni tocar cuentas. El score **no**
  habilita por sí solo acciones: revalidar `comment_allowed`, bloqueo,
  fecha del destino, follow y reglas del ejecutor antes de proponer
  un plan a los motores de cada red.
- Garantizar que la misma cuenta no se planifique dos veces entre colas
  y que el rechazo o falta de datos de una red no consuma presupuesto
  de otra. Verificar en especial X sin auto-like y corte antinecropost.
- Entregar código, fixtures ficticios 9x3, tests Windows/Ubuntu
  Python 3.11, benchmark de coste de lectura, rollback, fuentes
  públicas (licencias y commits fijos) y **segunda auditoría adversarial**.
  Separar simulación de canario supervisado.

**No duplicar:** #100 normaliza descubrimientos para el ranking de
cuentas/posts #66; esta PR lleva elegibilidad/observaciones del CRM
y PRIORIDAD DE RELACIONES de #71 al plan diario. #69 prepara el
historial inbound; esta PR lo consume sin implementar otro agregador.

**Base:** `research/public-reuse-parent`.
**Rama:** `research/daily-priority-planner-adapters`.
**Sin merge:** Claude integra tras aprobar #71 y contratos precursores.
