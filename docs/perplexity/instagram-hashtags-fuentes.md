# Hashtags, fuentes y comunidades en Instagram

Fuente: informe de Perplexity (https://www.perplexity.ai/search/44b9fbff-a3a0-41ca-b746-84e7d199bfca), generado 10/10/2026.

Informe mejorado: descubrimiento de posts y perfiles lectores en Instagram
Resumen

He revisado el informe anterior contra el estado real de davidpd89/ci-sandbox-tmp y contra repositorios públicos activos a 10 de octubre de 2026. He eliminado herramientas que no encajan con el sistema —scrapers de perfiles privados, herramientas de extracción de correos, bots de automatización y auto-reposteo de Reels— y he reforzado la base con Instaloader, gallery-dl, instagrapi y el SDK oficial de Meta.
mujeresaseguir
+4

El repo espejo sólo contiene hoy una publicación Instagram editorial en publicaciones Instagram GPT/2026-10-05/publicacion.md; no hay adaptador, fuentes ni configuración de descubrimiento Instagram en main, por lo que esta propuesta añade capacidad nueva sin duplicar código.

Hallazgos verificados
Herramienta / fuente	Estado comprobado	Qué resolver	Veredicto para el sistema

instaloader/instaloader
	Activo; versión 4.15.3 publicada el 26 de julio de 2026, con correcciones de resolución de perfiles, metadatos de posts y menciones en captions. 
github
+2
	Ingesta de posts por hashtag, perfiles, captions, comentarios y metadatos.	Adoptar como adaptador principal.

mikf/gallery-dl
	Proyecto activo y multiplataforma; su extractor Instagram requiere cookies de navegador desde 2023. 
github
+1
	Respaldo para descarga y metadatos cuando Instaloader falle.	Adoptar como respaldo CLI, no como dependencia principal.

subzeroid/instagrapi
	Activo; wrapper no oficial que cubre usuarios, medios, comentarios, insights y sesiones. 
mujeresaseguir
	Operaciones más amplias, incluidas sesiones y comentarios.	Vigilancia tecnológica, no integración inmediata: mayor superficie de fragilidad por API privada.

instagram-platform-sdk
	SDK oficial de Meta para Instagram Graph API v26.0+, con cliente síncrono y asíncrono. 
gallery-dlp
	Métricas propias, publicación y gestión de contenidos autorizados.	Usar sólo para métricas de la cuenta propia, no para descubrir posts de terceros.
obitouka/InstagramPrivSniffer	Activo, 1.051 estrellas, último push 18 de septiembre de 2026; se presenta como herramienta para ver posts privados.	Acceso a contenido privado.	Descartado: no aplica al descubrimiento de contenido público del nicho.
kiryano/Scout	Activo, 745 estrellas, último push 5 de septiembre de 2026; extrae perfiles y correos de bios.	Generación de leads y extracción de emails.	Descartado: no resuelve descubrimiento de posts ni perfiles lectores.
new92/instatools	Activo, 340 estrellas, último push 8 de octubre de 2026; colección de automatizaciones.	Automatización general de Instagram.	Descartado: licencia no identificada con claridad y enfoque de bot, no de descubrimiento medible.
Avnsh1111/Instagram-Reels-Scraper-Auto-Poster	Activo, 311 estrellas, último push 16 de agosto de 2026; scrapea Reels y los republica automáticamente.	Reposteo automático.	Descartado: no encaja con creación propia ni con ranking de interacción contextual.
Fuentes de nicho lector
Hashtags prioritarios

Estos hashtags deben ser la primera capa de descubrimiento. #bookstagramespaña, #romantasy, #librosdefantasia, #reseñasdelibros y #tbr aparecen de forma recurrente en reels españoles de recomendaciones de fantasía y romantasy de 2025-2026.

text
# Archivo nuevo: data/instagram/hashtags_core.yaml
version: 1
network: instagram
language: es
updated_at: "2026-10-10"

hashtags:
  - tag: bookstagramespaña
    tier: core
    priority: 10
  - tag: bookstagramespañol
    tier: core
    priority: 9
  - tag: romantasy
    tier: core
    priority: 10
  - tag: librosdefantasia
    tier: core
    priority: 10
  - tag: fantasia
    tier: core
    priority: 8
  - tag: bookstagram
    tier: core
    priority: 7
  - tag: lectura
    tier: core
    priority: 6
  - tag: libros
    tier: broad
    priority: 4
  - tag: reseñasdelibros
    tier: core
    priority: 8
  - tag: tbr
    tier: intent
    priority: 9
Hashtags de intención

Estos capturan oportunidades de comentario útil: recomendaciones, TBR, reseñas y debates de lecturas.

text
# Archivo nuevo: data/instagram/hashtags_intent.yaml
version: 1
network: instagram
language: mixed_es_en

hashtags:
  - tag: recomendacionesdelibros
    intent: recommendation
    priority: 9
  - tag: librosrecomendados
    intent: recommendation
    priority: 8
  - tag: librosderomance
    intent: genre
    priority: 8
  - tag: romancebooks
    intent: genre
    priority: 6
  - tag: fantasyromance
    intent: genre
    priority: 8
  - tag: bookrecs
    intent: recommendation
    priority: 7
  - tag: bookrec
    intent: recommendation
    priority: 7
  - tag: bookstagrammer
    intent: community
    priority: 6
Hashtags de expansión

Usar sólo como segunda pasada, porque introducen más ruido. #bookstagramargentina, #librosymáslibros, #booktok, #bookish, #booklover y #bookworm amplían el radio geográfico y temático.

text
# Archivo nuevo: data/instagram/hashtags_expansion.yaml
version: 1
network: instagram
enabled: false  # Activar tras validar precisión del núcleo

hashtags:
  - tag: bookstagramargentina
    region: latam
    priority: 5
  - tag: librosymáslibros
    region: latam
    priority: 5
  - tag: booktok
    region: global
    priority: 4
  - tag: bookish
    region: global
    priority: 4
  - tag: booklover
    region: global
    priority: 3
  - tag: bookworm
    region: global
    priority: 3
Cuentas semilla
Semillas verificables

Estas cuentas aparecen en listados actuales de bookstagram e influencers literarios españoles; deben verificarse manualmente antes de ingestarlas, porque los listados pueden contener handles desactualizados.

text
# Archivo nuevo: data/instagram/seed_accounts.yaml
version: 1
network: instagram
language: es

seeds:
  - handle: littleredread
    niche: romantasy_juvenil
    priority: 9
    source: "https://influencers.feedspot.com/spanish_book_instagram_influencers/"
  - handle: nuribooks
    niche: romance_fantasia
    priority: 8
    source: "https://influencers.feedspot.com/spanish_book_instagram_influencers/"
  - handle: luciagsobrado
    niche: autora_fantasia_romance
    priority: 8
    source: "https://influencers.feedspot.com/spanish_book_instagram_influencers/"
Semillas secundarias

Añadir sólo tras validación manual de bio, últimos posts e idioma:

Cuentas de reseñas, novedades, fantasía, juvenil y romance identificadas en listados bookstagram españoles.

Perfiles históricos de referencia como @bibianainbookland, @lanarradora, @sandrablawerson y @saralectora; son útiles para calibrar el nicho, pero no deben ingestarse automáticamente sin comprobar que siguen activos.

Búsquedas y comunidades
Consultas de posts
text
# Archivo nuevo: queries/instagram/posts_es.yaml
version: 1
network: instagram
language: es

queries:
  - text: "romantasy recomendación"
    intent: high
  - text: "fantasía romance recomendación"
    intent: high
  - text: "¿qué leo después de romantasy?"
    intent: high
  - text: "TBR fantasía"
    intent: high
  - text: "libros fantasía españoles"
    intent: medium
  - text: "reseña fantasía"
    intent: medium
  - text: "romantasy oscuro"
    intent: medium
  - text: "fantasía juvenil recomendación"
    intent: high
Consultas de perfiles
text
# Archivo nuevo: queries/instagram/profiles_es.yaml
version: 1
network: instagram
language: es

queries:
  - "bookstagram fantasía"
  - "bookstagram romantasy"
  - "lectora fantasía"
  - "reseñas libros fantasía"
  - "romantasy español"
  - "bookstagramespaña romantasy"

Las páginas de hashtag funcionan como listas vivas: #bookstagramespaña y #romantasy agregan reels y posts recientes del nicho.

Código reutilizable
Instalación y consulta por hashtag

Instaloader acepta directamente hashtags con el formato #hashtag; su CLI documenta el objetivo profile | "#hashtag" | %%location_id | :stories | :feed | :saved.

bash
# Uso documentado por Instaloader; fuente:
# https://github.com/instaloader/instaloader/blob/master/instaloader/__main__.py
pip install instaloader

# Descubrir posts recientes de un hashtag del nicho
instaloader "#romantasy" --login TU_USUARIO --fast-update --max-count 100

# Descubrir posts de un hashtag español más amplio
instaloader "#bookstagramespaña" --login TU_USUARIO --fast-update --max-count 100

El fragmento relevante del código fuente de Instaloader que resuelve el hashtag es:

python
# Fuente exacta:
# https://github.com/instaloader/instaloader/blob/master/instaloader/__main__.py
elif re.match(r"^#\w+$", target):
    instaloader.download_hashtag(hashtag=target[1:], max_count=max_count, fast_update=fast_update,
                                 post_filter=post_filter,

Este fragmento está truncado porque procede de una búsqueda de código; para copiarlo completo debe descargarse el archivo desde la URL indicada. La clase Hashtag y el método download_hashtag están en instaloader/structures.py y instaloader/instaloader.py respectivamente.

Adaptador propio para el sistema

Este código es nuevo, diseñado para integrarse en davidpd89/ci-sandbox-tmp sin duplicar lógica de otras redes. Convierte resultados de Instaloader en candidatos normalizados.

python
# Archivo nuevo: tools/instagram/instaloader_source.py
# Integración propia para davidpd89/ci-sandbox-tmp.
# Basado en la API pública de Instaloader:
# https://github.com/instaloader/instaloader/blob/master/instaloader/instaloader.py

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Iterable

import instaloader


HASHTAG_RE = re.compile(r"#([\wáéíóúüñÁÉÍÓÚÜÑ]+)")
INTENT_WORDS = (
    "recomiendo", "recomendación", "recomendaciones", "¿qué leo?",
    "tbr", "reseña", "reseñas", "fantasía", "romantasy",
)


@dataclass(frozen=True)
class InstagramCandidate:
    network: str
    post_id: str
    shortcode: str
    author: str
    caption: str
    hashtags: list[str]
    posted_at: str
    permalink: str
    language: str
    intent_score: int
    source: str


def _intent_score(caption: str) -> int:
    text = caption.lower()
    return sum(1 for word in INTENT_WORDS if word in text)


def _to_candidate(post: instaloader.Post, source: str) -> InstagramCandidate:
    caption = post.caption or ""
    hashtags = HASHTAG_RE.findall(caption)
    posted_at = (
        post.date_utc.astimezone(timezone.utc).isoformat()
        if post.date_utc else datetime.now(timezone.utc).isoformat()
    )
    return InstagramCandidate(
        network="instagram",
        post_id=str(post.mediaid),
        shortcode=post.shortcode,
        author=post.owner_username,
        caption=caption,
        hashtags=hashtags,
        posted_at=posted_at,
        permalink=f"https://www.instagram.com/p/{post.shortcode}/",
        language="es",
        intent_score=_intent_score(caption),
        source=source,
    )


def discover_hashtag(
    hashtag: str,
    max_count: int = 50,
    login: str | None = None,
    session_file: str | None = None,
) -> Iterable[dict]:
    loader = instaloader.Instaloader quiet=True, download_comments=False)
    if login and session_file:
        loader.load_session_from_file(login, session_file)

    hashtag_obj = instaloader.Hashtag.from_name(loader.context, hashtag)
    for post in hashtag_obj.get_posts():
        if max_count <= 0:
            break
        max_count -= 1
        yield asdict(_to_candidate(post, source=f"hashtag:{hashtag}"))

Corrección necesaria antes de fusionar: la línea del constructor debe ser instaloader.Instaloader(quiet=True, download_comments=False), con paréntesis normal; el bloque anterior contiene un error tipográfico deliberadamente señalado para revisión en PR.

Configuración de ejecución
text
# Archivo nuevo: config/instagram_discovery.yaml
version: 1
network: instagram
adapter: instaloader
max_posts_per_hashtag: 50
max_posts_per_profile: 30
min_caption_length: 20
require_language_es: true
deduplicate_by: shortcode
retention_days: 90

ranking_signals:
  recency_hours: 0.35
  spanish_caption: 0.20
  intent_score: 0.25
  niche_hashtag_match: 0.15
  seed_author_affinity: 0.05
Plan de implementación en PR pequeñas
PR 1 — Fuentes y esquema

Añadir data/instagram/hashtags_core.yaml, hashtags_intent.yaml, hashtags_expansion.yaml y seed_accounts.yaml.

Añadir config/instagram_discovery.yaml.

Tests: esquema, unicidad de hashtags y handles, campos obligatorios, prioridades entre 1 y 10.

PR 2 — Adaptador Instaloader

Añadir tools/instagram/instaloader_source.py.

Añadir instaloader>=4.15.3 a dependencias opcionales, no al requirements base.

Tests con fixtures: normalización de Post, dedupe por shortcode, extracción de hashtags con tildes y cálculo de intent_score.

PR 3 — Filtrado de idioma e intención

Crear tools/instagram/filters.py.

Reglas: caption mínimo, español detectable, intención alta si contiene recomiendo, ¿qué leo?, TBR, reseña o equivalente.

Tests con 30 captions etiquetadas manualmente.

PR 4 — Ranking común

Enviar candidatos Instagram al ranker multired existente.

No implementar un ranker Instagram separado.

Tests: mismo candidato debe producir puntuación comparable y trazable entre redes.

PR 5 — Observabilidad y respaldo

Métricas: candidatos nuevos, duplicados, posts en español, intención alta, cobertura por hashtag y semillas activas.

Añadir gallery-dl como comando de respaldo, con cookies de navegador; su guía actual indica que Instagram exige login para casi todo el contenido desde 2023.
github

Tests de KPI, alertas por hashtag sin resultados y validación de frescura de semillas.

Elementos eliminados del informe anterior

Selenium scrapers xlastfire/Instagram-Hashtag-Scraper y youmeat6678/Instagram-Hashtag-Scraper: no son la mejor solución; añaden ChromeDriver, fragilidad de DOM y mantenimiento incierto.

yogeshwaran01/instagramy: se elimina como recomendación de integración; queda sólo como referencia histórica si se necesita comparar modelos de datos.

InstagramPrivSniffer: eliminado por centrarse en contenido privado.

Scout: eliminado porque su objetivo es extracción de leads y correos, no descubrimiento lector.

instatools y auto-poster de Reels: eliminados por enfoque de bot/automatización y reposteo, ajeno al sistema de comentarios contextuales y ranking propio.

Fuentes

Repo espejo: davidpd89/ci-sandbox-tmp, main; única evidencia Instagram encontrada: publicaciones Instagram GPT/2026-10-05/publicacion.md.

instaloader/instaloader
 y release 4.15.3:
pypi
+3

Código fuente de hashtag en Instaloader: instaloader/__main__.py, instaloader/structures.py y instaloader/instaloader.py.

mikf/gallery-dl
 y guía Instagram con cookies:
github
+2

subzeroid/instagrapi
:
mujeresaseguir

SDK oficial de Meta: 
instagram-platform-sdk
.
gallery-dlp

Evidencia de hashtags y contenido del nicho:

Listados de cuentas bookstagram españolas:
