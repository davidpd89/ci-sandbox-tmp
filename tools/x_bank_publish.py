"""X: un post propio conversacional al dia desde un banco escrito a mano (06/10/2026).

Motivo (GPT 06/10, codigo abierto del algoritmo de X): el For You tiene un impulso para autores nuevos pero necesita material propio; la cuenta solo hacia interaccion saliente y las fichas
largas salen pocas veces a la semana. El banco `00_OPERATIVO/x_posts_banco.json` son preguntas y observaciones cortas de lector/escritor (sin experiencias personales inventadas, sin
enlaces, sin promocion); se publica UNA al dia como maximo y nunca la misma. El texto se relee en el perfil tras publicar (`x_interact.post` devuelve el permalink).

    python tools/x_bank_publish.py            # ensayo: dice cual publicaria
    python tools/x_bank_publish.py --apply    # publica
"""
import csv
import datetime
import json
import os
import random
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(__file__))

ROOT = os.path.join(os.path.dirname(__file__), "..")
BANK = os.path.join(ROOT, "00_OPERATIVO", "x_posts_banco.json")
LOG = os.path.join(ROOT, "SISTEMA_DIARIO_X", "posts_banco.csv")
MIN_GAP_HOURS = 6        # entre dos posts propios automaticos (banco o fichas)


def load_bank(path=None):
    with open(path or BANK, encoding="utf-8") as stream:
        return json.load(stream)


def _madrid_naive(when):
    """Los CSV históricos sin offset se interpretan como hora local de Madrid."""
    if when.tzinfo is not None and when.utcoffset() is not None:
        return when.astimezone(ZoneInfo("Europe/Madrid")).replace(tzinfo=None)
    return when


def conservative_elapsed_seconds(now, previous):
    """Mínimo tiempo real transcurrido, incluso ante horas locales DST ambiguas.

    Los CSV antiguos guardan Madrid sin offset. En otoño una hora puede
    corresponder a dos instantes UTC: usamos el inicio más tardío y el
    final más temprano para NO publicar antes del mínimo. En primavera
    la hora salta y la resta ingenua de reloj sobrestima el tiempo.
    """
    madrid = ZoneInfo("Europe/Madrid")

    def candidates(value):
        wall = _madrid_naive(value)
        return [wall.replace(tzinfo=madrid, fold=fold).astimezone(datetime.timezone.utc)
                for fold in (0, 1)]

    return (min(candidates(now)) - max(candidates(previous))).total_seconds()


def read_log(path=None, *, strict=False):
    """Lee el banco; en preflight estricto un CSV roto nunca equivale a vacío."""
    rows = []
    try:
        with open(path or LOG, encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=strict)
            required = {"fecha_hora", "id", "texto", "url"}
            if strict and (not reader.fieldnames or
                           not required.issubset(reader.fieldnames) or
                           len(reader.fieldnames) != len(set(reader.fieldnames))):
                raise ValueError("cabecera del registro de X banco inválida")
            for row in reader:
                # DictReader acepta filas cortas y guarda extras bajo clave None.
                if strict and (None in row or any(
                        not (row.get(key) or "").strip() for key in required)):
                    raise ValueError("registro de X banco con fila incompleta")
                try:
                    when = _madrid_naive(datetime.datetime.fromisoformat(row["fecha_hora"]))
                except (ValueError, KeyError, TypeError):
                    if strict:
                        raise ValueError("registro de X banco con fecha inválida") from None
                    continue
                rows.append({**row, "when": when})
    except FileNotFoundError:
        # CSV ausente con carpeta existente: primer día legítimo.
        # Carpeta desaparecida: posible pérdida completa del historial.
        if strict and not os.path.isdir(
                os.path.dirname(os.path.abspath(path or LOG))):
            raise
    except (csv.Error, UnicodeError):
        if strict:
            raise ValueError("registro de X banco con CSV o codificación inválida") from None
    except OSError:
        if strict:
            raise  # permisos/disco no deben autorizar publicar
    return rows


def choose(bank, log, now=None, rng=None, last_other_post=None):
    """Post a publicar ahora o (None, motivo): uno al dia, separacion minima con cualquier otro post automatico, sin repetir ids."""
    now = _madrid_naive(now or datetime.datetime.now(ZoneInfo("Europe/Madrid")))
    rng = rng or random
    # Fechas >5 minutos en el futuro son anomalías del reloj/CSV: no
    # inmovilizan la actividad durante días ni cuentan como "hoy".
    future_limit = now + datetime.timedelta(minutes=5)
    valid_times = [r["when"] for r in log if r["when"] <= future_limit]
    if any(when.date() == now.date() for when in valid_times):
        return None, "ya se publico uno hoy"
    if last_other_post is not None:
        last_other_post = _madrid_naive(last_other_post)
    other = [last_other_post] if last_other_post is not None and last_other_post <= future_limit else []
    latest = max(valid_times + other, default=None)
    if latest and conservative_elapsed_seconds(now, latest) < MIN_GAP_HOURS * 3600:
        return None, f"el ultimo post propio automatico fue a las {latest:%H:%M}: se espera (minimo {MIN_GAP_HOURS} h)"
    done = {r["id"] for r in log}
    options = [item for item in bank if item["id"] not in done]
    if not options:
        return None, "el banco esta agotado: escribir mas posts en 00_OPERATIVO/x_posts_banco.json"
    return rng.choice(options), ""


def record(item, url, now=None, path=None):
    path = path or LOG
    now = _madrid_naive(now or datetime.datetime.now(ZoneInfo("Europe/Madrid")))
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        if new:
            writer.writerow(["fecha_hora", "id", "texto", "url"])
        writer.writerow([now.isoformat(timespec="minutes"), item["id"], item["text"], url])


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    apply = "--apply" in argv
    import content_publisher as cp

    def select_current():
        # Revalidación de ambas fuentes dentro del turno Edge.
        log = read_log(strict=True)
        now = datetime.datetime.now(ZoneInfo("Europe/Madrid")).replace(tzinfo=None)
        future_limit = now + datetime.timedelta(minutes=5)
        other = cp.last_auto_publication(
            "x", strict=True, not_after=future_limit, notify=print)
        if any(r["when"] > future_limit for r in log):
            print("[x] AVISO: fecha futura anómala en banco; no cuenta para cadencia")
        return choose(load_bank(), log, now=now, last_other_post=other)

    try:
        item, why = select_current()
    except (OSError, ValueError) as exc:
        print(f"[x] ERROR integridad: NO se publica; fuentes no verificables ({type(exc).__name__})")
        return 1
    if item is None:
        print(f"[x] no se publica: {why}")
        return 0
    if not apply:
        print(f"[x] publicaria: «{item['text']}»")
        return 0
    import action_ledger
    import x_interact as x
    with action_ledger.browser_session(wait_minutes=40):
        # La espera del Edge puede durar 40 min. Otra tarea de banco/fichas
        # puede haber publicado entretanto: la elección exterior ha caducado.
        # Releer AMBOS registros dentro del turno exclusivo, y grabar el
        # resultado antes de soltarlo para que el siguiente publicador lo vea.
        try:
            item, why = select_current()
        except (OSError, ValueError) as exc:
            print(f"[x] ERROR integridad: NO se publica tras esperar Edge; fuentes no verificables ({type(exc).__name__})")
            return 1
        if item is None:
            print(f"[x] no se publica tras esperar el Edge: {why}")
            return 0
        import voice_output_finalization as voice
        voice.inspect(item["text"], network="x", queue="WEB")
        url = x.post(item["text"])
        record(item, url)
    print(f"[x] PUBLICADO: «{item['text']}» -> {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
