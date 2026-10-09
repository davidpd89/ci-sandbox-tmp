"""Clasificadores de texto COMUNES a todas las redes (06/10/2026): nicho (libros, lectura, escritura, fantasia), idioma (espanol / ingles / catalan / portugues) y spam.

Vivian en `bluesky_pool.py` y Mastodon, Threads y las instancias remotas los importaban de alli (`bp.niche_hits`, `bp.looks_spanish`...): la red mas antigua era el centro de las demas. Aqui
estan una sola vez; `bluesky_pool` los reexporta con los mismos nombres, asi que nada existente se rompe. Mejorar el vocabulario o la deteccion de idioma aqui mejora todas las redes.
"""
import re
import unicodedata

NICHE_TERMS = (
    "leer", "lectura", "lector", "lectora", "libro", "libros", "novela", "novelas", "escritor", "escritora", "autor", "autora", "fantasia", "fantasy", "romantasy",
    "ciencia ficcion", "literatura", "literario", "resena", "resenas", "biblioteca", "libreria", "booksky", "bookish", "reader", "writer", "worldbuilding",
    "manuscrito", "editorial", "club de lectura", "ficcion", "juvenil", "poeta", "poesia", "relato", "relatos", "cuentos", "saga", "tbr", "rol", "juegos de rol",
    "comic", "manga", "mitologia", "tolkien", "sanderson", "terror", "escribo", "escribiendo", "bibliofil", "bibliotecari", "librero", "booktuber", "bookstagram",
)
SPAM = re.compile(r"(follow ?back|f4f|l4l|sigueme y te sigo|crypto|cripto|casino|betting|apuestas|giveaway|airdrop|\bnft\b|onlyfans|18\+|nsfw|\bxxx\b|"
                  r"trading|forex|inversi[oó]n garantizada|ganar dinero|dm for|escort|sugar ?daddy|follow for follow)", re.I)
SPANISH_WORDS = frozenset(
    ("el la los las un una de del que y en es por con para se su sus lo al mas muy pero como mi tu me te nos soy somos escribo leo amante apasionada apasionado "
     "vivo vida libros lectora lector escritora escritor editorial independiente publicamos narrativa poesia ensayo fantasia terror ciencia ficcion novela novelas "
     "literatura juvenil comic comics libreria tienda especializada somos nuestro nuestra desde anos lectura relatos cuentos madrid barcelona espana mexico "
     "argentina colombia chile peru sevilla valencia bilbao autor autora traductor traductora ilustrador ilustradora cine series videojuegos rol manga").split()
)
ENGLISH_WORDS = frozenset(
    ("the and of for with is my to in a an at on from by that this who are was be your our you we about news writer author editor award global director board member "
     "senior former official founder based love lover mom dad he she him her they them his hers i am not only just new out all more can will been have has had "
     "do does book books reader readers writing writes working lives living").split()
)
CATALAN_HINT = re.compile(r"(?<![a-z])(llibres|llibre|catal[aà]|escriptura|ficci[oó]|des de|som|nostres)(?![a-zà-ü])", re.I)
PORTUGUESE_HINT = re.compile(r"(?<![a-z])(n[aã]o|voc[eê]|uma|com o|para os|leituras|livros e|nossa|nosso|portugu[eê]s|brasil)(?![a-zà-ü])", re.I)


def _norm(text):
    text = unicodedata.normalize("NFKD", str(text or "").casefold())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def niche_hits(text):
    value = _norm(text)
    tokens = set(re.findall(r"[a-z0-9_]+", value))
    hits = 0
    for term in NICHE_TERMS:
        if (" " in term and term in value) or term in tokens:
            hits += 1
    return hits


def looks_spanish(text):
    raw = str(text or "")
    if re.search(r"[¿¡ñÑ]", raw):
        return True
    words = [_norm(word) for word in re.findall(r"[a-záéíóúüñ]+", raw.casefold())]
    if len(words) < 3:
        return False
    hits = sum(1 for word in words if word in SPANISH_WORDS)
    return hits >= 2 and hits / len(words) >= 0.15


