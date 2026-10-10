Fuente primaria: https://github.com/fidelity/mabwiser
Fecha de consulta: 2026-10-10
Licencia SPDX: Apache-2.0
Referencia inmutable: https://github.com/fidelity/mabwiser/commit/b104071351d532aae977955d19b83872a9c1b1e3

## Problema
Falta un ranking experimental de acciones que consuma únicamente resultados D+7 confirmados, sin duplicar ranking de fuentes, cohortes ni ejecutores.

## Alternativas
MABWiser opcional para LinUCB; Vowpal Wabbit exige mayor complejidad operativa; contextualbandits y pybandits añaden una segunda dependencia; banditml no se reutiliza por GPL y falta de mantenimiento.

## Licencias y procedencia
Reutilizado por dependencia externa MABWiser 2.7.4 (Apache-2.0), commit inmutable arriba. Sin copia de código ajeno; enlaces/versiones del resto en la tabla de contraste.

## Decisión
Núcleo de solo lectura, nueve adaptadores, cold-start por reglas y entrenamiento LinUCB solo con cohortes completas D+7, 300 casos por red y 30 por acción. Sin conectar ejecutores.

## Pruebas
27 pruebas unitarias offline locales; integración MABWiser mediante CI Ubuntu/Windows Python 3.11. Comprobar siempre el HEAD exacto y la suite del oficial antes de integrar.

## Retirada
Eliminar núcleo, adaptadores, tres tests y workflow. Sin migraciones de estado persistido ni acciones ejecutadas.

---

# PR #116 — investigación aplicada y ranking experimental (10/10/2026)

## Decisión e integración

Se ha implementado **un núcleo puro de ranking offline** en `tools/action_bandit.py` y **nueve traductores de etiquetas nativas** en `tools/action_bandit_adapters.py`. Sin acceso a redes, credenciales, navegador, móvil, SQLite real ni modificaciones de planes. Los cambios de score nunca implican permiso de ejecución.

