# Ranking de cuentas y posts en Pinterest

Fuente: informe de Perplexity (https://www.perplexity.ai/search/862749f6-fbb2-48e1-8136-1ed0840b1e21), generado 10/10/2026.

Informe mejorado: señales y repositorios para priorizar perfiles y pines en Pinterest
Resumen

He revisado el informe anterior contra el código real de davidpd89/ci-sandbox-tmp y he eliminado las partes poco verificables o poco aplicables: Apify/Sociavault como dependencia principal, omkarcloud/pinterest-scraper por ser un servicio externo, y afirmaciones no comprobadas sobre endpoints de seguidores de terceros. La recomendación ahora se centra en tres fuentes activas y verificadas — EhsanShahbazii/Pinterest-Scraper, data-scrape/pinterest-scraper y shaikhsajid1111/social-media-profile-scrapers — más la API oficial para métricas de pines propios.
pypi
+1

El sistema ya dispone de pinterest_growth.py, pinterest_scan.py, pinterest_api_audit.py, pinterest_profile_audit.py, reciprocity.py, reciprocity_stats.py, score_hook.py, scan_common.py y relationship_policy.py; por tanto, la mejora correcta es un adaptador de señales + ranking, no un segundo pipeline de Pinterest.

Hallazgos verificados
Repositorio	Estado comprobado	Qué reutilizar	Integración	Descarte / precaución
EhsanShahbazii/Pinterest-Scraper	Python, MIT, 11 estrellas; creado el 3 de septiembre de 2026 y con último push el 8 de octubre de 2026.	CLI de scraping con metadatos de pin: guardados, creador, tablero, deduplicación persistente y exportación JSON/CSV.	Usarlo como proveedor primario de descubrimiento de pines: ejecutarlo o importar su lógica y normalizar su salida JSON/CSV hacia pinterest_scan.py.	Es muy reciente y con pocas estrellas; conviene aislarlo tras una interfaz propia y fijar versión/commit.

data-scrape/pinterest-scraper
	Python, MIT; último push en agosto de 2026; contiene scraper.py, examples/ y requirements.txt.	Extracción de pines, tableros e imágenes sin API; su scraper.py es el archivo más directo para adaptar.	Copiar el patrón de petición/parseo y el esquema de campos; no copiar el scraper completo si ya existe infraestructura propia de navegador.	Verificar en pruebas reales que la búsqueda y los campos siguen estables; el scraping puede romperse con cambios de Pinterest.
shaikhsajid1111/social-media-profile-scrapers	Python, Apache-2.0, 580 estrellas; último push el 15 de septiembre de 2026.	pinterest.py, extractor mínimo de perfil público mediante endpoint JSON.	Usarlo como enriquecedor de perfiles ya descubiertos: bio, contadores públicos y enlaces; conectarlo a pinterest_profile_audit.py.	No sirve para descubrimiento masivo ni para listas completas de seguidores; úsalo solo como señal complementaria.
iamatulsingh/pinscrape	Python, MIT, 153 estrellas; último push el 19 de agosto de 2026.	Descarga y scraping básico de imágenes por búsqueda.	No integrar como núcleo: solo puede servir como referencia de descarga de imágenes si más adelante necesitamos análisis visual.	Su salida está orientada a imágenes, no a señales de reciprocidad; no resuelve el problema principal.
sean1832/pinterest-dl	Python, Apache-2.0, 207 estrellas; último push el 14 de julio de 2026.	Descarga de medios y CLI madura.	No integrar ahora.	Es un descargador, no un extractor de perfiles, seguidores ni señales de conversación.
mirusu400/Pinterest-infinite-crawler	Python, MIT, 95 estrellas; último push el 11 de mayo de 2026.	Crawler de scroll infinito con Selenium.	Referencia para paginación por scroll si el endpoint JSON de data-scrape deja de funcionar.	Selenium y scroll infinito son más frágiles y lentos; mantenerlo como fallback, no como vía principal.
Pinterest API oficial v5 y SDK Python	Documentación activa; la API cubre cuentas, tableros, pines y analíticas.	PinsApi, BoardsApi, UserAccountApi y analíticas de pines propios.	Conectar con growth_attribution.py y reciprocity_stats.py para medir resultados reales de nuestras acciones.	No expone perfiles públicos de terceros ni listas de seguidores ajenos; no sirve para descubrir a quién seguir. 
themineworks
Código reutilizable tal cual
Búsqueda de pines mediante API gestionada

Este bloque es útil como referencia de campos y formato de salida, pero no debe convertirse en dependencia del sistema porque requiere API key y créditos de un proveedor externo. Los campos que muestra — repin_count, title, link — sí son útiles para diseñar nuestro contrato interno.
sociavault

python
# https://www.sociavault.com/blog/scrape-pinterest-data-pins-boards
import requests
import os

API_KEY = os.getenv('SOCIAVAULT_API_KEY')
BASE_URL = 'https://api.sociavault.com'
headers = {'X-API-Key': API_KEY}

def search_pinterest(query):
    response = requests.get(
        f'{BASE_URL}/v1/scrape/pinterest/search',
        params={'query': query},
        headers=headers
    )
    data = response.json()
    pins = data.get('data', [])

    print(f'\nSearch: "{query}" — {len(pins)} results\n')
    for i, pin in enumerate(pins[:10]):
        title = pin.get('title') or pin.get('grid_title') or 'Untitled'
        saves = pin.get('repin_count', 0)
        link = pin.get('link', 'No link')

        print(f"{i+1}. {title}")
        print(f"   Saves: {saves:,} | Link: {link}")

    return pins

search_pinterest('home office setup ideas')
Extracción de perfil con Playwright

Este fragmento es directamente aprovechable como referencia para obtener el contador público de seguidores de un perfil; el repositorio de origen lo presenta como método de scraping de perfiles, tableros y pines.
developers.pinterest

python
# https://thunderbit.com/es/blog/scrape-pinterest-with-python
async def scrape_profile(username):
    url = f"https://www.pinterest.com/{username}/"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent=USER_AGENT,
            viewport={"width": 1920, "height": 1080}
        )
        await page.goto(url)
        await asyncio.sleep(3)

        # Extraer número de seguidores
        follower_el = await page.query_selector(
            "div[data-test-id='follower-count']"
        )
        followers = await follower_el.inner_text() if follower_el else "N/A"

        return {"username": username, "followers": followers, "boards": boards}

