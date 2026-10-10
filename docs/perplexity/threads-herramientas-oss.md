# Herramientas y código abierto en Threads

Fuente: informe de Perplexity (https://www.perplexity.ai/search/a3caa9f6-3524-4241-ba4b-86d26118a899), generado 10/10/2026.

Informe mejorado: Threads con Python en Windows
Resumen

He revisado el informe anterior contra el código real de davidpd89/ci-sandbox-tmp y he eliminado lo que no aporta valor directo: rtk-ai/rtk, los catálogos genéricos de MCP/skills como piezas centrales y cualquier sugerencia que duplicaría tu ejecutor, cola, escáner o ledger ya existentes. La conclusión revisada es más estrecha y práctica: no necesitas otro framework de Threads; necesitas enriquecimiento de candidatos, investigación de tendencias, métricas atribuibles y ranking de acciones.

Correcciones al informe anterior
Elemento anterior	Decisión	Motivo
rtk-ai/rtk	Eliminado	Es una herramienta de desarrollo para reducir tokens en comandos; no resuelve descubrimiento, publicación, métricas ni crecimiento en Threads.
punkpeye/awesome-mcp-servers	Degradado a referencia	Es un catálogo, no una pieza reutilizable para tu flujo; no justifica una integración ahora.
VoltAgent/awesome-agent-skills y ComposioHQ/awesome-claude-skills	Degradados a inspiración	Útiles para el formato de skills, pero no contienen una capacidad Threads verificable que debas copiar hoy.
marclove/pythreads	Conservado	Es el hallazgo más relevante: wrapper Python de la Threads API de Meta, con 72 estrellas y actividad en 2026.
noahclark556/threads_api	Conservado con cautela	Aporta extracción pasiva de perfiles, pero es pequeño, con 14 estrellas; conviene usarlo como referencia, no como dependencia crítica.
mvanhorn/last30days-skill	Conservado	Muy activo, MIT y directamente aplicable al patrón de investigación de tendencias y síntesis con fuentes.
Hallazgos verificados
Repositorio	Estado	Qué resuelve	Qué copiar o adaptar	Integración
marclove/pythreads	Python; 72 estrellas; actualizado en junio de 2026; no archivado.	Cliente Python de la Threads API oficial de Meta.	Contratos de API, manejo de publicación, paginación y errores; no su cliente completo.	Crear tools/threads_api_compat.py que traduzca respuestas al formato que ya consumen threads_execute.py y threads_interact.py.
noahclark556/threads_api	Python; 14 estrellas; actualizado en julio de 2026; no archivado.	Recuperación pasiva de datos de perfil.	Normalización de perfil, extracción de bio/enlaces y tolerancia a campos ausentes.	tools/threads_profile_enrich.py, alimentado por threads_scan.py.
mvanhorn/last30days-skill	Python; MIT; 63.874 estrellas; último push el 9 de octubre de 2026.	Investigación reciente multiplataforma y síntesis fundamentada.	Estructura de skill, ventana temporal, fuentes, citas y salida estructurada.	skills/threads_trend_brief/ + tools/threads_trend_brief.py.
davidpd89/ci-sandbox-tmp	Tu espejo activo; contiene módulos Threads, ledger, colas, deduplicación y auditoría.	Base completa del sistema.	No copiar nada externo que duplique threads_api.py, threads_execute.py, threads_interact.py, threads_scan.py, reply_writer.py, reply_queue.py o action_ledger.py.	Extender, no reemplazar.
Código reutilizable

No incluyo bloques presentados como “copiados tal cual” de repos externos porque, en esta revisión, no he verificado el contenido línea a línea de los archivos concretos; copiarlos sin esa verificación sería introducir código no auditado en tu sistema. En su lugar, dejo el código de integración nuevo, diseñado para no chocar con tus módulos existentes, y los archivos externos que deben inspeccionarse antes de extraer fragmentos.

python
# tools/threads_profile_enrich.py
# Nuevo adaptador: no sustituye a tools/threads_scan.py ni a tools/threads_api.py.
# Referencia externa: https://github.com/noahclark556/threads_api
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

def normalize_profile(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(raw.get("id") or raw.get("pk") or ""),
        "username": (raw.get("username") or "").strip(),
        "full_name": (raw.get("full_name") or "").strip(),
        "bio": (raw.get("biography") or raw.get("bio") or "").strip(),
        "website": (raw.get("website") or raw.get("external_url") or "").strip(),
        "followers": int(raw.get("follower_count") or 0),
        "is_verified": bool(raw.get("is_verified", False)),
        "niche_signals": [],
    }

def enrich_file(path: Path, out_path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data if isinstance(data, list) else data.get("candidates", [])
    enriched = []
    for row in rows:
        profile = normalize_profile(row.get("profile", row))
        text = " ".join([profile["username"], profile["full_name"], profile["bio"]]).lower()
        profile["niche_signals"] = [
            term for term in ("fantasia", "fantasy", "romantasy", "booktok", "lectura", "libros")
            if term in text
        ]
        enriched.append({**row, "profile_enriched": profile})
    out_path.write_text(
        json.dumps({"candidates": enriched}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return len(enriched)
python
# tools/threads_action_ranker.py
# Nuevo módulo de ranking; se apoya en action_ledger.py y growth_attribution.py existentes.
# Base propia del sistema: https://github.com/davidpd89/ci-sandbox-tmp/blob/main/tools/action_ledger.py
from __future__ import annotations

from datetime import datetime, timezone

WEIGHTS = {
    "affinity": 0.35,
    "freshness": 0.25,
    "history": 0.20,
    "social": 0.10,
    "ease": 0.10,
}

def freshness(hours_old: float, max_hours: float = 72.0) -> float:
    return max(0.0, 1.0 - min(hours_old, max_hours) / max_hours)

def rank_candidate(candidate: dict) -> float:
    return sum(
        WEIGHTS[key] * float(candidate.get(key, 0.0))
        for key in WEIGHTS
    )

def rank_candidates(candidates: list[dict], now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    ranked = []
    for item in candidates:
        created = item.get("created_at")
        hours = 999.0
        if created:
            delta = now - datetime.fromisoformat(created.replace("Z", "+00:00"))
            hours = delta.total_seconds() / 3600
        scored = {
            **item,
            "freshness": freshness(hours),
            "score": rank_candidate({**item, "freshness": freshness(hours)}),
        }
        ranked.append(scored)
    return sorted(ranked, key=lambda x: x["score"], reverse=True)
python
# skills/threads_trend_brief/SKILL.md
# Nuevo skill; patrón inspirado en https://github.com/mvanhorn/last30days-skill
---
name: threads_trend_brief
description: Genera un informe diario de oportunidades de fantasía y romantasy en Threads, con temas, cuentas, formatos y acciones propuestas.
---

1. Lee los candidatos recientes generados por `tools/threads_scan.py`.
2. Filtra por español, fantasía, romantasy, libros, lectura, escritura y comunidad lectora.
3. Agrupa por tema, formato y tipo de cuenta.
4. Para cada oportunidad, indica: tema, por qué encaja, ejemplo de comentario humano y riesgo de repetición.
5. Devuelve Markdown en `00_OPERATIVO/threads/tendencias/YYYY-MM-DD.md`.
6. No propongas acciones sin contexto ni repitas plantillas ya presentes en `tools/check_duplicate_phrase.py`.
Plan de implementación revisado
PR 1 — Enriquecimiento de perfiles

Añade tools/threads_profile_enrich.py y tests offline. Debe leer la salida de threads_scan.py, normalizar perfiles y marcar señales del nicho sin llamar a la API durante los tests.

Tests: perfil completo, perfil sin bio, ID ausente, seguidores no numéricos y deduplicación por ID.

PR 2 — Brief diario de tendencias

Añade skills/threads_trend_brief/ y tools/threads_trend_brief.py. El patrón de investigación con ventana temporal y síntesis fundamentada procede de last30days-skill, pero la salida debe ser específica para fantasía/romantasy en español.

Tests: esquema Markdown, presencia de temas, citas o enlaces, ventana de 30 días y rechazo de temas irrelevantes.

PR 3 — Métricas atribuibles

Añade tools/threads_metrics.py sobre action_ledger.py y growth_attribution.py; no crees otra base de datos ni otro formato de registro.

Campos mínimos: network, action, target_id, candidate_score, reply_id, impressions, replies, likes, reposts, clicked, timestamp.

Tests: agregación por acción, ventanas de 24 horas y 7 días, registros incompletos e idempotencia.

PR 4 — Ranking y presupuesto

Añade tools/threads_action_ranker.py y conéctalo a volume_ramp.py y circuit_breaker.py. El ranking debe decidir qué acción hacer, no aumentar automáticamente el volumen.

Tests: orden estable, empates, candidatos sin historial, corte por presupuesto y exclusión de objetivos ya interactuados.

PR 5 — Compatibilidad con pythreads

Después de auditar su código, añade tools/threads_api_compat.py únicamente para normalizar respuestas y errores. No sustituyas threads_api.py ni cambies los contratos que ya usan threads_execute.py y threads_interact.py.

Tests: publicación de texto, recuperación de estado, error 4xx, error 5xx, token inválido y respuesta con campos inesperados.

Aplicación multirred

X, Bluesky y Mastodon: replica *_profile_enrich.py, *_trend_brief.py, *_metrics.py y *_action_ranker.py; ya existen escáneres e interacción específicos en el repo.

Facebook e Instagram: reutiliza meta_common.py, meta_insights.py y meta_publish.py; el ranking debe consumir métricas reales de Meta cuando estén disponibles.

Pinterest: prioriza palabras clave, tableros, pins y enlaces; conéctalo a pinterest_growth.py y pinterest_daily_pins.py.

Reddit: el brief de tendencias es especialmente útil para localizar hilos y comunidades activas antes de comentar; reutiliza reddit_comments.py y reddit_scan.py.

TikTok: adapta el brief a sonidos, ganchos, formatos y cuentas; conéctalo a tiktok_discovery.py y tiktok_growth_scan.py.

Fuentes

Inventario y arquitectura actual del sistema: davidpd89/ci-sandbox-tmp.

Wrapper Python de la Threads API: marclove/pythreads.

Extracción pasiva de perfiles de Threads: noahclark556/threads_api.

Skill de investigación reciente y síntesis con fuentes: mvanhorn/last30days-skill.
