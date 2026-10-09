"""Ejecutor supervisado de interacciones TikTok sobre Android nativo.

Por defecto SOLO hace preflight. Las escrituras requieren --apply. Antes de tocar la
app valida el lote entero, límites de proyecto, textos, duplicados y targets. Ya en
el móvil verifica la cuenta @autorademoescritor. Cualquier challenge, cuenta errónea,
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
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import check_duplicate_phrase as dup
import scan_common as sc
from mobile_client import MobileCliError
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


def _apply_action_ceiling(plan, config):
    ceiling = {k: max(0, int(v)) for k, v in config["action_ceiling"].items()}
    counts = {kind: 0 for kind in ALLOWED_KINDS}
    kept, skipped = [], []
    for item in plan:
        kind = item["kind"]
        if counts[kind] >= ceiling.get(kind, 0):
            skipped.append({**item, "resultado": "saltado_techo_sesion"})
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


SOFT_FAILURES = (TikTokWriteUnverified, TikTokTargetNotFound)


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
    kind = item["kind"]
    if kind == "follow":
        outcome = adapter.follow(item["handle"])
        return "saltado_ya_seguido" if outcome == "already" else "confirmado"
    if kind == "like":
        outcome = adapter.like(item.get("post_ref") or item["url"])
        return "saltado_ya_like" if outcome == "already" else "confirmado"
    outcome = adapter.comment(item.get("post_ref") or item["url"], item["text"])
    return "saltado_ya_comentado" if outcome == "already" else "confirmado"


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

    def record(entry):
        results.append(entry)
        print(f"[{len(results)}] {entry.get('kind')} @{entry.get('handle')} -> {str(entry.get('resultado'))[:140]}",
              file=sys.stderr, flush=True)
        if on_result is not None:
            on_result(entry)

    for index, item in enumerate(plan):
        if max_minutes is not None and (clock() - start) / 60.0 >= max_minutes:
            for pending in plan[index:]:
                record({**pending, "resultado": "no_intentado_tiempo_sesion"})
            break
        import conversation_turn_policy as ctp
        permitted, reason = ctp.check_execution("tiktok", item)
        if not permitted:
            record({**item, "resultado": f"saltado_cierre_conversacion:{reason}"})
            continue
        try:
            if item.get("kind") == "like":
                import like_context_policy as lcp
                allowed, why = lcp.check_execution("tiktok", item)
                if not allowed:
                    record({**item, "resultado": f"saltado_like_contexto:{why}"})
                    continue
            record({**item, "resultado": _one_action(adapter, item)})
            soft_failures = 0
        except SOFT_FAILURES as exc:
            # No verificado/objetivo ausente: no sabemos el estado de ESA acción, pero la sesión
            # puede seguir; tras 3 seguidos algo va mal (UI cambiada, throttle) y se para.
            record({**item, "resultado": f"fallo:{type(exc).__name__}:{exc}"})
            soft_failures += 1
            if soft_failures >= 3:
                for pending in plan[index + 1:]:
                    record({**pending, "resultado": "no_intentado"})
                break
            try:
                if behavior is not None:
                    behavior.recover()
            except Exception:  # noqa: BLE001
                pass
        except Exception as exc:  # noqa: BLE001  (challenge/cuenta/foreground: parada total)
            record({**item, "resultado": f"parada:{type(exc).__name__}:{exc}"})
            for pending in plan[index + 1:]:
                record({**pending, "resultado": "no_intentado"})
            break

        long_break = pace.register_action() if pace is not None else None
        if pause and index < len(plan) - 1:
            gap = pace.action_gap() if pace is not None else float(random.uniform(40, 90))
            if behavior is not None:
                try:
                    behavior.browse(gap * random.uniform(0.35, 0.7))
                except Exception:  # noqa: BLE001  (navegar es decorativo)
                    pass
                sleep(gap * 0.2)
            else:
                sleep(gap)
            if long_break:
                if behavior is not None:
                    try:
                        behavior.browse(long_break * 0.5)
                    except Exception:  # noqa: BLE001
                        pass
                sleep(long_break * 0.5)
    return results


def _append_registro_one(item):
    if item.get("resultado") == "confirmado":
        _append_registro([item])


def _append_registro(results):
    if not any(item.get("resultado") == "confirmado" for item in results):
        return
    day = datetime.date.today().isoformat()
    with open(REGISTRO_CSV, "a", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        for item in results:
            if item.get("resultado") != "confirmado":
                continue
            target_summary = item.get("url") or item.get("post_resumen") or ""
            caption = " ".join(str(item.get("post_resumen") or "").split())[:240]
            notes = item.get("motivo", "") + " | transporte=android_native"
            if item.get("url") and caption:
                notes += " | caption=" + caption
            writer.writerow([
                day,
                "@" + item["handle"].lstrip("@"),
                item["kind"],
                target_summary,
                item.get("text", ""),
                "confirmado",
                notes,
            ])


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
        kept, skipped, ceiling = _apply_action_ceiling(plan, config)
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

    session = config.get("session") or {}
    rng = random.Random()
    profile = HumanProfile(**config["human"]) if config.get("human") else HumanProfile()
    try:
        with mobile_session_lock():
            raw = ensure_server(device_id=args.device)
            client = HumanClient(raw, profile, rng)
            adapter = TikTokMobileAdapter(client, args.device, allow_writes=True)
            pace = Pace(profile, rng)
            behavior = Behavior(adapter, pace, rng)
            adapter.behavior = behavior
            adapter.verify_active_account(MY_HANDLE)
            behavior.browse(rng.uniform(*(session.get("warmup_s") or [45, 150])))
            results = run_plan(
                humanize_order(kept, rng), adapter, pace=pace, behavior=behavior,
                on_result=_append_registro_one, max_minutes=session.get("max_minutes"),
            )
            try:
                behavior.browse(rng.uniform(*(session.get("cooldown_s") or [20, 60])))
            except Exception:  # noqa: BLE001
                pass
    except Exception as exc:
        print(f"PARADA ANTES DE ESCRIBIR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 5

    results += skipped
    for item in results:
        print(
            f"{item.get('resultado','?'):35s} "
            f"{item.get('kind','?'):8s} @{item.get('handle','')}"
        )

    if any(str(item.get("resultado", "")).startswith("parada:") for item in results):
        print(
            "PARADA TOTAL: se guardaron únicamente acciones ya confirmadas. "
            "No se navega de nuevo para métricas."
        )
        return 5
    print(
        "Sesión finalizada. registro_interacciones.csv actualizado solo con "
        "escrituras confirmadas; métricas de perfil no se inventan ni se actualizan "
        "hasta validar un parser nativo específico."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
