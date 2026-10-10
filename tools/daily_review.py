"""Informe diario de las redes, sin consumo de IA (06/10/2026, David: que el sistema se revise y se mejore solo, sin que haya que pedirlo).

Reune en `00_OPERATIVO/INFORME_DIARIO.md` lo que cada red dejo hoy: acciones por tipo y seguidores (de los registros y metricas), los HUECOS que detecto su autoauditoria (con cuantos dias
seguidos llevan abiertos, `historial_huecos.csv`), la etapa de la rampa y las publicaciones pendientes. Es el unico fichero que hay que mirar: un hueco que lleva varios dias es lo que toca
arreglar en la siguiente sesion de mejora. Lo lanza la tarea `RRSS_informe_diario` (23:55) y se puede ejecutar a mano.

    python tools/daily_review.py
"""
import csv
import datetime
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "00_OPERATIVO", "INFORME_DIARIO.md")
HISTORY = os.path.join(ROOT, "00_OPERATIVO", "historial_huecos.csv")
NETWORKS = ["bluesky", "mastodon", "threads"]


def _csv(path):
    try:
        with open(path, encoding="utf-8", newline="") as stream:
            return list(csv.DictReader(stream))
    except OSError:
        return []


def day_counts(net, day):
    rows = [r for r in _csv(os.path.join(ROOT, f"SISTEMA_DIARIO_{net.upper()}", "registro_interacciones.csv"))
            if (r.get("fecha") or "")[:10] == day and (r.get("resultado") or "") in ("confirmado", "publicado")]
    return Counter((r.get("tipo") or "?").split("+")[0] for r in rows)


def followers_series(net, days=7):
    out = []
    for row in _csv(os.path.join(ROOT, f"SISTEMA_DIARIO_{net.upper()}", "metricas.csv"))[-40:]:
        value = str(row.get("seguidores") or "").replace(".", "").replace(",", "")
        if value.isdigit():
            out.append((row.get("fecha"), int(value)))
    return out[-days:]


def audit(net):
    path = os.path.join(ROOT, f"SISTEMA_DIARIO_{net.upper()}", "cache", "audit_latest.json")
    try:
        with open(path, encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, ValueError):
        return {}


def gap_key(text):
    return " ".join(str(text).split())[:70]


