"""Pide a ChatGPT 5 conceptos de contenido nuevos para RRSS DavidPorto Jul 18-19."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\GIT\manual escritura\novela fantasia\tools")
from ia_bridge import ask_chatgpt

PREGUNTA = """Eres director de contenido de @davidportodiaz, escritor español de fantasía juvenil.
Necesito 5 conceptos de contenido nuevos para Instagram/TikTok para publicar el 18-19 de julio.

CONTEXTO CRÍTICO (datos reales de métricas):
- Los reels con gancho confesional concreto consiguen >40% de retención en los primeros 3s
- Los reels con metáforas abstractas (peso, distancia, movimiento) consiguen <17%
- En TikTok: "¿Cuál fue el primer libro que te hizo llorar a escondidas?" = 763 views, 14 likes (top)
- En TikTok: "Echas de menos quién eras" = 803 views
- Último publicado exitoso: "Me compré el Kindle para leer más. Ahí está. Cargado. Sin abrir."

TEMAS YA USADOS (NO repetir):
- Magia con coste (3 veces)
- Pila de pendientes/libros sin leer (3 veces)
- Portales/puertas mágicas (sobresaturado)
- Worldbuilding (3 veces)
- Kindle con polvo (recién publicado)
- "Un capítulo más de noche" (recién publicado)

REGLAS ABSOLUTAS:
1. SOLO frases que hayas encontrado escritas por humanos reales en internet (Reddit, Twitter/X, comentarios de TikTok, Goodreads). Busca ahora mismo antes de proponer nada.
2. Si la frase no aparece escrita por un humano real en algún sitio, no la incluyas.
3. Cero metáforas de peso/huida/movimiento abstracto.
4. Cero negaciones encadenadas tipo "No hay X. No hay Y."
5. Gancho en la primera línea que funcione solo sin contexto.
6. Cierra siempre con pregunta directa de participación.

BUCKETS disponibles (elegir los menos usados):
- Romantasy / slow burn / enemies to lovers
- Comunidad lectora (humor, identificación de tribu)
- Autor/proceso de escritura (David es escritor)
- Frases y textos (microficción confesional)
- IA visual / estética de fantasía

Dame 5 conceptos con: hook de primera línea, 3-4 líneas de texto en pantalla, pregunta de cierre, y el prompt visual para la IA generativa. Solo incluye conceptos basados en contenido humano real que hayas encontrado buscando ahora."""

print("Preguntando a ChatGPT...")
resp = ask_chatgpt(PREGUNTA, timeout_s=300, new_thread=False)
print("\n=== RESPUESTA GPT ===")
print(resp)
