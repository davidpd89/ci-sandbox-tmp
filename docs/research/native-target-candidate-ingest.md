# PR #100 — Puentes nativos de candidatos al ranking compartido

Fecha de revisión: 2026-10-10. Estado: implementación offline; ninguna cuenta,
acción social ni estado real ha sido consultado o modificado. El ranker #66
permanece en otra rama y se inyecta por parámetro, no se copia ni importa.

## Problema y evidencia

Se leyó el protocolo y el encargo. El repositorio oficial privado se
consultó únicamente en lectura, rama integracion/crecimiento-2026-10,
commit [5449513d9b545d0a6a72abf066ab6a779bfdad71](https://github.com/davidpd89/rrss-davidporto-CODE/commit/5449513d9b545d0a6a72abf066ab6a779bfdad71).
No se publicaron fuentes privadas, identificadores, cuentas ni historiales.

| Red | Productor contrastado y datos nativos | Brecha |
| --- | --- | --- |
| X WEB | tools/x_scan.py: source, url, handle, text, kind, known_date | No hay created_at/lang ni ID estable; known_date no es fecha de post |
| Threads WEB | tools/threads_scan.py: source, handle, permalink, text, kind | No created_at/lang ni ID estable |
| Facebook WEB | tools/facebook_scan.py: tag, autor, permalink, text, known | autor es nombre visible; sin ID de cuenta, fecha o idioma |
| Reddit WEB | tools/reddit_interact.py: author, subreddit, title, url, comment_count, score; tools/reddit_scan.py usa la lectura en memoria | No JSON nativo ni fecha/lang en la captura |
| Pinterest WEB | tools/pinterest_growth.py: authors con handle/bio/followers, pins con URL/título/autor/descripción, date del scan | date no es fecha de Pin, sin timestamp/lang verificable |
| Instagram WEB | tools/instagram_scan.py: tupla (source,handle,text,permalink,kind) en memoria | No JSON, fecha o lang |
| API/MOBILE | Hay otros lectores, pero no se contrastó una emisión completa de candidatos por cola | Compatibilidad de esquema no implica captura conectada |

El ranker de [#66](https://github.com/davidpd89/ci-sandbox-tmp/pull/66)
requiere cuentas con identidad, fuente, relación y posts fechados y
referenciados. Esta PR transforma observaciones, sin reimplementar scoring.

## Alternativas públicas (consultadas en GitHub REST a 2026-10-10)

| Proyecto, commit inmutable | Licencia SPDX / último push | Valor / decisión |
| --- | --- | --- |
| [PRAW](https://github.com/praw-dev/praw/tree/4a9eb7ee3ac5743ce8b848e9f7b187eae4826da1) | BSD-2-Clause / 2026-10-09 | submission.created_utc e id útiles si se añade un productor; cliente API innecesario para JSON offline |
| [Tweepy](https://github.com/tweepy/tweepy/tree/c1978d643ecce491929084e4290b35f57e4921ad) | MIT / 2026-07-02 | Objetos Tweet con created_at y author_id; no suplen fechas ausentes de los escáneres WEB |
| [Pinterest SDK](https://github.com/pinterest/pinterest-python-sdk/tree/7daaa25e018e46ac960187655e8bed6680f6c8cf) | Apache-2.0 / 2026-09-02 | Cliente API orientado originalmente a anuncios, no verifica edad de Pin de nuestros escáneres |
| [PyThreads](https://github.com/marclove/pythreads/tree/a75fb277377ce73d92cca7eb464c78090150bfd3) | MIT / 2025-09-09 | Cliente API con respuestas Any, más dependencia sin utilidad para la serialización |
| [Threads SDK async](https://github.com/Inoue-AI/Inoue-AI-Threads-SDK/tree/e2b050d9313771be547328ba260dbf5738f546d1) | MIT / 2026-06-07 | aiohttp/Pydantic, candidato para futuro productor API, no para adaptador puro |
| [Facebook Business SDK](https://github.com/facebook/facebook-python-business-sdk/tree/efd8423a2e595ea8d4c04eb824ce113f2f1d68cd) | NOASSERTION (GitHub) / 2026-09-21 | No convierte nombre DOM en identidad estable; no copiar sin aclarar licencia |

La alternativa ganadora es conservar lectores nativos e incorporar un
adaptador estándar mínimo para los datos que realmente producen. No se
instalan librerías ni se copia código externo; las dependencias de clientes
HTTP/SDK aumentarían coste sin aportar fechas inexistentes. stdlib Python
3.11 sirve en Linux y Windows; instalación Windows de cada SDK candidato
no comprobada porque ninguno fue incorporado.

## Licencias y procedencia

Fuente primaria: https://github.com/praw-dev/praw/tree/4a9eb7ee3ac5743ce8b848e9f7b187eae4826da1
Fecha de consulta: 2026-10-10
Licencia SPDX: BSD-2-Clause
Referencia inmutable: N/A (sin codigo incorporado)

El patrón de fecha Unix created_utc se contrastó con PRAW. Código nuevo
original y sin dependencia de bibliotecas de terceros. La documentación
de atribución anterior identifica ideas, no archivos copiados.

## Decisión y contrato

Se añade tools/native_target_candidate_ingest.py, con tres interfaces:

- normalize_candidates(network, snapshot, as_of, queue, lane): transforma
  una observación de las seis redes y devuelve shortlist compatible con #66,
  diagnostics y complete=None. No lee fichero, red ni sesión.
- normalize_all: devuelve las seis redes, con unsupported cuando falta
  snapshot y normalized_offline cuando se ha suministrado una captura;
  no confunde ausencia con cero candidatos.
- rank_with_66: exige inyección explícita de la función rank_all de #66.
  Al no estar #66 integrada en la base, se prueba con consumidor sintético.

NATIVE_CAPTURE distingue JSON persistido (X, Threads, Facebook, Pinterest)
de lectura solo en memoria (Reddit, Instagram). WEB/API/MOBILE se registran
de manera independiente, pero los capturadores contrastados son WEB.
complete=None: ni siquiera un snapshot vacío garantiza páginas completas.

La cuenta prioriza account_id explícito si existe, y lo conserva ante
cambios de handle; si hay ID no emite handle como campo de identidad para
evitar que _identity de #66 privilegie un nombre mutable. En redes sin ID
se admite handle válido como identidad observable, NO estable entre
renombres: dependencia de la futura #85. Facebook exige ID; el campo
autor de facebook_scan no demuestra identidad y se rechaza sin dicho ID.
Las fuentes repetidas se agregan, sin imputar fuentes inexistentes.

Post: requiere permalink HTTPS canónico de la red, referencia no ordinal,
created_at con zona (o created_utc numérico en Reddit), tiempo dentro
del límite adquisición/comunidad, idioma observado language/lang. No se
deduce fecha del scan ni de known_date, ni idioma desde consulta o contenido.
El post de idioma desconocido se mantiene solo como información,
sin acciones; idioma no español se descarta. No se fabrican followers,
bio, relaciones o recuentos. Los kind sugeridos por escáner no confieren
acciones. Solo verified_actions explícitas permiten follow/reply/comment/
repost en el registro, sin grant de like, especialmente en X. Ni el
normalizador ni #66 ejecutan acciones.

Páginas parciales se mantienen con complete=None. Un post fuera de edad
se rechaza antes de #66. Máximos: 10000 observaciones, 30 posts por cuenta.

## Instrumentación pendiente para integrar de verdad

- X/Threads: incluir fecha del post, lang observado e ID nativo del autor
  desde origen con procedencia, sin interpretarlo desde ordinales.
- Facebook: recuperar ID de autor/página acreditado y fecha de publicación;
  no usar texto de autor como identidad.
- Pinterest: fecha e idioma propios de cada Pin; la fecha del archivo
  exportado no sirve.
- Reddit: persistir la lista de hilos con autor y añadir fecha/idioma
  (created_utc si procede de API validada).
- Instagram: persistir tuplas del scan junto con fecha e idioma observados.
- Todas las redes API/MOBILE: contrato por cola con evidencias reales,
  no dar por completa la cobertura por una etiqueta de esquema.

No duplicar #21/#4 (cohortes), #99 (hashtags), #23 (atribución),
#61/#62 (fecha), #66 (ranking) ni #85 (identidad longitudinal).

## Pruebas

Comandos sin red, credenciales ni acciones:

    python -m unittest discover -s tests -p test_native_target_candidate_ingest.py -v
    python -m py_compile tools/native_target_candidate_ingest.py

CI en .github/workflows/native-target-candidate-ingest.yml: Ubuntu y
Windows, Python 3.11, sin pip. Fixtures separados para seis redes;
identidad duplicada y handle renombrado, UTC/DST, fecha ausente/vencida/
futura, idioma desconocido, URLs falsas, no auto-like, origen de fuente,
cola equivocada, snapshot nulo/vacío, no mutación, consumidor #66 simulado.
Confirmar resultados concretos en Actions del HEAD final antes del merge.
Son pruebas sintéticas, NO canario supervisado.

Antes: los productores devuelven formatos heterogéneos sin contrato #66.
Después: cuatro archivos estructurados y dos lecturas en memoria pueden
normalizar perfiles aportados; posts sin fecha quedan rechazados
explícitamente. No es una mejora de conversiones medida ni despliegue.

## Segunda auditoría adversarial

1. Fecha de una interacción vs fecha del post: known_date ignorado.
2. Cambio handle con ID: dedupe por ID y diagnóstico; sin ID no se inventa
   vinculación longitudinal.
3. Spoofing URL: se requiere esquema, host, ruta e ID remoto de post.
4. Language inferido desde consulta o texto: prohibido por diseño.
5. Acción sugerida kind: no se convierte en verified_actions.
6. Páginas parciales: complete=None y sin imputación de ausencias.
7. Cuenta FB sin ID: se rechaza, nunca se atribuye nombre DOM a handle.
8. Adaptador no garantiza ingest real: capture=memory_only o
   persisted_json es clasificación de **emisor**, no despliegue.
9. No se importa #66 ni se suplanta API original: merge-preview pendiente.

Limitaciones para Claude: ejecución en Windows vivo/Edge, móvil real,
trazabilidad de las API, IDs y fechas efectivamente visibles,
merge-preview del ranker #66, suites oficiales y canario supervisado.
Las pruebas offline no garantizan cobertura ni eficacia en producción.

## Retirada

No existe llamada desde ejecutores, feature flag lógico default-off
(al no importar este módulo). Revertir commits de #100 o no invocar
normalize_candidates/rank_with_66. Sin migración, estados, secretos ni
side effects. Verificar tras revertir la suite previa de #66 y escáneres.
Solo Claude integrará posteriormente #66 y luego #100, sin auto-merge.


## Resultado de la segunda pasada y CI verificada

La auditoría adversarial posterior al primer verde detectó y corrigió cuatro
defectos en commits 030eb4b y fda2a40:

1. El idioma del post se filtraba en el campo de idioma del perfil. Ahora la
   cuenta usa solo profile_language o profile.language; la observación del
   post no acredita idioma del autor.
2. Dos lecturas del mismo permalink con fechas diferentes se fusionaban por
   orden de aparición. Ahora se descarta ese permalink contradictorio y se
   notifica conflicting_post_timestamps, incluso si hay terceras observaciones.
3. Datos duplicados de seguidores diferentes sobrescribían valores sin
   diagnóstico: se conserva el primero y se marca conflicto. Si una segunda
   observación aporta idioma explícito al mismo post y no contradice su
   fecha, se enriquece sin imputar.
4. Epoch Unix descomunal podía provocar OverflowError; se rechaza sin
   excepciones. Si created_at es null, se acepta timestamp explícito válido.
   Para renombres X/Threads, autor y permalink distintos solo se concilian
   con author_id igual al account_id contrastado.

**CI funcional final de la pasada:** [workflow 38022307542](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/38022307542)
ejecutó **38/38 pruebas en Ubuntu y 38/38 en Windows**, Python 3.11,
incluyendo compilación del módulo. Evidencia del código en HEAD
fda2a40e8831e041503e167fe1cf0ba22094df7f; no es un canario.

**Gate separado de campaña:** [workflow 38022307579](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/38022307579).
Los 30 tests de campaña y las validaciones offline fueron correctos,
con 76 hijas y cero errores. La comprobación online de Ubuntu devolvió:
FAIL: #100: child absent from parent manifest.
El job de Windows terminó correcto, pero no elimina este bloqueo del
paso online. Debe coordinarse con Claude la inclusión de #100 en
children.json/índice de la **rama padre** research/public-reuse-parent
y la repetición del gate. No se modifica esa rama desde esta PR #100.

Todos los tests funcionales usan datos artificiales y lector inyectado;
aún falta merge-preview real de #66 y ensayos supervisados de
WEB/API/MOBILE, Edge/Windows y dispositivo móvil. No declarar aptitud
de merge mientras el gate online y estas dependencias sigan abiertos.


### Tercera comprobación: enlaces de Facebook

El lector oficial de hashtags selecciona enlaces con /posts/, /videos/
y parámetros fbid. Se amplió la validación acotada en el commit 66e4cc9:
posts (ID numérico o pfbid), vídeos, publicaciones/permalinks de grupos
con slug y story.php/permalink.php con IDs numéricos. No se admiten páginas
de perfil ni hosts ajenos, ni se usa el nombre visible para atribuir autoría.
Prueba de regresión: test_facebook_posts_groups_videos_and_story_urls.

[CI de HEAD funcional 05eea3e](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/38022433415):
**39/39 Ubuntu + 39/39 Windows** Python 3.11, suites completas y
compilación exitosas. El gate de campaña
[38022433501](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/38022433501)
sigue con fallo online Ubuntu por no figurar #100 en el manifiesto del
padre; la validación offline es correcta. Es bloqueo de coordinación,
no un fallo de tests funcionales de los adaptadores. No se alteró
research/public-reuse-parent ni se hizo merge.


## Revisión adicional sobre base oficial sincronizada (10/10/2026)

Se incorporó la base `737fc011` mediante commit de merge propio de la rama.
La base ya contiene `tools/target_quality_ranking.py`, `tools/candidate_identity.py`
y la suite oficial; no se ha copiado ni reimplementado su scoring. La función
`rank_with_66` ahora permite pasar los tres snapshots nativos y se ejercita
contra `target_quality_ranking.rank_all` real con las nueve redes; si faltan,
permanecen en estado `missing_input`. La clasificación española de la base
usa BCP-47 estricto y ya rechaza `est`.

Se descarta la fusión por handle de la PR #132: un handle mutable no acredita
que una observación sin ID pertenezca a una cuenta con ID. Se omite la fila
ambigua con diagnóstico explícito, independientemente del orden de entrada.
Pinterest conserva una lista explícita de campos de Pin (IDs, procedencia,
fecha, idioma, cola y permisos), y rechaza contradicciones entre handle/autor.
Los enlaces a un mismo post presentes en dos IDs distintos se excluyen en
ambas candidaturas para evitar oportunidades duplicadas.

Las colas API/MOBILE del adaptador son contrato de **lectura de datos aportados**;
no se acreditan recolectores de producción ni campañas de nueve redes. El
gate de campaña requiere que la PR #100 aparezca en el manifiesto de la rama
padre: no se ha alterado desde la hija. La PR #132 contiene cientos de ficheros
incidentales (incluidos pycache) y no debe incorporarse sin filtrar.

Comprobación combinada en Ubuntu y Windows con Python 3.11:

    python -m unittest discover -s tests -p test_native_target_candidate_ingest.py -v
    python -m unittest discover -s tests -p test_target_quality_ranking.py -v
    python -m py_compile tools/native_target_candidate_ingest.py tools/target_quality_ranking.py

Pendientes externos: contrato real y procedencia de lectores Edge/Windows,
API/MOBILE y Android, canario supervisado sin automatización y suite completa
del repo privado; no convertir fechas de escaneo en fechas de publicación.
