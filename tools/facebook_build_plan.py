"""Plan mecanico de Facebook (04/10/2026): likes a posts ajenos del nicho, sin tokens.

La API de Meta no deja actuar sobre contenido ajeno como Pagina (David, 04/10: "tendra que ir por la web externo como el resto"),
asi que la salida a otras paginas va por navegador: `facebook_scan.py` (hashtags del dia) -> este constructor -> `facebook_execute.py`.
Solo `like_external`; los comentarios (`comment_external`) llevan texto con voz propia y siguen siendo pase editorial.
Se descartan instituciones/politica (`INSTITUTIONAL`, `scan_common.is_political`), spam y un autor repetido.

    python tools/facebook_build_plan.py [--max N]   # escribe SISTEMA_DIARIO_FACEBOOK/facebook_plan.json
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import scan_common as sc

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_FACEBOOK")
CANDIDATES_JSON = os.path.join(ROOT, "facebook_candidates.json")
PLAN_OUT = os.path.join(ROOT, "facebook_plan.json")
INSTITUTIONAL = re.compile(r"(gobierno|ministerio|ayuntamiento|diputaci[oó]n|junta de|guardia civil|polic[ií]a|"
                           r"direcci[oó]n general|monarqu[ií]a|partido|sindicato|embajada|universidad|vox\b|psoe|pp\b)", re.I)
SPAM = re.compile(r"(amazon|temu|aliexpress|oferta|descuento|comprar|drive\.google|pdf gratis|descarga gratis|sorteo|casino|apuestas|criptomoned|whatsapp|t\.me/)", re.I)
NICHE = re.compile(r"(libro|lectur|leer|novela|fantas|saga|escrit|autor|editorial|poes|relato|cuento|literari|narrativa|"
                   r"manuscrito|cap[ií]tulo|bookstagram|rese[nñ]a)", re.I)


# 06/10: clasificador negativo (la busqueda «lectura del dia» traia lecturas liturgicas; «escribiendo mi novela», famosos): una cuenta/post con estas senales no entra aunque mencione «lectura»
OFF_TOPIC = re.compile(r"(\bdios\b|jes[uú]s|ev[aá]ngelio|oraci[oó]n|rosario|\bsanto\b|\bsanta\b|biblia|iglesia|cat[oó]lic|\bmisa\b|liturgi|f[uú]tbol|real madrid|bar[cç]a\b|hor[oó]scopo|"
                       r"\brecetas?\b|actriz|cantante|presentador|famos[oa]s?|loter[ií]a|sorteo|\brifa\b)", re.I)
POOL_MIN_NICHE = 1           # 07/10: con 2 la reserva (62 posts disponibles) daba 4 acciones por ronda; la consulta de origen ya es de nicho, las exclusiones (religion, famosos, spam, institucional) siguen
RECENT_AUTHOR_DAYS = 7      # un autor al que ya dimos like no vuelve a entrar en dos semanas


def recent_authors(registro_path, today=None, days=RECENT_AUTHOR_DAYS):
    """Autores (en minusculas) con los que hubo una accion en los ultimos `days` dias, segun el registro de interacciones."""
    import csv
    import datetime
    today = today or datetime.date.today()
    out = set()
    try:
        with open(registro_path, encoding="utf-8", newline="") as stream:
            for row in csv.reader(stream):
                if len(row) < 3:
                    continue
                try:
                    when = datetime.date.fromisoformat(row[0])
                except ValueError:
                    continue
                if (today - when).days <= days:
                    out.add(row[1].strip().casefold())
    except OSError:
        pass
    return out


def build_from_pool(db, n, exclude_handles=frozenset(), mark_planned=True, max_comments=12, used_phrases=frozenset(), rng=None, allow=None):
    """Hasta `n` acciones elegidas de la reserva persistente: posts del nicho (>= POOL_MIN_NICHE terminos), sin senales fuera de tema/institucionales/spam, un autor por plan.
    06/10 (David: «maximas interacciones, comentarios»): si el post encaja con una intencion (recomendacion pedida, libro terminado, lectura en curso, avance de manuscrito…) se COMENTA con
    una frase corta del banco (`x_replies.py`, sin repetir en 7 dias) hasta `max_comments`; el resto recibe «me gusta»."""
    import random
    import facebook_pool as fpool
    import x_replies
    import facebook_source_quality as quality
    rng = rng or random
    used = set(used_phrases)
    plan, comments = [], 0
    for row in fpool.pick(db, n * 4, exclude_handles=exclude_handles):
        if not quality.page_post_url_shape(row["permalink"], source=row.get("source")):
            # No origin confirmed for group URLs or ambiguous /photo shares.
            continue
        text = f"{row['handle']} {row['text']}"
        if (row["niche"] < POOL_MIN_NICHE or OFF_TOPIC.search(text) or INSTITUTIONAL.search(text)
                or SPAM.search(text) or quality.hard_exclusion_reason(text) or sc.is_political(text)):
            continue
        item = {"kind": "like_external", "permalink": row["permalink"], "autor": row["handle"],
                "post_created_at": row.get("created_at") or "", "post_text": (row.get("text") or "")[:500], "motivo": f"reserva:{row['source']}:score={row['score']}"}
        intent = x_replies.classify(row["text"]) if comments < max_comments and (allow is None or allow(row["handle"])) else None
        phrase = x_replies.choose_phrase(intent, used, rng) if intent else None
        if phrase:
            used.add(x_replies._fold(phrase).strip())
            comments += 1
            item.update({"kind": "comment_external", "text": phrase, "bank": True, "post_text": (row.get("text") or "")[:500], "motivo": item["motivo"] + f":intent={intent}"})
        plan.append(item)
        if mark_planned:
            fpool.mark(db, row["permalink"], "planned")
        if len(plan) >= n:
            break
    return plan


def build(candidates, max_likes=12):
    import facebook_source_quality as quality
    plan, seen = [], set()
    for item in candidates:
        autor = (item.get("autor") or "").strip()
        text = item.get("text") or ""
        if not autor or autor.casefold() in seen or not quality.page_post_url_shape(item.get("permalink"), source=item.get("source") or item.get("tag")):
            continue
        if (INSTITUTIONAL.search(autor) or INSTITUTIONAL.search(text) or SPAM.search(text)
                or quality.hard_exclusion_reason(f"{autor} {text}")
                or OFF_TOPIC.search(f"{autor} {text}") or sc.is_political(f"{autor} {text}")):
            continue
        if not NICHE.search(f"{autor} {text}"):
            continue
        seen.add(autor.casefold())
        plan.append({"kind": "like_external", "permalink": item["permalink"], "autor": autor,
                     "post_created_at": item.get("created_at") or item.get("created_time") or "",
                     "post_text": text[:500], "motivo": f"hashtag {item.get('tag', '')}"})
        if len(plan) >= max_likes:
            break
    return plan


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    max_likes = int(argv[argv.index("--max") + 1]) if "--max" in argv else 60
    import facebook_pool as fpool
    db = fpool.connect()
    try:
        recent = recent_authors(os.path.join(ROOT, "registro_interacciones.csv"))
        import x_replies
        plan = build_from_pool(db, max_likes, exclude_handles=recent, used_phrases=x_replies.recent_phrases(os.path.join(ROOT, "registro_interacciones.csv")),
                               allow=__import__("relationship_policy").comment_filter("facebook", os.path.join(ROOT, "registro_interacciones.csv")))
        print(f"[facebook] reserva: {len(plan)} acciones elegidas; {fpool.stats(db)}")
        if len(plan) < max_likes:       # lo que aun quede del scan del dia, sin repetir autores
            taken = {item["autor"].casefold() for item in plan} | recent
            with open(CANDIDATES_JSON, encoding="utf-8") as stream:
                extra = [c for c in json.load(stream) if (c.get("autor") or "").strip().casefold() not in taken]
            plan += build(extra, max_likes - len(plan))
    finally:
        db.close()
    with open(PLAN_OUT, "w", encoding="utf-8") as stream:
        json.dump(plan, stream, ensure_ascii=False, indent=1)
    print(json.dumps({"plan": "SISTEMA_DIARIO_FACEBOOK/facebook_plan.json", "actions": len(plan)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
