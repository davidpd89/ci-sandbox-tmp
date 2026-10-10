# Tests y estandarización en Reddit

Fuente: informe de Perplexity (https://www.perplexity.ai/search/6198861a-4fcf-4160-8adf-bb0fb238bf47), generado 10/10/2026.

Informe mejorado: pruebas, contratos y fixtures para el adaptador de Reddit

He revisado el informe anterior contra el código real de davidpd89/ci-sandbox-tmp y he eliminado propuestas que no aplican o que no puedo verificar con una URL exacta. La base existente ya cubre comentarios, publicación, votos, URLs, identidad, CDP y revalidación bajo lock; por tanto, la mejora correcta es un contrato global de crecimiento con adaptador Reddit, fixtures JSON deterministas y regresiones sobre los tests actuales, no un segundo adaptador.

Resumen

Reddit exige normalizar tres puntos antes de que un candidato entre en descubrimiento, ranking, cola de respuestas, ledger y atribución: identidad (id base-36 frente a fullname), fecha (created_utc en epoch) y relación (parent_id puede ser t3_ o t1_). Un contrato único evita que cada red invente su propia deduplicación, su propio formato de fecha y su propia clasificación de errores.

El repositorio espejo ya contiene tools/reddit_comments.py, reddit_execute.py, reddit_interact.py, reddit_publish.py, reddit_scan.py y reddit_survey.py, además de tests específicos como test_reddit_comments.py, test_reddit_publish.py, test_reddit_scan_votes.py, test_reddit_thread_url.py, test_reddit_vote_outcome.py, test_reddit_account_email_fallback.py, test_reddit_cdp_host.py, test_reddit_micro_scope.py y test_r7_reddit_revalidate_under_browser_lock.py. Las PR deben ampliar esos ficheros, no crear un adaptador paralelo.

Hallazgos
Fuente / repositorio	Estado y utilidad	Qué reutilizar	Integración	Riesgos	Tests
leog25/reddit-cli	Activo; usa TDD, fixtures de respuestas reales y httpx.MockTransport. 
github
	Modelos con created_utc: float, manejo de [deleted], campos opcionales y tests de render/export.	Crear tools/growth_contracts.py y tests/contracts/test_reddit_contract.py; adaptar los modelos, no copiar su cliente.	Su Post/Comment no cubre fullname, link_id ni parent_id con la rigurosidad que necesita el sistema.	Tipos, valores por defecto, permalink, created_utc, comentario borrado y campos ausentes.
jackwener/rdt-cli	Activo; tiene fixtures reales de post_detail.json y morechildren.json. 
developers.reddit
+1
	Estructura de fixtures para post y morechildren; útil como referencia de forma, no como fuente de datos.	Crear tests/fixtures/reddit/ con variantes propias: post español, comentario, respuesta, listing y errores.	Los fixtures son grandes y contienen datos reales; no copiarlos tal cual por privacidad, tamaño o acoplamiento.	Carga de fixture, campos obligatorios, morechildren, paginación y respuestas malformadas.

praw-dev/prawcore
	Activo; en 2026 migró su suite de Betamax a VCR.py manteniendo cassettes convertidos. 
til.simonwillison
	Enfoque de grabación/replay HTTP y migración de cassettes.	Si se necesitan pruebas de red grabadas, usar VCR.py; para la primera fase, bastan JSON estáticos.	Los cassettes de PRAWCore están acoplados a su cliente y a endpoints concretos.	Retry, 401, 403, 429, 5xx, timeout y JSON inválido.

praw-dev/praw
	Activo; referencia principal de pruebas unitarias e integración para Reddit en Python.	Organización de tests/unit, tests/integration, conftest.py y casos de Submission.	Tomar la estructura de carpetas y los nombres de casos; no instalar PRAW sólo para tests.	Copiar dependencias o cassettes sin adaptarlos crearía acoplamiento innecesario.	Parseo de submission/comment, URL, fullname, created_utc y errores.

praw-dev/asyncpraw
	Activo, pero no aplicable ahora.	Sólo el patrón de placeholders y tests asíncronos.	No introducir Async PRAW ni asyncio en esta fase.	Duplicaría la pila HTTP y complicaría Windows/CI sin beneficio inmediato.	Ninguno por ahora; reconsiderar sólo si se migra un flujo a async.

Reddit API Overview
	Documentación oficial vigente.	Contrato de things: t1_, t2_, t3_; parentId puede ser t3_ o t1_.	Implementar normalize_reddit_ref() compartido.	Confundir id, name y permalink.	Parametrizados sobre prefijos, vacíos, None y mayúsculas.

reddit.com/dev/api
	Documentación oficial vigente.	Fullnames y raw_json=1 para evitar escape HTML en JSON.	Añadir raw_json=1 a discovery JSON y conservar un normalizador de entidades para respuestas legacy.	Texto con <, > o & puede contaminar corpus, logs o plantillas.	Comentarios con HTML, Unicode, markdown, enlaces y emojis.

reddit-archive/reddit wiki JSON
	Referencia histórica útil para el contrato de datos.	created_utc como epoch UTC; id de cuenta se convierte en t2_.	Crear parse_reddit_timestamp() con zona UTC explícita.	Confundir created con created_utc; usar datetime.now() naive.	0, negativo, futuro, float, string, None y milisegundos erróneos.

Simon Willison — Reddit JSON
	Referencia práctica vigente del JSON público.	Forma de listing: data.children[].data, id, subreddit, url, created_utc, permalink, num_comments.	Diseñar listing_to_candidates() y fixtures de listing.	children vacío, url interno, crosspost o galería.	Listings vacíos, un elemento, after, duplicados y posts borrados.

halstonblim/reddit_sentiment_pipeline
	Activo; usa pytest, mocks y reglas de deduplicación.	Patrón de monkeypatch y tests de dedupe/errores.	Aplicarlo a reddit_scan.py y reddit_comments.py, sin copiar su scraper.	Mocks amplios pueden ocultar cambios de formato.	Dedupe por (kind, short_id), red, rate limit y respuesta malformada.
Contrato global

No crear RedditCandidate. Crear GrowthCandidate en tools/growth_contracts.py, con network, identidad canónica, fecha normalizada, acción y estado. Reddit sólo aporta el adaptador que rellena kind, short_id, fullname, parent_fullname y created_utc.

json
{
  "network": "reddit",
  "kind": "t3",
  "short_id": "abc123",
  "fullname": "t3_abc123",
  "subreddit": "Fantasy",
  "author": "usuario_ejemplo",
  "permalink": "https://www.reddit.com/r/Fantasy/comments/abc123/...",
  "created_utc": 1760000000,
  "created_at": "2025-10-09T08:53:20+00:00",
  "title": "Recomendaciones de romantasy en español",
  "body_or_selftext": "...",
  "score": 42,
  "num_comments": 7,
  "language": "es",
  "action": "comment",
  "target_fullname": "t3_abc123",
  "parent_fullname": null
}

Para un comentario, kind es t1, target_fullname es el post t3_... y parent_fullname puede ser otro t1_...; para un post, kind es t3 y parent_fullname debe ser null. Esto coincide con el modelo oficial de things y evita publicar una respuesta como si fuera comentario de post.

Código reutilizable
Modelo de fecha e identidad

Este bloque adapta el patrón de leog25/reddit-cli, que ya modela created_utc como float y permalink como campo separado; el archivo original define esos campos en src/reddit_cli/models.py.
github

python
# https://github.com/leog25/reddit-cli/blob/main/src/reddit_cli/models.py
from dataclasses import dataclass

@dataclass
class Post:
    id: str
    title: str
    author: str
    subreddit: str
    score: int
    upvote_ratio: float
    num_comments: int
    created_utc: float
    permalink: str = ""
    url: str = ""
    selftext: str = ""
    is_self: bool = True
    over_18: bool = False

Para nuestro sistema, ampliarlo así:

python
# Propuesta: tools/growth_contracts.py
from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass(frozen=True)
class GrowthCandidate:
    network: str
    kind: str
    short_id: str
    fullname: str
    created_utc: float
    permalink: str
    action: str
    target_fullname: str
    parent_fullname: str | None = None
    subreddit: str | None = None
    author: str | None = None
    title: str | None = None
    body_or_selftext: str | None = None
    score: int | None = None
    num_comments: int | None = None
    language: str | None = None

    @property
    def created_at(self) -> datetime:
        return datetime.fromtimestamp(self.created_utc, tz=timezone.utc)

    @property
    def dedupe_key(self) -> tuple[str, str, str, str]:
        return (self.network, self.kind, self.short_id, self.action)
Normalizador de fullname

La documentación oficial define el fullname como prefijo de tipo más ID único; t1_ es comentario, t2_ usuario y t3_ post.

python
# Propuesta: tools/growth_contracts.py
import re

_REDDIT_ID = re.compile(r"^[A-Za-z0-9]+$")
_ALLOWED_PREFIXES = {"t1", "t2", "t3"}

def normalize_reddit_ref(value: str | None) -> tuple[str, str] | None:
    if not value:
        return None
    ref = value.strip()
    if "_" in ref:
        prefix, short_id = ref.split("_", 1)
        if prefix not in _ALLOWED_PREFIXES or not _REDDIT_ID.match(short_id):
            return None
        return prefix, short_id
    if not _REDDIT_ID.match(ref):
        return None
    return None, ref
Parser de created_utc

El wiki histórico de Reddit define created_utc como timestamp epoch en segundos UTC, sin fracción; created es la hora local del servidor y no debe usarse para frescura.

python
# Propuesta: tools/growth_contracts.py
from datetime import datetime, timezone

def parse_reddit_timestamp(value: float | int | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        if not value.strip().replace(".", "", 1).isdigit():
            return None
        value = float(value)
    if isinstance(value, float) and not value.is_integer():
        return None
    ts = int(value)
    if ts < 0:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)
Manejo de campos ausentes y borrados

leog25/reddit-cli ya usa data.get("author", "[deleted]"), data.get("body", ""), data.get("score", 0) y data.get("created_utc", 0.0) en src/reddit_cli/client.py; es un patrón útil, pero para crecimiento no debemos aceptar created_utc=0.0 como válido sin marcarlo como candidato inválido.
github

python
# https://github.com/leog25/reddit-cli/blob/main/src/reddit_cli/client.py
author=data.get("author", "[deleted]"),
body=data.get("body", ""),
score=data.get("score", 0),
created_utc=data.get("created_utc", 0.0),
permalink=data.get("permalink", ""),
depth=data.get("depth", 0),
is_submitter=data.get("is_submitter", False),

Adaptación recomendada:

python
# Propuesta: tools/reddit_scan.py
def candidate_from_reddit_thing(thing: dict) -> GrowthCandidate | None:
    data = thing.get("data") or {}
    kind = thing.get("kind")
    short_id = data.get("id")
    created_utc = data.get("created_utc")
    if kind not in {"t1", "t3"} or not short_id:
        return None
    parsed = parse_reddit_timestamp(created_utc)
    if parsed is None:
        return None
    fullname = f"{kind}_{short_id}"
    parent = data.get("parent_id")
    return GrowthCandidate(
        network="reddit",
        kind=kind,
        short_id=short_id,
        fullname=fullname,
        created_utc=float(created_utc),
        permalink=data.get("permalink", ""),
        action="comment",
        target_fullname=data.get("link_id") if kind == "t1" else fullname,
        parent_fullname=parent if kind == "t1" else None,
        subreddit=data.get("subreddit"),
        author=data.get("author"),
        title=data.get("title"),
        body_or_selftext=data.get("body") or data.get("selftext"),
        score=data.get("score"),
        num_comments=data.get("num_comments"),
    )
Casos límite obligatorios

Identidad: abc123, t1_abc123, t3_abc123, T1_ABC123, espacios, vacío, None, prefijo inválido y parent_id que apunte a t3_ o t1_.

Fechas: 0, negativo, futuro, float con .0, string numérica, None, milisegundos y ausencia; created_utc nunca debe interpretarse como ISO-8601.

Listings: data.children vacío, kind inesperado, data ausente, campos opcionales ausentes, paginación after, duplicados y orden no cronológico.

Contenido: vacío, null, [deleted], [removed], markdown, enlaces, u/usuario, r/subreddit, HTML escapado, emojis, RTL y textos largos.

Errores: 401, 403, 404, 429, 5xx, JSON inválido, timeout, error en cuerpo, falta de permisos y fallo parcial de ronda.
til.simonwillison

Regresiones de acción: no repetir comentario sobre el mismo fullname; no votar dos veces; respetar TTL; registrar skip, success, failure y pending; y no tratar contenido propio como objetivo.

Fixtures mínimos

Crear tests/fixtures/reddit/ con JSON estáticos, sin tokens, cookies ni datos privados:

submission_es.json

comment_es.json

comment_reply_es.json

listing_hot.json

listing_mixed.json

error_403.json

error_429.json

error_500.json

invalid_json.txt

legacy_escaped.json

Ejemplo de fixture de comentario:

json
{
  "kind": "t1",
  "data": {
    "id": "c1abc",
    "name": "t1_c1abc",
    "author": "lector_es",
    "body": "Me encanta la tensión romántica de este fragmento.",
    "score": 3,
    "created_utc": 1760000000,
    "permalink": "/r/Fantasy/comments/abc123/ejemplo/c1abc/",
    "link_id": "t3_abc123",
    "parent_id": "t3_abc123"
  }
}

Y una variante de respuesta:

json
{
  "kind": "t1",
  "data": {
    "id": "c2def",
    "name": "t1_c2def",
    "author": "autor_ejemplo",
    "body": "Gracias, intenté que el giro se sintiera inevitable.",
    "score": 1,
    "created_utc": 1760000300,
    "permalink": "/r/Fantasy/comments/abc123/ejemplo/c2def/",
    "link_id": "t3_abc123",
    "parent_id": "t1_c1abc"
  }
}
Aplicación multired

El contrato debe ser común para todas las redes; Reddit sólo define el adaptador. Así se evita que X, Threads, Facebook, Pinterest, Bluesky, Mastodon, TikTok e Instagram repliquen lógica de fecha, deduplicación, ledger o errores.

Aspecto	Reddit	Equivalente multired
Identidad	t1_ / t3_ + ID base-36	URI/AT-URI, DID, ID numérico, permalink o handle
Fecha	created_utc epoch segundos	created_at ISO-8601, epoch o campo específico
Objeto comentable	Post t3_ o comentario t1_	Post, reel, pin, toot, thread o comentario
Deduplicación	(network, kind, short_id, action)	(network, canonical_target_id, action)
Error transversal	403, 429, 5xx, JSON inválido	Mismas clases, con adaptador de códigos
Ledger	target_fullname + acción + estado	canonical_target_id + acción + estado
Recomendación

Implementar un contrato global + adaptador Reddit, no un adaptador Reddit aislado. La primera entrega debe ser pequeña: tools/growth_contracts.py, tests/contracts/test_reddit_contract.py y tests/fixtures/reddit/submission_es.json; después, migrar gradualmente reddit_scan.py, reddit_comments.py, reddit_publish.py y reddit_interact.py para que consuman el contrato sin cambiar su comportamiento externo.

Plan de implementación en PR pequeñas

PR 1 — Contrato base: añadir GrowthCandidate, GrowthAction, parse_reddit_timestamp(), normalize_reddit_ref() y tests unitarios puros.

PR 2 — Fixtures Reddit: añadir los JSON estáticos, un loader con validación de esquema y tests de carga.

PR 3 — Identidad y URLs: integrar normalize_reddit_ref() en test_reddit_thread_url.py, test_r1_candidate_identity.py y los flujos de comentario.

PR 4 — Fechas y frescura: sustituir conversiones ad hoc por parse_reddit_timestamp() en scan, ranking y filtros de historial.

PR 5 — Errores y reintentos: añadir fixtures 403/429/5xx, clasificación de errores y pruebas de circuit breaker, cola y recuperación.

PR 6 — Deduplicación y ledger: asegurar idempotencia por (network, kind, short_id, action) y cubrir skip, failure, success y pending.

PR 7 — Paridad multired: extraer los tests comunes a tests/contracts/test_growth_contract.py y añadir adaptadores mínimos para Bluesky y Mastodon.

Fuentes

Reddit API Overview — Thing IDs

Reddit API documentation — fullnames y raw_json

reddit-archive/reddit wiki — JSON, created_utc

Simon Willison — Scraping Reddit via JSON API

leog25/reddit-cli — modelos y tests
github

jackwener/rdt-cli — fixtures JSON
developers.reddit

praw-dev/prawcore — migración a VCR.py
til.simonwillison

praw-dev/praw — tests e integración

DeepWiki — PRAW testing framework

praw-dev/asyncpraw

halstonblim/reddit_sentiment_pipeline — tests y mocks

Reddit — orden no garantizado en listings
