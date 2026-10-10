# PR #66 — Ranking explicable de candidatos (10-10-2026)

**Estado:** implementación offline, sin activación de ejecutores ni mutación de estados.
**Alcance:** clasificación de cuentas, posts y oportunidades observadas, con contrato
común y adaptadores ligeros. La PR **no** ejecuta, selecciona cupos ni agenda acciones.
**Módulos:** `tools/target_quality_ranking.py`,
`tools/target_quality_benchmark.py`,
`tests/test_target_quality_ranking.py` y
`.github/workflows/target-quality-ranking.yml`.

## Problema

Leídos `docs/open-source-scouting/tasks/56-target-quality-ranking.md` y
`docs/open-source-scouting/PROTOCOL.md`. En el espejo se verificaron
`tools/bluesky_growth_scan.py`, `tools/mastodon_growth_scan.py`,
`tools/tiktok_growth_scan.py`, `tools/pinterest_growth.py`,
`tools/growth_policy.py` y `tools/candidate_identity.py`.

Se consultó en **solo lectura** el repositorio privado oficial
`davidpd89/rrss-davidporto-CODE`,
rama `integracion/crecimiento-2026-10`, commit
`5449513d9b545d0a6a72abf066ab6a779bfdad71` (10-10-2026):
`tools/discovery_ranking.py`, `tests/test_discovery_ranking.py`,
`tools/discovery_attribution.py` y `tools/discovery_graph.py`.
No se trasladan credenciales, identificadores de cuentas reales, historiales ni
datos privados. La implementación oficial de `discovery_ranking` clasifica
**cohortes de fuente con snapshots verificados**, no posts ni cuentas individuales;
conservarla para esa responsabilidad, no reemplazarla.

**Brecha demostrable:** los escáneres asignan puntuaciones distintas a cuentas
(Bluesky: fuentes y relaciones; Mastodon: bio, fuentes y actividad;
TikTok: coincidencias y recurrencias; Pinterest: reglas propias). Comparar scores
crudos entre redes no representa la misma evidencia y las oportunidades de
publicación no tienen una explicación común ni un replay retrospectivo aislado.

