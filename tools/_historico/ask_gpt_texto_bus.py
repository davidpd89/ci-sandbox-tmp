import sys
from ask_chatgpt_rrss import ask

Q = """Tengo un vídeo de una chica en parada de bus, absorta leyendo, el bus llega y se va sin ella, y al final ella levanta la vista tarde con cara de "y qué".

El texto que tenía era: "Llegué tarde por una escena. / Iba a parar. Mentí."
David dice que es IA 100%, que nadie habla así. Tiene razón.

TAREA CONCRETA: busca ahora mismo en Twitter/X España o Reddit r/libros cómo describen realmente los lectores españoles cuando se les va un bus/tren/cita leyendo. La jerga real, el registro coloquial, el humor sin esfuerzo.

Lo que necesito:
- 3 líneas máximo en pantalla
- Cada línea ≤5 palabras
- Total ≤5s (regla 2s por línea)
- Que suenen como algo que ESCRIBIRÍAS A UN AMIGO POR WHATSAPP, no para Instagram
- Sin metáforas, sin ser listo, sin double meaning forzado
- El humor tiene que ser reconocible al instante

Ejemplos del TIPO de registro que busco (no necesariamente estas):
- "Me comí el bus." (hecho, sin drama)
- "Tenía que saber qué pasaba." (lógica lectora)
- "¿A qué llegas tú tarde?" (participación directa)

Busca primero qué dice la gente de verdad y dame las 3 líneas definitivas."""

print("Preguntando ChatGPT...")
r = ask(Q, timeout_s=300)
print(r)