No copies este bloque sin completarlo: en el original, boards se rellena más adelante y USER_AGENT debe definirse antes. Para nuestro sistema, la parte valiosa es el selector div[data-test-id='follower-count'] y la estructura del resultado.
developers.pinterest

Código nuevo para el PR

Este código no está copiado: es la pieza de integración recomendada para tools/pinterest_ranking.py. Convierte señales crudas en una puntuación explicable y compatible con el enfoque existente de score_hook.py y reciprocity.py.

python
# Nuevo archivo propuesto: tools/pinterest_ranking.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class PinterestProfileSignal:
    username: str
    followers: int
    following: int
    recent_pins: int
    days_since_last_pin: int
    spanish_score: float
    affinity_score: float
    own_pins_ratio: float


@dataclass(frozen=True)
class PinterestPinSignal:
    pin_id: str
    author: str
    created_at: datetime
    saves: int
    repins: int
    spanish_score: float
    affinity_score: float
    has_question_or_cta: bool


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def score_profile(signal: PinterestProfileSignal) -> float:
    if signal.following <= 0:
        follow_balance = 0.0
    else:
        ratio = signal.followers / signal.following
        follow_balance = _clamp(ratio / 3.0)

    activity = _clamp(1.0 - signal.days_since_last_pin / 45.0)
    recent_volume = _clamp(signal.recent_pins / 15.0)
    language = _clamp(signal.spanish_score)
    affinity = _clamp(signal.affinity_score)
    quality = _clamp(signal.own_pins_ratio)

    score = (
        30 * follow_balance
        + 20 * activity
        + 10 * recent_volume
        + 20 * affinity
        + 15 * language
        + 5 * quality
    )
    return round(score, 2)


def score_pin(signal: PinterestPinSignal) -> float:
    now = datetime.now(timezone.utc)
    age_days = max(0.0, (now - signal.created_at).total_seconds() / 86400)

    freshness = _clamp(1.0 - age_days / 30.0)
    engagement = _clamp((signal.saves + signal.repins) / 200.0)
    language = _clamp(signal.spanish_score)
    affinity = _clamp(signal.affinity_score)
    conversable = 1.0 if signal.has_question_or_cta else 0.4

    score = (
        30 * freshness
        + 20 * engagement
        + 20 * affinity
        + 15 * language
        + 15 * conversable
    )
    return round(score, 2)
