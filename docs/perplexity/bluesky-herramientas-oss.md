# Herramientas y código abierto en Bluesky

Fuente: informe de Perplexity (https://www.perplexity.ai/search/acd5b3eb-d70f-47d6-8ce5-080bb21fbf42), generado 10/10/2026.

Informe mejorado: repos, SDK y agentes para crecer en Bluesky con Python
Resumen

Tras revisar el espejo davidpd89/ci-sandbox-tmp, tu sistema ya tiene una base Bluesky muy completa: escaneo, Jetstream, interacción, cola de respuestas, vocabulario, reciprocidad, starter packs, auditoría y ejecución. Por ello, este informe elimina propuestas redundantes y se centra en seis incorporaciones de alto valor: SDK tipado, ingesta Jetstream con cursor, escucha social multirred, servidor/laboratorio de ranking, análisis semántico con LLM y métricas versionadas.
bsky
+1

He descartado repos que parecían relevantes pero no lo son para este sistema: russss/polybot está archivado; bluesky/bluesky y TUDelft-CNS-ATM/bluesky no tienen relación con la red Bluesky; susumuota/arxiv-reddit-summary y sneezeparty/soupy son casos de uso demasiado específicos.
pypi

Correcciones al informe anterior
Elemento anterior	Decisión	Motivo
MarshalX/atproto	Mantener, prioridad máxima	Activo el 2 de octubre de 2026, 660 estrellas, MIT, Python y diseño sync/async. 
pypi

bluesky-social/jetstream	Mantener	Es la vía oficial para recibir eventos filtrados de la red como JSON por WebSocket. 
bsky

MarshalX/bluesky-feed-generator	Mantener como laboratorio, no como feed público inicial	Activo el 19 de agosto de 2026, 304 estrellas, MIT; su valor inmediato es la arquitectura de ranking. 
pypi

circularmachines/bsky2llm	Mantener con cautela	Útil como idea de pipeline posts → Markdown → análisis IA, pero debe verificarse su mantenimiento antes de depender de él. 
github

zzstoatzz/atproto-dashboard	Reducir a inspiración	Es un ejemplo, no una librería madura; copiar el patrón de assets/pipelines, no el stack completo.
srhnyldz/bluesky-unfollow-tracker	Reducir a métrica	No copiar su lógica de unfollow; ya existe reciprocity.py, follow_review.py y unfollow_cleanup.py. 
pypi

russss/polybot	Eliminar	Archivado; no es una base mantenible para código nuevo. 
pypi

advaith1/bluesky-followers y romiojoseph/atproto-explorer	Eliminar como dependencias	Son interfaces web útiles para explorar, pero no aportan código Python directamente reutilizable a tu pipeline.
Hallazgos verificados
Repositorio	Estado a 10/10/2026	Licencia	Qué copiar	Integración
MarshalX/atproto	Activo; último push 2026-10-02; 660 estrellas	MIT	Cliente XRPC, modelos tipados, paginación, Jetstream, publicación y respuestas. 
pypi
	Nuevo adaptador común tools/bluesky_client.py; migración gradual desde llamadas manuales.

bluesky-social/jetstream
	Servicio oficial; documentación actualizada en 2026	Código del servicio aparte; uso por WebSocket	Filtros por colección, cursor/checkpoint, reconexión y semántica de eventos. 
bsky
	Reforzar bluesky_jetstream_collect.py con cursor persistente y filtrado servidor-side.

MarshalX/bluesky-feed-generator
	Activo; último push 2026-08-19; 304 estrellas	MIT	Separación entre ingesta, server/data_filter.py, algoritmo y servidor de feed. 
pypi
	Crear tools/bluesky_rank_lab.py: mismo diseño, pero evaluación offline antes de publicar un feed.
snarfed/lexrpc	Activo; último push 2026-09-30; 46 estrellas	CC0	Cliente/servidor XRPC + validación Lexicon. 
pypi
	Usarlo como referencia para validar contratos de entrada/salida y detectar errores de esquema antes de ejecutar acciones.
snarfed/arroba	Activo; último push 2026-10-01; 80 estrellas	CC0	Implementación Python de PDS/ATProto: repo, MST y métodos XRPC de sincronización. 
pypi
	No integrar como cliente日常; usar como referencia avanzada si más adelante necesitas leer repos/CAR o construir pruebas de integridad.
VladUZH/harken	Activo; último push 2026-07-22; 34 estrellas	MIT	Social listening autoalojado para Bluesky, Mastodon, Reddit, Hacker News y RSS, con sentimiento y temas. 
pypi
	Extraer el modelo de menciones, sentimiento y temas para un módulo multirred tools/social_listening.py.

bluesky-social/cookbook
	Referencia oficial de ejemplos	Varía por ejemplo	Recetas de publicación, respuestas, imágenes y OAuth. 
github
	Consultar antes de implementar acciones; no copiar el repositorio completo.
circularmachines/bsky2llm	Por verificar antes de dependencia	Por verificar	Normalización de posts a Markdown y análisis con IA. 
github
	Implementar tools/bluesky_post_semantics.py con la idea, pero con proveedor y esquema propios.

sdk.blue
	Directorio público activo	—	Catálogo de SDKs y herramientas ATProto por lenguaje.	Vigilancia trimestral de alternativas; no es dependencia.
Piezas de código reutilizables

Nota de verificación: los bloques siguientes son código de integración listo para ci-sandbox-tmp, no volcados literales de ficheros completos. Cada bloque indica en la primera línea la URL exacta del archivo o documentación upstream desde la que debe copiarse/contrastarse la pieza original. El fichero de filtro del feed generator está en server/data_filter.py, no en la raíz.

1. Cliente Bluesky tipado
python
# Fuente base: https://github.com/MarshalX/atproto/blob/main/examples/send_post.py
# SDK: https://github.com/MarshalX/atproto
# Objetivo: adaptador común para scan, reply, like, follow y publicación.

from atproto import Client
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

class BlueskyClient:
    def __init__(self, handle: str, app_password: str):
        self._client = Client()
        self._handle = handle
        self._app_password = app_password

    @retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=1, max=30))
    def login(self):
        return self._client.login(self._handle, self._app_password)

    def author_feed(self, actor: str, limit: int = 50, cursor: str | None = None):
        return self._client.get_author_feed(actor=actor, limit=limit, cursor=cursor)

    def search_posts(self, q: str, limit: int = 50, cursor: str | None = None):
        return self._client.app.bsky.feed.search_posts({"q": q, "limit": limit, "cursor": cursor})

    def reply(self, parent_uri: str, parent_cid: str, text: str):
        return self._client.send_post(
            text=text,
            reply={"root": {"uri": parent_uri, "cid": parent_cid},
                   "parent": {"uri": parent_uri, "cid": parent_cid}},
        )

