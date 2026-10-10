# Ranking de cuentas y posts en Bluesky

Fuente: informe de Perplexity (https://www.perplexity.ai/search/2d22df97-9b3c-408c-a45c-2d21fa2e2e27), generado 10/10/2026.

Informe mejorado: señales y repos para priorizar follows y respuestas en Bluesky

Resumen. El sistema ya dispone de discovery, Jetstream, afinidad, reciprocidad y cola de respuestas; por tanto, la mejora correcta es un scorer de candidatos reutilizable, no otro collector ni otro pipeline de ejecución. La base técnica más sólida y verificable es el SDK Python atproto más los patrones oficiales de lectura, paginación y grafo social; el código siguiente puede copiarse tal cual como núcleo de hidratación y puntuación.
atproto
+1

Qué se elimina del informe anterior

lukeslp/skymarshal-js: se elimina como fuente de código a portar. Es TypeScript, no se verificó su archivo ni su actividad en esta revisión, y traducir PageRank o utilidades de bot detection añadiría complejidad sin necesidad inmediata.

Query-farm/vgi-bluesky: se degrada a referencia opcional. Es interesante para analítica SQL, pero introduce una dependencia adicional y no resuelve el problema central: decidir qué perfil seguir o qué post responder.

Fórmula concreta atribuida a bsky_neurobrain: se elimina porque no pude verificar el archivo de ranking ni su implementación exacta. Conservo solo la idea general —afinidad, engagement y decaimiento temporal—, que sí es coherente con un sistema de priorización.

Cualquier supuesto de “código tal cual” de repos no leídos: no se incluye. Solo se incorpora código verificado en la documentación oficial del SDK y en fuentes accesibles durante esta revisión.
atproto
+1

Hallazgos verificados
Hallazgo	Repo / fuente	Estado y utilidad	Qué integrar	Riesgos	Tests
SDK Python para ATProto/Bluesky	
MarshalX/atproto
	Activo y recomendado en el ecosistema; implementa cliente, lexicons, identidad, streaming y auth.	Cliente único para get_profile, get_profiles, get_follows, get_followers, get_author_feed, get_posts y get_post_thread	Cambios de modelos/lexicons; límites de paginación	Contract tests con fixtures de ProfileViewDetailed, FeedViewPost y PostView
Lectura de perfiles y conteos sociales	
atproto.blue — Reading
	Documentación oficial del SDK; confirma followers_count, posts_count, get_profile y get_profiles. 
atproto
	tools/bluesky_profile_signals.py	Perfiles suspendidos, borrados o privados	Test de perfil vacío, perfil borrado y caché por DID
Paginación por cursor	
atproto.blue — Pagination
	Patrón oficial: iterar mientras cursor sea verdadero; el límite suele ser 100. 
atproto
	Utilidad común paginate() para follows, followers y author feed	Bucles infinitos si se comprueba una página vacía en vez del cursor	Test con cursor final None, página vacía con cursor y límite 100
Grafo social de Bluesky	
AT Protocol — Social graph
	Guía oficial: app.bsky.graph.getFollows permite reutilizar el grafo para recomendaciones. 
atproto
	Señal de relación y detección de follows mutuos	Coste si se recorren grafos grandes	Test de mutuos, no mutuos y límite de profundidad
Feed de un autor	
atproto.blue — get_author_feed
	Permite obtener posts propios, sin respuestas, con media, hilos o vídeo. 
atproto
	Señales de actividad, idioma y afinidad por autor	Autores con poco histórico	Test de filtros posts_no_replies y posts_and_author_threads
Hilo y contexto de respuesta	
atproto.blue — get_post_thread
	Devuelve ancestros y respuestas; el nodo puede ser NotFoundPost o BlockedPost. 
atproto
	Validación previa a responder y detección de hilos activos	Post eliminado, bloqueado o no visible	Test de unión ThreadViewPost / NotFoundPost / BlockedPost
Relaciones y mutuos en CSV	
victoriano/bluesky-social-graph
	Script público centrado en followers/following y conexiones mutuas; coincide exactamente con la necesidad de relación social. 
pypi
+1
	Idea de exportación CSV y cálculo de mutuos; no duplicar su CLI	Dependencia de credenciales y volumen de peticiones	Test de CSV, deduplicación por DID y cálculo de mutuos
Ejemplo práctico de grafo + perfil	
David Gasquez — Exploring AT Protocol with Python
	Muestra el flujo real: extraer autores de posts, paginar follows y guardar followers_count, follows_count y posts_count. 
davidgasquez
	Adaptador de snapshot de red	Demasiadas llamadas si se hidratan todos los autores	Test de snapshot incremental y normalización de campos
Jetstream para observación continua	
bluesky-social/jetstream
	Servicio oficial de streaming, replay y archivo de red.	Mantener bluesky_jetstream_collect.py; añadir cursor persistente y eventos derivados	Duplicados en replay; memoria si se guardan posts completos	Test de cursor reanudable y deduplicación
Collector Python de Jetstream	
ruggsea/bluesky-firehose-py
	Librería/CLI para recoger y archivar posts mediante Jetstream.	Patrón de reconexión, JSONL y particionado temporal	Reconexiones y archivos duplicados	Test de reconexión y idempotencia
Respuestas requieren root y parent	
AT Protocol — create post
	Las respuestas usan strong references con AT URI y CID.	Validación estricta en bluesky_reply_queue.py	CID obsoleto o post eliminado	Test de rechazo sin CID/root/parent
Código reutilizable
1. Cliente de lectura y paginación

Este bloque es directamente aprovechable para hidratar candidatos sin reinventar la paginación. Procede de la documentación oficial del SDK y usa el patrón correcto: parar por cursor, no por página vacía.
atproto

python
# Fuente: https://atproto.blue/guides/reading/
from atproto import Client

def get_all_follows(client: Client, handle: str):
    cursor = None
    follows = []

    while True:
        fetched = client.get_follows(actor=handle, cursor=cursor)
        follows = follows + fetched.follows

        if not fetched.cursor:
            break

        cursor = fetched.cursor

    return follows

Integración: colocarlo en tools/bluesky_profile_signals.py como iter_follows(client, actor, max_pages), con max_pages y sleep_between_pages para no saturar la AppView. Debe alimentar relationship_policy.py y reciprocity.py, no sustituirlos.

2. Señales de perfil

Este bloque se basa en la API oficial de lectura: get_profile devuelve directamente un ProfileViewDetailed con followers_count, posts_count y otros campos útiles.
atproto

python
# Fuente: https://atproto.blue/guides/reading/
from atproto import Client

def get_profile_signals(client: Client, actor: str):
    profile = client.get_profile(actor)

    return {
        "did": profile.did,
        "handle": profile.handle,
        "display_name": profile.display_name,
        "description": profile.description,
        "followers_count": profile.followers_count,
        "follows_count": profile.follows_count,
        "posts_count": profile.posts_count,
        "created_at": profile.created_at,
    }

Integración: crear tools/bluesky_profile_signals.py con esta función y añadir campos derivados:

python
# Nuevo código para tools/bluesky_profile_signals.py
from datetime import datetime, timezone

def compute_profile_score(signals: dict, affinity: float, language: float, reciprocity: float) -> float:
    followers = max(int(signals.get("followers_count") or 0), 0)
    follows = max(int(signals.get("follows_count") or 0), 1)
    posts = max(int(signals.get("posts_count") or 0), 0)

    ratio = followers / follows
    ratio_score = min(ratio / 2.0, 1.0)
    activity_score = min(posts / 200.0, 1.0)

    return round(
        0.28 * affinity
        + 0.20 * language
        + 0.16 * ratio_score
        + 0.14 * activity_score
        + 0.12 * reciprocity
        + 0.10 * account_age_score(signals.get("created_at")),
        4,
    )

def account_age_score(created_at: str | None) -> float:
    if not created_at:
        return 0.0

    try:
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return 0.0

    age_days = max((datetime.now(timezone.utc) - created).days, 0)
    return min(age_days / 365.0, 1.0)

Nota: account_age_score no premia cuentas antiguas por sí mismas; satura a 1.0 al año. Así se evita favorecer cuentas inactivas solo por antigüedad.

3. Actividad y afinidad por autor

get_author_feed permite leer los posts de un autor y filtrar respuestas, lo cual es ideal para medir actividad y afinidad sin contaminar la señal con conversaciones ajenas.
atproto

python
# Fuente: https://atproto.blue/guides/reading/
from atproto import Client

def get_author_posts(client: Client, handle: str):
    profile_feed = client.get_author_feed(actor=handle, filter="posts_no_replies")

    for feed_view in profile_feed.feed:
        yield feed_view.post

Integración: en tools/bluesky_post_signals.py, calcular:

recent_posts_7d, recent_posts_30d.

spanish_ratio: proporción de posts con español detectado.

affinity_ratio: proporción de posts que activan el vocabulario de fantasía, romantasy, lectura, escritura y comunidad bookish.

conversation_openness: presencia de preguntas, peticiones de recomendación, opiniones y llamadas explícitas a conversación.

4. Contexto de hilo antes de responder

La documentación oficial advierte que thread.thread es una unión: puede ser ThreadViewPost, NotFoundPost o BlockedPost. Esa comprobación debe ser obligatoria antes de encolar una respuesta.
atproto

python
# Fuente: https://atproto.blue/guides/reading/
from atproto import Client

def get_safe_thread(client: Client, uri: str):
    thread = client.get_post_thread(uri=uri, depth=2)

    if getattr(thread.thread, "py_type", "") != "app.bsky.feed.defs#threadViewPost":
        return None

    return thread.thread

Integración: añadir a bluesky_reply_queue.py una validación previa:

python
# Nuevo código para tools/bluesky_reply_queue.py
def is_replyable(thread) -> bool:
    if thread is None:
        return False

    post = getattr(thread, "post", None)
    if post is None:
        return False

    record = getattr(post, "record", None)
    if record is None or not getattr(record, "text", "").strip():
        return False

    return bool(post.uri and post.cid)

Motivo: evita respuestas a posts borrados, bloqueados o sin contenido, y protege la cola existente sin cambiar su contrato.

5. Snapshot de grafo y perfiles

Este patrón procede de un ejemplo público que combina autores de posts, follows paginados y metadatos de perfil en CSV. Es útil como modelo de snapshot, aunque debe adaptarse a los archivos y convenciones ya presentes en SISTEMA_DIARIO_BLUESKY.
davidgasquez

python
# Fuente: https://davidgasquez.com/exploring-atproto-python
def get_all_follows(author):
    cursor = None
    follows = []

    while True:
        fetched = client.app.bsky.graph.get_follows(
            params={"actor": author, "cursor": cursor}
        )
        follows = follows + fetched.follows

        if not fetched.cursor:
            break

        cursor = fetched.cursor

    return follows
python
# Fuente: https://davidgasquez.com/exploring-atproto-python
from tqdm import tqdm

with open("databs.csv", "w") as f:
    f.write(
        "source,target,source_avatar_url,source_posts_count,"
        "source_followers_count,source_follows_count\n"
    )

    for source in tqdm(unique_authors):
        author_follows = get_all_follows(source)
        source_actor = client.app.bsky.actor.get_profile(params={"actor": source})

        for follow in author_follows:
            f.write(
                f"{source},{follow.handle},{source_actor.avatar},"
                f"{source_actor.posts_count},{source_actor.followers_count},"
                f"{source_actor.follows_count}\n"
            )

Integración: convertirlo en tools/bluesky_network_snapshot.py, pero con tres cambios:

Escribir en SISTEMA_DIARIO_BLUESKY/data/network_snapshot_YYYY-MM-DD.csv.

Usar DID como clave principal y handle solo como etiqueta.

Limitar la profundidad y guardar snapshot_run_id para que reciprocity_stats.py pueda atribuir resultados.

Scorer recomendado
Follow
𝑆
𝑐
𝑜
𝑟
𝑒
𝑓
𝑜
𝑙
𝑙
𝑜
𝑤
=
0.28
𝐴
+
0.20
𝐿
+
0.16
𝑅
+
0.14
𝑉
+
0.12
𝑃
+
0.10
𝐸
Score
follow
	​

=0.28A+0.20L+0.16R+0.14V+0.12P+0.10E

Donde:

𝐴
A: afinidad temática.

𝐿
L: compatibilidad de idioma.

𝑅
R: ratio followers/following normalizado.

𝑉
V: actividad reciente.

𝑃
P: reciprocidad previa.

𝐸
E: antigüedad sana de la cuenta.

Respuesta
𝑆
𝑐
𝑜
𝑟
𝑒
𝑟
𝑒
𝑝
𝑙
𝑦
=
0.30
𝐴
+
0.20
𝐿
+
0.18
𝐹
+
0.14
𝐶
+
0.10
𝑃
+
0.08
𝑉
Score
reply
	​

=0.30A+0.20L+0.18F+0.14C+0.10P+0.08V

Donde:

𝐴
A: afinidad temática del post.

𝐿
L: idioma.

𝐹
F: frescura.

𝐶
C: conversabilidad: pregunta, opinión, recomendación o hilo activo.

𝑃
P: reciprocidad previa.

𝑉
V: actividad del autor.

replyCount debe pesar más que likeCount: un post con muchos likes puede no generar conversación, mientras que un hilo con respuestas recientes indica que la conversación sigue abierta. La lectura de contexto debe hacerse con get_post_thread, comprobando explícitamente que el nodo siga visible.
atproto

Plan de PR pequeñas

PR 1 — Contrato de scoring. Crear tools/bluesky_candidate_scorer.py con ProfileSignals, PostSignals, FollowScore y ReplyScore; solo funciones puras y tests.

PR 2 — Perfiles. Crear tools/bluesky_profile_signals.py con get_profile_signals, caché por DID, ratio social, actividad y antigüedad.

PR 3 — Paginación segura. Añadir iter_follows / iter_followers con límite de páginas, pausa y parada por cursor.

PR 4 — Actividad y afinidad. Crear tools/bluesky_post_signals.py usando get_author_feed(filter="posts_no_replies").

PR 5 — Reciprocidad. Conectar el scorer con reciprocity.py y reciprocity_stats.py; bonus por interacción mutua y penalización por ausencia repetida.

PR 6 — Validación de respuesta. Añadir get_safe_thread e is_replyable a bluesky_reply_queue.py.

PR 7 — Snapshot de red. Crear tools/bluesky_network_snapshot.py, basado en el patrón de grafo + perfil, con salida CSV/JSONL incremental.

PR 8 — Ranking y auditoría. Crear tools/bluesky_discovery_ranking.py; cada candidato debe guardar score, reasons, evidence, source y created_at.

PR 9 — Extensión multired. Extraer el contrato de señales a growth_core.py para reutilizar afinidad, idioma, actividad, relación y frescura en X, Threads, Facebook, Pinterest, Reddit, Mastodon, TikTok e Instagram.

Aplicación multired
Red	Señal de relación	Señal de actividad	Señal de afinidad	Señal de frescura
X	Followers/following, interacciones previas	Últimos posts y replies	Bio, hashtags, comunidades	Edad del tweet
Threads	Seguidores y respuestas previas	Frecuencia de posts	Temas y respuestas	Edad del thread
Facebook	Amigos, grupos, reacciones	Actividad en grupos/páginas	Grupos de lectura y fantasía	Comentarios recientes
Pinterest	Seguidores y guardados	Pins recientes	Tableros y keywords	Fecha del pin
Reddit	Karma, historial, moderación	Posts y comentarios recientes	Subreddit y flair	Edad y actividad del hilo
Bluesky	Followers/following y grafo	Posts recientes	Bio, feed y términos	Edad del post
Mastodon	Followers/following e interacciones	Toots recientes	Instancia, bio y hashtags	Edad del toot
TikTok	Seguidores e interacciones	Vídeos recientes	Hashtags, sonido y bio	Edad del vídeo
Instagram	Seguidores y comentarios previos	Reels/posts recientes	Bio, hashtags y ubicación	Edad del post/reel
Fuentes

MarshalX/atproto — SDK Python de AT Protocol

atproto.blue — lectura de feeds, posts, hilos y perfiles
atproto

AT Protocol — social graph
atproto

AT Protocol — creación de posts y strong refs

victoriano/bluesky-social-graph
atproto

bluesky-social/jetstream

ruggsea/bluesky-firehose-py

David Gasquez — Exploring AT Protocol with Python
davidgasquez

AT Protocol SDKs
