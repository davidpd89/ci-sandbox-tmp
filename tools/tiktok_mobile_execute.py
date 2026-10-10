"""Ejecutor supervisado de interacciones TikTok sobre Android nativo.

Por defecto SOLO hace preflight. Las escrituras requieren --apply. Antes de tocar la
app valida el lote entero, límites de proyecto, textos, duplicados y targets. Ya en
<<<<<<< HEAD
el móvil verifica la cuenta @autorademoescritor. Cualquier challenge, cuenta errónea,
=======
el móvil verifica la cuenta @davidportoescritor. Cualquier challenge, cuenta errónea,
>>>>>>> origin/research/public-reuse-parent
target ambiguo o escritura no verificable detiene el resto del plan.

No es una API oficial de TikTok y no se usa para interacción masiva.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import random
import re
<<<<<<< HEAD
=======
import secrets
>>>>>>> origin/research/public-reuse-parent
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import check_duplicate_phrase as dup
import scan_common as sc
from mobile_client import MobileCliError
<<<<<<< HEAD
=======
from mobile_runtime import MobileSessionBusy
import tiktok_safety as safety
>>>>>>> origin/research/public-reuse-parent
from mobile_runtime import ensure_server, mobile_session_lock
from tiktok_behavior import Behavior
from tiktok_human import HumanClient, HumanProfile, Pace
from tiktok_mobile_interact import (
    MY_HANDLE,
    TikTokMobileAdapter,
    TikTokMobileChallenge,
    TikTokTargetNotFound,
    TikTokWrongAccount,
    TikTokWriteUnverified,
)

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_TIKTOK")
CONFIG_PATH = os.path.join(ROOT, "growth_config.json")
REGISTRO_CSV = os.path.join(ROOT, "registro_interacciones.csv")
METRICAS_CSV = os.path.join(ROOT, "metricas.csv")
ALLOWED_KINDS = {"follow", "like", "comment"}
COMMENT_LIMIT = 150  # techo operativo heredado; no se presenta como límite oficial actual.
_ENIE_RISK = {
    "anos", "anio", "senal", "senor", "senora", "manana", "mananas",
    "pequeno", "pequena", "espanol", "espanola", "nino", "nina", "diseno",
    "extrano", "extrana", "sueno", "otono", "dueno", "montana", "campana",
    "compania", "companero", "companera", "ensenar", "enganar", "empenar",
}


def _load_config():
    with open(CONFIG_PATH, encoding="utf-8") as stream:
        data = json.load(stream)
    if data.get("version") != 1 or data.get("mode") != "supervised_native":
        raise RuntimeError("growth_config TikTok incompatible")
    return data


def _check_spanish_orthography(text):
    from spellcheck_es import check_missing_accents
    problems = [word for word, _ in check_missing_accents(text)]
    words = re.findall(r"[a-záéíóúñü]+", text.casefold())
    problems += [word for word in words if word in _ENIE_RISK]
    if problems:
        raise ValueError(
            "posible tilde/ñ perdida en: " + ", ".join(sorted(set(problems)))
        )


_STRAY_TAIL = re.compile(r"(?:\s+[A-Z]{2,4}){2,}\s*$")


def _check_stray_tokens(text):
    """Corta artefactos tipo 'GT GT' al final (un comentario humano no acaba en siglas repetidas)."""
    words = text.split()
    if _STRAY_TAIL.search(text) or (len(words) >= 2 and words[-1].casefold() == words[-2].casefold()
                                    and len(words[-1]) <= 4 and words[-1].isalpha()):
        raise ValueError("el comentario acaba con tokens sueltos repetidos (p. ej. 'GT GT')")


def _valid_tiktok_url(url):
    return isinstance(url, str) and bool(
        re.match(r"^(?:https://(?:www\.)?(?:vm\.)?tiktok\.com/|tt://@[A-Za-z0-9._]{2,32}/\d+/[0-9a-f]{8}$)", url, re.I)
    )


def preflight_plan(plan, *, already_commented_urls=None):
    if not isinstance(plan, list):
        raise ValueError("plan.json debe contener una lista")
    already_commented_urls = set(
        sc.already_interacted_urls(REGISTRO_CSV)
        if already_commented_urls is None else already_commented_urls
    )
    validated = []
    action_keys = set()
    comment_texts = set()
    for index, raw in enumerate(plan, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"elemento {index}: debe ser objeto")
        item = dict(raw)
        kind = item.get("kind")
        if kind not in ALLOWED_KINDS:
            raise ValueError(f"elemento {index}: kind inválido {kind!r}")
        handle = item.get("handle")
        if not isinstance(handle, str):
            raise ValueError(f"elemento {index}: exige handle")
        handle = handle.strip().lstrip("@")
        if not re.fullmatch(r"[A-Za-z0-9._]{2,32}", handle):
            raise ValueError(f"elemento {index}: handle TikTok inválido")
        item["handle"] = handle

        if kind == "follow":
            key = ("follow", handle.casefold())
        else:
            url = item.get("url")
            if not _valid_tiktok_url(url):
                raise ValueError(f"elemento {index}: {kind} exige URL TikTok HTTPS")
            item["url"] = url.strip()
            key = (kind, item["url"])
        if key in action_keys:
            raise ValueError(f"elemento {index}: acción duplicada")
        action_keys.add(key)

        if kind == "comment":
            if item["url"] in already_commented_urls:
                raise ValueError(
                    f"elemento {index}: ya hay comentario confirmado para esa URL"
                )
            text = item.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"elemento {index}: comment exige texto")
            text = text.strip()
            sc.check_length(text, COMMENT_LIMIT)
            _check_stray_tokens(text)
            _check_spanish_orthography(text)
            hits = dup.check(text)
            if hits:
                raise ValueError(f"elemento {index}: texto duplicado - {hits[0]}")
            text_key = " ".join(text.split()).casefold()
            if text_key in comment_texts:
                raise ValueError(f"elemento {index}: comentario repetido en el plan")
            comment_texts.add(text_key)
            item["text"] = text
        validated.append(item)

    # Si un post ya tiene comentario, no añadir además like en el mismo lote.
    validated = sc.drop_stacked_actions(
        validated,
        cheap_kinds=("like",),
        rich_kinds=("comment",),
        key="url",
    )
    return validated


<<<<<<< HEAD
def _apply_action_ceiling(plan, config):
    ceiling = {k: max(0, int(v)) for k, v in config["action_ceiling"].items()}
    counts = {kind: 0 for kind in ALLOWED_KINDS}
=======
def _apply_action_ceiling(plan, config, *, used_today=None):
    ceiling = {k: max(0, int(v)) for k, v in config["action_ceiling"].items()}
    counts = {kind: int((used_today or {}).get(kind, 0)) for kind in ALLOWED_KINDS}
>>>>>>> origin/research/public-reuse-parent
    kept, skipped = [], []
    for item in plan:
        kind = item["kind"]
        if counts[kind] >= ceiling.get(kind, 0):
<<<<<<< HEAD
            skipped.append({**item, "resultado": "saltado_techo_sesion"})
=======
            reason = "saltado_techo_diario" if int((used_today or {}).get(kind, 0)) else "saltado_techo_sesion"
            skipped.append({**item, "resultado": reason})
>>>>>>> origin/research/public-reuse-parent
            continue
        counts[kind] += 1
        kept.append(item)
    return kept, skipped, ceiling


def _last_write_date():
    if not os.path.exists(REGISTRO_CSV) or os.path.getsize(REGISTRO_CSV) == 0:
        return None
    latest = None
    with open(REGISTRO_CSV, encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if (row.get("resultado") or "").strip().casefold() not in (
                "confirmado", "publicado",
            ):
                continue
            try:
                day = datetime.date.fromisoformat((row.get("fecha") or "").strip())
            except ValueError:
                continue
            if latest is None or day > latest:
                latest = day
    return latest


def _assert_session_spacing(config, *, today=None):
    today = today or datetime.date.today()
    minimum = max(0, int(config["session"]["min_days_between_write_sessions"]))
    last = _last_write_date()
    if last is not None and (today - last).days < minimum:
        raise RuntimeError(
            f"última escritura confirmada {last}; configuración exige "
            f"{minimum} día(s) entre sesiones"
        )


<<<<<<< HEAD
SOFT_FAILURES = (TikTokWriteUnverified, TikTokTargetNotFound)
=======
class TikTokPersistenceError(RuntimeError):
    """Registro local fallido: no reintentar una acción cuyo tap es incierto."""


SOFT_FAILURES = (TikTokTargetNotFound,)


def _optional_navigation(callback):
    """Solo fallos decorativos son prescindibles, nunca retos ni transporte."""
    try:
        callback()
    except (TikTokMobileChallenge, safety.SafetyWarning) as exc:
        safety.restrict("challenge")
        raise safety.SafetyBlocked("verificación detectada durante navegación auxiliar") from exc
    except TikTokWrongAccount as exc:
        safety.restrict("wrong_account")
        raise safety.SafetyBlocked("cuenta cambiada durante navegación auxiliar") from exc
    except MobileCliError as exc:
        safety.restrict("uncertain")
        raise safety.SafetyBlocked("estado del móvil incierto durante navegación auxiliar") from exc
    except (safety.SafetyBlocked, safety.SafetyStateError):
        raise  # nunca degradar una barrera ya activa a error decorativo
    except Exception:  # el contenido decorativo no determina el resultado de la acción
        pass
>>>>>>> origin/research/public-reuse-parent


def humanize_order(plan, rng=None, *, max_run=3):
    """Mezcla el orden y evita rachas largas de un mismo tipo: una persona alterna
    seguir, dar like y comentar."""
    rng = rng or random.Random()
    pending = list(plan)
    rng.shuffle(pending)
    out = []
    while pending:
        run_kind = out[-1]["kind"] if out else None
        run_len = 0
        for prev in reversed(out):
            if prev["kind"] != run_kind:
                break
            run_len += 1
        pick = next(
            (it for it in pending if not (it["kind"] == run_kind and run_len >= max_run)),
            pending[0],
        )
        pending.remove(pick)
        out.append(pick)
    return out


def _one_action(adapter, item):
<<<<<<< HEAD
    kind = item["kind"]
    if kind == "follow":
        outcome = adapter.follow(item["handle"])
        return "saltado_ya_seguido" if outcome == "already" else "confirmado"
    if kind == "like":
        outcome = adapter.like(item.get("post_ref") or item["url"])
        return "saltado_ya_like" if outcome == "already" else "confirmado"
    outcome = adapter.comment(item.get("post_ref") or item["url"], item["text"])
    return "saltado_ya_comentado" if outcome == "already" else "confirmado"
=======
    """Aceptar solo ACK explícitos del adaptador, nunca None/estado desconocido.

    Tras un tap incierto NO reintentar ni registrar confirmado: el ejecutor
    conserva la intención write-ahead y detiene el resto de la sesión.
    """
    kind = item["kind"]
    if kind == "follow":
        outcome = adapter.follow(item["handle"])
        if outcome == "already":
            return "saltado_ya_seguido"
        if outcome == "requested":
            return "pendiente_aprobacion"
        if outcome == "followed":
            return "confirmado"
    elif kind == "like":
        outcome = adapter.like(item.get("post_ref") or item["url"])
        if outcome == "already":
            return "saltado_ya_like"
        if outcome == "created":
            return "confirmado"
    elif kind == "comment":
        # Un post_ref de cuadrícula (ordinal + caption) no es un ID remoto estable.
        # Para texto con prueba, publicar únicamente mediante el permalink
        # que figura en la certificación, nunca sobre una posición de la cuadrícula.
        target = item["url"] if item.get("gpt_proof") else (item.get("post_ref") or item["url"])
        outcome = adapter.comment(target, item["text"])
        if outcome == "already":
            return "saltado_ya_comentado"
        if outcome == "created":
            return "confirmado"
    else:
        raise ValueError(f"kind TikTok desconocido: {kind!r}")
    raise TikTokWriteUnverified(
        f"resultado TikTok no acreditado ({kind}, {type(outcome).__name__}); no reintentar"
    )
>>>>>>> origin/research/public-reuse-parent


def run_plan(
    plan, adapter, *, pause=True, pace=None, behavior=None, on_result=None,
    max_minutes=None, clock=time.monotonic, sleep=time.sleep,
):
    """Ejecuta el plan con ritmo humano. Cada resultado se persiste al instante (`on_result`)
    para no perder acciones confirmadas si la sesión larga se corta. Ante cualquier estado
    inesperado, parada total (sin reintentos de escrituras)."""
    import reply_writer as _rw
    plan = _rw.require_gpt(plan, "tiktok")      # 08/10: nunca se publica texto que no venga de ChatGPT
    results = []
    start = clock()
    soft_failures = 0
<<<<<<< HEAD

    def record(entry):
        results.append(entry)
        print(f"[{len(results)}] {entry.get('kind')} @{entry.get('handle')} -> {str(entry.get('resultado'))[:140]}",
              file=sys.stderr, flush=True)
        if on_result is not None:
            on_result(entry)

    for index, item in enumerate(plan):
=======
    intent_opened = 0
    intent_closed = 0
    follow_blocked = False        # 09/10: limite de seguir de TikTok => se saltan los follows y se sigue con like/comment

    def screen_shows_follow_limit():
        try:
            safety.check_screen(adapter._tree())
        except safety.SafetyFollowLimit:
            return True
        except Exception:      # noqa: BLE001
            return False
        return False

    def record(entry, *, persist=True):
        nonlocal intent_closed
        if persist and on_result is not None:
            try:
                on_result(entry)
            except Exception as exc:
                raise TikTokPersistenceError("no se pudo registrar el resultado") from exc
            if entry.get("_intent_id") and _persistable(entry) and entry.get("resultado") != "pendiente_verificacion":
                intent_closed += 1
        # No anunciar confirmaciones o cierres antes de fsync. El resumen de
        # mechanical_round se calcula a partir del texto del ejecutor.
        print(f"[{len(results)+1}] {entry.get('kind')} @{entry.get('handle')} -> {str(entry.get('resultado'))[:140]}",
              file=sys.stderr, flush=True)
        results.append(entry)

    for index, item in enumerate(plan):
        # TikTok comparte cortacircuitos con el resto, además del cooldown
        # móvil: una queja sobrevenida detiene las acciones siguientes.
        import circuit_breaker as _cb
        _allowed, _reason = _cb.write_preflight("tiktok")
        if not _allowed:
            print(f"[tiktok] cortacircuitos ABIERTO: {_reason}; fin del lote", file=sys.stderr)
            break
>>>>>>> origin/research/public-reuse-parent
        if max_minutes is not None and (clock() - start) / 60.0 >= max_minutes:
            for pending in plan[index:]:
                record({**pending, "resultado": "no_intentado_tiempo_sesion"})
            break
        import conversation_turn_policy as ctp
        permitted, reason = ctp.check_execution("tiktok", item)
        if not permitted:
            record({**item, "resultado": f"saltado_cierre_conversacion:{reason}"})
            continue
<<<<<<< HEAD
        try:
=======
        if item.get("kind") == "follow" and (follow_blocked or safety.follow_paused()):
            follow_blocked = True
            record({**item, "resultado": "saltado_limite_follow"})
            continue
        try:
            safety.require_writable(kind=item.get("kind"))
            if hasattr(adapter, "_tree"):
                try:
                    safety.check_screen(adapter._tree())
                except safety.SafetyFollowLimit:
                    safety.restrict("follow_limit")
                    follow_blocked = True
                    if item.get("kind") == "follow":
                        record({**item, "resultado": "saltado_limite_follow"})
                        continue
>>>>>>> origin/research/public-reuse-parent
            if item.get("kind") == "like":
                import like_context_policy as lcp
                allowed, why = lcp.check_execution("tiktok", item)
                if not allowed:
                    record({**item, "resultado": f"saltado_like_contexto:{why}"})
                    continue
<<<<<<< HEAD
            record({**item, "resultado": _one_action(adapter, item)})
            soft_failures = 0
        except SOFT_FAILURES as exc:
=======
            # Intención write-ahead única: el cierre se vincula por id y nunca
            # borra ni modifica CSV anterior. Un crash deja pending y bloquea retry.
            if on_result is not None:
                item = {**item, "_intent_id": secrets.token_hex(16)}
                try:
                    on_result({**item, "resultado": "pendiente_verificacion"})
                    intent_opened += 1
                except Exception as exc:
                    raise TikTokPersistenceError("no se pudo guardar intención previa") from exc
            record({**item, "resultado": _one_action(adapter, item)})
            soft_failures = 0
        except TikTokPersistenceError:
            raise
        except TikTokWriteUnverified:
            if item.get("kind") == "follow" and screen_shows_follow_limit():
                safety.restrict("follow_limit")
                follow_blocked = True
                record({**item, "resultado": "saltado_limite_follow"})
                continue
            # La intención write-ahead ya es duradera. No escribir otra apertura
            # con el mismo intent_id: el ACK incierto conserva el bloqueo original.
            record({**item, "resultado": "pendiente_verificacion"},
                   persist=not bool(item.get("_intent_id")))
            for pending in plan[index + 1:]:
                record({**pending, "resultado": "no_intentado"})
            break
        except (TikTokMobileChallenge, safety.SafetyWarning) as exc:
            safety.restrict("challenge" if isinstance(exc, TikTokMobileChallenge) else "rate")
            record({**item, "resultado": f"parada:{type(exc).__name__}"})
            for pending in plan[index + 1:]:
                record({**pending, "resultado": "no_intentado"})
            break
        except SOFT_FAILURES as exc:
            # El adaptador comprueba like_contexto antes del tap. Cierre seguro
            # del intento: nunca hubo escritura remota. Otros fallos quedan
            # pendientes para revisión humana (pueden ser inciertos).
            if (item.get("kind") == "like" and isinstance(exc, TikTokTargetNotFound)
                    and str(exc).startswith("like_contexto:")):
                record({**item, "resultado": "saltado_like_contexto:" + str(exc).split(":", 1)[1]})
                soft_failures = 0
                continue
>>>>>>> origin/research/public-reuse-parent
            # No verificado/objetivo ausente: no sabemos el estado de ESA acción, pero la sesión
            # puede seguir; tras 3 seguidos algo va mal (UI cambiada, throttle) y se para.
            record({**item, "resultado": f"fallo:{type(exc).__name__}:{exc}"})
            soft_failures += 1
            if soft_failures >= 3:
                for pending in plan[index + 1:]:
                    record({**pending, "resultado": "no_intentado"})
                break
<<<<<<< HEAD
            try:
                if behavior is not None:
                    behavior.recover()
            except Exception:  # noqa: BLE001
                pass
        except Exception as exc:  # noqa: BLE001  (challenge/cuenta/foreground: parada total)
            record({**item, "resultado": f"parada:{type(exc).__name__}:{exc}"})
=======
            if behavior is not None:
                _optional_navigation(behavior.recover)
        except Exception as exc:  # noqa: BLE001  (sin retry automático)
            if isinstance(exc, TikTokWrongAccount):
                safety.restrict("wrong_account")
            result = "pendiente_verificacion" if isinstance(exc, MobileCliError) else f"parada:{type(exc).__name__}"
            # MobileCliError también puede ocurrir tras el tap. La apertura previa
            # basta: un duplicado de pendiente corrompería la máquina append-only.
            record({**item, "resultado": result},
                   persist=not (result == "pendiente_verificacion" and bool(item.get("_intent_id"))))
>>>>>>> origin/research/public-reuse-parent
            for pending in plan[index + 1:]:
                record({**pending, "resultado": "no_intentado"})
            break

        long_break = pace.register_action() if pace is not None else None
        if pause and index < len(plan) - 1:
            gap = pace.action_gap() if pace is not None else float(random.uniform(40, 90))
            if behavior is not None:
<<<<<<< HEAD
                try:
                    behavior.browse(gap * random.uniform(0.35, 0.7))
                except Exception:  # noqa: BLE001  (navegar es decorativo)
                    pass
=======
                _optional_navigation(lambda: behavior.browse(gap * random.uniform(0.35, 0.7)))
>>>>>>> origin/research/public-reuse-parent
                sleep(gap * 0.2)
            else:
                sleep(gap)
            if long_break:
                if behavior is not None:
<<<<<<< HEAD
                    try:
                        behavior.browse(long_break * 0.5)
                    except Exception:  # noqa: BLE001
                        pass
                sleep(long_break * 0.5)
    return results


def _append_registro_one(item):
    if item.get("resultado") == "confirmado":
=======
                    _optional_navigation(lambda: behavior.browse(long_break * 0.5))
                sleep(long_break * 0.5)
    if on_result is not None:
        unresolved = intent_opened - intent_closed
        # Sin cierre NO implica necesariamente huérfana: puede ser ACK incierto.
        print(f"TIKTOK_INTENTS opened={intent_opened} closed={intent_closed} "
              f"unresolved={unresolved}", file=sys.stderr, flush=True)
    return results


def _persistable(item):
    result = str(item.get("resultado") or "")
    return result in ("confirmado", "pendiente_verificacion") or (
        bool(item.get("_intent_id")) and result in
        ("saltado_ya_like", "saltado_ya_seguido", "saltado_ya_comentado", "pendiente_aprobacion") or (
            bool(item.get("_intent_id")) and result.startswith("saltado_like_contexto:")
        )
    )


def _append_registro_one(item):
    if _persistable(item):
>>>>>>> origin/research/public-reuse-parent
        _append_registro([item])


def _append_registro(results):
<<<<<<< HEAD
    if not any(item.get("resultado") == "confirmado" for item in results):
        return
    day = datetime.date.today().isoformat()
    with open(REGISTRO_CSV, "a", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        for item in results:
            if item.get("resultado") != "confirmado":
=======
    if not any(_persistable(item) for item in results):
        return
    day = datetime.date.today().isoformat()
    header = ["fecha", "cuenta", "tipo", "post_resumen", "texto_usado", "resultado", "notas"]
    new = not os.path.exists(REGISTRO_CSV) or os.path.getsize(REGISTRO_CSV) == 0
    if not new:
        # Un CSV legacy con otras columnas puede leerse para auditar, pero
        # anexarle nuestras 7 columnas rompería su interpretación futura.
        with open(REGISTRO_CSV, encoding="utf-8-sig", newline="") as existing:
            if next(csv.reader(existing), None) != header:
                raise TikTokPersistenceError("cabecera de registro incompatible con escritura")
    with open(REGISTRO_CSV, "a", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        if new:
            writer.writerow(header)
        for item in results:
            if not _persistable(item):
>>>>>>> origin/research/public-reuse-parent
                continue
            target_summary = item.get("url") or item.get("post_resumen") or ""
            caption = " ".join(str(item.get("post_resumen") or "").split())[:240]
            notes = item.get("motivo", "") + " | transporte=android_native"
<<<<<<< HEAD
=======
            if item.get("_intent_id"):
                if not re.fullmatch(r"[0-9a-f]{32}", item["_intent_id"]):
                    raise TikTokPersistenceError("identificador de intención inválido")
                notes += " | intent_id=" + item["_intent_id"]
>>>>>>> origin/research/public-reuse-parent
            if item.get("url") and caption:
                notes += " | caption=" + caption
            writer.writerow([
                day,
                "@" + item["handle"].lstrip("@"),
                item["kind"],
                target_summary,
                item.get("text", ""),
<<<<<<< HEAD
                "confirmado",
                notes,
            ])
=======
                item["resultado"],
                notes,
            ])
        stream.flush()
        os.fsync(stream.fileno())


def _session_has_uncertain_result(results):
    """Un follow saltado por aviso DESPUÉS de la intención sigue siendo incierto."""
    return any(
        str(item.get("resultado", "")).startswith(("parada:", "fallo:"))
        or item.get("resultado") in ("pendiente_verificacion", "no_intentado")
        or (item.get("_intent_id") and item.get("resultado") == "saltado_limite_follow")
        for item in results
    )
>>>>>>> origin/research/public-reuse-parent


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="habilita escrituras reales tras preflight; sin esto solo valida",
    )
    parser.add_argument("--device", default=os.getenv("ANDROID_DEVICE_ID"))
    args = parser.parse_args(argv)

    with open(args.plan, encoding="utf-8") as stream:
        raw_plan = json.load(stream)
    config = _load_config()
    try:
        plan = preflight_plan(raw_plan)
<<<<<<< HEAD
        kept, skipped, ceiling = _apply_action_ceiling(plan, config)
=======
        used_today, pending = safety.recorded_actions(REGISTRO_CSV)
        for item in plan:
            key = (item["kind"], item["handle"].casefold() if item["kind"] == "follow" else item["url"])
            if key in pending:
                raise ValueError("hay una acción incierta para este objetivo: revisar antes de repetir")
        kept, skipped, ceiling = _apply_action_ceiling(plan, config, used_today=used_today)
>>>>>>> origin/research/public-reuse-parent
        if args.apply:
            _assert_session_spacing(config)
    except Exception as exc:
        print(f"FALLO DE PREFLIGHT: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print(
        "PREFLIGHT OK | "
        f"plan={len(plan)} ejecutar={len(kept)} saltados_techo={len(skipped)} "
        f"| techo={ceiling}"
    )
    if not args.apply:
        print("DRY-RUN: no se abrió TikTok y no hubo escrituras. Añadir --apply para ejecutar.")
        return 0
<<<<<<< HEAD
=======
    if not kept:
        print("[tiktok] sin acciones ejecutables; no se abre el móvil")
        safety.step_status("no_budget")
        return 0
>>>>>>> origin/research/public-reuse-parent

    session = config.get("session") or {}
    rng = random.Random()
    profile = HumanProfile(**config["human"]) if config.get("human") else HumanProfile()
    try:
        with mobile_session_lock():
<<<<<<< HEAD
=======
            # La cuota calculada en preflight puede quedar obsoleta mientras
            # otra sesión ocupa el móvil: releerla bajo el mismo lock.
            # Con pausa solo de follows (09/10) basta con que pueda escribir like/comment; run_plan salta los follows.
            safety.require_writable(kind="like" if any(i["kind"] != "follow" for i in kept) else None)
            locked_usage, locked_pending = safety.recorded_actions(REGISTRO_CSV)
            for item in kept:
                key = (item["kind"], item["handle"].casefold() if item["kind"] == "follow" else item["url"])
                if key in locked_pending:
                    raise safety.SafetyStateError("acción incierta detectada al tomar el lock")
            kept, just_skipped, _ = _apply_action_ceiling(kept, config, used_today=locked_usage)
            skipped.extend(just_skipped)
            if not kept:
                print("[tiktok] la cuota cambió mientras se esperaba el móvil: ninguna escritura")
                safety.step_status("no_budget")
                return 0
>>>>>>> origin/research/public-reuse-parent
            raw = ensure_server(device_id=args.device)
            client = HumanClient(raw, profile, rng)
            adapter = TikTokMobileAdapter(client, args.device, allow_writes=True)
            pace = Pace(profile, rng)
            behavior = Behavior(adapter, pace, rng)
            adapter.behavior = behavior
<<<<<<< HEAD
            adapter.verify_active_account(MY_HANDLE)
            behavior.browse(rng.uniform(*(session.get("warmup_s") or [45, 150])))
=======
            try:
                adapter.verify_active_account(MY_HANDLE)
                behavior.browse(rng.uniform(*(session.get("warmup_s") or [45, 150])))
            except TikTokWrongAccount:
                safety.restrict("wrong_account")
                raise
            except TikTokMobileChallenge:
                safety.restrict("challenge")
                raise
            except MobileCliError:
                safety.restrict("uncertain")
                raise
>>>>>>> origin/research/public-reuse-parent
            results = run_plan(
                humanize_order(kept, rng), adapter, pace=pace, behavior=behavior,
                on_result=_append_registro_one, max_minutes=session.get("max_minutes"),
            )
<<<<<<< HEAD
            try:
                behavior.browse(rng.uniform(*(session.get("cooldown_s") or [20, 60])))
            except Exception:  # noqa: BLE001
                pass
    except Exception as exc:
        print(f"PARADA ANTES DE ESCRIBIR: {type(exc).__name__}: {exc}", file=sys.stderr)
=======
            # No navegar después de challenge, parada o escritura incierta.
            stopped = _session_has_uncertain_result(results)
            if not stopped:
                _optional_navigation(lambda: behavior.browse(rng.uniform(*(session.get("cooldown_s") or [20, 60]))))
    except MobileSessionBusy:
        print("MobileSessionBusy: móvil ocupado", file=sys.stderr)
        safety.step_status("busy")
        return 3
    except safety.SafetyBlocked:
        print("PARADA: TikTok requiere revisión manual", file=sys.stderr)
        safety.step_status("restricted")
        return 4
    except Exception as exc:
        print(f"PARADA_LOCAL: {type(exc).__name__}; estado incierto", file=sys.stderr)
        safety.step_status("local_error")
>>>>>>> origin/research/public-reuse-parent
        return 5

    results += skipped
    for item in results:
        print(
            f"{item.get('resultado','?'):35s} "
            f"{item.get('kind','?'):8s} @{item.get('handle','')}"
        )

<<<<<<< HEAD
    if any(str(item.get("resultado", "")).startswith("parada:") for item in results):
=======
    if _session_has_uncertain_result(results):
>>>>>>> origin/research/public-reuse-parent
        print(
            "PARADA TOTAL: se guardaron únicamente acciones ya confirmadas. "
            "No se navega de nuevo para métricas."
        )
<<<<<<< HEAD
=======
        labels = [str(item.get("resultado", "")) for item in results]
        if any("TikTokMobileChallenge" in x or "SafetyWarning" in x for x in labels):
            status = "restricted"
        elif "pendiente_verificacion" in labels or any(
                x.get("_intent_id") and x.get("resultado") == "saltado_limite_follow"
                for x in results):
            status = "uncertain"
        else:
            status = "local_error"
        safety.step_status(status)
>>>>>>> origin/research/public-reuse-parent
        return 5
    print(
        "Sesión finalizada. registro_interacciones.csv actualizado solo con "
        "escrituras confirmadas; métricas de perfil no se inventan ni se actualizan "
        "hasta validar un parser nativo específico."
    )
<<<<<<< HEAD
=======
    safety.step_status("completed")
>>>>>>> origin/research/public-reuse-parent
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