def update_history(today, found):
    """Anota los huecos de hoy y devuelve {(red, hueco): dias seguidos abiertos}."""
    rows = _csv(HISTORY)
    rows = [r for r in rows if r.get("fecha") != today]
    rows += [{"fecha": today, "red": net, "hueco": key} for net, key in found]
    with open(HISTORY, "w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["fecha", "red", "hueco"])
        writer.writeheader()
        writer.writerows(rows[-3000:])
    by_key = {}
    for row in rows:
        by_key.setdefault((row["red"], row["hueco"]), set()).add(row["fecha"])
    streaks = {}
    day = datetime.date.fromisoformat(today)
    for key, dates in by_key.items():
        n, cursor = 0, day
        while cursor.isoformat() in dates:
            n += 1
            cursor -= datetime.timedelta(days=1)
        streaks[key] = n
    return streaks


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    today = datetime.date.today().isoformat()
    found, sections = [], []
    import volume_ramp as vr
    for net in NETWORKS:
        counts = day_counts(net, today)
        series = followers_series(net)
        stage = vr.current(network=net)
        data = audit(net)
        gaps = [g.get("gap", "") for g in data.get("gaps", [])]
        found += [(net, gap_key(g)) for g in gaps]
        gain = f"{series[0][1]} -> {series[-1][1]} en {len(series)} registros" if len(series) >= 2 else "sin serie"
        sections.append((net, stage, counts, gain, gaps))
    streaks = update_history(today, found)
    lines = [f"# Informe diario {today}", "", "Lo genera `tools/daily_review.py` (tarea `RRSS_informe_diario`, 23:55; sin IA). Un hueco con muchos dias seguidos es lo primero a arreglar.", ""]
    for net, stage, counts, gain, gaps in sections:
        total = sum(counts.values())
        lines += [f"## {net.capitalize()}", f"- Etapa {stage['stage']} (objetivo {stage['daily']}/dia): hoy {total} acciones {dict(counts)}", f"- Seguidores: {gain}"]
        if gaps:
            lines.append("- Huecos abiertos:")
            for gap in gaps:
                lines.append(f"  - ({streaks.get((net, gap_key(gap)), 1)} d) {gap[:200]}")
        else:
            lines.append("- Sin huecos detectados por la autoauditoria.")
        lines.append("")
    pending_path = os.path.join(ROOT, "00_OPERATIVO", "PENDIENTES_PUBLICACION.md")
    try:
        with open(pending_path, encoding="utf-8") as stream:
            pending = [ln.rstrip() for ln in stream if ln.startswith("- **VENCIDA**") or ln.startswith("## ")]
    except OSError:
        pending = []
    vencidas = sum(1 for ln in pending if ln.startswith("- **VENCIDA**"))
    lines += ["## Publicaciones", f"- {vencidas} ficha(s) vencidas sin publicar (detalle en `PENDIENTES_PUBLICACION.md`)", ""]
    lines += extra_sections(today)
    with open(OUT, "w", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


def extra_sections(today):
    """07/10: rondas del dia por estado, fidelizacion por red, follow-back de TikTok por fuente y cola de respuestas (para vigilar que TODAS las redes avanzan igual)."""
    out = []
    # VER_ESTADO_RONDAS.bat llama a este informe; sin depender del futuro HTML.
    try:
        from plan_failure_events import collect_alerts
        alerts = collect_alerts(ROOT)
        if alerts:
            out += ["## Alertas de plan (últimas 2 h)", ""]
        for alert in alerts:
            out.append(f"- {alert['code']} | {alert['network']}: "
                       f"{alert['count']} fallos en 2 h; último "
                       f"{alert['last_stage']} ({alert['last_cause']}); "
                       f"log {alert['last_log_name']}")
    except OSError:
        out.append("- Alertas de plan: lectura no disponible")
    try:
        with open(os.path.join(ROOT, "00_OPERATIVO", "tiempos_rondas.csv"), encoding="utf-8", newline="") as stream:
            rows = [r for r in csv.DictReader(stream) if r.get("fecha") == today]
        states = {}
        for row in rows:
            states.setdefault(row["red"], {}).setdefault(row["estado"], 0)
            states[row["red"]][row["estado"]] += 1
        out += ["## Rondas del dia (estado por red)", ""] + [f"- {net}: {dict(v)}" for net, v in sorted(states.items())] + [""]
    except OSError:
        pass
    try:
        import loyalty
        out += ["## Fidelizacion (cuentas que nos dan algo y premios)", "", loyalty.report(), ""]
    except Exception as exc:
        out += [f"## Fidelizacion: no disponible ({type(exc).__name__})", ""]
    try:
        with open(os.path.join(ROOT, "SISTEMA_DIARIO_TIKTOK", "reciprocity_audit.json"), encoding="utf-8") as stream:
            audit_tt = json.load(stream)
        out += [f"## TikTok: follow-back por fuente (auditoria {audit_tt.get('date')})", ""]
        out += [f"- {src}: {e['followed']} seguidas, {e['back']} devueltas ({e['rate']:.0%})" for src, e in list(audit_tt.get("sources", {}).items())[:10]] + [""]
    except (OSError, ValueError):
        pass
    try:
        import reply_queue
        answers = reply_queue._load(reply_queue.ANSWERS)
        out += ["## Cola de respuestas de ChatGPT", "", f"- pendientes {len(reply_queue._load(reply_queue.PENDING))}, respuestas utiles {sum(1 for v in answers.values() if v.get('reply'))}, descartadas {sum(1 for v in answers.values() if not v.get('reply'))}", ""]
    except Exception:
        pass
    # Telemetría transversal y solo lectura: mide edad del POST DESTINO, no
    # la fecha de encolado. Ausencia de un plan != cero candidatos recientes.
    try:
        import post_age_distribution
        out += post_age_distribution.daily_lines(ROOT)
    except (OSError, ValueError, TypeError) as exc:
        out += [f"## Antigüedad de posts: no disponible ({type(exc).__name__})", ""]
    return out


if __name__ == "__main__":
    raise SystemExit(main())
