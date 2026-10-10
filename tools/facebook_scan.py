"""
Fase 1 del pipeline de Facebook (22/09, descubrimiento externo anadido
24/09). Hasta el 23/09 este scan solo cubria los posts PROPIOS de la pagina
(reciprocidad/mantenimiento) porque Facebook resulto tener el DOM mas fragil
de las nueve redes (sin atributos estables tipo data-testid, re-renderizados
frecuentes que desprenden elementos a mitad de accion) y no habia habido
tiempo de investigar el descubrimiento externo con cuidado.

A peticion explicita de David (24/09: "Facebook lo hacemos que esta sin
hacer... arreglalo y haz que sea una red social productiva tambien
buscando, comentando, etc y no solo eso"): se investigo en vivo y
`facebook.com/hashtag/<tag>` SI funciona para descubrir contenido real
mientras se navega como la Pagina (confirmado con contenido autentico:
Dolmen Editorial hablando del festival Celsius 232, e incluso un fragmento
real de la propia novela de David publicado por la revista Arbol Invertido,
nunca detectado antes por no tener este pipeline). Ver
`facebook_interact.py` (`get_hashtag_data`/`like_external`/
`comment_external`) para el mecanismo - los permalinks de posts ajenos
(`facebook.com/photo/?fbid=...`) son navegables directamente, a diferencia
de los posts propios que se manejan por indice.

HASHTAG_POOL validado en vivo el 24/09 (probadas 6, descartadas 2: "escritura"
daba señal mixta/generica y "literaturaespañola" colaba cuentas
institucionales/politicas - Direccion General del Libro, Monarquia Española -
ver diario/2026-09-24.md).

Kind sugerida (mismo criterio que el resto de redes): "comment_external" si
el texto invita a conversacion, si no "like_external", para el
descubrimiento; los posts propios siguen igual que antes ("like"/"comment"
por indice).

Uso:
    python tools/facebook_scan.py
"""
import datetime
import os
import sys
<<<<<<< HEAD

sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")
=======
import time

sys.path.insert(0, os.path.dirname(__file__))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
>>>>>>> origin/research/public-reuse-parent
import facebook_interact as fb
import scan_common as sc

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_FACEBOOK")
REGISTRO_CSV = os.path.join(ROOT, "registro_interacciones.csv")
CANDIDATES_JSON = os.path.join(ROOT, "facebook_candidates.json")   # lo lee facebook_build_plan.py (ronda mecanica)

HASHTAG_POOL = [
    "literaturafantastica", "novelafantastica", "clubdelectura", "librosrecomendados",
    # 04/10 (David: "si no encuentras es fallo del script"): con 4 etiquetas y 2 por dia salian 2 candidatos.
    # Pool ampliado con etiquetas de lectores/autores en español; 4 por dia.
    "fantasiaepica", "fantasiajuvenil", "novelajuvenil", "escritoresindependientes", "lecturaenespañol",
    "librosfantasia", "bookstagramespaña", "reseñadelibros",
    # 04/10 tarde: mas etiquetas de lectores/autores en espanol para llegar a ~10 candidatos al dia (6 por dia).
    "librosyletras", "amantesdelalectura", "autoresespañoles", "novedadeseditoriales",
]


# 04/10: busquedas de texto ademas de hashtags (la busqueda de posts recientes de Facebook trae mas gente real que las etiquetas)
SEARCH_POOL = [
    # 06/10 (David: "no hay movimiento"; GPT: 8 consultas son muy pocas): ~48 consultas rotatorias por familia (lectores, fantasia, juvenil, escritura, editoriales, resenas, clubes).
    "libros de fantasía", "novela de fantasía reseña", "club de lectura", "autor independiente novela", "recomiendo este libro", "escribiendo mi novela", "mi lectura de esta semana", "booktok libros",
    "fantasía juvenil", "novela juvenil recomendada", "saga de fantasía", "romantasy libros", "libro que estoy leyendo", "reseña de libro", "mi lectura de hoy", "qué libro me recomiendan",
    "reto de lectura", "tbr libros pendientes", "libros que he leído este mes", "feria del libro firmas", "presentación de novela", "editorial independiente novela", "autopublicación novela",
    "escritores noveles", "consejos para escritores", "bloqueo del escritor", "worldbuilding fantasía", "personajes de novela", "primera novela publicada", "mi novela publicada",
    "lector de fantasía", "libros de magia", "libros de aventuras juveniles", "club de lectura online", "librería independiente", "novedades editoriales fantasía", "booktuber español",
    "bookstagram libros", "reseñas literarias", "citas de libros", "microrrelato", "relato corto fantasía", "taller de escritura", "escritura creativa", "lecturas del verano",
    "libros recomendados para jóvenes", "autores españoles de fantasía", "leyendo ahora",
    # 07/10: cultura de reciprocidad en castellano (me gusta por me gusta, apoyo mutuo entre autores): sus publicaciones traen cuentas que devuelven el gesto
    "autores independientes apoyo mutuo", "escritores me gusta por me gusta", "lectores sígueme y te sigo", "comparte tu página de autor", "apoyo a autores noveles",
    "grupo de apoyo a escritores", "comentario por comentario autores", "promociona tu libro gratis",
]


