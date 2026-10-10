# Puentes nativos de evidencia para el ledger común de relaciones

## Origen demostrado

La [PR #84](https://github.com/davidpd89/ci-sandbox-tmp/pull/84)
añade `RelationshipLedger`, importador histórico de `registro_interacciones.csv`,
reconciliación basada en snapshots completos y consultas de conversión.
La paridad demostrada es **de contrato sobre fixtures**: el repositorio oficial
`davidpd89/rrss-davidporto-CODE` todavía no emite de forma homogénea
`source_id` y correlación en nueve productores WEB/API/MOBILE.

## Encargo para GPT

**Implementación obligatoria**, no una investigación sin código. Leer el
código y `docs/research/relationship-event-ledger.md` de #84,
`docs/open-source-scouting/PROTOCOL.md` y los escritores actuales del repo
privado en `integracion/crecimiento-2026-10` (solo lectura para contexto;
no trasladar datos personales). Integrar **después** de revisar #84.

Implementar puentes de ingestión de solo lectura desde registros, ACK,
respuestas y snapshots de X, Threads, Facebook, Pinterest, Reddit, Bluesky,
Mastodon, TikTok e Instagram al contrato de #84, respetando tres colas
WEB/API/MOBILE. No duplicar el almacén, la máquina de relaciones de #60,
el modelo de fidelización de #69, ni los adaptadores experimentales de #107.

**Aceptación:** al menos un productor fuente contrastado por red con fixtures
reproducibles y matriz de disponibilidad real (presente/desconocido) por
red y cola; trazabilidad `reserve -> confirmation -> event` cuando el
origen exponga confirmación verificable; IDs de evento estables y
reprocesables; no considerar `skipped/uncertain` como éxito;
snapshots parciales nunca generan no-followback; separación entre
simulación offline y canario supervisado. Si no existe fuente suficiente,
registrar `unknown` sin inventar eventos.

Comparar proyectos públicos activos a fecha de ejecución con licencia SPDX,
revisión inmutable, mantenimiento y Windows/Python 3.11; reutilizar
componentes pertinentes. Añadir código, tests offline sintéticos, CI
Ubuntu/Windows 3.11, `docs/research` con prueba antes/después, segunda
revisión adversarial y rollback. Sin red social real, sin publicar, seguir,
responder o eliminar, sin credenciales o logs sensibles, sin merge.

Base: `research/public-reuse-parent`. Trabajo autónomo únicamente en esta
rama después de #84. Claude hará la integración final.
