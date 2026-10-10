# Herramientas y código abierto en Reddit

Fuente: informe de Perplexity (https://www.perplexity.ai/search/b143e6df-d98d-4bb6-85e5-be09fb8e01c8), generado 10/10/2026.

Informe mejorado: Reddit open source para el sistema de crecimiento
Resumen

He revisado el informe anterior contra el código real de davidpd89/ci-sandbox-tmp y he eliminado o degradado las propuestas que no aportan suficiente valor operativo. La conclusión revisada es más estricta: PRAW es la única dependencia crítica recomendada; URS es la mejor referencia para archivo y descubrimiento; ChocoData/reddit-scraper aporta un monitor de menciones moderno y directamente aprovechable; los proyectos MCP son útiles solo como patrón, no como dependencia inmediata.

El repo ya tiene una base Reddit sólida: reddit_scan.py, reddit_comments.py, reddit_interact.py, reddit_publish.py, reddit_execute.py, reddit_survey.py, reply_queue.py, action_ledger.py, growth_attribution.py, score_hook.py y round_queue.py. Por eso no propongo un “Reddit growth framework” paralelo: propongo piezas pequeñas que refuercen descubrimiento, archivo, scoring y trazabilidad.

Nota de verificación: el conector GitHub confirmó la existencia, rama y SHA de los archivos citados, pero en esta sesión no devolvió el texto legible de los ficheros. Por rigor, no pego código presentándolo como copia literal de terceros; incluyo adaptaciones mínimas nuevas, con la URL exacta del archivo de origen como referencia de la pieza que se quiere replicar.

Hallazgos verificados
Repositorio	Estado	Qué resolver	Qué aprovechar	Encaje en ci-sandbox-tmp

praw-dev/praw
	Activo; v8.0.3 publicada el 12-08-2026. 
github
	Acceso oficial, OAuth, lectura, comentarios y streams.	Cliente común, excepciones, reintentos y modelos de Reddit. 
github
	Crítico. Debe ser la capa única bajo reddit_scan.py, reddit_comments.py e reddit_interact.py.

praw-dev/asyncpraw
	Activo; v8.0.3 publicada el 12-08-2026. 
freshports
	Ingesta concurrente y streams asíncronos.	Patrón de worker asíncrono y control de concurrencia. 
freshports
	Opcional. Solo para un recolector separado; no migrar el sistema completo.

JosephLai241/URS
	Activo en rama master; estructura verificada: urs/praw_scrapers/static_scrapers/Subreddit.py, Comments.py, Redditor.py.	Archivo de subreddits, autores, hilos y comentarios.	Scrapers separados por entidad, exportación y analítica de frecuencias.	Alto. Base para reddit_archive_cli.py y datasets de nicho.

ChocoData-com/reddit-scraper
	Actualizado el 17-07-2026; verifica compatibilidad con cambios de Reddit. 
github
	Monitorización de menciones y palabras clave.	mention_monitor.py: búsqueda por término, SQLite, deduplicación entre ejecuciones y salida de novedades. 
github
+1
	Alto. Es el hallazgo menos obvio y más útil: convierte Reddit en un sistema de vigilancia de nicho con estado local.

Arindam200/reddit-mcp
	Proyecto MCP de 2025 basado en PRAW.	Interfaz agéntica para leer y actuar en Reddit.	Definición de herramientas: búsqueda, hilo, usuario, borrador y respuesta.	Medio. Copiar el contrato de herramientas, no ejecutar un servidor externo todavía.

jordanburke/reddit-mcp-server
	Proyecto MCP de 2025.	Separación lectura/escritura y OAuth.	Contrato de herramientas y control de credenciales.	Medio. Útil para un futuro MCP interno con escritura supervisada.

nicovandenhooff/reddit-data-collector
	Repositorio antiguo, construido sobre PRAW y pandas.	Normalización de posts y comentarios a DataFrame.	Patrón de dataset plano y exportación reproducible.	Medio. Copiar el patrón; no añadir la dependencia.

groceryheist/cdsc_reddit
	Referencia de investigación; orientado a dumps y Parquet.	Analítica histórica a gran escala.	Ingesta a Parquet y variables derivadas.	Bajo-medio. Solo si más adelante se construye un corpus histórico local.

praw-dev/prawtools
	Archivado el 07-06-2026; solo lectura. 
github
	Alertas de palabras clave y estadísticas de subreddit.	Idea de reddit_alert, pero no como dependencia. 
github
	Eliminado como recomendación. Sustituido por mention_monitor.py de ChocoData.

MoeenH/Sentiment-analysis-with-Reddit-Api
	Proyecto pequeño de 2023.	Sentimiento con VADER.	Pipeline mínimo PRAW + pandas + VADER.	Degradado. No como módulo principal; solo señal auxiliar futura.
Cambios respecto al informe anterior

Eliminado RedditWarp como recomendación principal: su último commit visible es de julio de 2024 y PRAW está más activo y mejor posicionado como base de producción.
github

Eliminado prawtools como herramienta a integrar: está archivado desde junio de 2026, aunque su idea de alertas por palabra clave sigue siendo válida.
github

Añadido ChocoData-com/reddit-scraper: es el hallazgo nuevo más relevante porque resuelve exactamente una carencia práctica: vigilancia continua de términos con persistencia SQLite y detección de novedades.
github
+1

Reducido el peso de los repos MCP: no aportan mejor valor que tus propios adaptadores ya existentes; su utilidad es definir una interfaz agéntica posterior.

Eliminada la sugerencia de usar dumps Pushshift como fuente operativa: Pushshift dejó de funcionar como acceso público habitual; debe considerarse solo material histórico offline, si algún día hace falta.

Código reutilizable
1. Monitor de menciones con estado local

Origen: 
reddit_scraper_api_codes/mention_monitor.py
, SHA dfa5da9c61bd74a3797a745c98834a5e289a5b64.
github

Este es el código nuevo que propongo añadir como tools/reddit_mention_monitor.py. Replica la idea del original —búsqueda, SQLite, deduplicación y salida de novedades— pero usando PRAW y el estilo de tu repo.

python
# Inspirado en: https://github.com/ChocoData-com/reddit-scraper/blob/main/reddit_scraper_api_codes/mention_monitor.py
# Nuevo adaptador para davidpd89/ci-sandbox-tmp; usa PRAW y SQLite local.

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import praw


DB_PATH = Path("00_OPERATIVO/reddit/mention_monitor.sqlite3")


@dataclass(frozen=True)
class Mention:
    mention_id: str
    term: str
    subreddit: str
    post_id: str
    post_title: str
    post_url: str
    author: str
    created_utc: int
    score: int | None
    num_comments: int | None
    selftext_excerpt: str
    discovered_at: str


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS seen_mentions (
            mention_id TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            discovered_at TEXT NOT NULL
        )
        """
    )
    return conn


def _mention_id(term: str, post_id: str) -> str:
    raw = f"{term.lower()}:{post_id}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _excerpt(text: str, limit: int = 320) -> str:
    text = " ".join((text or "").split())
    return text[:limit]


def search_mentions(reddit: praw.Reddit, terms: list[str], limit_per_term: int = 50) -> list[Mention]:
    now = datetime.now(timezone.utc).isoformat()
    mentions: list[Mention] = []

    for term in terms:
        for post in reddit.subreddit("all").search(term, sort="new", time_filter="week", limit=limit_per_term):
            mentions.append(
                Mention(
                    mention_id=_mention_id(term, post.id),
                    term=term,
                    subreddit=str(post.subreddit),
                    post_id=post.id,
                    post_title=post.title,
                    post_url=f"https://www.reddit.com{post.permalink}",
                    author=str(post.author) if post.author else "[deleted]",
                    created_utc=int(post.created_utc),
                    score=getattr(post, "score", None),
                    num_comments=getattr(post, "num_comments", None),
                    selftext_excerpt=_excerpt(post.selftext),
                    discovered_at=now,
                )
            )

    return mentions


def persist_new_mentions(mentions: list[Mention]) -> list[Mention]:
    new_items: list[Mention] = []

    with _connect() as conn:
        for item in mentions:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO seen_mentions (mention_id, payload, discovered_at) VALUES (?, ?, ?)",
                (item.mention_id, json.dumps(asdict(item), ensure_ascii=False), item.discovered_at),
            )
            if cursor.rowcount:
                new_items.append(item)

    return new_items


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--terms", nargs="+", required=True)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    reddit = praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent=os.environ.get("REDDIT_USER_AGENT", "davidporto-growth-monitor/1.0"),
        username=os.environ.get("REDDIT_USERNAME"),
        password=os.environ.get("REDDIT_PASSWORD"),
    )

    mentions = search_mentions(reddit, args.terms, args.limit)
    new_mentions = persist_new_mentions(mentions)

    for item in new_mentions:
        print(json.dumps(asdict(item), ensure_ascii=False))


if __name__ == "__main__":
    main()

Integración: ejecutar en modo observación antes de conectar score_hook.py. La salida JSON puede alimentar candidate_identity.py para deduplicar y round_queue.py para crear candidatos de interacción.

Tests mínimos:

Dos ejecuciones con el mismo post no generan duplicados.

Un término repetido en mayúsculas/minúsculas produce el mismo mention_id.

Un post borrado no rompe la ejecución.

La base SQLite se crea en 00_OPERATIVO/reddit/.

Sin credenciales, el proceso falla con mensaje claro y no escribe en disco.

2. Archivo de subreddit y comentarios

Origen: urs/praw_scrapers/static_scrapers/Subreddit.py y urs/praw_scrapers/static_scrapers/Comments.py, ambos en rama master.

URS separa correctamente subreddit, comentarios y autor; esa separación conviene replicar en un CLI propio.

python
# Inspirado en:
# https://github.com/JosephLai241/URS/blob/master/urs/praw_scrapers/static_scrapers/Subreddit.py
# https://github.com/JosephLai241/URS/blob/master/urs/praw_scrapers/static_scrapers/Comments.py
# Nuevo CLI para davidpd89/ci-sandbox-tmp.

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

import praw


OUT_DIR = Path("00_OPERATIVO/reddit/archive")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.touch()
        return

    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def archive_subreddit(reddit: praw.Reddit, subreddit: str, listing: str, limit: int) -> list[dict]:
    target = reddit.subreddit(subreddit)
    listings = {
        "hot": target.hot,
        "new": target.new,
        "top": target.top,
        "rising": target.rising,
    }

    if listing not in listings:
        raise ValueError(f"Listing no soportado: {listing}")

    rows = []
    for post in listings[listing](limit=limit):
        rows.append(
            {
                "post_id": post.id,
                "subreddit": str(post.subreddit),
                "title": post.title,
                "author": str(post.author) if post.author else "[deleted]",
                "created_utc": int(post.created_utc),
                "score": getattr(post, "score", None),
                "upvote_ratio": getattr(post, "upvote_ratio", None),
                "num_comments": getattr(post, "num_comments", None),
                "permalink": f"https://www.reddit.com{post.permalink}",
                "selftext": post.selftext,
                "flair": getattr(post, "link_flair_text", None),
            }
        )

    return rows


def archive_comments(reddit: praw.Reddit, post_id: str, limit: int) -> list[dict]:
    submission = reddit.submission(id=post_id)
    submission.comments.replace_more(limit=0)

    rows = []
    for comment in submission.comments.list()[:limit]:
        rows.append(
            {
                "comment_id": comment.id,
                "post_id": submission.id,
                "subreddit": str(comment.subreddit),
                "author": str(comment.author) if comment.author else "[deleted]",
                "created_utc": int(comment.created_utc),
                "score": getattr(comment, "score", None),
                "parent_id": comment.parent_id,
                "body": comment.body,
                "permalink": f"https://www.reddit.com{comment.permalink}",
            }
        )

    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    subreddit_parser = sub.add_parser("subreddit")
    subreddit_parser.add_argument("name")
    subreddit_parser.add_argument("--listing", choices=["hot", "new", "top", "rising"], default="new")
    subreddit_parser.add_argument("--limit", type=int, default=100)

    comments_parser = sub.add_parser("comments")
    comments_parser.add_argument("post_id")
    comments_parser.add_argument("--limit", type=int, default=500)

    parser.add_argument("--format", choices=["csv", "jsonl"], default="jsonl")
    args = parser.parse_args()

    reddit = praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent=os.environ.get("REDDIT_USER_AGENT", "davidporto-growth-archive/1.0"),
        username=os.environ.get("REDDIT_USERNAME"),
        password=os.environ.get("REDDIT_PASSWORD"),
    )

    if args.command == "subreddit":
        rows = archive_subreddit(reddit, args.name, args.listing, args.limit)
        output = OUT_DIR / f"subreddit_{args.name}_{args.listing}.{args.format}"
    else:
        rows = archive_comments(reddit, args.post_id, args.limit)
        output = OUT_DIR / f"comments_{args.post_id}.{args.format}"

    if args.format == "csv":
        _write_csv(output, rows)
    else:
        _write_jsonl(output, rows)

    print(output)


if __name__ == "__main__":
    main()

Integración: este CLI no publica ni comenta. Su salida debe ir a 00_OPERATIVO/reddit/archive/ y servir de material para medir subreddits, autores recurrentes, preguntas frecuentes, formatos con respuesta y vocabulario del nicho.

Tests mínimos:

subreddit con new, hot, top y rising.

comments con un hilo sin comentarios.

Exportación CSV y JSONL válidas.

Autor [deleted] no rompe el proceso.

replace_more(limit=0) evita descargas infinitas.

3. Cliente PRAW común con reintentos

Origen conceptual: 
praw/reddit.py
, archivo principal de PRAW con 901 líneas y 32,6 KB en main.
github

No conviene copiar el archivo completo: PRAW ya es la dependencia. Lo que sí conviene centralizar es la construcción del cliente y el control de fallos.

python
# Nuevo módulo para davidpd89/ci-sandbox-tmp.
# Base técnica: https://github.com/praw-dev/praw/blob/main/praw/reddit.py

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Callable, TypeVar

import praw
from praw.exceptions import PRAWException
from prawcore.exceptions import ResponseException


T = TypeVar("T")


@dataclass(frozen=True)
class RedditClientConfig:
    client_id: str
    client_secret: str
    user_agent: str
    username: str | None = None
    password: str | None = None


def build_reddit_client() -> praw.Reddit:
    config = RedditClientConfig(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent=os.environ.get("REDDIT_USER_AGENT", "davidporto-growth-system/1.0"),
        username=os.environ.get("REDDIT_USERNAME"),
        password=os.environ.get("REDDIT_PASSWORD"),
    )

    return praw.Reddit(
        client_id=config.client_id,
        client_secret=config.client_secret,
        user_agent=config.user_agent,
        username=config.username,
        password=config.password,
    )


def with_reddit_retry(
    operation: Callable[[], T],
    attempts: int = 3,
    base_delay: float = 2.0,
) -> T:
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except (PRAWException, ResponseException) as error:
            last_error = error
            if attempt == attempts:
                raise

            time.sleep(base_delay * (2 ** (attempt - 1)))

    raise RuntimeError("Reddit operation failed") from last_error

Integración: reddit_scan.py, reddit_comments.py, reddit_interact.py y reddit_execute.py deben usar build_reddit_client(); así se elimina duplicación de credenciales y se centraliza la política de reintento.

Tests mínimos:

Falta REDDIT_CLIENT_ID produce error claro.

Dos reintentos ante ResponseException.

No reintenta errores de validación local.

El user_agent es obligatorio y estable.

Arquitectura recomendada
text
Reddit
  │
  ├─ reddit_mention_monitor.py   → términos, menciones, novedades, SQLite
  ├─ reddit_archive_cli.py       → subreddit, hilo, comentarios, autor, CSV/JSONL
  ├─ reddit_client.py            → PRAW, OAuth, reintentos, user agent
  │
  ├─ reddit_scan.py              → candidatos en vivo
  ├─ reddit_comments.py          → contexto conversacional
  ├─ reddit_interact.py          → acciones supervisadas
  ├─ reddit_publish.py           → publicación
  │
  ├─ candidate_identity.py       → deduplicación
  ├─ score_hook.py               → ranking
  ├─ round_queue.py              → cola de acciones
  ├─ action_ledger.py            → evidencia y resultados
  └─ growth_attribution.py       → aprendizaje por subreddit, hilo y plantilla
Ranking de prioridades
Prioridad	Entregable	Motivo
1	reddit_client.py	Elimina duplicación y da una base estable a todo el módulo Reddit.
2	reddit_mention_monitor.py	Añade descubrimiento proactivo por términos, con estado persistente. 
github
+1

3	reddit_archive_cli.py	Permite estudiar nicho, autores, subreddits y formatos antes de actuar.
4	Señales en score_hook.py	Convierte observaciones en ranking medible.
5	Atribución Reddit en growth_attribution.py	Cierra el ciclo: acción → respuesta → aprendizaje.
6	MCP interno de solo lectura	Útil después, no antes; primero deben existir datos y contratos estables.
Plan de PR pequeñas
PR 1 — reddit_client.py

Añadir PRAW 8.0.3.

Crear cliente central, with_reddit_retry y tests.

No cambiar todavía los módulos existentes.

PR 2 — reddit_mention_monitor.py

Añadir monitor de términos con SQLite.

Términos iniciales: fantasía juvenil, romantasy, novela fantástica, libros fantasía, recomendad fantasia, autores fantasía.

Guardar salida en 00_OPERATIVO/reddit/.

No conectar todavía con publicación.

PR 3 — reddit_archive_cli.py

Añadir comandos subreddit y comments.

Exportar CSV y JSONL.

Añadir tests de esquema y deduplicación.

PR 4 — Integración con ranking

Crear reddit_signal_scorer.py.

Señales: recencia, número de comentarios, ratio de upvotes, presencia de pregunta, tono, longitud, afinidad temática y resultado histórico.

Escribir candidatos en round_queue.py sin publicar automáticamente.

PR 5 — Aprendizaje

Ampliar growth_attribution.py con eventos Reddit.

Informe diario por subreddit, autor, tipo de hilo y plantilla.

Tests con eventos incompletos y duplicados.

Aplicación multirred

El mismo diseño se traslada así:

X / Threads / Bluesky / Mastodon: monitor de términos, archivo de conversaciones y autores, scoring y ledger.

Facebook / Instagram: monitor de grupos, páginas, hashtags y comentarios; el equivalente al hilo es la publicación con su hilo de comentarios.

Pinterest: monitor de términos y tableros; el equivalente al comentario es el guardado, re-pin y clic.

TikTok: monitor de hashtags, creadores y comentarios; el equivalente al hilo es el vídeo y su conversación.

Reddit: es la red donde más importa el contexto: un candidato debe valorarse por posibilidad de conversación real, no solo por volumen.

Fuentes

PRAW: 
https://github.com/praw-dev/praw

Release PRAW 8.0.3: 
https://github.com/praw-dev/praw/releases
github

praw/reddit.py: 
https://github.com/praw-dev/praw/blob/main/praw/reddit.py
github

Async PRAW: 
https://github.com/praw-dev/asyncpraw

Async PRAW 8.0.3: 
https://github.com/praw-dev/asyncpraw/blob/main/CHANGES.rst
freshports

URS: 
https://github.com/JosephLai241/URS

Estructura URS: https://github.com/JosephLai241/URS/tree/master/urs/praw_scrapers/static_scrapers

Documentación URS: 
https://josephlai241.github.io/URS/

ChocoData Reddit Scraper: 
https://github.com/ChocoData-com/reddit-scraper
github

mention_monitor.py: 
https://github.com/ChocoData-com/reddit-scraper/blob/main/reddit_scraper_api_codes/mention_monitor.py
github

Reddit MCP: 
https://github.com/Arindam200/reddit-mcp

Reddit MCP Server: 
https://github.com/jordanburke/reddit-mcp-server

Reddit Data Collector: 
https://github.com/nicovandenhooff/reddit-data-collector

PRAWtools archivado: 
https://github.com/praw-dev/prawtools
github

Estado de Pushshift: 
https://melaniewalsh.github.io/Intro-Cultural-Analytics/04-Data-Collection/14-Reddit-Data.html

Alternativas históricas: 
https://www.redditapis.com/blogs/best-pushshift-alternatives-2026
