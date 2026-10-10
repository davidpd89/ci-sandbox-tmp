# Hashtags, fuentes y comunidades en Threads

Fuente: informe de Perplexity (https://www.perplexity.ai/search/bcb5e7da-6a5f-4ba5-a5fe-da0d97b2c9d8), generado 10/10/2026.

Informe mejorado: descubrimiento de nicho lector en Threads
Resumen

La vía más sólida para encontrar posts y perfiles de fantasía, romantasy y lectura en español en Threads es un catálogo de keywords y topic tags alimentado por la API oficial keyword_search; los scrapers públicos solo deben usarse como proveedor de respaldo o enriquecimiento, nunca como fuente única. La API oficial expone GET /keyword_search, requiere el permiso threads_keyword_search y está sujeta a límites estrictos de consulta.
developers.facebook
+2

He retirado del informe anterior los repos y herramientas que no aportan código directamente reutilizable o que dependen de servicios de pago: themineworks/threads-keyword-scraper, data-scrape/threads-scraper, ThreadsPipe-py, Apify, Captapi, Hootsuite y SociaVault. También retiro omkarcloud/threads-scraper como recomendación principal: no aparece entre los resultados actuales de repos Python activos con suficiente evidencia de mantenimiento, mientras que Zeeshanahmad4/Threads-Scraper sí está activo, tiene 137 estrellas y su último push es del 21 de agosto de 2026.

Hallazgos
Recurso	Estado verificado	Qué copiar	Aplicación al sistema	Riesgos

Meta — Keyword and Topic Tag Search
	Documentación oficial vigente. 
developers.facebook
	Contrato de GET /keyword_search y modelo de respuesta.	Adaptador primario de descubrimiento por keyword.	Permiso threads_keyword_search y cuota; no sirve para barrido masivo. 
blotato
+1


Zeeshanahmad4/Threads-Scraper
	Python, 137 estrellas, último push 2026-08-21, no archivado.	src/scraper/parser.py, src/scraper/exporter.py, config/settings.yaml.	Normalización de posts, exportación CSV/JSON y configuración de perfiles objetivo.	Licencia marcada como Other/NOASSERTION; copiar patrones, no el código completo, salvo revisión de licencia.

galihkjaya/threadscraper
	Publicado en 2026; 2 estrellas, 7 commits, CLI por keywords, CSV y reanudación. 
github
	Formato de keywords.txt, columnas CSV, checkpoint y limpieza de texto.	Fuente de respaldo para comentarios y respuestas; útil para detectar perfiles comentadores.	Mantenimiento y adopción muy bajos; usa navegador headless y tokens de sesión. 
github

vdite/threads-scraper	Python + Playwright, MIT, creado y actualizado en febrero de 2026.	Arquitectura de extracción de respuestas anidadas con Playwright.	Solo como referencia de arquitectura; no integración inmediata.	7 estrellas y un único push; riesgo alto de abandono.

marclove/pythreads
	Wrapper Python de la API oficial de Threads, MIT. 
github
	Patrón de cliente OAuth y manejo de endpoints oficiales.	Base conceptual para el adaptador oficial; revisar actividad antes de depender de él.	Enfocado en API oficial, no en descubrimiento masivo. 
github


iSarabjitDhiman/MetaThreads
	Librería Python para datos y acciones de Threads. 
github
	Referencia de operaciones de perfil, hilos y respuestas.	No prioritario para descubrimiento; posible referencia futura.	No verificado como activo ni con licencia clara en esta pasada. 
github
Catálogo operativo de Threads

Threads trata las etiquetas como topic tags; una publicación admite una etiqueta, que puede ser una frase con espacios. Por ello, el sistema debe separar claramente topic_tag —para publicar— de keyword_query —para descubrir—.

Topic tags para publicar
text
# Propuesta: config/discovery/threads.yaml
topic_tags:
  - "Lectura"
  - "Libros"
  - "Bookstagram"
  - "BookTok en español"
  - "Fantasía"
  - "Fantasía juvenil"
  - "Romantasy"
  - "Romance fantástico"
  - "Novela romántica"
  - "Libros de fantasía"
  - "Jóvenes adultos"
  - "Autores independientes"
  - "Escritores en español"
  - "Reseña de libro"
  - "Club de lectura"

Las etiquetas de lectura en español con mayor respaldo en guías públicas son #Lectura, #Libros, #Bookstagram, #BookTokEspañol, #ReseñaDeLibro y #ClubDeLectura; las de fantasía y romance cubren el subnicho de autor.

Keywords de descubrimiento
text
# Propuesta: config/discovery/threads.yaml
keyword_queries:
  priority:
    - "romantasy recomendación"
    - "fantasía juvenil libros"
    - "libros de fantasía en español"
    - "romance fantástico recomendación"
    - "lectores de fantasía"
    - "booktok español"
    - "bookstagram español"
    - "reseña fantasía"
    - "autor independiente fantasía"
    - "novela romantasy"
  secondary:
    - "lectura fantasía"
    - "libros parecidos a"
    - "TBR fantasía"
    - "club de lectura fantasía"
    - "escritora fantasía"
    - "escritor independiente libros"
    - "libros de romance juvenil"
    - "recomiéndame un libro de fantasía"
Cuentas semilla

No incorporar cuentas sin validación: los directorios de influencers mezclan Instagram, X y otros perfiles, y no garantizan una cuenta activa equivalente en Threads. Usar esta lista como cola de verificación, no como semillas confirmadas:

text
# Propuesta: config/discovery/threads_seed_profiles.yaml
seed_profiles:
  - handle: "urbanbookly"
    reason: "Referencia editorial de romantasy en español"
    source: "https://urbanbookly.com/autores-romantasy/"
    status: "pending_validation"
  - handle: "TBD_desde_keyword_search"
    reason: "Candidatos detectados por 'romantasy recomendación' o 'fantasía juvenil libros'"
    status: "pending_validation"

@urbanbookly es una referencia actual del romantasy en castellano: su guía de 2026 destaca autoras y sagas del género. El resto debe provenir de la ejecución real de las queries, con filtros de idioma, actividad reciente y afinidad temática.

Código reutilizable
1. Catálogo de descubrimiento
python
# Origen: diseño propio para davidpd89/ci-sandbox-tmp
# Archivo propuesto: tools/discovery/threads_catalog.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ThreadsDiscoverySource:
    kind: str
    value: str
    priority: int = 2
    language: str = "es"

    @property
    def key(self) -> str:
        return f"threads:{self.kind}:{self.value.lower()}"


def load_threads_catalog(path: str | Path) -> list[ThreadsDiscoverySource]:
    data: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    sources: list[ThreadsDiscoverySource] = []

    for value in data.get("topic_tags", []):
        sources.append(ThreadsDiscoverySource("topic_tag", value, priority=1))

    for group, priority in (("priority", 1), ("secondary", 2)):
        for value in data.get("keyword_queries", {}).get(group, []):
            sources.append(ThreadsDiscoverySource("keyword", value, priority=priority))

    if len({source.key for source in sources}) != len(sources):
        raise ValueError("Hay fuentes duplicadas en el catálogo de Threads")

    return sources
2. Cliente oficial de keyword search
python
# Origen: contrato oficial documentado en
# https://developers.facebook.com/documentation/threads/keyword-search
# Archivo propuesto: tools/discovery/threads_keyword_search.py
from __future__ import annotations

import os
from typing import Any

import requests

GRAPH_URL = "https://graph.threads.net/v1.0/keyword_search"


class ThreadsKeywordSearchClient:
    def __init__(self, access_token: str | None = None, timeout: int = 20) -> None:
        self.access_token = access_token or os.environ["THREADS_ACCESS_TOKEN"]
        self.timeout = timeout

    def search(self, query: str, limit: int = 25) -> list[dict[str, Any]]:
        if not query.strip():
            raise ValueError("La keyword no puede estar vacía")

        response = requests.get(
            GRAPH_URL,
            params={"q": query, "limit": limit, "access_token": self.access_token},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("data", [])

Meta documenta que la búsqueda se realiza mediante GET /keyword_search con una keyword; el permiso específico threads_keyword_search es necesario para buscar contenido público de terceros.
developers.facebook
+1

3. Normalización de candidatos
python
# Origen: patrón de normalización inspirado en
# https://github.com/Zeeshanahmad4/Threads-Scraper/blob/main/src/scraper/parser.py
# Archivo propuesto: tools/discovery/threads_normalize.py
from __future__ import annotations

import hashlib
import re
from typing import Any


def normalize_threads_post(raw: dict[str, Any], source: str, query: str) -> dict[str, Any]:
    post_id = str(raw.get("id") or raw.get("pk") or "")
    if not post_id:
        raise ValueError("El post de Threads no tiene identificador")

    text = re.sub(r"\s+", " ", str(raw.get("text") or raw.get("caption") or "")).strip()
    username = (
        raw.get("username")
        or raw.get("user", {}).get("username")
        or raw.get("author", {}).get("username")
        or ""
    )

    return {
        "network": "threads",
        "post_id": post_id,
        "dedupe_key": hashlib.sha1(f"threads:{post_id}".encode()).hexdigest(),
        "username": username,
        "text": text,
        "permalink": raw.get("permalink") or raw.get("url") or "",
        "published_at": raw.get("timestamp") or raw.get("taken_at") or "",
        "likes": int(raw.get("like_count") or 0),
        "replies": int(raw.get("reply_count") or 0),
        "reposts": int(raw.get("repost_count") or 0),
        "quotes": int(raw.get("quote_count") or 0),
        "source": source,
        "query": query,
    }

El scraper activo de Zeeshanahmad4 normaliza los elementos crudos de Threads en campos como id y username, y exporta los resultados a JSON o CSV; ese patrón es directamente adaptable a nuestro modelo interno.

4. Archivo de keywords compatible con el scraper de respaldo
text
# Origen: formato documentado en
# https://github.com/galihkjaya/threadscraper
# Archivo propuesto: config/discovery/threads_keywords.txt
# Prioridad 1
romantasy recomendación
fantasía juvenil libros
libros de fantasía en español
romance fantástico recomendación
lectores de fantasía
booktok español
bookstagram español
reseña fantasía
autor independiente fantasía
novela romantasy

# Prioridad 2
lectura fantasía
libros parecidos a
TBR fantasía
club de lectura fantasía
escritora fantasía
escritor independiente libros

threadscraper acepta un archivo con una keyword por línea, ignora líneas que empiezan por # y guarda la keyword que originó cada comentario en la columna keyword; eso permite atribuir cada candidato a su fuente de descubrimiento.
github

Qué no integrar

themineworks/threads-keyword-scraper: depende de Apify y de pago por resultado; no es una pieza pública autónoma útil para nuestro repo.

data-scrape/threads-scraper: no superó la verificación de actividad y adopción en esta pasada; dejarlo fuera hasta nueva comprobación.

ThreadsPipe-py: está orientado a publicación y gestión de hashtags, no a descubrimiento; no aporta al objetivo actual.

Apify, Captapi, Hootsuite y SociaVault: son servicios externos o de pago, no repos públicos reutilizables.
urbanbookly
+3

omkarcloud/threads-scraper: retirado como recomendación principal por falta de evidencia suficiente de mantenimiento y adopción frente a alternativas verificadas.

Plan de implementación en PR pequeñas

PR 1 — Catálogo y esquema: crear config/discovery/threads.yaml, threads_keywords.txt y tools/discovery/threads_catalog.py; tests de duplicados, normalización Unicode y prioridades.

PR 2 — Adaptador oficial: añadir ThreadsKeywordSearchClient, control de cuota, paginación, reintentos y deduplicación por post_id.

PR 3 — Normalización e ingesta: implementar normalize_threads_post, guardar fuente, query, score provisional y evidencia nativa.

PR 4 — Respaldo local: integrar threadscraper solo como job manual o programado de baja frecuencia, con checkpoint, límites y exportación a CSV.

PR 5 — Validación de perfiles: crear cola threads_seed_profiles con validación de bio en español, actividad reciente, temática y exclusión de cuentas irrelevantes.

PR 6 — Ranking multired: alimentar el ranking existente con source, query, topic_tag, antigüedad, engagement y resultado de interacción; replicar el patrón en X, Bluesky, Mastodon, Instagram, TikTok, Pinterest, Facebook y Reddit.

Fuentes

Meta — Keyword and Topic Tag Search
developers.facebook

Blotato — Threads API pricing, permisos y límites
blotato

SocialCrawl — Threads API en 2026
socialcrawl

Zeeshanahmad4/Threads-Scraper

galihkjaya/threadscraper
github

vdite/threads-scraper

marclove/pythreads
github

iSarabjitDhiman/MetaThreads
github

Urbanbookly — Autoras de Romantasy 2026

Feedspot — Top 60 Spanish Book Influencers

Task Ant — Topic tags en Threads

Meta — Uso de Threads: búsqueda y etiquetas
