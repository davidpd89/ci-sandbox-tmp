"""Filtro de contenido de ligue / sexo / chat de citas (03/10/2026, David).

Una busqueda como "autores indie espana" devolvio posts recientes de gente ligando ("hablemos por ig",
"ocupo un novio", "quien me califica...") y dimos like. Este filtro corta ese contenido en TODAS las redes:
`scan_common.is_political()` lo incluye (es el filtro de "no tocar este contenido" que ya usan todos los scans,
tambien sobre biografias). Es deliberadamente conservador: ante la duda, se descarta.

Se evalua sobre texto normalizado (minusculas, sin tildes). Una palabra suelta ambigua (p. ej. "coger",
"titan") no basta: se usan frases y terminos inequivocos.
"""
import re
import unicodedata

_TERMS = [
    # sexo explicito / adulto
    r"sexo", r"sexual\w*", r"sexy", r"sexting", r"nudes?", r"desnud\w*", r"porn\w*", r"xxx", r"onlyfans", r"fansly",
    r"erotic\w*", r"cachond\w*", r"calientes?", r"calentur\w*", r"hormon(?:o|a|al|ada|ado)s?\b", r"follar", r"follamos",
    r"levante duro", r"(?:ando|tengo) (?:el |con )?titan", r"titan parad\w*", r"paradit[oa] y bonit[oa]", r"verga\w*", r"vergota\w*", r"pene", r"vagina", r"tetas?", r"culo\w*", r"nalgas?", r"pack(?:s)? (?:de )?(?:fotos|nudes)",
    r"smut", r"spicy", r"🔞", r"masturb\w*", r"orgasm\w*", r"fetich\w*", r"kink\w*", r"contenido (?:para )?adult\w*", r"\+18", r"18\+",
    # ligue / chat de citas / captacion de seguidores
    r"hablemos", r"hablamos por (?:ig|insta|dm|privado|telegram|whatsapp)", r"escribeme al (?:privado|dm|inbox)",
    r"(?:me )?sigues? (?:en|por) (?:ig|insta)", r"sigueme", r"te sigo", r"follow ?back",
    r"por (?:ig|insta|instagram|dm|privado)\b", r"(?:mi|el) (?:ig|insta)\b", r"quiero amistad",
    r"ocupo (?:un|una) (?:novi[oa]|pareja|amig[oa])", r"busco (?:novi[oa]|pareja|amig[oa]s? con)", r"novi[oa] ya",
    r"quien me califica", r"me califica", r"calificame", r"te quiero ver", r"quien (?:quiere )?(?:chatear|platicar)",
    r"alguien (?:despiert[oa]|para (?:chatear|platicar))", r"aburrid[oa] (?:y|hablemos)", r"mamacit\w*", r"mamasit\w*",
    r"mamii+", r"papito\w*", r"amigas? (?:hormon\w*|solitar\w*|con derecho\w*)",
    r"solter[oa]s? (?:y|buscando)", r"ligar\b", r"\bligue\b", r"mensaje(?:s)? al privado",
]
_ADULT_RE = re.compile(r"(?<![a-z0-9])(?:" + "|".join(_TERMS) + r")(?![a-z0-9])")


def _normalize(text):
    text = unicodedata.normalize("NFKD", str(text).casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.split())


def is_adult_or_dating(text):
    """True si el texto es de ligue, sexo o chat de citas (o no es texto: se descarta por prudencia)."""
    if text is None or text == "":
        return False
    if not isinstance(text, str):
        return True
    return bool(_ADULT_RE.search(_normalize(text)))