def looks_english(text):
    """Ingles claro: >=4 palabras, al menos 2 palabras funcionales inglesas (sin contar «a», que tambien es espanol) y >=30 % del texto. Se tokeniza con acentos: «Garcia Fernandez»
    ya no se partia en «garc a fern ndez» y daba un falso positivo (06/10)."""
    words = re.findall(r"[a-záéíóúüñ]+", str(text or "").casefold())
    if len(words) < 4:
        return False
    hits = sum(1 for word in words if word in ENGLISH_WORDS and word != "a")
    return hits >= 2 and hits / len(words) >= 0.3


def seed_quality(info):
    """Solo se mina el grafo de semillas del mundo hispano de libros/rol/comic: los seguidores de una periodista de WIRED son lectores de WIRED y los de una
    editorial portuguesa lusohablantes."""
    info = info or {}
    bio = info.get("bio") or ""
    if looks_english(bio) or PORTUGUESE_HINT.search(bio) or CATALAN_HINT.search(bio):
        return False
    words = re.findall(r"[a-záéíóúüñ]+", bio.casefold())
    if looks_spanish(bio):
        return True
    return len(words) < 8 and (niche_hits(bio) >= 1 or info.get("type") in ("editorial", "libreria", "resenador", "club"))


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# Otros idiomas (06/10/2026). El 06/10 un usuario aleman nos pregunto en Bluesky si nuestra cuenta de Mastodon era la nuestra porque le habia seguido: el scan seguia a cuentas
# en aleman (11 de las 488 que seguimos) porque «no es espanol ni ingles» pasaba el filtro. Palabras funcionales DISTINTIVAS (que no existan en espanol) de los idiomas
# que mas aparecen en el nicho; gallego y catalan NO se tratan como «otro idioma» (David es gallego; ver CATALAN_HINT para las semillas).
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
OTHER_LANGUAGE_WORDS = {
    # solo palabras que NO existen en espanol (06/10: «para», «dos», «escritor», «autor», «con», «una» daban falsos positivos con biografias espanolas)
    "de": frozenset("der die das und ist nicht ich mit für ein eine auch auf von zu den dem des sich wir sie bücher schreibe schreibt autorin über wohne lebe bin habe sind oder wie aber nur noch mehr".split()),
    "fr": frozenset("les des une est pas pour avec dans sur qui je suis nous vous ce cette mais aussi sont être très écrivain auteur livres lectrice j'aime".split()),
    "it": frozenset("il gli di è per sono non anche dei delle scrittore scrittrice libri leggo amo della nel che".split()),
    "nl": frozenset("het een van ik niet voor met zijn ook maar schrijf schrijver boeken lees mijn wij".split()),
    "pt": frozenset("não você uma com os das são também livros leitor leitora sou meu minha eu apenas ela elu muito mais ou escritora, brasileira escritor,".split()),
}


def other_language(text):
    """Codigo del idioma (de/fr/it/nl/pt) si el texto es CLARAMENTE de otro idioma que el espanol; None si es espanol, ingles, gallego/catalan o no se puede saber."""
    cleaned = re.sub(r"https?://\S+|www\.\S+|\S+@\S+|@\w+", " ", str(text or "").casefold())       # enlaces, correos y menciones no son idioma
    words = re.findall(r"[a-zà-ÿ']+", cleaned)
    if len(words) < 4 or looks_spanish(text):
        return None
    best, best_hits = None, 0
    for code, vocabulary in OTHER_LANGUAGE_WORDS.items():
        hits = sum(1 for w in words if w in vocabulary)
        if hits > best_hits:
            best, best_hits = code, hits
    return best if best_hits >= 2 and best_hits / len(words) >= 0.12 else None


def foreign_language(text):
    """Codigo del idioma si el texto NO es de nuestro publico (06/10, David: «cuentas en otros idiomas no nos interesan, nos orientamos al espanol»): aleman, frances, italiano,
    neerlandes, portugues o ingles (`en`). None si es espanol, gallego/catalan o no se puede saber (biografia vacia o muy corta)."""
    other = other_language(text)
    if other:
        return other
    return "en" if looks_english(text) and not looks_spanish(text) else None
