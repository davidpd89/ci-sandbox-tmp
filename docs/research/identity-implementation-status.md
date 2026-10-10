# PR #85 — Identidad entre redes (10/10/2026)

Fuente primaria: https://github.com/rapidfuzz/RapidFuzz
Fecha de consulta: 2026-10-10
Licencia SPDX: MIT
Referencia inmutable: N/A (sin codigo incorporado)

## Problema

El mirror y el repositorio privado `davidpd89/rrss-davidporto-CODE` (rama `integracion/crecimiento-2026-10`) conservan autores por plataforma. Leídos: `tools/candidate_identity.py`, `tools/relationship_policy.py`, `tools/reciprocity.py` y `tools/loyalty.py`. La primera función valida autores exclusivamente en Mastodon/Bluesky, y la política de reciprocidad contabiliza por red. No había grupo global de cuentas con evidencias, desambiguación, separación y trazabilidad hacia CRM.

Los perfiles públicos con nombre o usuario parecidos pueden ser cuentas diferentes. Una web compartida puede ser una editorial, biblioteca o Linktree. La deduplicación automática de identificadores de acción sería incorrecta.

## Alternativas

| Proyecto público (revisión 10/10/2026) | Referencia fija | Licencia | Actividad y compatibilidad | Resultado |
| --- | --- | --- | --- | --- |
| [RapidFuzz](https://github.com/rapidfuzz/RapidFuzz) | [db6e504](https://github.com/rapidfuzz/RapidFuzz/commit/db6e504539a9c895180b266a06b36a32cb6029ee) | MIT | 12/09/2026; Python >=3.11; wheels Windows/Linux; Windows requiere VC++ redistributable | Útil si escalamos candidatos fuzzy; no resuelve verificación de propiedad ni fusiones reversibles; no se añade dependencia |
| [Splink](https://github.com/moj-analytical-services/splink) | [68ced2a](https://github.com/moj-analytical-services/splink/commit/68ced2a46105dca1df1f35b037a3edcdf87a60c7) | MIT | 06/10/2026; SQL y entrenamiento probabilístico, mayor coste operativo | Potente para millones de fichas con labels; excesivo para enlaces explícitos y 9 redes |
| [dedupe](https://github.com/dedupeio/dedupe) | [3f61e79](https://github.com/dedupeio/dedupe/commit/3f61e79102910bd355e920a2df7e44c14c9cb247) | MIT | última actividad examinada 29/07/2025; scikit-learn, NumPy, Cython y más; anuncia Windows | Requiere entrenamiento y dependencias adicionales sin aportar pruebas de autoría |
| [recordlinkage](https://github.com/J535D165/recordlinkage) | [b93d976](https://github.com/J535D165/recordlinkage/commit/b93d97641952f8c85106be5794ca93b1f1298fbc) | BSD-3-Clause | última actividad 2024; soporta 3.11 y requiere pandas, SciPy, scikit-learn | No mejora el caso de alta precisión basada en enlaces |

Se reutiliza el patrón de pares candidatos / comparación de nombres mediante [`difflib.SequenceMatcher` de Python](https://docs.python.org/3.11/library/difflib.html), con comparación simétrica. Código nuevo original, sin copiar archivos de terceros. Sin dependencias ni ejecución de red. Las fechas arriba son el último commit o la actividad examinada, no una auditoría formal de vulnerabilidades.

## Licencias y procedencia

No se incorpora código de RapidFuzz, Splink, dedupe o recordlinkage. Los vínculos anteriores son referencias inmutables comparadas; se mantiene su atribución aquí. `difflib` forma parte de Python estándar (licencia PSF). Compatible por diseño con Python 3.11/Windows/Linux, sin módulos nativos nuevos. No se ejecutó un escaneo de seguridad de las dependencias históricas porque no se instalan.

## Decisión

Se implementa `tools/identity_profiles.py` + `tools/identity_graph.py` + `tools/cross_network_identity.py`:

1. Contrato único para X, Threads, Facebook, Pinterest, Reddit, Bluesky, Mastodon, TikTok e Instagram; clave operativa siempre `network|handle`. Mastodon exige `acct` con instancia.
2. Los enlaces cruzados observados en AMBOS perfiles y URLs plausibles permiten agrupar automáticamente; links no capturados (`links_observed=False`), nombres, handles y webs iguales sólo proponen revisión. No hay acceso a web ni validación en vivo; el adaptador que marque `links_observed` debe aportar su evidencia real.
3. Decisiones humanas explícitas `same/different`, revocación, separación, reevaluación determinista, `conflicts()` cuando vínculos positivos contradicen rechazos. `to_document/from_document` constituyen formato portable versionado.
4. `crm_view(account, records)` es una proyección de reciprocidad y memoria conversacional: agrupa eventos entrantes/salientes y referencias de hilo sin modificar `relationship_policy.py`, `loyalty.py` ni `action_ledger.py`. Deduplicación de observaciones sólo con (`network|handle`, `event_id`); jamás sustituye el ID operativo por el global.
5. El identificador `entity_snapshot_id` es derivado del conjunto de cuentas y **no es estable** al fusionar/separar. Persistir claves locales y reconstruir proyecciones; no usar como FK de CRM.

Ejemplo offline: `g=IdentityGraph(); x=g.observe(Profile("x","autora")); ig=g.observe(Profile("instagram","autora")); g.decide(x,ig,same=True,reason="revisión"); g.crm_view(x,[{"account":ig,"event_id":"ig:1","kind":"comment","direction":"inbound"}])`.

## Pruebas

En referencia local: `python -m unittest discover -s tests -p test_cross_network_identity.py -q`: **21 pruebas superadas**, simuladas. Se aportan también pruebas del árbol GitHub en `tests/test_cross_network_identity_matches.py` y `tests/test_cross_network_identity_crm.py`; en el pipeline de GitHub debe ejecutarse el gate del proyecto y, si está habilitado, `python -m pytest tests/test_cross_network_identity_* -q` en Windows y Ubuntu Python 3.11. Casos: nueve redes, falsos positivos por mismo nombre/web, enlaces unidireccionales, enlaces sin procedencia, URLs inconsistentes, cierre transitivo contradictorio, merge/split, serialización e idempotencia de eventos.

**Segunda revisión adversarial:** se corrigieron la exigencia de observación explícita de enlaces, el informe de conflictos de fusión y la asimetría de SequenceMatcher. Límites abiertos: no hay ingesta nativa desde nueve adaptadores, no se realizó canario en Edge/móvil/Windows local, no hay historial temporal de cambios ni reconciliación de alias por DID/actor URI, la comparación todos-con-todos crece O(n²) y la comprobación del enlace no incluye recuperación HTTPS ni `rel=me`. Mantener como componente de análisis offline hasta integrar observaciones reales verificables.

## Retirada

Cambios aditivos: eliminar los tres módulos y las pruebas; ninguna BD/registro operativo se migra ni modifica. Documento JSON v1 se puede conservar para auditoría o desechar sin afectar acciones. El siguiente paso es acoplar lectores sintéticos y después adaptadores de captura con canario supervisado, sin acciones reales.
