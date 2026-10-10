# PR #124 — Resultados SERP del nicho lector, solo lectura

Fecha: 2026-10-10. Objetivo: convertir el informe de Facebook en un importador **real y offline** para revisar candidatos encontrados en búsquedas ya autorizadas. No crea listas inventadas de grupos ni altera ejecutores en las nueve redes.

## Comparación con el código oficial

Rama privada inspeccionada: integracion/crecimiento-2026-10. Ya existen herramientas Facebook Graph v26 para Página propia (facebook_api.py, meta_common.py), facebook_scan.py, facebook_pool.py, facebook_source_quality.py (filtro de grupos y URL ambigua antes de acciones), discovery_terms.py y discovery_ranking.py. Las PR oficiales #55, #158 y #161 ya abordan filtros y medición de Facebook; la PR espejo #15 cubre reutilización de Facebook y #99–#101 incluyen términos y hashtags. Por tanto no se duplica cliente Graph, ranking ponderado ni escaneo.

## Procedencia verificada

| Fuente y commit comprobado | Licencia real | Compatibilidad y mantenimiento | Decisión |
| --- | --- | --- | --- |
| [HasData/social-listening-tool@086ddc5](https://github.com/HasData/social-listening-tool/commit/086ddc5894c6c3c8b48841496f1dc339db299899), 05/04/2026 | MIT | Requiere Python 3.10+; el pipeline completo pide API HasData, LLM y más dependencias. Windows no ejecutado aquí. | **Adaptar sin conexión** esquema get_serp_results (src/api.py) y remove_duplicates_serp_results (src/utils.py), con deduplicación por URL canónica, selección del mejor snippet y clasificación en nueve redes. Copia del aviso MIT en docs/licenses/. |
| [sns-sdks/python-facebook@c0aa73f](https://github.com/sns-sdks/python-facebook/commit/c0aa73f4fbd08005eca05956edf4cb64275fd83d), 10/02/2026 | Apache-2.0 | pyproject.toml 0.24.0 declara Python 3.11, OS independiente; añade requests, requests-oauthlib, dataclasses-json. | No instalar: meta_common ya maneja Graph. |
| [facebook/facebook-python-business-sdk@efd8423](https://github.com/facebook/facebook-python-business-sdk/commit/efd8423a2e595ea8d4c04eb824ce113f2f1d68cd), 17/09/2026 | Licencia propia para software usado con servicios/API de Meta | SDK amplio de Marketing APIs. | No copiar ni añadir la dependencia. |
| [gitroomhq/postiz-app@91c91f6](https://github.com/gitroomhq/postiz-app/commit/91c91f633a0175fb3914dba64c932928c514b72a), 09/10/2026 | AGPL-3.0 | Stack Node/Next distinto del núcleo Python. | No copiar: solo comparativa arquitectónica. |
| kevinzg/facebook-scraper y forks | Licencia/estado de forks no verificados | Dependencia de selectores y cambios de interfaz. | Descartado para el pipeline. |

Las fechas anteriores son las de los commits comprobados, **no** una prueba de compatibilidad con Windows. El importador no accede ni sustituye la Graph API.

## Código operativo

tools/serp_discovery_import.py acepta una lista JSON o un objeto con organicResults del esquema HasData (link, title, snippet). Canoniza URL, deduplica variantes con trackers conocidos, prefiere el snippet con evidencia literaria, infiere **intención de revisión**, identifica nueve redes y exporta un informe de revisión humana. Facebook grupo → group_manual, post → page_post_unverified, foto/story o URLs dudosas → ambiguous_manual. En todas las redes action_allowed=false, permission_verified=false, published_at=null, author_id_verified=false: ninguna búsqueda SERP acredita fecha, identidad ni permiso para actuar.

Uso, siempre con archivo local y sin red:

    python tools/serp_discovery_import.py entrada.json --output revision-local.json
    python -m unittest discover -s tests -p test_serp_discovery_import.py -v
    python -m compileall -q tools/serp_discovery_import.py tests/test_serp_discovery_import.py

No subir revision-local.json a GitHub si contiene enlaces de terceros. Sin secretos, peticiones externas, cambios de esquema/DB o dependencias.

## Evidencias y revisión adversarial

- Situación anterior (dedup de HasData): los UTM generaban entradas distintas y un primer resultado vacío podía ocultar otro más contextual.
- Tras la adaptación: claves de URL canonizadas, dedup por lote con preferencia contextual, rechazo explícito de URL no reconocidas o red declarada incorrecta y contadores verificables.
- Primera ejecución local: 13/14 por error con «recomendáis». Corregido con regresión. Tercera ejecución local tras revisión adversarial: **17/17** y compileall OK (Python/Linux).
- Independiente de los ejecutores del espejo/oficial: no integrado con acciones reales ni con la reserva de producción; integrar requiere validación posterior de Claude.
- QA pendiente en Windows Python 3.11, Edge/móvil, suite completa privada, compatibilidad de esquemas en producción, CI espejo y revisión humana. No se confunde «mergeable=true» con aptitud de merge.
- Revisión adversarial adicional: enlaces con parámetros de token/código/contraseña no pasan al informe; al deduplicar se prefiere un resultado cuya red declarada coincida con su URL. Dos regresiones añadidas.
- Riesgos: resultados SERP obsoletos, heurística léxica aproximada, instancias Mastodon mal declaradas; todos quedan en revisión, no ejecución.
- Retirada reversible: eliminar exclusivamente importador, prueba y documentación. Escáneres/colas/ledger permanecen intactos.
