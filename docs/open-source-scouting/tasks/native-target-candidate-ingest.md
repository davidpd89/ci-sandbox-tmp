# Implementación: normalización nativa de candidatos para ranking común

**Origen concreto:** PR #66 (`research/56-target-quality-ranking`) aportó un
ranker 0..100 de solo lectura compatible con nueve redes, pero verificó que
solo Bluesky, Mastodon y TikTok disponen de `shortlist` nativa contrastada;
Pinterest únicamente expone autores y X, Threads, Facebook, Reddit e Instagram
requieren normalizadores para las entradas de sus recolectores. Sin ellos, una
afirmación de "ranking activado en nueve redes" sería incorrecta.

## Encargo para GPT

Implementa **código real**, pruebas sintéticas y documentación para adaptar
solo lecturas de candidaturas (no productores de comentarios ni automatización
de acciones) de **X, Threads, Facebook, Reddit, Pinterest e Instagram** al
contrato común de `tools/target_quality_ranking.py` de la PR #66.

1. Leer `docs/open-source-scouting/PROTOCOL.md`, los escáneres del espejo
   y los lectores oficiales desde `rrss-davidporto-CODE` en rama
   `integracion/crecimiento-2026-10` (solo lectura, sin copiar datos
   sensibles), verificando qué campos existen por red y por cola WEB/API/MOBILE.
2. Comparar librerías públicas actuales con sus licencias SPDX y commits
   inmutables; reutilizar adaptadores/serializadores públicos compatibles
   Windows y Python 3.11 si ahorran código.
3. Generar filas normalizadas con `network`, identidad estable de cuenta,
   `sources`, bio, recuento de seguidores si existe, relación y **posts con
   referencias reales estables, timestamp con zona e idioma observado**.
   Ausencia debe ser `None` y quedar explicada, nunca inventarse desde
   ordinales del escáner o recibos ambiguos.
4. Cubrir fixtures separados de seis redes, cuentas duplicadas, cambio de
   handle, fechas ausentes/futuras, UTC/DST, bloqueo del necroposting, posts
   antiguos, páginas parciales y compatibilidad con la salida de #66.
5. Diseñar **módulos de lectura puros** y contract tests; no modificar planes
   de ejecución ni activar follows, respuestas, auto-likes o reposts.
   Tests Ubuntu/Windows Python 3.11 y segunda revisión adversarial.
6. Entregar `docs/research/native-target-candidate-ingest.md` con límites de
   cobertura, comparativa, atribuciones, resultados y forma reversible de
   retirar la integración. Si alguna red no tiene lector verificable,
   dejar estado explícito `unsupported` y una propuesta concreta de
   instrumentación, sin falsificar cobertura.

**Separación de trabajos:** #21/#4 son cohortes y descubrimiento; #99 son
observaciones de hashtags, #23 atribución longitudinal; #66 clasifica filas
ya normalizadas. Esta PR implementa **solo los puentes de datos de candidatos**
faltantes. Integrar después de revisión de #66. No merge: Claude revisa.

**Límites:** solo datos sintéticos, sin credenciales ni estados de usuarios
reales, ninguna acción en redes, no guardar información privada en la PR.
