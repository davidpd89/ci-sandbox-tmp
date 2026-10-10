# Adaptadores Nativos de Evidencia Contextual para Nueve Redes

## Problema

La auditoría de evidencia contextual realizada en PRs previas (#74) evidenció que los productores de observaciones (pistas de lecturas WEB, API y MOBILE en Bluesky, Mastodon, X, Threads, Facebook, Pinterest, Reddit, TikTok e Instagram) no contaban con adaptadores normalizados homogéneos. Se observaba fragilidad en permalinks, discrepancias de tipos en fechas y falta de indicación explícita de campos ausentes, provocando que los analizadores aguas abajo intentaran interpretar datos faltantes o inventar descripciones no vistas.

## Alternativas

| Baseline | Candidato OSS | Adaptar patrón | Mantener baseline |
|---|---|---|---|
| Módulos heterogéneos sin contrato estándar | SDKs oficiales de las 9 redes (atproto, Mastodon.py, Tweepy, PRAW, etc.) | Norma global `ContextPacket` con adaptadores finos por red y cola | Mantener extractores ad-hoc dispersos |

**Decisión:** Adaptar el patrón unificado mediante la estructura `ContextPacket` y el adaptador `adapt_native_observation()`. Se consulta la estructura estándar de las respuestas de las APIs/extraccciones web/móvil públicas reutilizando contratos oficiales con licencias permisivas.

## Licencias y procedencia

Fuente primaria: https://docs.github.com/en/rest/pulls/pulls
Fecha de consulta: 2026-10-09
Licencia SPDX: MIT / Apache-2.0 / BSD-3-Clause
Referencia inmutable:
- ATProtocol / Bluesky (MIT / Apache-2.0): `bluesky-social/atproto` commit `6d8d5146`
- Mastodon.py (MIT): `halcy/Mastodon.py` commit `0077e868`
- Tweepy / X API (MIT): `tweepy/tweepy` commit `dc403549`
- PRAW / Reddit (BSD-2-Clause): `praw-dev/praw` commit `ccb24a5bf`

## Decisión

Adoptada la opción C (patrón reimplementado y normalizado en `tools/native_context_adapters.py`).
Soporta las 9 redes sociales en las 3 colas de ejecución (WEB, API, MOBILE). Preserva:
- `remote_id` e identificadores de hilo/padre estables.
- Normalización estricta de `published_at_iso` en UTC.
- Texto principal y cuerpo/desglose si está presente.
- Metadata del autor (`author_handle`, `author_name`).
- Elementos multimedia con origen y procedencia explícitos, sin inventar descripciones o alt text no provistos.
- Marcado explícito de `missing_fields` cuando la red o el nivel de acceso no entregan la evidencia.

## Pruebas y Benchmark

Pruebas ejecutadas con `unittest`:
```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_native_context_adapters.py
```
Resultado: 4/4 tests pasados en 0.011s.
- Verificación diferencial 9 redes × 3 colas de ejecución.
- Casos visual-only sin inventar alt/texto.
- Verificación de Unicode, fechas diversas (ej. Twitter header format, timestamps Unix) e ISO 8601.
- Cálculo de `completeness_score` con métricas transparentes.

## Revisión Adversarial y Salvaguardas

1. **Riesgo:** Inyección de instrucciones a través del texto normalizado de publicaciones ajenas.
   - **Salvaguarda:** El paquete aísla `text` y `body` como datos pasivos de contexto. No se evalúan como instrucciones ejecutables por los workers.
2. **Riesgo:** Fabricación de descripciones de imágenes/vídeos cuando no existen alt textos.
   - **Salvaguarda:** Se declara explícitamente `alt: None` y `text: None` cuando no estén en la carga nativa, añadiendo el campo faltante a `missing_fields`.
3. **Riesgo:** Deriva de zona horaria o fechas incompletas.
   - **Salvaguarda:** `_normalize_iso_timestamp` fuerza conversión explícita a UTC con sufijo `Z` o devuelve `None` marcado en `missing_fields`.

## Retirada y Rollback

- Módulo aislado sin efectos secundarios sobre ledgers o cuentas reales.
- Rollback simple: eliminar `tools/native_context_adapters.py` y `tests/test_native_context_adapters.py`.
