# PR #4 — ranking conservador de fuentes y perfiles

Fecha de auditoría: 09/10/2026.

## Estado revalidado

- PR: https://github.com/davidpd89/ci-sandbox-tmp/pull/4
- Rama: `ci/discovery-ranking`
- Base: `ci/test-campaign-parent`
- HEAD inicial auditado: `bbe2e063adae0596c7696acd95b83a663e6b489f`.
- Al comenzar, la rama estaba 1 commit por delante y 1 por detrás de la base. El único commit nuevo de la base indexa las PR de la campaña y no toca el ranking.
- El cuerpo actual de la PR no contiene una sección literal `## Encargo para GPT`; se tomó como contrato el cuerpo existente y el mandato de esta ronda.
- `docs/open-source-scouting/PROTOCOL.md` no existe ni en la rama de la PR ni en la base comprobada.

No se ha usado ninguna cuenta, credencial, dato real ni acción social. Todo el cambio sigue siendo offline y sintético.

## Contexto recuperado del repositorio oficial

Se leyó `davidpd89/rrss-davidporto-CODE@integracion/crecimiento-2026-10` mediante el conector GitHub. Antes de esta ronda, los dos archivos del mirror eran copias exactas del oficial:

- `tools/discovery_ranking.py`: blob `7b8ef59a6ce6dce8e17031115c2978bf17b7cd72`.
- `tests/test_discovery_ranking.py`: blob `4370d9b2d1e8030e6d83048870ab29095c87c2f7`.

También se revisaron `docs/PR_050_DISCOVERY_RANKING_QA.md` y `tools/growth_attribution.py`. El oficial confirma que, para este contrato, solo Bluesky y Mastodon disponen de lector de seguidores reutilizable; además advierte que la coincidencia legacy de identidades Mastodon y la procedencia textual no bastan para certificar cohortes. Esta PR no conecta esos lectores ni eleva ningún flag de verificación automáticamente.

## Hallazgos de esta ronda

### 1. Instagram quedaba fuera del contrato multired

El proyecto operativo actual incluye X, Threads, Facebook, Pinterest, Reddit, Bluesky, Mastodon, TikTok **e Instagram**, pero `NETWORKS` solo enumeraba ocho redes. Eso hacía que una cohorte sintética de Instagram se tratase como `invalid_network` y ni siquiera apareciese en el informe, pese a que el contrato pretende separar todas las redes.

Corrección: se añade `instagram` a `NETWORKS`, pero **no** a `SUPPORTED_SNAPSHOTS`. Por tanto:

- aparece de forma explícita como `not_instrumented`;
- una cohorte de Instagram queda `snapshot_adapter_unverified`;
- un `scan_slots={"instagram": 1}` sigue fallando cerrado;
- no se inventa disponibilidad de API, navegador o lector de followers.

### 2. El cursor se exigía incluso sin trabajo de exploración

Con `scan_slots=0`, `exploration_fraction=0` o sin cohortes pequeñas elegibles, el resultado podía declarar `exploration_cursor_required=True`. Era un falso requisito: no había nada que rotar.

Corrección:

- si la reserva es cero o no existen cohortes `insufficient_sample`, `exploration_candidates=[]` y `exploration_cursor_required=False`;
- si hay reserva positiva **y** cohortes pequeñas seguras, sin cursor se conserva `exploration_candidates=None` y `exploration_cursor_required=True`;
- sigue sin persistirse cursor ni programarse ninguna lectura.

## Reutilización pública evaluada

La política de esta ronda es reutilizar si una dependencia pública gana con evidencia. Se compararon tres referencias:

| Proyecto | Licencia / mantenimiento | Compatibilidad relevante | Decisión |
| --- | --- | --- | --- |
| [statsmodels/statsmodels](https://github.com/statsmodels/statsmodels) | BSD-3-Clause; commit inspeccionado del 08/10/2026 | Python 3.11 soportado; `proportion_confint(..., method="wilson")`; requiere NumPy, SciPy, Pandas y otras dependencias | **Referencia/oráculo, no dependencia**. La fórmula actual es pequeña, stdlib-only y ya coincide con Wilson; añadir todo statsmodels sería coste y superficie de suministro innecesarios. |
| [fidelity/mabwiser](https://github.com/fidelity/mabwiser) | Apache-2.0; último commit inspeccionado 30/08/2024 | CI incluye Windows, pero la matriz publicada llega a Python 3.10; depende de NumPy/Pandas/scikit-learn/SciPy/joblib/seaborn | **No adoptar**. Implementa políticas de bandit que el contrato actual prohíbe convertir en acciones; además no hay evidencia CI de Python 3.11 en su workflow actual. |
| [bayesianbandits/bayesianbandits](https://github.com/bayesianbandits/bayesianbandits) | MIT; commit inspeccionado del 05/10/2026 | README declara Python 3.10–3.14 y CI cross-platform; exige NumPy 2, SciPy y scikit-learn | **No adoptar**. Es mantenido, pero resolvería un problema más amplio y stateful que esta reserva offline; aumentaría dependencias y cambiaría semántica. |

Referencia metodológica primaria usada para Wilson:
- https://github.com/statsmodels/statsmodels/blob/main/statsmodels/stats/proportion.py
- https://www.statsmodels.org/stable/generated/statsmodels.stats.proportion.proportion_confint.html

No se ha copiado código de estos proyectos. Se conserva la implementación stdlib del repositorio y se usa statsmodels como referencia externa. No se ha realizado un escaneo CVE exhaustivo de terceros; la decisión de no añadir dependencias reduce, no elimina, riesgo de cadena de suministro.

## Tests de regresión añadidos

- La lista esperada de redes se fija explícitamente a nueve; ya no se valida tautológicamente contra `rank.NETWORKS`.
- Instagram debe aparecer como red conocida pero sin snapshot acreditado.
- Presupuesto positivo de Instagram debe rechazarse.
- Reserva cero, fracción cero y ausencia de candidatos no deben exigir cursor.
- El caso con cohortes pequeñas y reserva positiva sigue exigiendo cursor y rotación externa.

Los tests usan fecha fija, tokens sintéticos y no leen entorno, ficheros de producción ni red.

## Revisión adversarial

Se volvió a tratar el módulo como ajeno después del primer parche:

- no se añadió Instagram a `SUPPORTED_SNAPSHOTS`;
- no se relajaron gates de identidad, procedencia, política, follow confirmado o snapshot completo;
- no se convierten faltantes en tasa cero;
- no se mezclan redes;
- no se exponen handles crudos;
- no se introducen Scheduler, colas, follow, publicación ni navegación;
- el cursor continúa siendo estado externo: esta función no guarda historial ni ejecuta exploración.

Límite mantenido: `source_policy_approved=True` y los demás flags siguen siendo atestaciones de un importador confiable aún no implementado; no deben alimentarse directamente desde CSV legacy.

## Validación y bloqueos

La validación definitiva de esta versión debe venir del workflow del mirror en Ubuntu y Windows sobre el HEAD final. El checkout local completo y un Windows vivo fuera de GitHub Actions no están disponibles en esta sesión.

No se abre una PR adicional por estos hallazgos: ambos defectos pertenecen al alcance exacto de #4 y quedan corregidos aquí. La instrumentación de un importador de cohortes verificadas sigue siendo trabajo separado ya identificado en el repositorio oficial; no se duplica sin comprobar primero las PR abiertas.
