import sys
from ask_chatgpt_rrss import ask

Q = """Soy director de contenido de @davidportodiaz. Necesito 6 conceptos nuevos para 3 días (2 por día: 21, 22, 23 de julio).

MÉTRICAS REALES — LO QUE MEJOR FUNCIONA:
- IG reel #1: "Te dejo el principio. El final lo escribes tú." → 49.5% retención 3s, 140 views (PARTICIPACIÓN DIRECTA)
- IG reel #2: "A veces lo único que se gana en un día es seguir de pie" → 46.3%, 227 views (EMOCIÓN DIRECTA, 2ª persona)
- TikTok #1: "Echas de menos quién eras" → 803 views (NOSTALGIA IDENTIDAD)
- TikTok #2: "¿Cuál fue el primer libro que te hizo llorar a escondidas?" → 763 views, 14 likes (PREGUNTA ESPECÍFICA + detalle concreto)
- TikTok #3: "¿Cuántas de las 3 te han pasado a ti?" → 504 views (LISTA DE IDENTIFICACIÓN)

LO QUE NO FUNCIONA (<17% retención):
- Metáforas abstractas de movimiento/peso/distancia
- "No hay X. No hay Y." (cadenas de negación)

TEMAS YA PROGRAMADOS ESTA SEMANA (no repetir):
- Bus stop / perder el bus leyendo
- Enemies to lovers en librería
- Resaca de libro / libro cerrado
- Capítulos que no terminas
- Kindle con polvo
- "Seguir de pie" / motivación abstracta

REGLAS ABSOLUTAS:
- Busca PRIMERO una fuente humana real (Reddit, Twitter, comentarios reales). Cita la fuente.
- Máx 3 líneas en pantalla. Cada línea ≤ 5 palabras. Regla estricta: 2 segundos por línea.
- Hook primera línea solo, sin contexto → ¿para el scroll?
- Una pregunta directa al final que sea fácil de responder en 3 palabras

FORMATOS VARIADOS (no todo reels):
- Día 21 pieza 1: Reel PixVerse o Meta AI (algo visual y cinematográfico)
- Día 21 pieza 2: Carrusel de 4-5 slides O quote card (algo más editorial)
- Día 22 pieza 1: Reel Meta AI (paisaje fantástico o escena de lectora)
- Día 22 pieza 2: Reel corto tipo "lista" o "pregunta directa"
- Día 23 pieza 1: Reel PixVerse (mejor día de TikTok — máximo impacto)
- Día 23 pieza 2: Cualquier formato

Dame para cada uno: fuente humana real → concepto → 3 líneas exactas → pregunta → prompt visual (en inglés para IA) → 8 hashtags NUEVOS que no hayamos usado de entre: #bookstagramespaña #maniaslectoras #cosasdelectores #comunidadlectora #lectoresunidos #libroslibroslibros #librosymaslibros #clubdelectura #librosfantasia #bookstagrammer #bookish #bookworm #happyreader #bookreels #slowburn #enemiestolovers #romantasy #bookhumor #resacaliteraria"""

print("Preguntando ChatGPT...")
r = ask(Q, timeout_s=420)
print(r)
