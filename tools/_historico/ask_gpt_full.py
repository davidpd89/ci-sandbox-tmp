"""Pide a ChatGPT conceptos + hashtags para Jul 18-19 de RRSS DavidPorto."""
import sys
from ask_chatgpt_rrss import ask

Q1 = """Eres director de contenido de @davidportodiaz, escritor español de fantasía juvenil.
Necesito 5 conceptos de contenido nuevos para Instagram/TikTok para publicar el 18-19 de julio 2026.

DATOS REALES QUE NOS FUNCIONAN:
- "¿Cuál fue el primer libro que te hizo llorar a escondidas?" = 763 views, 14 likes TikTok (TOP)
- "Echas de menos quién eras" = 803 views TikTok
- "Me compré el Kindle para leer más. Ahí está. Cargado. Sin abrir." = gancho confesional concreto
- Reels con emoción directa/confesional: >40% ven más de 3s. Metáforas abstractas: <17%.

TEMAS YA USADOS (NO repetir):
Magia con coste (3x), pila de pendientes (3x), portales/puertas (saturado), worldbuilding (3x),
Kindle con polvo, capítulo más de noche, cerrar un libro, marcapáginas, recomendación de libro.

REGLA ABSOLUTA antes de responder: busca AHORA MISMO en Reddit r/libros, Twitter/X en español
y comentarios de TikTok booktok español, frases REALES escritas por lectores humanos.
Solo incluye conceptos basados en lo que encuentres. Cita la fuente de cada frase.

BUCKETS prioritarios (menos usados por nosotros):
- Enemies to lovers / slow burn (romantasy — comunidad muy activa)
- Humor lector específico (vergüenza/manías reales)
- Autores indie / proceso de escritura real de David
- Bloqueo lector / resaca de libro

Para cada concepto dame: (1) hook primera línea, (2) 3-4 líneas de texto pantalla,
(3) pregunta de participación, (4) prompt visual para IA."""

print("Pregunta 1: Conceptos de contenido...")
r1 = ask(Q1, timeout_s=300)
print("\n=== CONCEPTOS GPT ===")
print(r1)

Q2 = """Busca ahora en tiempo real qué hashtags en español sobre lectores/fantasía/bookstagram
tienen actividad REAL en julio 2026 en TikTok e Instagram.

HASHTAGS QUE YA USAMOS (NO repetir estos):
#booktok #bookstagram #librosenespañol #lectores #frasesdelibros #booktokespañol
#librosquemarcan #leoporquequiero #parati #lectura #libros #bookaddicted #bloqueoloctor
#kindle #booktokespanol #fantasiajuvenil #fantasiaespanola #portalfantasy #worldbuilding
#escritura #escritores #writingtips #autorindie

Necesito (con datos reales si los encuentras):
- 10 hashtags de nicho para lectores que NO son los de arriba (humor lector, slow burn, romantasy en español, etc.)
- 5 hashtags para escritores/autores indie españoles
- 5 hashtags de alta viralidad en booktok español que aún no usamos
- Los 3 hashtags de fantasía épica más activos en español ahora mismo"""

print("\nPregunta 2: Hashtags frescos...")
r2 = ask(Q2, timeout_s=300)
print("\n=== HASHTAGS GPT ===")
print(r2)