**Reutilización real:** `fidelity/mabwiser` **2.7.4**, licencia **Apache-2.0**, HEAD/tag verificado `b104071351d532aae977955d19b83872a9c1b1e3` ([fuente](https://github.com/fidelity/mabwiser/commit/b104071351d532aae977955d19b83872a9c1b1e3), [licencia](https://github.com/fidelity/mabwiser/blob/b104071351d532aae977955d19b83872a9c1b1e3/LICENSE), [API](https://fidelity.github.io/mabwiser/api.html)). Se importa `MAB`/`LearningPolicy.LinUCB` y se llaman `fit` y `predict_expectations`; no se copia ni reescribe el algoritmo. Dependencia **opcional**, aislada del `requirements-ci.txt` general. La dependencia publica wheel `py3-none-any` y declara Python >=3.8, pero arrastra NumPy/SciPy/scikit-learn/pandas/seaborn, por lo que se prueba aparte en Windows/Ubuntu Python 3.11.

**Selección conservadora:** cold-start usa score explicable de afinidad, actividad, conversación, fiabilidad de fuente y priors declarativos. Solo tras **300 recompensas completas D+7 por red**, con **30 por cada uno de los tres brazos** (`follow`, `reply`, `repost`), puede entrenar LinUCB. Predicciones se mezclan al 40% con el prior. El ranking es propuesta de solo lectura; no hace exploración aleatoria en perfiles reales ni se promociona a selección automática. Los pesos de recompensa (0,45 reciprocidad / 0,35 engagement / 0,20 conversación) **son hipótesis**, no estimaciones de uplift. La calidad del perfil NO se contabiliza como resultado. Recompensa 0 exige cobertura completa y negativo observado, nunca ausencia de dato.

**Nueve redes, misma norma:** X/Threads/Bluesky/Mastodon/Facebook/Pinterest/Reddit/TikTok/Instagram. Los adaptadores convierten `retweet/reblog/share/save/crosspost/repost` al brazo abstracto `repost` y `comment/reply` a `reply`; **no afirman que una operación sea implementable**. `capability_verified=True` debe venir del adaptador operativo que conoce el modo API/WEB/MOBILE, y `eligible=True` del filtrado previo de nicho, edad, lengua, reciprocidad y permisos. Las distintas semánticas de `save`/compartir no habilitan acciones por sí mismas.

### Contraste con lo que YA EXISTE

- En el oficial `integracion/crecimiento-2026-10`: `tools/discovery_ranking.py` clasifica **fuentes** con cohortes maduras; `tools/cohort_metrics.py` distingue convertido/desconocido/censurado D+1/3/7; `tools/cross_network_learning.py` evalúa transferencia de hipótesis; `tools/experiment_uplift.py` compara grupos preasignados. El mirror también tiene `relationship_policy.py`, `growth_attribution.py` y `action_ledger.py`.
- PRs #66 (calidad de candidatos), #71 (prioridad relacional), #100 (ingesta de candidatos), #103 (adaptadores a planes), #107 (evidencia de experimentos), #111 (estratificación por cola), #80 (experimentos), #134 (atribución) cubren partes próximas. **No se duplican ni sustituyen**: este módulo es un clasificador experimental posterior al filtro de candidatos. Para integrar habrá que adaptar sus entradas, revisar la coherencia entre modelos y mantener vetos/orden existente hasta validación.
- Este mirror queda deliberadamente **no conectado a los ejecutores**: conectarlo aquí a nueve pipelines privativos sin unir esas PRs produciría código contradictorio y riesgo de inferir funciones inexistentes.

### Verificación de bibliotecas públicas (consultas al 10/10/2026)

| Proyecto | Commit de referencia | Licencia verificada | Actividad y compatibilidad | Decisión |
|---|---|---|---|---|
| [MABWiser](https://github.com/fidelity/mabwiser) | `b104071351d532aae977955d19b83872a9c1b1e3` (30/08/2024) | Apache-2.0, fichero LICENSE | 2.7.4 en PyPI (30/08/2024); wheel universal, Python >=3.8; dependencias científicas grandes | **Reutilizado como import opcional**; probar Python 3.11 Windows |
| [Vowpal Wabbit](https://github.com/VowpalWabbit/vowpal_wabbit) | `00196b35f63bcb8a6d66966e2b4cf67d6a2bd335` (28/09/2026) | BSD-3-Clause, LICENSE | PyPI 9.11.9 (27/09/2026) con wheel cp311 win_amd64; soporta contextual bandits | **No añadido**: modelo/serialización y política de logging más complejos, sin datos para justificar sustitución |
| [contextualbandits](https://github.com/david-cortes/contextualbandits) | `fc49364bf7f98abb6171351521deeade7800f01e` (28/06/2026) | BSD-2-Clause, LICENSE | PyPI **0.3.30** (22/02/2026), corrige afirmación desactualizada de 0.3.28; sdist, compilación Windows sin verificar | No introducir segunda biblioteca de producción |
| [pybandits](https://github.com/PlaytikaOSS/pybandits) | `830ff530edecb96093724052dc42c2bdcd723377` (07/10/2026) | MIT, LICENSE | PyPI **8.3.0** (07/10/2026), Python >=3.9,<3.15, wheel universal; componentes bayesianos pesados | Descartado ahora, no duplicar inferencia |
| [banditml](https://github.com/banditml/banditml) | `bfbfeabc9d276fc2fd4f8a3a125d94132137753c` (04/06/2021) | GPL-3.0-or-later, [COPYING/README](https://github.com/banditml/banditml) | Sin actividad reciente; compatibilidad Windows/3.11 no demostrada | Descartado; no copiar código GPL |
| [Mab2Rec](https://github.com/fidelity/mab2rec) | `ad217268c5f34e7ebc19c45df26a127e4a0c7bb6` (10/07/2026) | Apache-2.0, LICENSE | PyPI >=3.8; más orientado a recomendación de ítems | Descartado por añadir capas innecesarias |

**Corrección del informe Perplexity:** `contextualbandits` no se quedó en 0.3.28; tampoco `pybandits` está inactivo en octubre 2026. La existencia de un wheel Python universal no demuestra que su árbol completo de dependencias esté probado en Windows: para MABWiser se añadió CI de integración real.

## Contrato y límites de aprendizaje

- Cada `Observation` conserva `network`, `event_id`, acción, features al decidir, fecha local de acción y observación, hito D+1/D+3/D+7, tres componentes opcionales, `coverage`, `provenance` y confirmación. Solo `coverage=complete`, componentes numéricos explícitos y ventana **D+7 ya observada** entran en el entrenamiento. Una misma acción puede tener registros D+1/D+3/D+7 sin convertirse en tres recompensas.
- `provenance=audited_api` o `complete_snapshot` **no prueba por sí misma el dato**: solo acepta ese contrato declarado por el productor. Claude debe conectar evidencia fiable desde #107/#108 y comprobar cobertura e identidad. Los sintéticos quedan excluidos salvo `allow_synthetic=True` explícito para tests.
- Entrenar LinUCB sobre acciones históricamente elegidas no demuestra causalidad, mejora neta, calibración de puntuaciones ni utilidad de explorar; faltan propensiones de asignación y evaluación off-policy. No mezclar los resultados observacionales con los ensayos causales de `experiment_uplift.py`.
- El módulo no persiste modelos ni lee el ledger: recalcula desde histórico validado inyectado; eso evita crear un segundo registro y hace reversible la integración. En frío o sin MABWiser conserva el score prior, etiquetado `policy=prior`.
- No hay afirmación de ganancias reales ni followers generados. Toda la demostración usa datos sintéticos.

## Pruebas y auditoría adversarial

Local (Python 3.13, Linux, fixtures sintéticos): `python -m pytest -q tests/test_action_bandit.py tests/test_action_bandit_adapters.py` → **27 pruebas superadas** después de segunda pasada. Cobertura: nueve redes, 3 brazos, ventana D+7, cancelación de feedback desconocido/parcial/no maduro, veto, duplicados por ventana, identidad entre hitos, cold-start, aislamiento por red, 300 observaciones, 30 por brazo, import opcional y predicciones inválidas.

GitHub: `.github/workflows/test-action-bandit.yml` instala `mabwiser==2.7.4` en Python 3.11 Ubuntu/Windows y añade `test_action_bandit_mabwiser_integration.py` de entrenamiento real. La ejecución inicial del commit `d8a88649` falló en ambos SO: MABWiser devuelve escalares NumPy que el adaptador inicial no reconocía. **Corregido** con `numbers.Real`; comprobar un nuevo run verde del HEAD actual antes de declarar aptitud de integración. La suite global del repo privado, Windows con Edge, y móvil/ADB no se han ejecutado aquí.

**Rollback**: eliminar `tools/action_bandit*.py`, los tres tests y el workflow aislado. No hay esquema SQL ni cola que migrar.

## Pasadas realizadas

1. Comparación del informe con PyPI, licencias y commits de origen; descubrimiento de diferencias reales frente al repositorio oficial y PRs en curso.
2. Implementación del núcleo con MABWiser por import, adaptadores de nueve redes y tests puramente offline.
3. Revisión adversarial: detectado riesgo de comparar ventanas distintas, sobrescritura de candidatos multiacción y dependencia opcional no validada; corregidos y protegidos con tests.
4. CI contra la biblioteca original encontró fallo de tipos NumPy que los dobles no reproducían; corregido y añadido al control final. **No merge**.
