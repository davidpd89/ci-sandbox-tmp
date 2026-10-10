# Hashtags, fuentes y comunidades en Facebook (páginas y grupos)

Fuente: informe de Perplexity (https://www.perplexity.ai/search/326994cb-4be2-4ee5-bf15-7f2ac153401c), generado 10/10/2026.

Informe mejorado: descubrimiento de nicho lector en Facebook
Resumen

Tu sistema ya resuelve correctamente el descubrimiento por hashtags y búsquedas de Facebook mediante facebook_scan.py, facebook_interact.py, facebook_pool.py y facebook_build_plan.py; no conviene duplicarlo ni sustituirlo. La mejora prioritaria es incorporar grupos y páginas como fuentes de primera clase, usando un extractor GraphQL activo y MIT como referencia técnica, sin copiar su capa de autenticación ni sus dependencias de GUI.
facebook
+1

He retirado del informe anterior las recomendaciones poco accionables o de dudosa vigencia: kevinzg/facebook-scraper —obsoleto frente a alternativas más recientes—, apurvmishra99/facebook-scraper-selenium —proyecto antiguo— y la dependencia de Meta Content Library, que no aplica a un pipeline basado en navegador propio.
developers.facebook
+2

Hallazgos verificables
Recurso	Estado a 10/10/2026	Licencia	Qué reutilizar	Integración en tu sistema
mohdtalal3/facebook_post_comment_scraper	Activo: último push 07/10/2026; 44 estrellas; MIT. 
facebook
	MIT	Modelo de datos de grupo, paginación por cursor, filtros por fecha/comentarios e idempotencia por post_id.	Adaptar la extracción y el esquema de candidato; no copiar auth.py, cookies ni GUI PyQt6.
opplieam/FacebookCrawler	Activo: último push 04/10/2026; 36 estrellas; Playwright/Scrapy. 
facebook
	No confirmada en la búsqueda	Arquitectura de crawler sistemático para posts, reacciones y comentarios.	Usar como referencia de estructura; priorizar tu Playwright ya existente.

SSujitX/facebook-pages-scraper
	Activo: último push 29/09/2026; 63 estrellas; MIT; publicado en PyPI.	MIT	Ficha pública de página y último post sin navegador ni API key.	Enriquecer facebook_pages.json; no usarlo para descubrir grupos ni comentar.
wael-sudo2/facebook-page-info-scraper	Activo: último push 29/08/2026; 68 estrellas; MIT. 
facebook
	MIT	Alternativa de enriquecimiento de metadatos de página.	Evaluar como fallback si SSujitX cambia su HTML; no integrar ambos a la vez.
FaustRen/facebook-graphql-scraper	Activo: último push 18/08/2026; 95 estrellas; MIT. 
facebook
	MIT	Recogida de métricas de posts: likes, comentarios y shares.	Útil para enriquecer ranking, no para descubrimiento inicial.
veltzer/pyscrapers	Muy activo: último push 09/10/2026; 34 estrellas; MIT. 
facebook
	MIT	Patrones de scraping multiplataforma y utilidades; no es la mejor pieza específica para grupos.	No integrar directamente; vigilar como referencia de mantenimiento.
hhsm95/FacebookPostsScraper	Archivado: 154 estrellas, pero archived: true; último push 10/09/2026. 
facebook
	MIT	Solo como referencia histórica de cobertura de perfiles, páginas y grupos.	No integrar: descartado por estado archivado.

MasuRii/FBScrapeIdeas
	Último push 25/05/2025; menos reciente que las alternativas anteriores. 
github
	No confirmada	CLI por grupo con Playwright y export local.	No integrar: su flujo depende de sesión/credenciales y Gemini; tomar solo la idea de límite de posts y análisis offline.
Código reutilizable
Extractor de grupos

Este es el bloque más valioso: resuelve grupos, feed de discusión, cursor, filtro temporal, mínimo de comentarios, deduplicación y permalink. Procede de un repositorio activo, MIT y con soporte explícito para páginas, grupos y perfiles.
facebook

python
# https://github.com/mohdtalal3/facebook_post_comment_scraper/blob/main/scraper/group_posts.py
def _story_nodes(item):
    node = item.get("node", {})
    typename = node.get("__typename")
    if typename == "Story":
        return [node]
    if typename == "Group":
        return [e.get("node", {}) for e in node.get("group_feed", {}).get("edges", [])
                if e.get("node", {}).get("__typename") == "Story"]
    return []


def fetch_posts(group_url, limit=10, min_comments=0, download_images=True,
                batch_size=10, on_batch_complete=None, should_stop=None,
                group_name_state=None, start_date=None, end_date=None):
    group_id = extract_group_id_from_url(group_url)
    if not group_id:
        return []

    if group_name_state is None:
        group_name_state = {"name": None}

    headers = _headers(group_id)
    all_posts, batch_posts = [], []
    cursor, page_num = None, 1
    reached_start = False

    while len(all_posts) < limit and not reached_start:
        if should_stop and should_stop():
            break

        cleaned = []
        for attempt in range(3):
            r = graphql_post(_payload(group_id, cursor), headers=headers)
            cleaned = parse_fb_response(r.text)
            if cleaned:
                break
            time.sleep(2)
        if not cleaned:
            break

        posts_found = 0
        next_cursor = None

        for item in cleaned:
            if not isinstance(item, dict):
                continue

            for node in _story_nodes(item):
                if should_stop and should_stop():
                    break
                if is_reel_or_video_post(node):
                    continue

                created = node.get("creation_time")
                if end_date and created and created > end_date:
                    continue
                if start_date and created and created < start_date:
                    reached_start = True
                    break

                comment_count = extract_comment_count(node)
                if min_comments > 0 and comment_count < min_comments:
                    continue

                if not group_name_state["name"]:
                    group_name_state["name"] = extract_group_name(node)

                post_id = node.get("post_id")
                if not post_id:
                    continue

                name_folder = sanitize_name_folder(group_name_state["name"]) or "Unknown"
                if post_exists("group_post", name_folder, post_id):
                    continue

                content_story = (node.get("comet_sections", {})
                                     .get("content", {}).get("story", {}))

                post = {
                    "id": node.get("id"),
                    "post_id": post_id,
                    "created_at": node.get("creation_time"),
                    "text": (content_story.get("message", {}) or {}).get("text", ""),
                    "comment_count": comment_count,
                    "reaction_count": extract_reaction_count(node),
                    "share_count": extract_share_count(node),
                    "group_name": group_name_state["name"],
                    "permalink": node.get("permalink_url") or f"https://www.facebook.com/{post_id}",
                }

                batch_posts.append(post)
                all_posts.append(post)
                posts_found += 1

                if batch_size > 0 and len(batch_posts) >= batch_size and on_batch_complete:
                    on_batch_complete(batch_posts, len(all_posts), limit)
                    batch_posts = []

                if len(all_posts) >= limit:
                    break

            if len(all_posts) >= limit:
                break

            page_info = item.get("page_info")
            if page_info and page_info.get("has_next_page"):
                next_cursor = page_info.get("end_cursor")

        if not next_cursor or len(all_posts) >= limit:
            break

        cursor = next_cursor
        page_num += 1
        time.sleep(2)

    if batch_posts and on_batch_complete:
        on_batch_complete(batch_posts, len(all_posts), limit)

    return all_posts

Qué copiar tal cual: _story_nodes, el contrato de fetch_posts, los campos normalizados del post y la lógica de cursor/idempotencia.
Qué no copiar: DOC_ID, _headers, _payload, graphql_post, config.FB_DTSG y user_id(): dependen de una sesión autenticada y pueden cambiar sin aviso.
facebook

Adaptación a tu pipeline

No copies el cliente GraphQL: tu facebook_scan.py ya tiene navegador, salud, dedupe, filtro político y reserva en facebook_pool. Añade una fase de grupos que produzca exactamente la misma tupla que ya consume tu scan:
facebook

python
# Nuevo archivo sugerido: tools/facebook_group_discovery.py
# Basado en el contrato de salida de:
# https://github.com/mohdtalal3/facebook_post_comment_scraper/blob/main/scraper/group_posts.py

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GROUPS_JSON = ROOT / "00_OPERATIVO" / "facebook_groups.json"


def load_groups():
    if not GROUPS_JSON.exists():
        return []

    with GROUPS_JSON.open(encoding="utf-8") as stream:
        data = json.load(stream)

    groups = data.get("groups", [])
    return [
        {
            "slug": item["slug"],
            "url": item["url"],
            "tema": item.get("tema", "lectura"),
            "prioridad": int(item.get("prioridad", 3)),
            "max_posts": int(item.get("max_posts", 10)),
            "min_comments": int(item.get("min_comments", 0)),
        }
        for item in groups
        if item.get("slug") and item.get("url")
    ]


def normalize_candidate(group, post):
    return {
        "origen": f"group:{group['slug']}",
        "grupo": group["slug"],
        "autor": post.get("autor"),
        "permalink": post.get("permalink"),
        "texto": post.get("texto", ""),
        "creado_en": post.get("created_at"),
        "comentarios": post.get("comment_count", 0),
        "reacciones": post.get("reaction_count", 0),
        "compartidos": post.get("share_count", 0),
        "prioridad": group["prioridad"],
    }

Este adaptador mantiene la separación entre descubrimiento, reserva y plan de acciones que ya usa tu sistema.
facebook

Fuentes de nicho
Grupos prioritarios

Círculo de lectores de Fantasía y Ciencia Ficción
: reseñas y debate de fantasía y ciencia ficción.

Lecturas Fantásticas: Club de lectura de fantasía juvenil
: club específico de fantasía juvenil.

Fantasía Épica y algo más
: comunidad de fantasía épica.
facebook

Romantasy BookClub
: club centrado en romantasy.

Recomienda Libros – Lectores y Escritores
: recomendaciones, debate y autores.

Adictos a la lectura
: comunidad generalista de lectura.

Amigos de la Lectura
: opiniones y comentarios de lecturas.

Páginas y semillas

No incluyas páginas concretas como semillas fijas hasta validar que siguen publicando; en su lugar, usa estas familias de descubrimiento:

Editoriales y librerías de fantasía, especialmente las que ya aparecen en hashtags válidos.

Autores independientes españoles de fantasía, juvenil y romantasy.

Festivales literarios, especialmente Celsius 232 y eventos de fantasía.

Booktubers, bookstagrammers y creadores BookTok en español.

Páginas de reseñas literarias y clubes de lectura con actividad reciente.

Tu propio scan ya validó Dolmen Editorial y Arbol Invertido como señales reales del nicho, lo que confirma que las páginas pueden aportar candidatos útiles.
facebook

Hashtags y búsquedas
Hashtags a añadir

Mantén el pool actual y añade estos términos al JSON central, no a facebook_scan.py:

text
#romantasy
#darkromance
#novelaromantica
#fantasiaromantica
#romantasyespañol
#librosfantasticos
#librosjuveniles
#lectoresespañoles
#recomendacionesliterarias
#lecturasrecomendadas
#booktok
#bookstagram
#autopublicacion
#libreriasindependientes

Tu discovery_terms.py ya está diseñado para fusionar términos externos sin duplicados, por lo que esta es la vía correcta de ampliación.

Búsquedas nuevas
text
romantasy español
novela romantasy reseña
fantasía romántica recomendaciones
club de lectura romantasy
libros parecidos a
lecturas juveniles fantásticas
reseña novela fantástica
autor de fantasía español
editorial fantástica española
booktuber romantasy
bookstagrammer español
lecturas de octubre
reto lectura 2026
tbr fantasía
novedades romantasy
libros de fantasía recomendados

No añadas búsquedas de reciprocidad agresiva como semillas principales: pueden aumentar volumen, pero empeoran la calidad del descubrimiento. Tu SEARCH_POOL ya las tiene segregadas; conviene medirlas por separado antes de ampliarlas.
facebook

JSON operativo

Crea 00_OPERATIVO/facebook_groups.json; discovery_terms.py puede seguir siendo la puerta de hashtags y búsquedas, mientras que este archivo alimenta la nueva fase de grupos.
facebook

json
{
  "groups": [
    {
      "slug": "circulo-lectores-fantasia-ciencia-ficcion",
      "url": "https://www.facebook.com/groups/207124236162026/",
      "tema": "fantasia_ciencia_ficcion",
      "prioridad": 1,
      "max_posts": 10,
      "min_comments": 0
    },
    {
      "slug": "lecturas-fantasticas-juvenil",
      "url": "https://www.facebook.com/groups/lecturasfantasticas/",
      "tema": "fantasia_juvenil",
      "prioridad": 1,
      "max_posts": 10,
      "min_comments": 0
    },
    {
      "slug": "fantasia-epica-y-algo-mas",
      "url": "https://www.facebook.com/groups/215627118464853/",
      "tema": "fantasia_epica",
      "prioridad": 1,
      "max_posts": 10,
      "min_comments": 0
    },
    {
      "slug": "romantasy-bookclub",
      "url": "https://www.facebook.com/groups/599577785909907/",
      "tema": "romantasy",
      "prioridad": 1,
      "max_posts": 10,
      "min_comments": 0
    },
    {
      "slug": "recomienda-libros",
      "url": "https://www.facebook.com/groups/RecomiendaLibros/",
      "tema": "lectura_general",
      "prioridad": 2,
      "max_posts": 8,
      "min_comments": 0
    },
    {
      "slug": "adictos-a-la-lectura",
      "url": "https://www.facebook.com/groups/403666423153977/",
      "tema": "lectura_general",
      "prioridad": 2,
      "max_posts": 8,
      "min_comments": 0
    },
    {
      "slug": "amigos-de-la-lectura",
      "url": "https://www.facebook.com/groups/247845471929442/",
      "tema": "lectura_general",
      "prioridad": 3,
      "max_posts": 8,
      "min_comments": 0
    }
  ]
}
Plan de PR pequeñas

PR 1 — JSON de grupos: añadir 00_OPERATIVO/facebook_groups.json, validación de esquema y tests de carga.

PR 2 — Descubrimiento por grupos: crear tools/facebook_group_discovery.py; extraer autor, permalink, texto, fecha y métricas; registrar origen group:<slug>.

PR 3 — Integración con scan: llamar al descubridor desde facebook_scan.py después de hashtags y antes de búsquedas; reutilizar facebook_pool.record_posts().
facebook

PR 4 — JSON de páginas: añadir 00_OPERATIVO/facebook_pages.json; usar SSujitX/facebook-pages-scraper solo para enriquecer nombre, descripción y último post.

PR 5 — Métricas para ranking: guardar comment_count, reaction_count, share_count, antigüedad e idioma; conectarlos al ranking de acciones.

PR 6 — Observabilidad: añadir KPI por fuente: candidatos nuevos, candidatos comentables, interacciones realizadas, respuestas recibidas y descartes.

Aplicación multired

X, Threads, Bluesky y Mastodon: reutiliza hashtags y búsquedas; sustituye “grupos” por comunidades, listas, feeds o hashtags.

Instagram y TikTok: convierte grupos en perfiles y creadores semilla; páginas en cuentas de editoriales, librerías y booktubers.

Pinterest: usa páginas y grupos como fuentes de tableros, cuentas y palabras clave visuales.

Reddit: mapea grupos a subreddits y posts de grupo a hilos; conserva source_type normalizado.

Ranking global: usa siempre source_type en hashtag, search, group, page, creator y community para comparar rendimiento entre las nueve redes.

Fuentes

Código actual del sistema: davidpd89/ci-sandbox-tmp, especialmente tools/facebook_scan.py y tools/discovery_terms.py.
facebook

Repositorio recomendado para el extractor de grupos: mohdtalal3/facebook_post_comment_scraper, activo y MIT.
facebook

Archivo exacto del extractor: scraper/group_posts.py.
facebook

Repositorio recomendado para enriquecer páginas: 
SSujitX/facebook-pages-scraper
, activo, MIT y disponible en PyPI.

Repositorios adicionales activos: opplieam/FacebookCrawler, FaustRen/facebook-graphql-scraper, wael-sudo2/facebook-page-info-scraper y veltzer/pyscrapers.
facebook

Grupos del nicho: 
Círculo de lectores de Fantasía y Ciencia Ficción
, 
Lecturas Fantásticas
, 
Fantasía Épica y algo más
, 
Romantasy BookClub
, 
Recomienda Libros
, 
Adictos a la lectura
 y 
Amigos de la Lectura
.
facebook
