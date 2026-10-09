# Reddit: control offline de contexto antes de comentar
Fecha de consulta: **2026-10-09**. Rama: `research/08-reddit` (mirror público).
Decisión: **C — patrón propio mínimo, sin añadir SDK ni publicar**.

## Problema y reproducción

El mirror `davidpd89/ci-sandbox-tmp` no incluye los ejecutores `tools/reddit_*.py`. Se inspeccionó el repositorio oficial **privado**, rama `main`, commit `db0edb9328358e0181e67573fa1bd71c55b04fec` (09-10-2026): `tools/reddit_scan.py`, `tools/reddit_execute.py`, `tools/reddit_interact.py`, `SISTEMA_DIARIO_REDDIT/{PROCESO,REGLAS,ESTADO}.md`, `tests/test_reddit_thread_url.py`, `AI_REVIEWER_BRIEF.md` y los puntos de entrada generales. El mirror solo reproduce parte del código anonimizado; no se portan fuentes privadas ni identificadores personales.

El recorrido real es: `reddit_scan.scan` (subreddits mapeados; `shreddit-post`) → lectura manual de hilo con `reddit_interact.dump_thread` → plan JSON editorial → `reddit_execute._preflight_plan` (URL, idioma, duplicados en el plan) → `run_plan` → `reddit_interact.comment` (CDP, cuenta activa, CSV, DOM del hilo y confirmación visual tras recarga) → `_append_registro` solo para estados confirmados → métricas y ESTADO. El consumidor del resultado es `reddit_execute.run_plan`; el `scan` usa la identidad canónica del hilo y el CSV para descartar objetivos repetidos. El proceso común de otras redes usa `scan_common`; los controles propios de Reddit NO deben hacerse globales sin evidencia de paridad.

**Hueco comprobado por inspección**: el `preflight` del plan no usa estado HTTP, antigüedad, `locked`, `archived`, retirada por moderación, contenido de citas o integridad de árbol de comentarios. `comment()` revisa el navegador, pero no un contrato estructurado de esas señales antes de abrir el compositor. Además, `run_plan` captura excepciones genéricas, continúa con otras acciones y `_append_registro` omite los intentos ambiguos: no equivale a reconciliación duradera. Esto último precisa integración privada y no se resuelve desde esta PR.

## Decisión aplicada y alternativas

| Baseline | Candidato 1 | Candidato 2 | Elección | Motivo / riesgo |
| --- | --- | --- | --- | --- |
| CDP + validación de URL/CSV/DOM ya operativa | PRAW 8.0.3 (BSD-2-Clause) para OAuth sincrónico | Async PRAW 8.0.3 (BSD-2-Clause) / Devvit (API de comunidad, otro ámbito) | **C: verificador Python estándar de Listings y revisión humana; conservar CDP sin ampliarlo** | No hay autorización API verificada ni equivalencia de actuar como esta cuenta en comunidades externas; un SDK añade OAuth, costes de mantenimiento y superficie de datos, sin resolver por sí solo la política editorial. El verificador aislado aún no está conectado a producción. |

No se integra código de PRAW, Async PRAW ni Devvit: no se generan obligaciones de atribución de librería redistribuida en la implementación nueva. Las alternativas tienen licencias permisivas, pero esa compatibilidad **no concede permiso para usar la API**. `PRAW` y `Async PRAW` tienen release `v8.0.3` de 12-08-2026; son mantenidas, con interfaz Python 3.10+. Async PRAW añade `aiohttp`/`asyncprawcore` y complejidad asíncrona improductiva para una revisión humana de pocas sesiones. PRAW añade `prawcore` y autenticación OAuth. Devvit usa permisos de la app instalada en la comunidad; su modelo no sustituye automáticamente una sesión de usuario en subreddits ajenos. `prawcore` directamente daría control a nivel HTTP, pero duplicaría trabajo del wrapper. Se contrastó política y actividad, no se inventa un benchmark de API sin credenciales.

Procedencia y referencias permanentes:
- PRAW: [tag 8.0.3](https://github.com/praw-dev/praw/releases/tag/v8.0.3), [commit 4a9eb7e](https://github.com/praw-dev/praw/commit/4a9eb7ee3ac5743ce8b848e9f7b187eae4826da1), [licencia BSD simplificada](https://github.com/praw-dev/praw/blob/main/LICENSE.txt).
- Async PRAW: [tag 8.0.3](https://github.com/praw-dev/asyncpraw/releases/tag/v8.0.3), [commit a669548](https://github.com/praw-dev/asyncpraw/commit/a669548484596492714f806652ea9c52ccee190e), [dependencias/licencia](https://github.com/praw-dev/asyncpraw/blob/main/pyproject.toml).
- Devvit: [commit 2aac5a4](https://github.com/reddit/devvit/commit/2aac5a4b5742045de43ee65238b0fa0eb38692da), [documentación API, commit 7557a3b](https://github.com/reddit/devvit-docs/blob/7557a3b3ca9faf9c63c7e0b264b8ad1460b3511a/docs/capabilities/server/reddit-api.mdx), [Devvit Rules](https://github.com/reddit/devvit-docs/blob/main/docs/devvit_rules.md). Es una plataforma con licencia/condiciones por componentes; no se ha importado su código.
- Contrato y restricciones: [API de Reddit, Listings](https://www.reddit.com/dev/api/), [Data API Terms, revisión 20-07-2026](https://redditinc.com/policies/data-api-terms), [Developer Terms](https://redditinc.com/policies/developer-terms), [AutoModerator, 02-10-2026](https://support.reddithelp.com/hc/es-es/articles/52866343172500-Documentaci%C3%B3n-completa-sobre-el-automoderador), [OWASP supply chain](https://cheatsheetseries.owasp.org/cheatsheets/Software_Supply_Chain_Security_Cheat_Sheet.html).
- Versión oficial inspeccionada (acceso privado): [reddit_execute.py](https://github.com/davidpd89/rrss-davidporto-CODE/blob/db0edb9328358e0181e67573fa1bd71c55b04fec/tools/reddit_execute.py) y [reddit_interact.py](https://github.com/davidpd89/rrss-davidporto-CODE/blob/db0edb9328358e0181e67573fa1bd71c55b04fec/tools/reddit_interact.py). Enlaces solo para autorizados; no trasladar contenido al mirror público.

## Qué se implementó y contrato

- `tools/reddit_snapshot_preflight.py` evalúa sin red un `plan` de comentario raíz, un envelope `{http_status,retrieved_at,body}` y una revisión humana explícita de normas/lectura/historial. `body` debe tener **dos Listings** de `/comments/<id>.json`: `t3` del hilo y `t1` de comentarios, con `more` bloqueado.
- Valida origen HTTPS canónico y coincidencia exacta de ID/subreddit, vigencia de snapshot (5 min), ventana editorial (7 días, **no límite de Reddit**), `locked`, `archived`, retirada, restricción de subreddit, revisión de reglas vigente (7 días), CSV informado como `history_state=none`, duplicado por autor, citas con ID existente y no eliminado, AutoModerator que anuncia retirada y contexto de comentarios incompleto.
- Una respuesta HTTP `429`, campos desconocidos o un error de parsing siempre **bloquean**, sin reintento. No envía comentarios, no abre navegador, no registra datos identificables y no gestiona credenciales.
- `tests/fixtures/reddit_snapshot_preflight.json`: estructuras sintéticas con nombres ficticios y campos `Listing/t3/t1` alineados con el JSON de la API; `tests/test_reddit_snapshot_preflight.py`: pruebas de bloqueo, caso válido, comprobaciones adversariales y CLI con proceso real. No es un mock de un endpoint OAuth: **no prueba** la autenticación, cuota, propagación de moderación o veracidad de la revisión humana.

Ejemplo de ejecución offline (tras escribir los tres archivos JSON propios, sin tokens):
```sh
python -m unittest tests.test_reddit_snapshot_preflight -v
python tools/reddit_snapshot_preflight.py --plan plan.json --snapshot reddit_listing.json --review revision.json
```
El primer comando tiene el mismo criterio que pytest, pero `python -m pytest tests/test_reddit_snapshot_preflight.py -q` es el comando de CI. CLI devuelve 0 para *apto para revisión*, 2 si bloquea. **Nunca autoriza por sí sola publicar**; el snapshot debe adquirirse de modo autorizado y revalidarse bajo el candado de escritura.

## Riesgos, alcance y retirada

- TOS: cualquier API requiere OAuth autorizado, agente de usuario honesto, consentimiento/aprobación que corresponda y respeto a cuotas; el wrapper no elude estas obligaciones. Devvit puede exigir revisión. Sin acuerdo/permisos confirmados, no consultar la API desde esta PR.
- Privacidad: no guardar cuerpos de mensajes de usuarios, enlaces a perfiles, tokens, correos, cookies ni cookies CDP en este mirror. El snapshot de prueba es **inventado**. El repositorio privado contiene identificadores en el código antiguo; NO se portan.
- Autenticación: el JSON puede alterarse; un booleano `approved_by_human` no es prueba criptográfica de revisión. Esta utilidad es auxiliar, no barrera final independiente; bloquear ejecución hasta integrar una fuente fiable y comprobaciones de estado bajo lock.
- Datos: comentario moderado tras la lectura, respuestas cargadas parcialmente, API 429, estados `deleted` y UI que no refleja el backend pueden dar falsos positivos o negativos. Se opta por bloqueo conservador; los avisos de AutoModerator no tienen frase universal, se necesita revisión humana.
- Coste: **cero dependencias Python externas**, cero solicitudes y cero tokens nuevos; coste de revisión del contrato y de validar API/DOM en integración futura. No hay cifras de rendimiento comparables ni estimaciones monetarias de API.
- Rollback: revertir los commits de `tools/reddit_snapshot_preflight.py`, `tests/test_reddit_snapshot_preflight.py`, `tests/fixtures/reddit_snapshot_preflight.json` y este documento; no hay cambios en base de datos ni estado de producción.

## Coordinación

Las PR mirror [#21](https://github.com/davidpd89/ci-sandbox-tmp/pull/21) (selección), [#22](https://github.com/davidpd89/ci-sandbox-tmp/pull/22) (texto/contexto), [#25](https://github.com/davidpd89/ci-sandbox-tmp/pull/25) (memoria) y [#41](https://github.com/davidpd89/ci-sandbox-tmp/pull/41) (drift API) siguen abiertas y, a la consulta, solo cambian sus encargos. Esta PR no modifica `scan_common`, colas, `ledger`, puntuaciones, writer, historial ni parseadores compartidos. La PR **#44 del repositorio oficial** es otra numeración y añade fidelización Reddit, en `sub/11-loyalty-reddit`, base `integracion/crecimiento-2026-10`, abierta a esta consulta. No copiar ni pisar su política de respuestas.

Orden recomendado: integrar primero el estado real/continuidad de la rama oficial de fidelización tras revisar sus cambios; adaptar luego el verificador a un transport autorizado/DOM bajo lock; solo después extender evaluación/ranking y drift. Una API compartida de status/snapshot deberá pertenecer a #41, no se crea aquí.

## Autorrevisión adversarial

1. **Un plan válido puede comentar tras ser archivado.** Corrección: la función bloquea `archived`/`locked` y snapshots de más de 5 minutos; riesgo residual de carrera entre snapshot y clic **no resuelto**, requiere revalidación bajo lock.
2. **Una respuesta HTTP 200 puede llevar un hilo distinto o árbol incompleto.** Corrección: identidad exacta de `t3` y rechazo de `more` y `num_comments` que supera los `t1` leídos; recuentos de Reddit pueden diferir, así que puede haber bloqueos conservadores.
3. **AutoMod puede retirar sin cambiar un campo que vemos.** Corrección: señal `removed_by_category`, comentarios con avisos inequívocos de AutoModerator y aprobación humana obligatoria; el lenguaje de avisos no es exhaustivo, por tanto no se prometen detecciones universales.
4. **Un fallo posterior al clic puede dejar una respuesta publicada sin ledger.** No lo corrige un verificador previo: se exige reservar intento/reconciliar estado ambiguo antes de cualquier reintento en el repo privado.
5. **Falsa sensación de seguridad por flags manuales.** La utilidad no publica y la documentación exige fuente auténtica, frescura y revisión humana; no sustituye cumplimiento ni revisión editorial.

## Evidencia y pendiente para integración real

El baseline oficial **no se ejecutó en este mirror**: faltan sus módulos. Por inspección de `_preflight_plan` no existe entrada para `Listing` ni HTTP 429; por tanto no puede compararse rendimiento antes/después con idéntico fixture. La nueva prueba reproduce el contrato offline con casos negativos y verifica que el CLI devuelve 2; resultados de ejecución de CI deben asociarse al SHA final de la rama. No contabilizar como pruebas de producción ni como resultado de una consulta a Reddit.

**Estado: BLOQUEADA para producción** hasta llevar una comprobación equivalente al repo privado, auditar permisos API, consumir un snapshot real autorizado (o señales DOM verificadas), enlazarla a `comment()` bajo lock y guardar intentos ambiguos. La PR de investigación puede revisarse como pieza auxiliar independiente, pero no debe llamarse protección instalada en la cuenta real.