Dependencias de integración:
- [#21](https://github.com/davidpd89/ci-sandbox-tmp/pull/21) y
  [#4](https://github.com/davidpd89/ci-sandbox-tmp/pull/4): ranking de cohortes,
  muestras maduras, rotación de fuentes; **no duplicar ni sustituir**.
- [#23](https://github.com/davidpd89/ci-sandbox-tmp/pull/23):
  atribución y medición longitudinal.
- [#49](https://github.com/davidpd89/ci-sandbox-tmp/pull/49):
  trazabilidad; no inferir consulta/semilla por similitud de texto.
- [#61](https://github.com/davidpd89/ci-sandbox-tmp/pull/61):
  paridad temporal; el ranking mantiene su propia comprobación de antigüedad
  como defensa sobre posts del input.
- [#66](https://github.com/davidpd89/ci-sandbox-tmp/pull/66)
  no altera ninguna rama de las anteriores.

## Alternativas

## Licencias y procedencia

Fuente primaria: https://github.com/lightgbm-org/LightGBM/tree/1910cd9f8c90b3207f348ce2c78d17d07bf042d7
Fecha de consulta: 2026-10-10
Licencia SPDX: MIT
Referencia inmutable: N/A (sin codigo incorporado)

Los cuatro campos anteriores documentan una fuente contrastada: la licencia MIT
pertenece a LightGBM, no se atribuye al código original de esta PR. No se ha
copiado código de LightGBM ni de ningún tercero.

Comprobaciones de GitHub REST a 10-10-2026; los enlaces de commit fijan la
versión observada. Se consultó licencia SPDX declarada por cada repositorio;
no se ha importado ni copiado código de terceros.

| Proyecto | Commit verificado, licencia y última actividad | Encaje y decisión |
| --- | --- | --- |
| [LightGBM](https://github.com/lightgbm-org/LightGBM/tree/1910cd9f8c90b3207f348ce2c78d17d07bf042d7) | MIT; push 10-10-2026 | `LGBMRanker` admite learning-to-rank, Python 3.11 y wheel Windows. Exige etiquetas por candidato y grupos, calibración y suficientes históricos; **no** incluir todavía en un contrato cold-start. Candidato cuando haya holdout real. |
| [implicit](https://github.com/benfred/implicit/tree/8a95dbe24ca675a6edd86aafb3b4cd5ae7287edf) | MIT; push 08-05-2026 | BPR/ALS para preferencias usuario-ítem, prueba Windows/Python 3.11 declarada. Datos de un único autor y baja interacción no sostienen factorizar matrices. Descartado por dependencia SciPy/nativa y escasez de interacciones. |
| [rank_bm25](https://github.com/dorianbrown/rank_bm25/tree/47aa3ddf8dc1ebeb7ef4e65f2b4536af44594099) | Apache-2.0; push 02-05-2026 | Relevancia léxica; no aprende reciprocidad ni frescura, y añade NumPy. Alternativa útil en **recuperación** (#21), no para ordenar oportunidades pequeñas ya recuperadas. |
| [ranx](https://github.com/AmenRa/ranx/tree/7363db0c35e92e90d6fa6fe73907b760678f765e) | MIT; push 07-08-2025 | Métricas de ranking offline (nDCG, P@k). Para cuatro métricas binarias y dataset reducido resulta más ligero mantener evaluador stdlib comprobable; candidato cuando haya varios experimentos y estudios de significación. Compatibilidad efectiva Windows/3.11 no probada aquí. |
| [scikit-learn](https://github.com/scikit-learn/scikit-learn/tree/46449a10defc79e0615391c15106fc966bbc8261) | BSD-3-Clause; push 09-10-2026 | Métricas, pipelines y regresión supervisada. Más complejidad que un baseline interpretable sin históricos fiables. Evaluar tras disponer de cohorte prospectiva. |

Se conserva la parte útil existente (campos de `shortlist`, reglas de edad
configuradas en `growth_policy`, patrón de evidencia conservadora Wilson del
ranking de fuentes) y se implementa **solo** la interfaz común necesaria.
Sin dependencias externas ni importaciones del repositorio privado: stdlib
Python 3.11; OS-independiente. No se copian implementaciones de las bibliotecas
externas; por tanto no se arrastran notices ni licencias de terceros.

## Decisión

Conservar los algoritmos de ranking de fuentes existentes y añadir un módulo
stdlib, de solo lectura, para candidatos. El enfoque conservador es reversible,
explicable e independiente de credenciales.

### Contrato

`rank_network(network, candidates, *, as_of, outcomes={}, ...)` devuelve
`ranked`, `rejected`, `adapter` y `note`.
`rank_all(snapshots, as_of=...)` contempla las **nueve** redes; una entrada
ausente se muestra como `missing_input`, nunca como "0 candidatos".
`evaluate_orders(new_ids, old_ids, heldout, k)` calcula P@k y nDCG@k
por `followback`, `response`, `conversation`, `traffic`;
los no observados **no** se convierten en resultados negativos: si hay
etiquetas no observadas entre los k puestos expuestos, se informa
`observed/exposed/unjudged`, pero precisión y nDCG quedan `null`.
La referencia ideal de nDCG considera todos los positivos conocidos del
universo evaluado, no únicamente los recuperados en top-k.

- Cuentas: `topic` 34 %, diversidad de fuentes 12 %, actividad 14 %,
  español 9 %, tamaño de audiencia 10 %, reciprocidad 9 % e histórico observado
  12 %. Score **0..100** = suma de puntos conocidos con pesos fijos; campo
  `coverage` separa evidencia ausente de evidencia negativa. No vender
  `score` como probabilidad ni como conversión causal.
- Histórico: solo `{verified:true, mature:true, trials>=10, followbacks,
  responses, conversations, traffic}`; Wilson unilateral 95 % combinado
  con pesos explícitos. Fuente sin confirmación: valor `null`, no cero.
- Posts: fecha con zona, idioma observado, coincidencias de nicho,
  respuestas y antigüedad. Límite adquisición 21 días, comunidad 45 días
  por defecto (parámetros ajustables al `growth_policy` de cada scan).
  Fuera de edad o con fecha ausente no obtiene oportunidad de interactuar.
  Un post de idioma desconocido se conserva solo como evidencia informativa:
  no genera interacciones ni aumenta el score temático de la cuenta.
  Únicamente los posts vigentes con español explícito suman afinidad.
  Una cuenta no desaparece por tener todos sus posts vencidos.
- Acciones: **solo** las permitidas por la shortlist de origen:
  `follow`, `reply`, `comment`, `repost`. `like` no se propone,
  especialmente nunca auto-like en X. Ranking informativo, sin ejecución,
  sin escrituras ni colas.
- Identidad y deduplicación: namespaced por red; prefiere DID Bluesky;
  Mastodon acct + instancia; resto handle o ID explícito. Cuentas duplicadas
  en un snapshot se rechazan; posts se deduplican por URI/ref/status/URL,
  **no** por ordinal del scan.
- Explainability: dimensión `value` (o `null`), `weight`,
  `points`; empates con orden estable, `post_rejections` con causas.

### Compatibilidad de adaptadores comprobada

| Red | Entrada disponible en espejo | Qué cubre y qué queda |
| --- | --- | --- |
| Bluesky | `shortlist` con profile, posts (`es`, `created_at`, URI) | Cuenta y posts con edad explícita; integrado **solo offline** |
| Mastodon | `shortlist` con acct, follower counts, lengua, fechas y URL | Cuenta y posts con edad explícita; integrado **solo offline** |
| TikTok | `shortlist` con handle, independencia de fuentes, vídeos | Cuentas; vídeos sin fecha observable **rechazados**, no inventar timestamps |
| Pinterest | `authors` con handle y bio | Perfiles; pins precisan normalización temporal específica |
| X, Threads, Facebook, Reddit, Instagram | Formato común explícito `handle/account_id`, `posts` | Contrato soportado offline; **sin puente de lector nativo verificado**. Ninguna red activada |

**No confundir nueve contratos compatibles con nueve integraciones operativas.**
Un adaptador específico deberá validar IDs, marcas temporales e idioma antes
de pasar una `shortlist` a la capa. `normalized_input_only` señala esa brecha.

Ejemplo reproducible, sin fichero de estado real:

```python
import datetime as dt
from tools.target_quality_ranking import rank_all
out = rank_all({"instagram": [{"handle": "synthetic.reader",
    "bio": "Leo libros de fantasía", "followers": 300,
    "actions": ["follow"], "posts": []}]},
    as_of=dt.datetime(2026, 10, 10, tzinfo=dt.timezone.utc))
print(out["networks"]["instagram"]["ranked"][0]["explanation"])
```

## Antes/después verificable

`python tools/target_quality_benchmark.py` usa **ocho cuentas inventadas**:
cuatro lectores pertinentes con score legacy inferior (4), cuatro perfiles
desvinculados con score legacy superior (20). Labels futuros **sintéticos**,
cuatro oportunidades etiquetadas para cada métrica, k=4.

| Métrica sintética @4 | Legacy (orden por score original) | Ranking común |
| --- | ---: | ---: |
| Precisión followback / respuesta / conversación / tráfico | 0,00 | 1,00 |
| nDCG de las cuatro métricas | 0,00 | 1,00 |

**Interpretación estricta:** verifica que la regla selecciona contenido del
nicho por delante de scores nativos inflados en **este caso diseñado**. No es
una mejora de conversión medida, ni un backtest histórico, ni una causalidad.
Faltan registros reales seguros, etiquetas posteriores, auditoría de
observación y separación temporal, fuera del alcance de este espejo.
Una cohorte con señales contrarias puede invertir el resultado; ajustar
pesos solo tras probar en holdout y documentar deriva y calibración.

## Pruebas y revisión adversarial

Comandos (no acceden a ninguna cuenta):

```shell
python -m unittest discover -s tests -p test_target_quality_ranking.py -v
python tools/target_quality_benchmark.py
```

CI del HEAD: `Target quality ranking (synthetic)` con matriz
`ubuntu-latest` / `windows-latest` y Python 3.11. No requiere pip.

Pasadas adversariales:
1. Identidades cruzadas y repetidas, empate estable y cuentas sin evidencia.
2. Unicode/tildes, valores NaN/Inf/bool, idiomas incorrectos y desconocidos.
3. Necroposting, fecha sin zona, fecha futura, límite comunidad vs adquisición,
   publicaciones duplicadas, ordinal del scan sin ID real.
4. Cohortes pequeñas/inmaduras o inverificadas: no elevar tasas de éxito.
   Evaluación con etiquetas parciales: sin compactar slots desconocidos
   hacia puestos más altos ni ideal nDCG autorreferencial.
5. Sin auto-like X, sin ampliar permisos de acciones observadas, sin acceso
   a autenticación y sin mutaciones.
6. Replay con baseline hostil y etiquetas independientes sintéticas.
7. Separación de datos desconocidos, salidas deterministas y benchmark no causal.

**Limitaciones para Claude:** la biblioteca no está conectada a los ejecutores;
antes del merge revisar la suite oficial completa y merge-preview contra
`integracion/crecimiento-2026-10`. En Windows vivo, Edge y TikTok móvil
faltan canarios **supervisados**, distintos de estos tests simulados.
En concreto TikTok carece de fecha fiable en la shortlist publicada, y otras
redes no tienen mapping nativo auditado. Comparar con PR #21 y #4 para
mantener separadas métricas de fuentes y candidaturas. No se cambió ningún
formato/estado real ni se activaron oportunidades.

## Retirada

**Rollback:** revertir commits de esta PR (nuevos módulos, tests y workflow),
sin migraciones, tablas ni efectos secundarios; código de producción existente
no importa el nuevo módulo. No hay dependencias añadidas.

**Futuro, sin promesa de producción:** conectar adaptadores de lectura reales,
hacer replay temporal con observaciones verificadas y explorar ML solo si
hay etiquetas suficientes; coordinar esa integración con Claude/#21/#23.
