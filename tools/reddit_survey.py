"""Censo de comunidades de Reddit en espanol (solo lectura, 06/10/2026).

Busca subreddits por palabras clave con el JSON publico de Reddit (sesion del Edge 9223), y para los que tienen cierto tamano
guarda tamano, tipo, descripcion, normas, flairs y si exigen karma/antiguedad (por texto de normas/descripcion).
Salida: SISTEMA_DIARIO_REDDIT/cache/comunidades_es.json  (el informe humano se escribe a mano a partir de ahi).

    python tools/reddit_survey.py [--min-subs 1500]
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import action_ledger as al

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "SISTEMA_DIARIO_REDDIT", "cache", "comunidades_es.json")
QUERIES = ["libros", "lectura", "lectores", "literatura", "fantasia", "escritura", "escritores", "escribir", "novela", "relatos", "cuentos",
           "poesia", "autopublicacion", "booktok", "club de lectura", "ciencia ficcion", "rol", "preguntas", "charla", "espanol", "hispano"]
SEED = ["libros", "escribir", "escritura", "LiteraturaHispana", "escritores", "preguntaleareddit", "AskRedditespanol", "POESIA", "RolEnEspanol",
        "es", "Fantasia", "FantasiaEpica", "LibrosEnEspanol", "Literatura", "Cuentos", "Relatos", "EscritoresEspanol", "autopublicacion",
        "ciencia_ficcion", "CienciaFiccionEs", "lecturas", "bookstagram", "KindleEspana", "Hispanohablantes", "askspain", "spain", "argentina", "mexico"]
GATE = re.compile(r"(karma|antig[uü]edad|d[ií]as de cuenta|cuenta nueva|cuentas nuevas|edad de la cuenta|account age|new account)", re.I)
PROMO = re.compile(r"(autopromo|promoci[oó]n|publicidad|spam|self-?promo|enlaces propios|vender|tus propios)", re.I)
AI = re.compile(r"(\bIA\b|inteligencia artificial|\bAI\b|chatgpt|generad[oa]s? por)", re.I)

JS = """async (args) => {
  const [q, names, minSubs] = args;
  const get = async (u) => { try { const r = await fetch(u, {credentials: 'include'}); return r.ok ? await r.json() : null; } catch (e) { return null; } };
  const found = {};
  for (const term of q) {
    const j = await get('/subreddits/search.json?limit=25&q=' + encodeURIComponent(term));
    for (const c of ((j && j.data && j.data.children) || [])) { const d = c.data; found[d.display_name] = d.subscribers || 0; }
    await new Promise(r => setTimeout(r, 700));
  }
  for (const n of names) { if (!(n in found)) found[n] = -1; }
  const out = [];
  for (const name of Object.keys(found)) {
    const about = await get('/r/' + name + '/about.json');
    if (!about || !about.data) continue;
    const d = about.data;
    if ((d.subscribers || 0) < minSubs && !names.includes(name)) continue;
    const rules = await get('/r/' + name + '/about/rules.json');
    const flairs = await get('/r/' + name + '/api/link_flair_v2.json');
    await new Promise(r => setTimeout(r, 800));
    out.push({name: name, subs: d.subscribers, lang: d.lang, type: d.subreddit_type, over18: d.over18, submission_type: d.submission_type,
      created: d.created_utc, active: d.accounts_active || d.active_user_count || null, title: d.title,
      desc: (d.public_description || '').slice(0, 300),
      rules: ((rules && rules.rules) || []).map(x => [x.short_name, (x.description || '').slice(0, 400)]),
      flairs: ((Array.isArray(flairs) ? flairs : []).map(f => f.text)).slice(0, 15),
      restrict_posting: d.restrict_posting, user_is_banned: d.user_is_banned, user_is_subscriber: d.user_is_subscriber});
  }
  return out;
}"""


def main(argv=None):
    from playwright.sync_api import sync_playwright
    argv = list(sys.argv[1:] if argv is None else argv)
    min_subs = int(argv[argv.index("--min-subs") + 1]) if "--min-subs" in argv else 1500
    with al.browser_session(wait_minutes=60):
        p = sync_playwright().start()
        try:
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9223")
            page = browser.contexts[0].new_page()
            page.set_default_timeout(120000)
            try:
                page.goto("https://www.reddit.com/", wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(2500)
                data = page.evaluate(JS, [QUERIES, SEED, min_subs])
            finally:
                page.close()
        finally:
            p.stop()
    for entry in data:
        text = " ".join(f"{n} {d}" for n, d in entry["rules"]) + " " + entry["desc"]
        entry["gate_hint"] = bool(GATE.search(text))
        entry["promo_rule"] = bool(PROMO.search(text))
        entry["ai_rule"] = bool(AI.search(text))
    data.sort(key=lambda e: -(e.get("subs") or 0))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=1)
    sys.stdout.reconfigure(encoding="utf-8")
    for e in data:
        print(f"r/{e['name']:<22} {e.get('subs') or 0:>8} subs {e.get('lang') or '-':<3} {e.get('type'):<10} sub={e.get('submission_type')} reglas={len(e['rules'])} karma/edad={'SI' if e['gate_hint'] else 'no'} promo={'SI' if e['promo_rule'] else 'no'} ia={'SI' if e['ai_rule'] else 'no'}")
    print(f"{len(data)} comunidades -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
