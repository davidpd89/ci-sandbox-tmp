# Herramientas y código abierto en Instagram

Fuente: informe de Perplexity (https://www.perplexity.ai/search/03541082-92a8-4cc1-be2c-a47d0a56143d), generado 10/10/2026.

Informe mejorado: repos, SDK, skills y agentes para Instagram con Python en Windows
Resumen

Tras revisar el espejo davidpd89/ci-sandbox-tmp, confirmo que tu sistema ya tiene una base Instagram completa: descubrimiento, interacción, ejecución, API Meta, métricas, atribución, colas, políticas y tests. La mejora no consiste en añadir otro bot ni otro cliente Graph completo, sino en incorporar adaptadores de ingesta pública, normalización de métricas oficiales, un fallback externo de scraping y una capa MCP/agentes que reutilice tus módulos existentes.

Descarto pystagram porque su última publicación en PyPI es de marzo de 2024 y no cumple el criterio de mantenimiento actual. También reduzco aiograpi a “no prioritario”: es activo, pero duplicaría capacidades de instagrapi y añadiría una capa async que tu arquitectura actual no necesita.
developers.facebook
+2

Hallazgos verificados
Repositorio / recurso	Estado	Qué aporta	Qué copiar	Veredicto para tu repo

instaloader/instaloader
	Activo; v4.15.1, 21 de marzo de 2026; 13.500 estrellas.	Ingesta pública de perfiles, posts, Reels, stories, captions, comentarios y hashtags.	Iteradores de perfil/hashtag, filtros por fecha y reanudación de iteraciones.	Alta prioridad: mejor base para descubrir posts y perfiles del nicho.

subzeroid/instagrapi
	Muy activo; release 3.0.21 el 9 de octubre de 2026. 
developers.facebook
	API privada: usuarios, medios, comentarios, DM, stories, insights y subidas.	Manejo de sesión, challenge, normalización de objetos y lectura de insights.	Complemento acotado: no como motor de engagement masivo.

facebook/facebook-python-business-sdk
	Oficial y activo; actualización automática en septiembre de 2026.	SDK oficial Meta/Graph para Instagram, Facebook y Business Manager.	Patrones de cliente, errores Graph, paginación y objetos de insights.	Alta prioridad: refuerza instagram_api.py y meta_insights.py.

apify/apify-sdk-python
	SDK oficial Apify.	Ejecución y consumo de Apify Actors desde Python.	Cliente de Actor, dataset exportable y manejo de run.	Fallback: útil si la observación directa falla.

apify/instagram-scraper
	Actor mantenido por Apify.	Posts, Reels, perfiles, hashtags, carruseles y comentarios mediante API gestionada.	Esquema de salida y mapeo a tu modelo interno.	Fallback de ingesta, no dependencia crítica.

brightdata/instagram-scraper-python
	Actualizado en agosto de 2026. 
subzeroid
	Perfiles, posts, Reels y comentarios como JSON, sin login ni navegador, sobre Bright Data.	Cliente de alto nivel y formato de resultados.	Alternativa de pago/freemium; útil como segundo proveedor externo.

adelaidasofia/instagram-mcp
	Actualizado en 2026; Python 3.10+. 
pypi
	MCP oficial Graph API: lectura, publicación, comentarios, insights y DM con revisión previa.	Diseño de herramientas MCP y patrón “review-gated actions”.	Muy relevante: modelo para tu futuro agente Instagram.

mcpware/instagram-mcp
	Actualizado en septiembre de 2026.	23 herramientas Graph API: posts, comentarios, DM, stories, hashtags, Reels, carruseles y analítica.	Contrato de herramientas y separación lectura/escritura/analítica.	Referencia de diseño, no dependencia directa.

subzeroid/aiograpi
	Activo. 
developers.facebook
+1
	Cliente async de API privada.	Patrones async.	No prioritario: redundante con instagrapi y con tu arquitectura de workers.

pystagram
	Inactivo desde marzo de 2024. 
pypi
	Cliente Graph/Basic Display.	—	Descartado por falta de mantenimiento reciente.
Código reutilizable tal cual
1. Ingesta de últimos posts de un perfil

Este bloque es directamente útil para alimentar instagram_scan.py y tu contrato de candidatos. Procede del repositorio Bellingcat, que documenta Instaloader con ejemplos ejecutables.
github

python
# https://github.com/bellingcat/toolkit/blob/main/gitbook/tools/instaloader/README.md
from itertools import islice
import instaloader

PROFILE = "instagram"
MAX_POSTS = 10

L = instaloader.Instaloader()
L.context.log("Logging in…")
L.load_session_from_file("my_user")  # reuse saved session, or:
# L.login("my_user", "PASSWORD")

posts = instaloader.Profile.from_username(L.context, PROFILE).get_posts()
for post in islice(posts, MAX_POSTS):
    L.download_post(post, target=PROFILE)

print("Done.")

Integración: no descargues los archivos multimedia por defecto. Convierte cada post en un registro JSON con shortcode, date_utc, caption, caption_hashtags, owner_username, likes, comments, video_view_count y is_video. Así alimentas descubrimiento sin duplicar tu capa de publicación.

2. Minería de hashtags desde un perfil

Este segundo bloque también procede del mismo archivo documentado de Bellingcat y es útil para ampliar discovery_terms.py y hashtag_report.py.
github

python
# https://github.com/bellingcat/toolkit/blob/main/gitbook/tools/instaloader/README.md
"""
Build hashtag counts across the latest 400 posts of a target profile.
Output TSV sorted by frequency.
"""
import re, collections, instaloader, itertools, csv

TARGET = "nasa"
MAX_POSTS = 400
hashtag_re = re.compile(r"#(\w+)")

freq = collections.Counter()
L = instaloader.Instaloader(quiet=True)

for post in itertools.islice(
    instaloader.Profile.from_username(L.context, TARGET).get_posts(),
    MAX_POSTS,
):
    freq.update(hashtag_re.findall(post.caption or ""))

with open(f"{TARGET}_hashtags.tsv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f, delimiter="\t")
    writer.writerow(["hashtag", "count"])
    for tag, count in freq.most_common():
        writer.writerow([tag.lower(), count])

print("Top 10:", freq.most_common(10))

Integración: cambia TARGET por cuentas semilla de fantasía, romantasy, BookTok, autores independientes y editoriales. Guarda el resultado en tools/hashtag_research/ y pásalo por tus filtros de idioma y calidad.

3. Iteración reanudable por hashtag

Para capturar muchos posts por hashtag sin reiniciar desde cero, Instaloader documenta un iterador reanudable. Este patrón encaja con tus módulos de recuperación, colas e idempotencia.
github

python
# https://github.com/instaloader/instaloader/issues/1077
import instaloader

SHORTCODE_FILE = "shortcodes.txt"
HASHTAG = "100daysofpractice"
IG_USER = ...  # (insert your username)

L = instaloader.Instaloader(fatal_status_codes=[400, 429])
L.load_session_from_file(IG_USER)

# Resumable iterator for recent hashtag posts, from #874.
hashtag_posts = instaloader.NodeIterator(
    context=L.context,
    query_hash="9b498c08113f1e09617a1703c22b2f32",
    edge_extractor=lambda d: d["data"]["hashtag"]["edge_hashtag_to_media"],
    node_wrapper=lambda n: instaloader.Post(L.context, n),
    query_variables={"tag_name": HASHTAG},
    query_referer=f"https://www.instagram.com/explore/tags/{HASHTAG}/",
)

with open(SHORTCODE_FILE, "a") as file:
    with instaloader.resumable_iteration(
        context=L.context,
        iterator=hashtag_posts,
        load=instaloader.load_structure_from_file,
        save=instaloader.save_structure_to_file,
        format_path=lambda magic: f"resume_info_{magic}.json.xz",
    ) as (is_resuming, start_index):
        if is_resuming:
            # After resuming, the first post is the last post that had been returned in
            # the previous iteration. Here we avoid that this post shortcode is repeated.
            next(hashtag_posts)

        # Here we write all shortcodes to the file
        for post in hashtag_posts:
            print(post.shortcode, file=file)

Integración: sustituye la escritura de shortcodes por una función upsert_candidate() que escriba en tu ledger o en el contrato de ingesta. Conserva fatal_status_codes=[400, 429] y el estado de reanudación.

4. Normalizador propio de candidatos

Este bloque no se copia de otro repo: es el pegamento que evita que Instaloader, Apify, Bright Data o la Graph API creen esquemas distintos en tu sistema.

python
# tools/instagram_ingest_schema.py
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional

@dataclass
class InstagramCandidate:
    external_id: str
    source: str                      # instaloader | graph_api | apify | brightdata
    kind: str                        # post | reel | comment | profile
    author_username: str
    author_external_id: Optional[str]
    caption: Optional[str]
    hashtags: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    lang: Optional[str] = None
    permalink: Optional[str] = None
    captured_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["network"] = "instagram"
        return data

def normalize_instaloader_post(post) -> InstagramCandidate:
    return InstagramCandidate(
        external_id=post.shortcode,
        source="instaloader",
        kind="reel" if post.is_video else "post",
        author_username=post.owner_username,
        author_external_id=str(post.owner_id),
        caption=post.caption,
        hashtags=[h.lower() for h in post.caption_hashtags],
        metrics={
            "likes": post.likes,
            "comments": post.comments,
            "video_views": getattr(post, "video_view_count", None),
        },
        permalink=f"https://www.instagram.com/p/{post.shortcode}/",
        raw={"typename": post.typename},
    )

Integración: colócalo junto a scan_common.py y haz que todos los adaptadores devuelvan InstagramCandidate. Así el ranking, la atribución y los tests no dependen del proveedor de datos.

Qué quité del informe anterior

pystagram: eliminado; sin release desde 2024.
pypi

aiograpi como recomendación principal: degradado a “no prioritario”; añade async sin necesidad actual y se solapa con instagrapi.
developers.facebook
+1

“Copiar el SDK oficial completo”: sustituido por “copiar patrones y usar llamadas normalizadas”; tu instagram_api.py ya existe y no debe duplicarse.

Promesa de métricas Graph sin matices: Instagram ofrece insights de cuenta y contenido, pero el acceso depende del tipo de cuenta, permisos y versión de API; debe validarse por endpoint antes de integrarlo.
github
+1

Recomendación final

Instaloader para descubrimiento público y minería de hashtags.

Graph API oficial / Meta SDK para métricas propias, publicación y comentarios.

instagrapi solo para sesiones, lectura complementaria y casos que Graph no cubra.

Apify o Bright Data como proveedores externos de respaldo.

MCP como interfaz de agente, con acciones sensibles siempre sujetas a aprobación y registro.

Plan de implementación en PR pequeñas
PR 1 — Contrato único de ingesta

Añadir tools/instagram_ingest_schema.py.

Crear InstagramCandidate y normalize_instaloader_post().

Tests: campos obligatorios, deduplicación por external_id, serialización JSON y compatibilidad con action_ledger.py.

PR 2 — Adaptador Instaloader

Añadir tools/instagram_instaloader_ingest.py.

Implementar ingesta por perfil, hashtag y rango de fechas.

Reutilizar el iterador reanudable documentado en Instaloader.
github

Tests: Windows/Python 3.11, hashtag público, perfil público, post sin caption, error 429, reanudación y escritura idempotente.

PR 3 — Minería de hashtags

Añadir tools/instagram_hashtag_miner.py.

Basarse en el contador de hashtags de Bellingcat, pero exportar JSON además de TSV.
github

Integrar salida con discovery_terms.py y hashtag_report.py.

Tests: normalización a minúsculas, exclusión de hashtags irrelevantes, top N y estabilidad del orden.

PR 4 — Métricas oficiales normalizadas

Ampliar meta_insights.py.

Normalizar métricas de cuenta y contenido: alcance, impresiones, visitas de perfil, seguidores, guardados, compartidos, interacciones, reproducciones y comentarios.

Meta documenta insights de cuenta y de contenido dentro de Instagram Platform.
github
+1

Tests: métricas ausentes, periodos inválidos, token caducado y reconciliación con growth_attribution.py.

PR 5 — Fallback Apify

Añadir tools/instagram_apify_ingest.py.

Usar apify/apify-sdk-python y mapear el Actor apify/instagram-scraper a InstagramCandidate.

Tests con Actor simulado, export JSON/CSV, límite de resultados, error de token y deduplicación.

PR 6 — Fallback Bright Data opcional

Añadir tools/instagram_brightdata_ingest.py.

Reutilizar el patrón de cliente de brightdata/instagram-scraper-python, que expone perfiles, posts, Reels y comentarios como JSON.
subzeroid

Tests: mock de API, perfiles, Reels, comentarios y fallos de red.

PR 7 — MCP de Instagram

Crear tools/instagram_agent_mcp.py.

Primera fase, solo lectura: ig_discover_posts, ig_score_candidate, ig_prepare_comment, ig_get_media_insights.

Segunda fase, con aprobación: ig_request_comment_approval, ig_publish_comment, ig_record_action_result.

Tomar como referencia el MCP oficial Graph de adelaidasofia/instagram-mcp, que separa lectura, publicación, comentarios, analítica y DM con revisión previa.
pypi

Tests: JSON estable, ninguna escritura sin aprobación, registro en ledger y bloqueo de acciones duplicadas.

PR 8 — Paridad multired

Extender el contrato a tools/network_capabilities.py.

Declarar capacidades: public_discovery, authenticated_discovery, comments, publish, insights, dm, approval_required.

Instagram, Facebook y Threads comparten parte de la capa Meta; Bluesky, Mastodon, Reddit, Pinterest, TikTok y X necesitan adaptadores propios, pero deben emitir el mismo esquema de candidato, acción y resultado.

Fuentes

Instagram Graph API y capacidades oficiales: 
https://developers.facebook.com/products/instagram/apis/

Instagram Platform: medios, publicación, comentarios, menciones, hashtags e insights: 
https://developers.facebook.com/documentation/instagram-platform/

Insights de Instagram Platform: 
https://developers.facebook.com/documentation/instagram-platform/insights/
github

Instagram Account Insights: 
https://developers.facebook.com/documentation/instagram-platform/api-reference/instagram-user/insights/
github

Meta Business SDK Python: 
https://github.com/facebook/facebook-python-business-sdk

Instaloader: 
https://github.com/instaloader/instaloader

Estado y versión de Instaloader: https://instaloader.github.io/

Ejemplos ejecutables de Instaloader: 
https://github.com/bellingcat/toolkit/blob/main/gitbook/tools/instaloader/README.md
github

Iterador reanudable por hashtag: 
 instaloader/instaloader#1077
github

instagrapi: 
https://github.com/subzeroid/instagrapi

Release actual de instagrapi: 
https://pypi.org/project/instagrapi/
developers.facebook

aiograpi: 
https://github.com/subzeroid/aiograpi
developers.facebook

Apify SDK Python: 
https://github.com/apify/apify-sdk-python

Apify Instagram Scraper API: 
https://apify.com/apify/instagram-scraper/api

Bright Data Instagram Scraper Python: 
https://github.com/brightdata/instagram-scraper-python
subzeroid

MCP oficial Graph API con acciones revisadas: 
https://github.com/adelaidasofia/instagram-mcp
pypi

Tema GitHub de MCP Instagram: 
https://github.com/topics/instagram-mcp

Tema GitHub instagram-graph-api: https://github.com/topics/instagram-graph-api
github
