# Hashtags, fuentes y comunidades en Mastodon

Fuente: informe de Perplexity (https://www.perplexity.ai/search/6f15bfb0-e9a5-44b1-885d-82986e92b3a4), generado 10/10/2026.

Informe mejorado: descubrimiento lector en Mastodon

Resumen: La vía más robusta para encontrar posts y perfiles de fantasía/romantasy/lectura en español es un descubrimiento multi-instancia basado en la API pública de Mastodon: timelines por hashtag, búsqueda v2, tendencias y directorios externos. He eliminado del informe anterior las herramientas dudosas o poco aplicables —especialmente scrapers con Selenium y repos inactivos— y he priorizado documentación oficial, Mastodon.py, agregadores activos y directorios del Fediverso. El endpoint GET /api/v1/timelines/tag/:hashtag devuelve estados públicos por etiqueta, y GET /api/v2/search devuelve cuentas, estados y hashtags.
docs.joinmastodon
+1

Correcciones al informe anterior
Elemento anterior	Decisión	Motivo
Muneeb1030/WebScrapper_Mastodon	Eliminado	Depende de scraping/Selenium; añade fragilidad en CI Windows y no aporta ventaja frente a la API oficial
alexdrk14/Mastodon_crawler	Eliminado como dependencia	Streaming continuo no encaja en un sistema diario de CI; no es necesario para descubrimiento por hashtags
volfpeter/mastodon-social-graph	Eliminado	Último push en enero de 2023; el grafo social es útil, pero el repo no está activo y no resuelve mejor el descubrimiento por hashtags
mastodoner	Degradado a referencia opcional	Puede ser útil para archivar, pero no lo adoptaría como núcleo sin revisar su mantenimiento y compatibilidad actual
jmrplens/mastodon_official_profiles	Eliminado	Lista de perfiles oficiales, poco alineada con el nicho lector
Mastodon.py	Confirmado como base	Cliente Python documentado, con métodos directos para timelines por hashtag y timelines públicos/locales. 
mastodonpy.readthedocs

awesome-mastodon	Añadido	Lista curada que recopila herramientas de descubrimiento, búsqueda, tendencias y clientes Python. 
github
Hallazgos principales
Recurso	Estado / utilidad	Qué copiar o reutilizar	Integración

Documentación oficial: timelines
	Activa; actualizada en 2026	Patrón de GET /api/v1/timelines/tag/:hashtag y paginación	Núcleo del descubridor de posts

Documentación oficial: search
	Activa	GET /api/v2/search con resultados de accounts, statuses y hashtags	Descubrimiento de perfiles y etiquetas
Mastodon.py	Activa; librería Python madura	timeline_hashtag, search, paginación y normalización de resultados	Cliente único para todas las instancias

awesome-mastodon
	Lista curada y mantenida como recurso de referencia	Enlaces a FediBuzz, Fediverse Explorer, Followgraph, FediSearch y Whom To Follow	Semillas externas y validación de cuentas

Bookstodon.es
	Instancia temática de lectura	Timelines, hashtags locales y perfiles	Fuente prioritaria en español

mast.lat
	Instancia general hispanohablante	Timelines y búsqueda local	Segunda fuente en español

Fedi.Directory
	Directorio humano de cuentas	Categoría de libros, cine y TV	Semillas manuales y validación
FediBuzz	Tendencias por idioma	Hashtags en tendencia filtrables por lengua	Detección semanal de etiquetas emergentes
Fediverse Explorer	Tendencias y posts populares	Hashtags y toots populares	Señal complementaria, no fuente única
Followgraph	Descubrimiento por grafo social	Cuentas seguidas por varias cuentas semilla	Expansión de perfiles afines
FediSearch	Búsqueda de personas en instancias indexadas	Búsqueda por bio y nombre	Detección de autores, lectores y reseñistas
Whom To Follow	Recomendaciones de cuentas menores	Perfiles similares a semillas	Ampliación de la lista de candidatos

awesome-mastodon recoge explícitamente herramientas de descubrimiento como FediBuzz, Fediverse Explorer, Followgraph, FediScope, FediSearch y Whom To Follow, además de Mastodon.py.
github

Hashtags operativos

No conviene usar una lista plana: el sistema debe distinguir núcleo, expansión y descarte. Los hashtags con tilde y sin tilde deben tratarse como variantes distintas en Mastodon, porque el endpoint recibe el nombre exacto de la etiqueta sin #.
docs.joinmastodon

Núcleo estable
json
{
  "hashtags_core": [
    "libros",
    "lectura",
    "leo",
    "bookstodon",
    "bookstagram",
    "amoleer",
    "recomendacionlibros",
    "fantasia",
    "fantasía",
    "fantasiaepica",
    "fantasíaépica",
    "novelafantastica",
    "novelafantástica",
    "romantasy",
    "romance",
    "juvenil",
    "librosjuveniles",
    "autores",
    "escritores",
    "reseñasdelibros"
  ]
}
Expansión temática
json
{
  "hashtags_expansion": [
    "dragones",
    "magia",
    "fae",
    "vampiros",
    "darkacademia",
    "darkromance",
    "enemiestolovers",
    "enemiestolovers",
    "foundfamily",
    "highfantasy",
    "epicfantasy",
    "yabooks",
    "youngadult",
    "booklover",
    "bookworm",
    "reading",
    "books"
  ]
}

Los hashtags en inglés no deben alimentar comentarios directamente: sirven para detectar formatos, tropes y cuentas bilingües. El filtro final debe exigir contenido en español o una biografía claramente hispanohablante.

Cuentas semilla
Cuenta	Rol	Uso en el sistema
@bookstodon.es	Comunidad de lectura	Rastrear perfiles, hashtags y posts locales
@mastodon_es@mastodon.social	Comunidad hispanohablante	Detectar conversaciones y ampliar perfiles en español
@donporque@mastodon.social	Lector/autor de fantasía y romantasy	Semilla temática; explorar etiquetas e interacciones
@Alemanita@mastodon.social	Lectora/escritora de fantasía y terror	Semilla de perfil lector
@helenawagner@mastodon.social	Lectora de fantasía literaria	Semilla de lectores de fantasía traducida
@lanaveinvisible@mastodon.social	Difusión literaria	Semilla editorial/comunidad
@arteesetica@mastodon.social	Industria editorial, romantasy y dark academia	Semilla para tendencias editoriales

Estas cuentas son puntos de partida, no destinos fijos: el sistema debe ampliarlas con menciones, autores de posts relevantes, seguidores públicos y resultados de búsqueda.

Comunidades y directorios

Bookstodon.es es la fuente más directa para el nicho: se presenta como una comunidad para compartir lecturas y participar en discusiones sobre libros.

mast.lat aporta volumen general en español; es útil como segunda instancia, pero requiere filtros de relevancia porque no está especializada en libros.

Fedi.Directory permite encontrar cuentas por categorías, incluida una de libros, cine y televisión; sirve para validar candidatos manualmente.

FediBuzz es especialmente relevante porque indexa tendencias por idioma; conviene consultarlo semanalmente para proponer hashtags nuevos en español.
github

Followgraph y Whom To Follow resuelven la expansión de perfiles a partir de cuentas semilla, algo que la API de hashtags no cubre bien.
github

Código reutilizable
1. Timeline por hashtag

Este es el patrón oficial para leer una timeline pública por hashtag; debe adaptarse a cada instancia.

python
# https://github.com/mastodon/documentation/blob/main/content/en/client/public.md
import requests

response = requests.get("https://mastodon.example/api/v1/timelines/tag/cats?limit=2")
statuses = response.json()
assert statuses[0]["visibility"] == "public"
print(statuses[0]["content"])

Fuente exacta: 
documentación oficial de Mastodon, client/public.md
.
github

2. Cliente Python para hashtags

Mastodon.py ya implementa la llamada necesaria y acepta local, remote, limit y cursores de paginación.

python
# https://mastodonpy.readthedocs.io/en/v2.1.2/07_timelines.html
from mastodon import Mastodon

mastodon = Mastodon(api_base_url="https://bookstodon.es")

statuses = mastodon.timeline_hashtag(
    hashtag="romantasy",
    local=False,
    limit=40
)

Fuente exacta: 
Mastodon.py — Reading data: Timelines
.
mastodonpy.readthedocs

3. Descubridor multi-instancia

Este bloque es código nuevo para nuestro repo, basado en los endpoints oficiales; no copia un proyecto tercero.

python
# Nuevo módulo: tools/mastodon/discover_mastodon.py
import json
import time
from pathlib import Path

import requests

INSTANCES = [
    "https://bookstodon.es",
    "https://mast.lat",
    "https://mastodon.social",
]

HASHTAGS = [
    "romantasy", "fantasia", "fantasía", "fantasiaepica",
    "novelafantastica", "libros", "lectura", "bookstodon",
]

SPANISH_HINTS = (
    "libro", "lectura", "leo", "novela", "autor", "escritor",
    "fantasía", "fantasia", "romantasy", "recomiendo", "reseña"
)


def fetch_hashtag(instance: str, hashtag: str, limit: int = 40):
    url = f"{instance}/api/v1/timelines/tag/{hashtag}"
    response = requests.get(url, params={"limit": limit}, timeout=20)
    response.raise_for_status()
    return response.json()


def normalize_status(instance: str, status: dict, hashtag: str) -> dict | None:
    if status.get("visibility") != "public":
        return None

    account = status.get("account") or {}
    content = status.get("content", "")
    text = content.lower()

    if not any(hint in text for hint in SPANISH_HINTS):
        return None

    return {
        "source_instance": instance,
        "hashtag": hashtag,
        "status_id": status.get("id"),
        "uri": status.get("uri"),
        "created_at": status.get("created_at"),
        "language": status.get("language"),
        "author_acct": account.get("acct"),
        "author_url": account.get("url"),
        "content": content,
        "tags": [tag.get("name") for tag in status.get("tags", [])],
        "replies_count": status.get("replies_count", 0),
        "reblogs_count": status.get("reblogs_count", 0),
        "favourites_count": status.get("favourites_count", 0),
    }


def discover(output_path: str = "output/mastodon_discovery.jsonl"):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    seen = set()

    with open(output_path, "w", encoding="utf-8") as out:
        for instance in INSTANCES:
            for hashtag in HASHTAGS:
                try:
                    statuses = fetch_hashtag(instance, hashtag)
                except requests.RequestException:
                    continue

                for status in statuses:
                    item = normalize_status(instance, status, hashtag)
                    if not item or item["uri"] in seen:
                        continue

                    seen.add(item["uri"])
                    out.write(json.dumps(item, ensure_ascii=False) + "\n")

                time.sleep(0.4)
4. Búsqueda de perfiles y hashtags

La API v2 devuelve objetos Tag en lugar de cadenas simples; esto permite conservar metadatos de cada hashtag encontrado.
docs.joinmastodon

python
# Nuevo módulo: tools/mastodon/search_mastodon.py
import requests

def search_instance(instance: str, query: str, token: str | None = None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = requests.get(
        f"{instance}/api/v2/search",
        params={"q": query, "type": "accounts", "limit": 20},
        headers=headers,
        timeout=20,
    )
    response.raise_for_status()
    return response.json().get("accounts", [])


QUERIES = [
    "romantasy",
    "fantasía épica",
    "lectura fantasía",
    "bookstodon español",
    "autores fantasía",
    "reseñas de libros",
]
Recomendación

No adoptar crawlers genéricos como núcleo. El sistema debe basarse en:

Mastodon.py como cliente.

Timelines por hashtag en bookstodon.es, mast.lat y mastodon.social.

GET /api/v2/search para cuentas y etiquetas.

Tendencias y directorios externos —FediBuzz, Fediverse Explorer, FediSearch, Followgraph— solo como señales complementarias.

Una cola de candidatos revisable antes de cualquier interacción.

La documentación oficial confirma que las timelines públicas, locales y por hashtag pueden ser accesibles sin autenticación si la instancia lo permite; por eso el descubrimiento debe probar varias instancias en lugar de depender de una sola.
mastodonpy.readthedocs

Plan de PR pequeñas
PR 1 — Configuración de descubrimiento

Añadir hashtags_core, hashtags_expansion, seed_accounts e instances a SISTEMA_DIARIO_MASTODON/growth_config.json.

Incluir variantes con y sin tilde.

Test: esquema JSON, unicidad y validación de instancias.

PR 2 — Cliente de lectura

Crear tools/mastodon/discovery_client.py con Mastodon.py.

Métodos: timeline_hashtag, search_accounts, search_hashtags, trending_tags.

Test: mock de respuestas, paginación, errores HTTP y normalización acct@dominio.

PR 3 — Descubrimiento por hashtags

Crear tools/mastodon/discover_by_hashtags.py.

Entrada: hashtags_core + hashtags_expansion.

Salida: output/mastodon_discovery.jsonl.

Test: deduplicación por uri, filtrado por visibilidad pública y relevancia en español.

PR 4 — Expansión de perfiles

Crear tools/mastodon/discover_accounts.py.

Fuentes: autores de posts, menciones, búsqueda v2, Followgraph y FediSearch.

Salida: output/mastodon_account_candidates.jsonl.

Test: sin acciones automáticas; solo candidatos con motivo, fuente y puntuación.

PR 5 — Tendencias semanales

Crear tools/mastodon/discover_trends.py.

Consultar /api/v1/trends/tags por instancia y contrastar con FediBuzz.

Promocionar etiquetas solo si generan posts relevantes en español.

Test: etiquetas candidatas con fecha, instancia, volumen y estado proposed|accepted|rejected.

PR 6 — Ranking

Crear tools/mastodon/rank_discovery.py.

Señales: recencia, coincidencia con fantasía/romantasy, idioma, interacción pública, autor validado y rendimiento histórico del hashtag.

Salida: mastodon_discovery_ranked.jsonl.

Test: ranking reproducible y exclusión de posts ya procesados.

Fuentes

Mastodon — Timelines API
docs.joinmastodon

Mastodon — Tags API
docs.joinmastodon

Mastodon — Search entity
docs.joinmastodon

Mastodon — API index
docs.joinmastodon

Mastodon documentation — public API example
github

Mastodon.py — Timelines
mastodonpy.readthedocs

awesome-mastodon
github

Bookstodon.es — About

mast.lat

Fedi.Directory

Post de Mastodon con hashtags de fantasía y romantasy