import discovery_terms
SEARCH_POOL += discovery_terms.terms("facebook", "busquedas", skip=SEARCH_POOL)      # 07/10: consulta M a GPT (grupos, eventos, reels, hilos de presentacion)


def _round_index():
    """Numero de franja del dia (0, 1, 2): con 3 rondas al dia cada una rota a consultas distintas."""
    now = datetime.datetime.now()
    return now.timetuple().tm_yday * 6 + min(now.hour // 4, 5)      # 07/10: 6 franjas al dia


def _rotate_searches(n=10):
    base = _round_index() * n
    return [SEARCH_POOL[(base + i) % len(SEARCH_POOL)] for i in range(n)]


def _rotate_hashtags(n=8):
    base = _round_index() * n
    return [HASHTAG_POOL[(base + i) % len(HASHTAG_POOL)] for i in range(n)]


_suggest_kind_own = lambda *a, **k: sc.downgrade_for_opinion(_suggest_kind_own_raw(*a, **k), a[0], 'like')


def _suggest_kind_own_raw(text):
    return "comment" if sc.invites_conversation(text) else "like"


_suggest_kind_external = lambda *a, **k: sc.downgrade_for_opinion(_suggest_kind_external_raw(*a, **k), a[0], 'like_external')


def _suggest_kind_external_raw(text):
    return "comment_external" if sc.invites_conversation(text) else "like_external"


<<<<<<< HEAD
=======
def _exclude_unverified_surfaces(rows):
    """No incorporar URL de grupo ni foto ambigua a reserva/plan.

    Operamos sobre observaciones YA obtenidas por el escáner heredado;
    esta función no navega, no acredita autorización y no genera acciones.
    """
    import facebook_source_quality as quality
    accepted = []
    for row in rows:
        if (isinstance(row, (tuple, list)) and len(row) == 3
                and quality.page_post_url_shape(row[1])):
            accepted.append(row)
    return accepted



def _source_quality_metrics(rows, source_type, elapsed_seconds):
    """Métricas pasivas del escaneo recibido, sin PII ni nuevos requests."""
    import facebook_source_quality as quality
    if source_type not in ("hashtag", "search"):
        raise ValueError("tipo de fuente Facebook no reconocido")
    prepared = [{"source": source_type + ":local", "permalink": row[1], "text": row[2]}
                for row in rows if isinstance(row, (tuple, list)) and len(row) == 3]
    result = quality.summary(prepared)
    row = result["sources"][0] if result["sources"] else {}
    return {"fuente": source_type, "observados": len(rows),
            "unicos_lote": row.get("unique_post_urls", 0),
            "post_shape": sum(quality.page_post_url_shape(item["permalink"]) for item in prepared),
            "grupos": row.get("group_blocked", 0), "spam": row.get("spam_blocked", 0),
            "edad_desconocida": row.get("age_unknown", 0),
            "segundos_escaneo": round(max(0.0, elapsed_seconds), 2),
            "permiso_acreditado": False}


def _print_source_quality(rows, source_type, elapsed_seconds):
    # Observabilidad pasiva: un error de métricas NO modifica el lote que
    # el escáner ya obtuvo ni dispara más navegación.
    try:
        report = _source_quality_metrics(rows, source_type, elapsed_seconds)
    except Exception as exc:
        print(f"[CALIDAD_FUENTE] fuente={source_type} estado=no_disponible "
              f"causa={type(exc).__name__} permiso_acreditado=False")
        return None
    print("[CALIDAD_FUENTE] " + " ".join(f"{key}={value}" for key, value in report.items()))
    return report



>>>>>>> origin/research/public-reuse-parent
def scan():
    known = sc.known_accounts(REGISTRO_CSV)
    discarded = sc.discarded_handles(REGISTRO_CSV)

    p, pg = fb._connect()
    try:
        print("=== HEALTH ===")
        ok, msg = fb._health_check(pg)
        print(msg)
        if not ok:
            print("\nParando aqui - resolver esto antes de nada mas.")
            return

        print("\n=== POSTS PROPIOS (por indice, mas reciente primero) ===")
        fb._dump_own_feed(pg)
        n = pg.locator('div[aria-label="Me gusta"][role="button"]').count()
        n_liked = pg.locator('div[aria-label="Suprimir Me gusta"][role="button"]').count()
        print(f"{n} post(s) sin like todavia, {n_liked} ya con like nuestro, en la carga actual.")
        for i in range(n):
            preview = fb._post_preview(pg, i)
            kind = _suggest_kind_own(preview)
            print(f"[{i}] sugerido={kind} | {preview[:200]}")
    finally:
        p.stop()

    hashtags_hoy = _rotate_hashtags()
    print(f"\n=== DESCUBRIMIENTO EXTERNO (hashtags del dia: {hashtags_hoy}) ===")
    seen = set()
    externos = []
    import facebook_pool as fpool
    pool = fpool.connect()
    for tag in hashtags_hoy:
<<<<<<< HEAD
        rows_tag = fb.get_hashtag_data(tag)
=======
        t0 = time.monotonic()
        raw_rows = fb.get_hashtag_data(tag)
        _print_source_quality(raw_rows, "hashtag", time.monotonic() - t0)
        rows_tag = _exclude_unverified_surfaces(raw_rows)
>>>>>>> origin/research/public-reuse-parent
        fpool.record_posts(pool, rows_tag, f"hashtag:{tag}")
        for author, permalink, text in rows_tag:
            if author in seen or author in discarded:
                continue
            seen.add(author)
            if sc.is_political(text):
                continue
            externos.append((tag, author, permalink, text[:200].replace("\n", " ")))

    busquedas = _rotate_searches()
    print(f"\n=== BUSQUEDAS DE POSTS (hoy: {busquedas}) ===")
    for query in busquedas:
        try:
<<<<<<< HEAD
            rows = fb.get_search_data(query)
=======
            t0 = time.monotonic()
            raw_rows = fb.get_search_data(query)
            _print_source_quality(raw_rows, "search", time.monotonic() - t0)
            rows = _exclude_unverified_surfaces(raw_rows)
>>>>>>> origin/research/public-reuse-parent
        except fb.BotWarningDetected:
            raise
        except Exception as exc:   # un fallo de una busqueda no tumba el resto
            print(f"  busqueda {query!r}: {type(exc).__name__}")
            continue
        fpool.record_posts(pool, rows, f"search:{query}")
        for author, permalink, text in rows:
            if author in seen or author in discarded or sc.is_political(text):
                continue
            seen.add(author)
            externos.append((f"busqueda:{query}", author, permalink, text[:200].replace("\n", " ")))

    print("reserva:", fpool.stats(pool))
    pool.close()
    import json
    with open(CANDIDATES_JSON, "w", encoding="utf-8") as stream:
        json.dump([{"tag": t, "autor": a, "permalink": pl, "text": tx, "known": a in known} for t, a, pl, tx in externos],
                  stream, ensure_ascii=False, indent=1)
    print(f"=== CANDIDATOS EXTERNOS FILTRADOS: {len(externos)} (tras politica/dedupe/descartados) ===")
    for tag, author, permalink, text in externos:
        known_tag = f"[CONOCIDA fecha={known[author]}] " if author in known else "[NUEVA] "
        kind = _suggest_kind_external(text)
        print(f"{known_tag}sugerido={kind} | {author} | hashtag:{tag} | {permalink}")
        print(f"   {text}")


if __name__ == "__main__":
    try:
        fb.ensure_browser()
        scan()
    except fb.BotWarningDetected as e:
        print(str(e))
        sys.exit(2)