Señales finales
Perfil: a quién seguir
Señal	Peso	Cómo medirla	Decisión
Equilibrio seguidores/siguiendo	30	followers / following, normalizado; evita tanto cuentas masivas como perfiles sin audiencia	Prioriza perfiles con señales de reciprocidad real
Actividad reciente	20	Días desde el último pin y número de pines de los últimos 30 días	Descarta cuentas dormidas
Afinidad temática	20	Bio, nombres de tableros, títulos y descripciones frente a fantasía, romantasy, libros, lectura y escritura	Solo interactuar con afinidad alta
Idioma español	15	Detección sobre bio, títulos, descripciones y comentarios	Prioriza español; degrada otros idiomas
Calidad de contenido propio	5	Proporción de pines propios frente a repins	Evita cuentas que solo republican
Volumen reciente	10	Pines recientes, con tope para evitar cuentas de spam	Penaliza publicación masiva
Pin: a qué post responder
Señal	Peso	Cómo medirla	Decisión
Frescura	30	created_at; decae a los 30 días	Prioriza pines de 0–14 días
Engagement observable	20	Guardados y repins, normalizados	Evita pines sin tracción y pines virales masivos
Afinidad	20	Título, descripción, tablero y texto del pin	Solo comentarios contextualmente relevantes
Español	15	Texto del pin, tablero y perfil del autor	Prioriza conversación en español
Apertura a conversación	15	Pregunta, CTA o descripción conversacional	Prioriza pines que inviten a responder

EhsanShahbazii/Pinterest-Scraper anuncia exactamente los metadatos necesarios para esta segunda tabla: guardados, creador, tablero, deduplicación y exportación estructurada. data-scrape/pinterest-scraper complementa esa vía con búsqueda y extracción de pines, tableros e imágenes.

Plan de implementación en PR pequeñas
PR 1 — Contrato de señales

Crear tools/pinterest_signals.py.

Definir PinterestProfileSignal y PinterestPinSignal.

Campos mínimos: username, followers, following, recent_pins, days_since_last_pin, spanish_score, affinity_score, own_pins_ratio, pin_id, created_at, saves, repins.

Tests con fixtures JSON, sin red.

PR 2 — Ranking explicable

Crear tools/pinterest_ranking.py con el código anterior.

Añadir reason_codes: low_activity, not_spanish, low_affinity, old_pin, spam_volume, good_reciprocity_candidate.

Tests de frontera: perfil inactivo, perfil masivo, pin antiguo viral, pin reciente sin engagement y candidato ideal.

PR 3 — Proveedor de descubrimiento

Crear tools/pinterest_discovery_provider.py.

Proveedor primario: salida JSON/CSV de EhsanShahbazii/Pinterest-Scraper.

Proveedor secundario: adaptación de data-scrape/pinterest-scraper/scraper.py.

Reutilizar http_retry.py, circuit_breaker.py, scan_common.py y browser_pool.py; no introducir Selenium salvo como fallback.

PR 4 — Cola de oportunidades

Crear tools/pinterest_opportunities.py.

Salida: 00_OPERATIVO/pinterest/oportunidades/YYYY-MM-DD.jsonl.

Acciones posibles: follow, comment, save, observe.

Registrar cada oportunidad en action_ledger.py antes de ejecutarla.

PR 5 — Aprendizaje con API oficial

Ampliar reciprocity_stats.py con métricas Pinterest: follow-back a 7 y 30 días, respuesta a comentario, guardados y clics salientes.

Consultar analíticas de pines propios mediante la API oficial; Pinterest documenta impresiones, guardados, clics y clics salientes como métricas de pines.

Guardar score_predicho, accion, resultado_real y fecha_resultado para recalibrar pesos.

Aplicación multired

El mismo contrato debe servir para todas las redes:

X, Bluesky, Mastodon, Threads: seguidores/siguiendo, último post, frecuencia, idioma, afinidad y respuestas previas.

Facebook: grupos, páginas, actividad reciente y calidad de comentarios.

Reddit: karma, antigüedad, actividad por subreddit y adecuación al hilo.

TikTok e Instagram: seguidores/siguiendo, frecuencia, idioma, engagement y comentarios.

Pinterest: añade guardados, repins, tableros, frescura del pin y organización temática.

La diferencia de Pinterest es que la conversación directa es menos central que en X, Bluesky o Mastodon; por eso el objetivo operativo debe ser: primero identificar perfiles activos y afines, después comentar pines recientes y concretos, y finalmente medir si eso se traduce en follow-back, guardados o clics a contenido propio.

Fuentes

Repositorio espejo y módulos existentes: davidpd89/ci-sandbox-tmp.

EhsanShahbazii/Pinterest-Scraper, activo con push el 8 de octubre de 2026.

data-scrape/pinterest-scraper
 y su scraper.py.

shaikhsajid1111/social-media-profile-scrapers y 
pinterest.py
.

iamatulsingh/pinscrape, sean1832/pinterest-dl y mirusu400/Pinterest-infinite-crawler.

Documentación oficial de Pinterest API v5, pines y analíticas.

Referencias de scraping con campos y selectores útiles: Sociavault y Thunderbit.
sociavault
+1
