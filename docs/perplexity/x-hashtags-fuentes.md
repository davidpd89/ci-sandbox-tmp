# Hashtags, fuentes y comunidades en X (Twitter)

Fuente: informe de Perplexity (https://www.perplexity.ai/search/1ae5e80f-840e-4c66-b994-974c6483f015), generado 10/10/2026.

Informe mejorado: descubrimiento de lectores en X para fantasía/romantasy en español
Resumen

Tu sistema ya cubre el núcleo del descubrimiento en X: x_scan.py rota búsquedas, procesa notificaciones, lee listas, explora la pestaña Personas, mantiene una reserva de candidatos y registra experimentos en query_trials.csv. Por tanto, la mejora correcta es ampliar y versionar el catálogo de hashtags, consultas, semillas y listas, no crear otro escáner ni duplicar pools hard-coded.

He retirado del informe anterior los elementos no accionables o poco fiables: no incluyo “listas” concretas de X sin URL verificable, ni datasets literarios genéricos que no resuelven descubrimiento social. También corrijo la recomendación principal: twscrape es la opción más adecuada como capa auxiliar de ingesta; twikit es útil como alternativa, pero su última actividad verificada es marzo de 2026, frente al 5 de octubre de 2026 de twscrape.

Estado actual del repo

x_scan.py ya incorpora:

Búsquedas de nicho: #BookTok lang:es libros, #LiteraturaFantastica lang:es, #FantasíaJuvenil lang:es, romantasy lang:es, dragones libro lang:es, "saga de fantasía" lang:es, entre otras.

Consultas conversacionales: recomendaciones, lecturas terminadas, TBR, manuscritos, bloqueo del escritor y clubes de lectura.

Perfiles por bio: booktok español, bookstagram, reseñas libros, lectora fantasía, romantasy, autora indie, worldbuilding, bibliófila.

Rotación diaria, filtrado de idioma, deduplicación, exclusión de cuentas descartadas y medición de consultas experimentales.

Carga externa de términos desde 00_OPERATIVO/descubrimiento_gpt.json mediante discovery_terms.terms("x", "busquedas", " lang:es").

Hallazgos
Tipo	Elemento recomendado	Integración	Estado en el repo	Fuente
Hashtags nucleares	#BookTok, #Bookstagram, #Lectura, #RecomendaciónLiteraria, #Fantasía, #FantasíaJuvenil, #LiteraturaFantástica, #Romantasy, #Escritura, #AutoresIndie	Catálogo hashtags_core	Parcialmente cubiertos	X admite combinación con lang:es, exclusiones y filtros.
Hashtags de intención	#TBR, #QuéLeo, #Leyendo, #Relectura, #RetoDeLectura, #ClubDeLectura, #Reseña, #ReseñaSinSpoilers, #KindleUnlimited	Catálogo hashtags_intent	Parcialmente cubiertos	Útiles para localizar actividad lectora reciente.
Consultas de recomendación	("recomendadme" OR "me recomendáis") (libro OR novela OR fantasía) lang:es -filter:replies	CONVERSATION_SEARCHES	Ya existe una variante	Los operadores oficiales permiten OR, frases, exclusiones e idioma.
Consultas de lectura activa	("acabo de terminar" OR "terminé de leer") (libro OR saga) lang:es -filter:replies; ("estoy leyendo" OR "leyendo ahora") (fantasía OR romantasy) lang:es -filter:replies	CONVERSATION_SEARCHES	Ya existen variantes	Priorizan posts con intención conversacional.
Consultas de autor indie	("escribiendo mi novela" OR "escribiendo mi libro") lang:es -filter:replies; ("primer borrador" OR "mi manuscrito") lang:es -filter:replies; ("bloqueo del escritor" OR "atascada con mi novela") lang:es -filter:replies	CONVERSATION_SEARCHES	Ya existen variantes	La búsqueda avanzada soporta frases exactas, exclusiones y filtros.
Consultas de subgénero	"romantasy" lang:es, "fantasía épica" lang:es, "fantasía oscura" lang:es, "romance de fantasía" lang:es, "novela juvenil" lang:es, worldbuilding lang:es, dragones libro lang:es	SEARCH_POOL	La mayoría ya existen	El romantasy es una categoría editorial reconocida en España.
Cuenta semilla verificada	@Romantasy_Reads	seed_accounts.json, prioridad media	Nueva	Cuenta pública especializada en romantasy.
Cuenta semilla verificada	@la_alfano	seed_accounts.json, prioridad baja	Nueva	Bio orientada a fantasía, YA fantasy y royal romance. 
x

Cuenta semilla verificada	@fantasy_books	seed_accounts.json, prioridad baja	Nueva	Cuenta pública centrada en fantasía. 
help.x

Cuenta institucional	@Kobo_ES	Observación de tendencias, no interacción prioritaria	Nueva	Cuenta oficial en español con recomendaciones editoriales. 
x

Cuenta editorial	@ReservoirBooks	Semilla de editoriales y novedades	Nueva	Sello de Penguin Random House Grupo Editorial. 
docs.x

Superficie de listas	list:usuario/lista término lang:es	Añadir solo listas con URL validada	El código ya lee listas diarias	El operador list: existe, aunque X devuelve resultados inconsistentes. 
x

Repositorio principal	vladkens/twscrape	Ingesta estructurada opcional y auditoría	Nuevo	MIT, Python, 2.851 estrellas, último push 5 de octubre de 2026.
Repositorio alternativo	d60/twikit	Alternativa si twscrape falla; no base principal	Nuevo	MIT, Python, 4.718 estrellas, último push 10 de marzo de 2026.
Repositorio alternativo	Altimis/Scweet	Respaldo para búsqueda, perfiles, seguidores y following	Nuevo	MIT, Python, 1.640 estrellas, último push 29 de septiembre de 2026.
Repositorio de referencia	fa0311/TwitterInternalAPIDocument	Documentación de endpoints internos; no copiar código sin licencia clara	Solo consulta	721 estrellas, último push 24 de septiembre de 2026; licencia NOASSERTION.
Repositorio descartado	mahrtayyab/tweety	No como dependencia principal	Descartado	Activo, pero menor cobertura y sin ventaja frente a twscrape; 669 estrellas.
Repositorio descartado	shaikhsajid1111/twitter-scraper-selenium	No como dependencia principal	Descartado	Solapado con el navegador propio del sistema; 346 estrellas.
Código reutilizable
1. Búsqueda con twscrape

Recomendado como capa auxiliar de ingesta y auditoría. Requiere Python 3.10+ y cuentas autorizadas en su pool; la librería gestiona rotación y límites.
docs.x

python
# Fuente: https://github.com/vladkens/twscrape/blob/main/README.md
# Licencia: MIT — https://github.com/vladkens/twscrape/blob/main/LICENSE
import asyncio
from twscrape import AccountsPool, API

async def buscar_nicho():
    pool = AccountsPool()
    await pool.add_account(
        "usuario_x", "password", "email@example.com", "email_password"
    )
    await pool.login_all()

    api = API(pool)

    query = '("recomendadme" OR "me recomendáis") (libro OR novela OR fantasía) lang:es -filter:replies'

    async for tweet in api.search(query, limit=50):
        yield {
            "id": tweet.id,
            "url": f"https://x.com/{tweet.user.username}/status/{tweet.id}",
            "handle": tweet.user.username,
            "texto": tweet.rawContent,
            "fecha": tweet.date.isoformat(),
            "idioma": tweet.lang,
        }

asyncio.run(buscar_nicho())

Archivo y documentación de referencia: https://github.com/vladkens/twscrape/blob/main/README.md.
docs.x

2. Búsqueda con twikit

Útil como fallback o para validar resultados con una implementación distinta. Su ejemplo oficial usa search_tweet(query, "Latest") y devuelve autor, texto y fecha.
x
+1

python
# Fuente: https://github.com/d60/twikit/blob/main/README.md
# Licencia: MIT — https://github.com/d60/twikit/blob/main/LICENSE
import asyncio
from twikit import Client

async def buscar_nicho():
    client = Client("es")

    await client.login(
        auth_info_1="usuario_x",
        auth_info_2="email@example.com",
        password="password",
        cookies_file="cookies.json",
    )

    query = '("acabo de terminar" OR "terminé de leer") (libro OR saga) lang:es -filter:replies'
    tweets = await client.search_tweet(query, "Latest")

    for tweet in tweets:
        yield {
            "id": tweet.id,
            "url": f"https://x.com/{tweet.user.screen_name}/status/{tweet.id}",
            "handle": tweet.user.screen_name,
            "texto": tweet.text,
            "fecha": tweet.created_at,
        }

asyncio.run(buscar_nicho())

Archivo y ejemplo oficial: https://github.com/d60/twikit/blob/main/README.md.
x

3. Adaptador de catálogo para discovery_terms.py

Este código es nuevo y encaja con el patrón actual: no sustituye discovery_terms.py, sino que añade un catálogo específico de X sin tocar los pools internos.

python
# Archivo propuesto: tools/x_discovery_catalog.py
# Licencia: MIT — proyecto interno davidpd89/ci-sandbox-tmp
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "00_OPERATIVO" / "x" / "discovery_x_v2.json"


def load_catalog() -> dict:
    if not CATALOG.exists():
        return {"hashtags_core": [], "hashtags_intent": [], "search_queries": []}

    with CATALOG.open(encoding="utf-8") as stream:
        data = json.load(stream)

    required = {"id", "texto", "tipo", "estado"}
    for section, items in data.items():
        for item in items:
            missing = required - item.keys()
            if missing:
                raise ValueError(f"Entrada incompleta en {section}: {missing}")

    return data


def active_terms(kind: str, suffix: str = "") -> list[str]:
    data = load_catalog().get(kind, [])
    seen: set[str] = set()
    output: list[str] = []

    for item in data:
        if item.get("estado") != "activo":
            continue

        text = str(item["texto"]).strip()
        if kind.startswith("hashtags"):
            text = text.lstrip("#")

        key = text.casefold()
        if not text or key in seen:
            continue

        seen.add(key)
        output.append(text + suffix)

    return output
4. Esquema propuesto del catálogo
json
// Archivo propuesto: 00_OPERATIVO/x/discovery_x_v2.json
// Licencia: MIT — proyecto interno davidpd89/ci-sandbox-tmp
{
  "hashtags_core": [
    {
      "id": "x_hashtag_romantasy",
      "texto": "#Romantasy",
      "tipo": "hashtag",
      "subnicho": "romantasy",
      "idioma": "es",
      "origen_url": "https://help.x.com/en/using-x/x-search",
      "fecha_alta": "2026-10-10",
      "estado": "trial",
      "notas": "Núcleo del subgénero; medir antes de promocionar."
    }
  ],
  "hashtags_intent": [
    {
      "id": "x_hashtag_tbr",
      "texto": "#TBR",
      "tipo": "hashtag",
      "subnicho": "lectura_general",
      "idioma": "es",
      "origen_url": "https://help.x.com/en/using-x/x-search",
      "fecha_alta": "2026-10-10",
      "estado": "trial",
      "notas": "Alta intención lectora; puede traer ruido internacional."
    }
  ],
  "search_queries": [
    {
      "id": "x_query_recomendacion_fantasia",
      "texto": "(\"recomendadme\" OR \"me recomendáis\") (libro OR novela OR fantasía) lang:es -filter:replies",
      "tipo": "conversacion",
      "subnicho": "lectura_general",
      "idioma": "es",
      "origen_url": "https://docs.x.com/x-api/posts/search/integrate/operators",
      "fecha_alta": "2026-10-10",
      "estado": "trial",
      "notas": "Detecta peticiones explícitas de recomendación."
    }
  ]
}
Comparativa de repositorios
Repositorio	Licencia	Actividad	Cobertura	Recomendación

vladkens/twscrape
	MIT	Último push: 5 de octubre de 2026	Búsqueda, GraphQL, perfiles, seguidores, favoritos, retweets, pool de cuentas y límites	Sí, opción principal para ingesta auxiliar.

d60/twikit
	MIT	Último push: 10 de marzo de 2026	Búsqueda, tendencias, publicación, login con cookies	Sí, fallback; no como base primaria por menor actividad reciente.
Altimis/Scweet	MIT	Último push: 29 de septiembre de 2026	Tweets, perfiles, seguidores, following, proxies y pool	Opcional, para respaldo de datos de perfil.
ythx-101/x-tweet-fetcher	MIT	Último push: 6 de septiembre de 2026	Tweets, respuestas, timelines y artículos sin API	No prioritario; útil como referencia, pero menos maduro.
fa0311/TwitterInternalAPIDocument	Sin licencia clara (NOASSERTION)	Último push: 24 de septiembre de 2026	Documentación de API interna	Solo consulta; no reutilizar código.
mahrtayyab/tweety	No verificada en este resultado	Último push: 13 de septiembre de 2026	Scraper general	No prioritario.
shaikhsajid1111/twitter-scraper-selenium	MIT	Último push: 17 de agosto de 2026	Selenium, hashtags y perfiles	No: duplica la capa de navegador que ya tienes.
Recomendación

No añadir más consultas directamente en x_scan.py. El catálogo debe vivir en JSON versionado y entrar por discovery_terms.py o un cargador equivalente.

Adoptar twscrape como capa de respaldo y auditoría, no como sustituto del navegador. Es MIT, está activa y su modelo de pool encaja con la arquitectura multi-cuenta del sistema.
docs.x

Mantener twikit como fallback documentado, pero no integrarlo en producción de inmediato: su último push es marzo de 2026 y twscrape está más reciente.

No usar TwitterInternalAPIDocument como dependencia: carece de licencia clara y solo sirve como referencia técnica.

Descartar Selenium adicional: el repo ya tiene browser_common.py, browser_lean.py, browser_pool.py y x_scan.py; añadir otro scraper Selenium generaría duplicación operativa.

Plan de implementación en PR pequeñas
PR 1 — Catálogo X v2

Crear 00_OPERATIVO/x/discovery_x_v2.json.

Añadir 40 hashtags y 35 consultas, todos como trial.

No modificar x_scan.py.

PR 2 — Cargador x_discovery_catalog.py

Añadir el módulo de carga y validación.

Exponer active_terms("hashtags_core", " lang:es") y active_terms("search_queries").

Test: IDs únicos, esquema obligatorio, deduplicación case-insensitive y ausencia de términos vacíos.

PR 3 — Fusión segura con discovery_terms.py

Ampliar discovery_terms.terms("x", ...) para fusionar el catálogo X v2 con descubrimiento_gpt.json.

Prioridad: términos ya activos, luego trials rotatorios.

Test: no duplicar términos existentes ni romper llamadas actuales.

PR 4 — Semillas y listas validadas

Crear 00_OPERATIVO/x/seed_accounts.json y seed_lists.json.

Incluir @Romantasy_Reads, @la_alfano, @fantasy_books, @ReservoirBooks y @Kobo_ES como semillas de observación, con origen_url y motivo.

No añadir listas sin URL exacta y verificación manual.

PR 5 — Adaptador twscrape

Crear tools/x_twscrape_ingest.py como fuente auxiliar.

Normalizar salida al contrato actual: URL canónica, handle, texto, idioma y fecha.

Enviar resultados solo a x_pool.py o a una cola de revisión; no ejecutar acciones automáticas desde esta capa.

PR 6 — Evaluación de términos

Registrar cada término nuevo en query_trials.csv durante 10–14 días.

Métricas mínimas: descubiertos, elegibles, nuevos, respuestas, respuesta_recibida, follow_reciproco, tasa_nicho.

Promocionar solo términos por encima de la mediana del pool y sin degradar idioma o calidad de nicho.

Aplicación a todas las redes
Capa	X	Adaptación multired
Hashtags	#Romantasy, #BookTok, #TBR	Threads/Instagram: etiquetas; TikTok: hashtags de descubrimiento; Pinterest: keywords; Bluesky/Mastodon: etiquetas y feeds
Intención	“recomendadme”, “terminé de leer”	Reddit: posts de petición; Facebook: grupos y comentarios; TikTok: comentarios y sonidos
Semillas	Cuentas, listas y respuestas	Perfiles, páginas, tableros, subreddits, packs, feeds e instancias
Ranking	query_trials.csv	Misma tabla con network, source_id, query_id y cohortes
Ingesta auxiliar	twscrape	Adaptador propio por red; mantener contrato común de candidatos
Fuentes

Código actual: davidpd89/ci-sandbox-tmp, rama research/perplexity-crecimiento-x; tools/x_scan.py y tools/discovery_terms.py.

twscrape: 
https://github.com/vladkens/twscrape
 — MIT, 2.851 estrellas, último push 5 de octubre de 2026.

Documentación y ejemplo de twscrape: 
https://pypi.org/project/twscrape/0.4.1/
 — MIT, Python 3.10/3.11.
docs.x

twikit: 
https://github.com/d60/twikit
 — MIT, 4.718 estrellas, último push 10 de marzo de 2026.

Ejemplo oficial de twikit: https://github.com/d60/twikit/blob/main/README.md.
x

Scweet: https://github.com/Altimis/Scweet — MIT, 1.640 estrellas, último push 29 de septiembre de 2026.

x-tweet-fetcher: https://github.com/ythx-101/x-tweet-fetcher — MIT, 984 estrellas, último push 6 de septiembre de 2026.

TwitterInternalAPIDocument: https://github.com/fa0311/TwitterInternalAPIDocument — sin licencia clara; solo referencia.

Operadores oficiales de X: 
https://docs.x.com/x-api/posts/search/integrate/operators
.

Búsqueda avanzada de X: 
https://help.x.com/en/using-x/x-advanced-search
.

Guía de listas y operador list:: 
https://thunderbit.com/blog/effectively-search-twitter-lists-guide
.
x

Cuenta semilla romantasy: 
https://x.com/Romantasy_Reads
.

Contexto editorial del romantasy: 
https://www.planetadelibros.com/blog/listas-y-tops-literarios/articulo-que-es-romance-fantasy
.
