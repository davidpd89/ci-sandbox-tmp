"""Pide a Perplexity hashtags variados para RRSS DavidPorto."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\GIT\manual escritura\novela fantasia\tools")
from ia_bridge import ask_notebooklm

# Usamos NotebookLM para Perplexity-style de búsqueda en tiempo real
# En realidad aquí usaremos el ask_chatgpt con búsqueda web
from ia_bridge import ask_chatgpt

PREGUNTA_HASHTAGS = """Busca ahora mismo en tiempo real (usa tu navegación web) qué hashtags en español sobre libros, lectores, fantasía y bookstagram están teniendo mayor rendimiento en TikTok e Instagram en julio 2026.

HASHTAGS QUE YA USAMOS SIEMPRE (NO proponer estos, están agotados para nosotros):
#booktok #bookstagram #librosenespañol #lectores #frasesdelibros #booktokespañol #librosquemarcan #leoporquequiero #parati #bookaddicted #lectura #libros #books #booktokespañol

Necesito:
1. 15 hashtags de nicho que NO sean los de arriba, con datos reales de volumen/engagement si los encuentras (romantasy, slow burn, fantasía española, escritores, autores indie, bloqueo lector, etc.)
2. 5 hashtags para formato "humor de lector" en español
3. 5 hashtags para autores indie españoles
4. 3 hashtags para cada una de estas categorías: (a) recomendaciones de libros, (b) mundos de fantasía, (c) proceso de escritura

Solo hashtags con actividad real demostrable. Si no tienes dato real de que exista comunidad activa, no lo incluyas."""

print("Preguntando a ChatGPT sobre hashtags...")
resp = ask_chatgpt(PREGUNTA_HASHTAGS, timeout_s=300, new_thread=False)
print("\n=== RESPUESTA HASHTAGS ===")
print(resp)
