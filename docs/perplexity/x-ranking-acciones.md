# Ranking de cuentas y posts en X (Twitter)

Fuente: informe de Perplexity (https://www.perplexity.ai/search/83126d44-2c53-462d-9a3b-64a0e31946bd), generado 10/10/2026.

Informe mejorado: señales y repositorios para priorizar follows y respuestas en X
Resumen

Revisé el informe anterior contra el código real de davidpd89/ci-sandbox-tmp y eliminé lo dudoso o poco aprovechable. La recomendación se mantiene: no crear un segundo motor de crecimiento, sino añadir un ranker de oportunidades que consuma los candidatos de x_scan.py / x_interact.py, calcule score_follow y score_reply, y alimente las colas existentes.

Las piezas públicas con mejor relación entre utilidad, licencia y mantenimiento son vladkens/twscrape para normalizar perfiles y posts, d60/twikit como fuente alternativa, y LlmKira/fast-langdetect para validar español más allá del campo lang de X.
github

Correcciones al informe anterior

Eliminado: Codewithmirzabaig/social-media-engagement-analysis-python. Es un proyecto de análisis en notebook, no una librería reutilizable para un pipeline CI; su KPI no encaja con tu modelo de reciprocidad.
docs.x
+1

Eliminado: kaiyoo/Twitter-Follower-Link-prediction. Es un experimento de link prediction de 2020, sin evidencia de mantenimiento reciente ni licencia clara; no es una base segura para producción.
docs.x

Eliminado: la sugerencia de usar impression_count como señal principal. Es una métrica del propio post y, en la práctica, no es la mejor señal para decidir a quién responder; reply_count, like_count y antigüedad son más accionables.

Corregido: twikit original tuvo su última release en febrero de 2025; sigue siendo MIT, pero conviene tratarlo como fallback y vigilar forks mantenidos.

Añadido: fast-langdetect, con código MIT y modelos FastText CC BY-SA 3.0; es útil porque el campo lang de un tweet puede fallar en textos cortos o con muchos hashtags.
github

Hallazgos
Hallazgo	Repo / fuente	Licencia	Actividad y encaje	Qué reutilizar	Riesgos	Tests
Modelos normalizados de usuario y tweet, con todas las señales necesarias	
vladkens/twscrape — twscrape/models.py
	MIT	~2.9k estrellas; proyecto activo y mantenido	User y Tweet: seguidores, siguiendo, posts, antigüedad, idioma, replies, likes, retweets, citas, conversación	Depende de la API interna de X; aislar tras un adaptador propio	Test de contrato sobre fixtures; test de campos obligatorios
Cliente X sin API key, búsqueda, timelines y usuarios	
d60/twikit
	MIT	Última release 2.3.1, febrero de 2025	Cliente de respaldo y funciones de búsqueda; no copiar su lógica de interacción	Posible desincronización con cambios de X	Test de paridad con twscrape
Detección de idioma offline, rápida y compatible con Windows/Python 3.9–3.14	
LlmKira/fast-langdetect
	Código MIT; modelos CC BY-SA 3.0 
github
	324 estrellas, 108 commits; activo 
github
	Validación de es sobre bio y texto del post	Los modelos tienen licencia distinta al código; no redistribuir modelos modificados sin cumplir CC BY-SA	Test con tweets cortos, hashtags, spanglish y acentos
Señales oficiales de perfil	
X API v2 — User lookup
	Documentación oficial	Referencia vigente	public_metrics, created_at, description, verified	Hay que pedir campos explícitamente con user.fields	Fixtures JSON y cálculo de métricas
Señales oficiales de post	
X API v2 — Recent search
	Documentación oficial	Referencia vigente	created_at, lang, public_metrics, conversation_id, in_reply_to_user_id	Recent search cubre solo los últimos 7 días	Test de ventana temporal y exclusión de retweets
Código reutilizable tal cual
1. Modelo de perfil y post de twscrape

Este es el fragmento exacto que conviene reutilizar como referencia de normalización. No conviene copiarlo a ciegas dentro de tools/: mejor crear un adaptador que convierta estos objetos al esquema común del sistema.

Archivo: 
https://github.com/vladkens/twscrape/blob/main/twscrape/models.py

Licencia: MIT — 
https://github.com/vladkens/twscrape/blob/main/LICENSE

python
# Fuente: https://github.com/vladkens/twscrape/blob/main/twscrape/models.py
# Licencia: MIT — https://github.com/vladkens/twscrape/blob/main/LICENSE

@dataclass
class User(JSONTrait):
    id: int
    id_str: str

    url: str
    username: str
    displayname: str
    rawDescription: str
    created: datetime
    followersCount: int
    friendsCount: int
    statusesCount: int
    favouritesCount: int
    listedCount: int
    mediaCount: int
    location: str

    profileImageUrl: str
    profileBannerUrl: str | None = None
    protected: bool | None = None
    verified: bool | None = None
    blue: bool | None = None
    blueType: str | None = None
    descriptionLinks: list[TextLink] = field(default_factory=list)

    pinnedIds: list[int] = field(default_factory=list)
    _type: str = "snscrape.modules.twitter.User"
python
# Fuente: https://github.com/vladkens/twscrape/blob/main/twscrape/models.py
# Licencia: MIT — https://github.com/vladkens/twscrape/blob/main/LICENSE

@dataclass
class Tweet(JSONTrait):
    id: int
    id_str: str
    url: str
    date: datetime

    user: User
    lang: str
    rawContent: str
    replyCount: int
    retweetCount: int
    likeCount: int
    quoteCount: int
    bookmarkedCount: int
    conversationId: int
    conversationIdStr: str
    hashtags: list[str]
    cashtags: list[str]
    mentionedUsers: list[UserRef]
    links: list[TextLink]
    media: "Media"
    viewCount: int | None = None
    retweetedTweet: Optional["Tweet"] = None
    quotedTweet: Optional["Tweet"] = None
    place: Place | None = None
    coordinates: Coordinates | None = None
    inReplyToTweetId: int | None = None
    inReplyToTweetIdStr: str | None = None
    inReplyToUser: UserRef | None = None

Uso en tu sistema: followersCount, friendsCount, statusesCount y created cubren las señales de perfil; date, lang, replyCount, likeCount, retweetCount, quoteCount y conversationId cubren las señales de post. Esto evita inventar campos y permite mapear directamente a tu esquema de x_scan.py.

2. Detección de idioma con fast-langdetect

Archivo / documentación: 
https://github.com/LlmKira/fast-langdetect

Licencia del código: MIT
Licencia de los modelos FastText incluidos: CC BY-SA 3.0
github

python
# Fuente: https://github.com/LlmKira/fast-langdetect
# Licencia del código: MIT
# Licencia de los modelos FastText: CC BY-SA 3.0
from fast_langdetect import detect

print(detect("Hello, world!", model="auto", k=1))
print(detect("Hello 世界 こんにちは", model="auto", k=3))
python
# Fuente: https://github.com/LlmKira/fast-langdetect
# Licencia del código: MIT
# Licencia de los modelos FastText: CC BY-SA 3.0
from fast_langdetect import LangDetectConfig, LangDetector

config = LangDetectConfig(cache_dir="/custom/cache", model="lite")
detector = LangDetector(config)
print(detector.detect("Hola", model="full", k=1))

Uso en tu sistema: aplica este detector solo cuando tweet.lang sea vacío, distinto de es o poco fiable; por ejemplo, en posts menores de 80 caracteres o con muchos hashtags. La propia documentación advierte que la precisión baja en textos demasiado cortos o largos.
github

Señales finales
Perfil: a quién seguir
Señal	Cálculo	Peso inicial	Motivo
Reciprocidad estructural	friendsCount / max(followersCount, 1)	30%	Detecta cuentas activas y con disposición a seguir
Actividad	statusesCount / días_desde_created	25%	Evita cuentas antiguas pero dormidas
Afinidad temática	Coincidencia de bio, nombre y posts con fantasía, romantasy, libros y escritura	20%	Filtra el nicho de David
Idioma	es validado por lang + FastText	15%	Evita seguir cuentas no hispanohablantes
Antigüedad	Días desde created	5%	Descuenta cuentas recién creadas
Comunidad	listedCount normalizado	5%	Señal débil de relevancia
python
# Propuesta propia para tools/x_opportunity_ranker.py
def score_follow(profile: dict) -> float:
    followers = max(profile["followers_count"], 1)
    ratio = profile["following_count"] / followers
    reciprocidad = min(ratio / 2.0, 1.0)  # 2:1 following/followers = techo
    actividad = min(profile["tweets_per_day"] / 1.0, 1.0)
    afinidad = profile["topic_affinity"]  # 0..1
    idioma = 1.0 if profile["lang"] == "es" else 0.0
    antiguedad = min(profile["account_age_days"] / 180, 1.0)
    comunidad = min(profile["listed_count"] / 100, 1.0)

    return round(
        100 * (
            0.30 * reciprocidad
            + 0.25 * actividad
            + 0.20 * afinidad
            + 0.15 * idioma
            + 0.05 * antiguedad
            + 0.05 * comunidad
        ),
        2,
    )
Post: a qué responder
Señal	Cálculo	Peso inicial	Motivo
Frescura	Decaimiento por horas desde created_at	30%	Prioriza conversaciones vivas
Conversabilidad	replyCount / max(likeCount, 1)	25%	Detecta hilos con debate real
Afinidad	Fantasía, romantasy, lectura, escritura, tropes	20%	Aumenta probabilidad de réplica útil
Idioma	es validado	15%	Filtra el público objetivo
Autor alcanzable	score_follow del autor	10%	Prioriza perfiles con reciprocidad potencial
python
# Propuesta propia para tools/x_opportunity_ranker.py
from datetime import datetime, timezone

def score_reply(post: dict, author_score: float) -> float:
    age_hours = (
        datetime.now(timezone.utc) - post["created_at"]
    ).total_seconds() / 3600

    frescura = max(0.0, 1.0 - age_hours / 24.0)
    conversabilidad = min(
        post["reply_count"] / max(post["like_count"], 1),
        1.0,
    )
    afinidad = post["topic_affinity"]  # 0..1
    idioma = 1.0 if post["lang"] == "es" else 0.0

    return round(
        100 * (
            0.30 * frescura
            + 0.25 * conversabilidad
            + 0.20 * afinidad
            + 0.15 * idioma
            + 0.10 * (author_score / 100)
        ),
        2,
    )
Recomendación

Implementa tools/x_opportunity_ranker.py como módulo nuevo, sin modificar x_interact.py ni reciprocity.py. Debe leer candidatos ya capturados, normalizarlos al esquema inspirado en twscrape, calcular ambos scores y escribir:

x_follow_candidates.jsonl

x_reply_candidates.jsonl

reason_codes explicando cada decisión

Usa twscrape como fuente principal y twikit como fallback; usa fast-langdetect solo como validador de idioma.
github

Plan de implementación en PR pequeñas

PR 1 — Esquema común: tools/opportunity_schema.py con XProfileCandidate y XPostCandidate; campos basados en User y Tweet de twscrape.

PR 2 — Normalizador: tools/x_opportunity_normalize.py; convierte objetos de x_scan.py, twscrape o twikit al esquema común.

PR 3 — Scoring de follows: x_opportunity_ranker.py --mode follow; implementa score_follow con pesos configurables.

PR 4 — Scoring de replies: x_opportunity_ranker.py --mode reply; implementa score_reply, filtros de frescura, idioma y retweets.

PR 5 — Integración: conecta salidas a reply_queue.py, relationship_policy.py y action_ledger.py.

PR 6 — Medición: amplía growth_attribution.py con follows realizados, respuestas recibidas, nuevos seguidores y conversaciones de dos o más turnos.

PR 7 — Multired: extrae opportunity_schema.py y opportunity_ranker.py a una capa común, con adaptadores para Bluesky, Mastodon, Threads, Facebook, Pinterest, Reddit, Instagram y TikTok.

Aplicación a las demás redes
Red	Señal de perfil	Señal de post	Adaptación
Bluesky	Seguidores/siguiendo, posts, antigüedad, descripción	Fecha, idioma, replies, likes, reposts	Reutiliza bluesky_growth_scan.py como fuente
Mastodon	Seguidores/siguiendo, notas, antigüedad, instancia	Fecha, idioma, respuestas, boosts, favoritos	Reutiliza mastodon_growth_scan.py
Threads	Seguidores, respuestas, actividad reciente, bio	Respuestas, likes, antigüedad, tema	Adaptador sobre threads_scan.py
Facebook	Amigos/seguidores, actividad de grupo, afinidad	Comentarios, reacciones, recencia	Prioriza grupos y comentarios, no solo posts
Pinterest	Seguidores, pins, tableros, nicho visual	Guardados, comentarios, frescura	El objetivo pasa de “responder” a “interactuar con pin relevante”
Reddit	Karma, antigüedad, actividad por subreddit	Upvotes, comentarios, edad del hilo	Prioriza hilos pequeños, recientes y con reglas compatibles
Instagram	Seguidores/siguiendo, bio, reels recientes	Comentarios, guardados, recencia	Reutiliza instagram_commenters_scan.py
TikTok	Seguidores/siguiendo, actividad, nicho	Comentarios, likes, recencia, formato	Prioriza comentarios conversacionales
Fuentes

twscrape: 
https://github.com/vladkens/twscrape

Licencia MIT de twscrape: 
https://github.com/vladkens/twscrape/blob/main/LICENSE

twscrape/models.py: 
https://github.com/vladkens/twscrape/blob/main/twscrape/models.py

twikit: 
https://github.com/d60/twikit

Licencia MIT de twikit: 
https://github.com/d60/twikit/blob/main/LICENSE

Releases de twikit: 
https://github.com/d60/twikit/releases

fast-langdetect: 
https://github.com/LlmKira/fast-langdetect
github

X API v2 — campos: 
https://docs.x.com/x-api/fundamentals/fields

X API v2 — diccionario de datos: 
https://docs.x.com/x-api/fundamentals/data-dictionary

X API v2 — User lookup: 
https://docs.x.com/x-api/users/lookup/introduction

X API v2 — Recent search: 
https://developer.x.com/apitools/api?endpoint=/2/tweets/search/recent&method=get

Comparativa de scrapers X en 2026: 
https://scrapfly.io/blog/posts/best-twitter-scrapers-github
