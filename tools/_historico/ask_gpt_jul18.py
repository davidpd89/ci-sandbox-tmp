import sys
from ask_chatgpt_rrss import ask

Q = """Necesito 1 concepto para un vídeo de 5 segundos en PixVerse para Instagram/TikTok lectores de fantasía.

REGLA CRÍTICA: máximo 2-3 líneas de texto en pantalla, cada una ≤2 segundos. Total texto = 5s exactos.

DATOS DE LO QUE MEJOR FUNCIONA (métricas reales nuestras):
- "Echas de menos quién eras": 803 views TikTok (TOP)
- "¿Cuál fue el primer libro que te hizo llorar a escondidas?": 763 views, 14 likes
- "Si se odian demasiado, ya sospecho": concept fuerte
- La estructura que funciona: confesión específica + detalle concreto + pregunta participativa

YA USADOS (no repetir):
- Kindle con polvo
- Resaca de libro
- Enemies to lovers
- Capítulo más de noche
- Librería "solo a mirar"
- Magia con coste (3 veces)
- Pila de pendientes (3 veces)
- Portales/puertas (saturado)
- Worldbuilding (3 veces)

HASHTAGS QUE YA USAMOS (no proponer estos):
#booktok #bookstagram #librosenespañol #lectores #frasesdelibros #booktokespañol #librosquemarcan
#leoporquequiero #parati #lectura #libros #bookaddicted #bloqueoloctor #kindle #resacaliteraria
#slowburn #enemiestolovers #romantasy #bookhumor #humorlector #bookworm #bookish #bookreels
#happyreader #autoresindie #escritoresespañoles #fantasiaepica #fantasybooks

ANTES DE PROPONER NADA: busca ahora mismo en Twitter/X, Reddit r/libros, o comentarios de TikTok booktok español, una frase REAL que haya escrito un lector humano que sirva de base. Cita la fuente.

Dame:
1. La frase real que encontraste (con fuente)
2. El concepto (máximo 2 frases explicando el ángulo)
3. Las 2-3 líneas exactas en pantalla (cada una ≤5 palabras, total ≤5s)
4. La pregunta para el caption
5. 10 hashtags NUEVOS que nunca hayamos usado, con datos de que tienen actividad real en julio 2026"""

print("Preguntando a GPT...")
r = ask(Q, timeout_s=300)
print("=== RESPUESTA ===")
print(r)
