# PR #126 — descubrimiento de conversaciones Reddit (10/10/2026)

**Alcance:** adaptador **opt-in, solo lectura**, sin cuentas, sin secretos, sin escrituras ni cambios al runner. El informe de Perplexity `docs/perplexity/crecimiento-reddit.md` es el punto de partida, **no** evidencia suficiente.

## Problema

El escáner Reddit actual carece de un puente **API de consulta read-only** y no debe recibir recomendaciones ajenas a su scope editorial.

## Alternativas

Se contrasta PRAW con menshun, social-listening-tool, Reddit-Monitor, prawtools y el notebook de análisis; véase la tabla de comparación y descartes más abajo.

## Licencias y procedencia

Fuente primaria: https://github.com/praw-dev/praw
Fecha de consulta: 2026-10-10
Licencia SPDX: BSD-2-Clause
Referencia inmutable: https://github.com/praw-dev/praw/tree/4a9eb7ee3ac5743ce8b848e9f7b187eae4826da1

## Decisión

Se incorpora como **dependencia opcional real** la API PRAW y un extractor limitado a comunidades aprobadas. El contrato multirred de #100 y el ranking de #116 siguen separados para evitar duplicación.

## Pruebas

Suite sintética con PRAW mock + instalación de PRAW en Windows/Ubuntu Python 3.11, sin red ni datos de cuentas. Reproducibilidad detallada más abajo.

## Retirada

Eliminar lector, pruebas, requisitos opcionales, workflow e informe. Ninguna migración ni efecto sobre el programa operativo.

## Revisión contra el sistema operativo

Repositorio privado `davidpd89/rrss-davidporto-CODE`, rama
`integracion/crecimiento-2026-10`, commit **5449513d9b545d0a6a72abf066ab6a779bfdad71**:

- `tools/reddit_interact.py` ya implementa navegación y búsqueda manual con Edge CDP, lectura de `<shreddit-post>`, comentarios e identidad de hilos.
- `tools/reddit_scan.py` lee comunidades aprobadas, filtra preguntas y consulta historial confirmado/incierto. `reddit_execute.py` solo admite `comment`/`vote`; no sigue perfiles ni hace reposts.
- `SISTEMA_DIARIO_REDDIT/REGLAS.md` (scope 03/10) obliga a **microrrespuestas de 1–5 palabras y máximo 40 caracteres**, sin enlaces, y a revisar normas de cada comunidad. **El informe proponía respuestas largas, follow y repost: se descartan por contradicción.**
- `tools/discovery_terms.py` y `tools/growth_common.py` ya tienen vocabulario y presupuestos de lectura. Las PR públicas [#115](../perplexity/descubrimiento-nicho-booktok.md), [#100](https://github.com/davidpd89/ci-sandbox-tmp/pull/100), [#116](https://github.com/davidpd89/ci-sandbox-tmp/pull/116), [#117](https://github.com/davidpd89/ci-sandbox-tmp/pull/117), [#120](https://github.com/davidpd89/ci-sandbox-tmp/pull/120), [#134](https://github.com/davidpd89/ci-sandbox-tmp/pull/134) cubren descubrimiento multirred, puentes, ranking, paridad, reciprocidad y experimentos. No se copia su lógica ni se conecta aquí al ejecutor.

## Repositorios externos auditados en GitHub (10/10/2026)

| Proyecto | Commit/fuente | Licencia | Decisión |
| --- | --- | --- | --- |
| [praw-dev/praw](https://github.com/praw-dev/praw/tree/4a9eb7ee3ac5743ce8b848e9f7b187eae4826da1) | `4a9eb7ee` (09/10/2026), release `v8.0.3` (12/08/2026) | BSD-2-Clause | **Reutilizado realmente** como dependencia opcional del adaptador: `praw.Reddit(client_id, client_secret, user_agent)` y `subreddit.search()`. Soporta Python >=3.10 y es independiente de Edge. No vendoring ni modificación del código original. |
| [dansholds/menshun](https://github.com/dansholds/menshun/tree/f65f1d80db65bb3b84bf150679a3cd05d36546b5) | `f65f1d80` (18/09/2024) | MIT | Se verificó código `menshun.py`, usa PRAW + `ahocorasick` + monitor continuo. **No se importa ni copia**: dependencia y modalidad de stream innecesarias para la lectura por lotes y scope actual. Solo se toma el principio de detectar temas. |
| [phil-morton/social-listening-tool](https://github.com/phil-morton/social-listening-tool/tree/ffef49b655d5ab37d85d9f77b3bd00436592a643) | `ffef49b6` (16/10/2025) | Sin licencia verificable (no hay LICENSE en raíz) | **No copiar**. JSONL es formato interoperable estándar, implementado de cero; no se copió `reddit-pull.py`. |
| [AlexAbbamondi/Reddit-Monitor](https://github.com/AlexAbbamondi/Reddit-Monitor/tree/31d5f8aadcd3d5be66284a5121897fd6b37ae6d2) | `31d5f8aa` (27/01/2025) | MIT | No aporta mayor valor que el motor/cola existentes; sin integración. |
| [praw-dev/prawtools](https://github.com/praw-dev/prawtools) | archivado, último push 19/12/2022 | BSD-2-Clause | No dependencia nueva; solo referencia conceptual. |
| [pillaikartik10/python-reddit-analysis](https://github.com/pillaikartik10/python-reddit-analysis) | último push 02/06/2021 | Sin licencia verificable | Notebook sin encaje; no copiar. |

**Compatibilidad:** PRAW 8.0.3 soporta Python 3.11 y distribuye paquete Python; no necesita CDP/Windows para consultas API. La ejecución real en una cuenta/cliente OAuth **no se ha comprobado ni autorizado**. El paquete se declara en `requirements-reddit-opportunities.txt`, separado de las dependencias del sistema productivo.

## Implementación concreta

- `tools/reddit_opportunity_reader.py`: inyección del cliente PRAW para búsqueda por subreddits y consultas, con `sort=new`, `time_filter=week`, `limit` acotado (el servidor puede ignorar el filtro temporal con `new`; se verifica localmente la antigüedad); solo `r/libros` y `r/filosofia_en_espanol` admitidos. **La segunda sigue pendiente de validar normas en vivo antes de comentar**: este lector no autoriza hacerlo.
- Rechaza posts sin ID/fecha/título verificables, fechas futuras, posts antiguos, comunidad fuera de scope, iteradores anómalamente extensos y conflicto de identidad para un mismo ID. Fusiona búsquedas duplicadas, pero **no** fusiona observaciones contradictorias; el 429/5xx se propaga sin simular éxito.
- Añade señales léxicas de temas/posible pregunta, con distinción explícita entre pistas y hechos. No inventa idioma, valoración, intención, resultados ni autor para cuentas eliminadas. `verified_actions=[]`, `status=manual_review_required`: **no existe función reply/submit/follow ni cola ejecutable**.
- `to_jsonl()` permite al coordinador obtener un texto JSONL en memoria. No crea/modifica archivos, no lee tokens y no publica.
- El contrato de salida explicita `network=reddit`, `queue=API`, `url`, `author`, `created_utc`, `source` y `language=None`, campos afines al adaptador común de #100. **Integración efectiva en #100/#66/#116 pendiente de revisión de Claude**: especialmente idioma y comprobación del scope editorial, sin duplicar ranking de las nueve redes.

## Pruebas y revisión adversarial

```bash
python -m pytest -q tests/test_reddit_opportunity_reader.py -p no:cacheprovider
python -m compileall -q tools/reddit_opportunity_reader.py tests/test_reddit_opportunity_reader.py
```

Fixtures herméticos: búsquedas PRAW simuladas, bloqueo a `r/all`/comunidades no aprobadas, fechas inválidas/futuras, identidad canónica, duplicados de distintas consultas, conflictos de ID, idiomas desconocidos, autor borrado, ratio/tasas nulas, señales Unicode, excepciones de servicio sin falso éxito, tope de iterador, serialización JSONL y factoría read-only. Workflow dedicado ejecuta Windows/Ubuntu **Python 3.11** con paquete real instalado, sin llamadas a Reddit.

**Revisión independiente — 2.ª pasada:** se eliminó del alcance la propuesta de `follow_profile`/`repost` y se evitó reemplazar `reddit_scan.py`. Un post con palabras clave no demuestra encaje editorial ni permite inferir español. El lector tampoco interpreta 1.000 resultados como censo completo ni promete tasa de API fija: el comportamiento y las cuotas dependen del cliente/servidor. **3.ª pasada:** comprobaciones de entradas duplicadas, timestamp, subconjunto por comunidad y difusión de errores sin falsos positivos.

## Estado / pendientes

- No se modifica el programa operativo ni el espejo original, ni se efectúan acciones reales en redes.
- Claude deberá validar Windows/Edge/Android, secretos locales sin exponerlos, el lector real de PRAW si consigue acceso autorizado, el scope actual y la suite completa del repo privado; conectar a contratos de #100/#66/#116 después de revisarlos y sin activación accidental.
- **Rollback:** eliminar `tools/reddit_opportunity_reader.py`, `tests/test_reddit_opportunity_reader.py`, `requirements-reddit-opportunities.txt`, workflow dedicado y este informe. Nada que migrar.