Integración: no sustituyas de golpe bluesky_scan.py, bluesky_interact.py y bluesky_execute.py. Primero crea tools/bluesky_client.py, añade tests con respuestas grabadas y migra una sola lectura; después, una acción de escritura.
bsky
+1

2. Jetstream con cursor persistente
python
# Fuente base: https://github.com/bluesky-social/jetstream
# Documentación: https://bsky.network/docs/jetstream/
# Objetivo: sustituir/completar tools/bluesky_jetstream_collect.py
# con cursor persistente, filtrado y deduplicación.

import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from websockets.sync.client import connect

JETSTREAM_URL = "wss://jetstream2.us-east.bsky.network/subscribe"
COLLECTIONS = ["app.bsky.feed.post", "app.bsky.feed.like", "app.bsky.graph.follow"]

@dataclass
class Cursor:
    did: str
    rkey: str
    time_us: int

class JetstreamCollector:
    def __init__(self, db_path: Path):
        self.db = sqlite3.connect(db_path)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS jetstream_events (
                did TEXT, rkey TEXT, collection TEXT, time_us INTEGER,
                payload TEXT, PRIMARY KEY (did, rkey, collection)
            )
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS jetstream_cursor (
                id INTEGER PRIMARY KEY CHECK (id = 1), time_us INTEGER
            )
        """)

    def last_cursor(self) -> int | None:
        row = self.db.execute("SELECT time_us FROM jetstream_cursor WHERE id = 1").fetchone()
        return row[0] if row else None

    def save_event(self, event: dict) -> bool:
        commit = event.get("commit")
        if not commit or commit.get("collection") not in COLLECTIONS:
            return False
        try:
            self.db.execute(
                "INSERT INTO jetstream_events VALUES (?, ?, ?, ?, ?)",
                (commit["did"], commit["rkey"], commit["collection"],
                 commit["timestamp_us"], json.dumps(event, ensure_ascii=False)),
            )
            self.db.execute(
                "INSERT INTO jetstream_cursor VALUES (1, ?) "
                "ON CONFLICT(id) DO UPDATE SET time_us = excluded.time_us",
                (commit["timestamp_us"],),
            )
            self.db.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def stream(self):
        params = f"?wantedCollections={';'.join(COLLECTIONS)}"
        cursor = self.last_cursor()
        if cursor:
            params += f"&cursor={cursor}"
        with connect(JETSTREAM_URL + params) as ws:
            while True:
                yield self.save_event(json.loads(ws.recv()))

Integración: guarda eventos crudos en SQLite o Parquet y deja que bluesky_growth_scan.py consuma una vista limpia. Filtra colecciones en la URL, no después de descargar todo; Jetstream está diseñado precisamente para ese filtrado.
bsky

3. Laboratorio de ranking offline
python
# Fuente base: https://github.com/MarshalX/bluesky-feed-generator/blob/main/server/data_filter.py
# Objetivo: reutilizar la separación ingesta -> filtro -> ranking,
# pero sin publicar un feed hasta validar el modelo con datos históricos.

from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass(frozen=True)
class Candidate:
    uri: str
    cid: str
    author_did: str
    text: str
    created_at: datetime
    like_count: int = 0
    reply_count: int = 0
    repost_count: int = 0
    topic_score: float = 0.0
    author_affinity: float = 0.0
    already_actioned: bool = False

def recency_score(created_at: datetime, now: datetime | None = None) -> float:
    now = now or datetime.now(timezone.utc)
    hours = max((now - created_at).total_seconds() / 3600, 0)
    return 1.0 / (1.0 + hours / 6.0)

def engagement_score(c: Candidate) -> float:
    return min(1.0, (c.like_count + 3 * c.reply_count + 2 * c.repost_count) / 100)

def rank_candidates(items: list[Candidate]) -> list[Candidate]:
    scored = []
    for c in items:
        if c.already_actioned:
            continue
        score = (
            0.30 * c.topic_score
            + 0.25 * c.author_affinity
            + 0.20 * recency_score(c.created_at)
            + 0.15 * engagement_score(c)
        )
        scored.append((score, c))
    return [c for _, c in sorted(scored, key=lambda pair: pair[0], reverse=True)]

Integración: este módulo no debe decidir acciones todavía. Debe generar informe_ranking_bluesky.csv con score, componentes y URI; después, bluesky_build_plan.py puede consumir sólo los candidatos que superen un umbral validado.
bsky
+1

4. Escucha social multirred
python
# Fuente base: https://github.com/VladUZH/harken
# Objetivo: adoptar su modelo de menciones, sentimiento y temas
# para detectar conversaciones de fantasía/romantasy en varias redes.

from dataclasses import dataclass
from datetime import datetime

@dataclass
class Mention:
    network: str
    external_id: str
    author_handle: str
    text: str
    url: str
    created_at: datetime
    sentiment: float
    themes: list[str]
    matched_terms: list[str]

def is_actionable(mention: Mention, min_score: float = 0.55) -> bool:
    relevant = any(t in {"fantasia", "romantasy", "lectura", "escritura"} for t in mention.themes)
    positive_or_neutral = mention.sentiment >= -0.15
    return relevant and positive_or_neutral and len(mention.matched_terms) >= 1

Integración: crea tools/social_listening.py con el mismo contrato para Bluesky, Mastodon, Reddit y, donde exista acceso, X/Threads. Así discovery_terms.py y growth_attribution.py dejan de depender sólo de términos de búsqueda y empiezan a aprender de conversaciones reales.
pypi

5. Perfil de autor y afinidad
python
# Fuente base: https://github.com/MarshalX/atproto/blob/main/examples/profile_posts.py
# Objetivo: puntuar autores antes de interactuar, usando señales ya presentes
# en candidate_identity.py, discovery_terms.py y reciprocity.py.

from datetime import datetime, timezone

def author_score(
    posts: int,
    original_ratio: float,
    recent_activity: float,
    topic_affinity: float,
    engagement_per_post: float,
    reciprocal: bool,
) -> float:
    if posts < 3:
        return 0.0
    base = (
        0.30 * min(original_ratio, 1.0)
        + 0.25 * min(recent_activity, 1.0)
        + 0.25 * min(topic_affinity, 1.0)
        + 0.20 * min(engagement_per_post, 1.0)
    )
    return base * (1.10 if reciprocal else 1.0)

def is_stale(last_post_at: datetime, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    return (now - last_post_at).days > 45

Integración: añade tools/bluesky_author_profile.py y alimenta candidate_identity.py. No uses este score para seguir automáticamente: úsalo para ordenar candidatos y marcar perfiles para revisión.
bsky
+1

Qué eliminar definitivamente

Bots genéricos de follow/unfollow: tu repo ya tiene bluesky_followback_wave.py, reciprocity.py, reciprocity_stats.py, follow_review.py y unfollow_cleanup.py; añadir otro tracker sólo crearía duplicación.
pypi

Feed generator como dependencia inmediata: publicar un feed exige exponer un servicio y mantener disponibilidad; primero conviene usar su arquitectura como evaluador offline.
pypi

bluesky de PyPI: es orquestación de experimentos científicos, no el SDK de la red Bluesky.
pypi

Firehose completo: Jetstream cubre mejor tu necesidad de ingesta filtrada y reanudable.
bsky

Plan de PR pequeñas
PR 1 — bluesky_client.py

Añadir atproto con versión fijada.

Crear adaptador con login, reintentos, logging y operaciones de lectura.

Migrar una única función de bluesky_scan.py.

Tests: mock HTTP, paginación, timeout, reconexión y compatibilidad Windows/Python 3.11.

PR 2 — Jetstream durable

Mejorar bluesky_jetstream_collect.py con SQLite/Parquet, cursor, filtros por NSID y deduplicación.

Añadir métricas: eventos recibidos, guardados, duplicados y lag.

Tests: cursor reanudable, desconexión, filtrado y backfill limitado.

PR 3 — Perfil de autor

Crear bluesky_author_profile.py.

Calcular actividad, ratio original/repost, temas, engagement y recencia.

Escribir informe_autores_bluesky.csv.

Tests con fixtures y regresión de puntuación.

PR 4 — Semántica de posts

Crear bluesky_post_semantics.py.

Convertir candidatos a Markdown auditable y clasificar temas en español.

Limitar llamadas LLM a candidatos con score previo alto.

Tests: golden set de 50 posts, detección de idioma, duplicados y coste máximo.

PR 5 — Laboratorio de ranking

Crear bluesky_rank_lab.py inspirado en server/data_filter.py del feed generator.

Comparar variantes de score con histórico real.

Generar informe, no acciones.

Tests: reproducibilidad, sin fuga temporal y comparación A/B offline.

PR 6 — Escucha y métricas multirred

Crear social_listening.py con contrato común de menciones.

Crear bluesky_metrics_assets.py para snapshots diarios y atribución.

Reutilizar el mismo esquema en Mastodon y Reddit.

Tests: idempotencia, integridad referencial, anomalías y exportación.

Fuentes

MarshalX/atproto
pypi

atproto en PyPI
pypi

Bluesky Jetstream
bsky

bluesky-social/jetstream

MarshalX/bluesky-feed-generator
pypi

server/data_filter.py

snarfed/lexrpc
pypi

snarfed/arroba
pypi

VladUZH/harken
pypi

bluesky-social/cookbook
github

circularmachines/bsky2llm
github

sdk.blue

Ejemplos oficiales de atproto
