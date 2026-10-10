import sys
from ask_chatgpt_rrss import ask

Q = """Eres director creativo de redes sociales. Tarea CONCRETA: proponer contenido genuinamente nuevo para @davidportodiaz (escritor fantasía juvenil española).

ANÁLISIS OBLIGATORIO ANTES DE PROPONER:
Busca ahora mismo en internet el perfil @davidportodiaz o david porto diaz escritor. Revisa qué hace la competencia que FUNCIONA y nosotros AÚN NO HEMOS HECHO.

PATRONES QUE YA HEMOS AGOTADO (prohibidos):
- Persona sola con libro de noche / cerrando libro
- Kindle con polvo o sin abrir
- "Echas de menos quién eras"
- Enemies to lovers genérico en librería
- Resaca de libro (libro cerrado → silencio)
- Frases tipo "ya seguiré" / "no avancé"
- Listas de 3 cosas de lectores
- Portales y puertas mágicas
- Worldbuilding abstracto

QUÉ HA FUNCIONADO MEJOR (métricas reales):
- "¿Cuál fue el primer libro que te hizo llorar a ESCONDIDAS?" → 763 views, 14 likes (el detalle "a escondidas" es la clave)
- "A veces no echas de menos a alguien, echas de menos quién eras" → 803 views (identidad, no el libro)
- Participación directa con pregunta ESPECÍFICA, no genérica

LO QUE NECESITO:
1 SOLA PROPUESTA completamente nueva (máx 3 líneas en pantalla, regla 2s por línea)
Que sea visualmente filmable en PixVerse: personaje(s), acción concreta, escena real
Que el hook en línea 1 funcione SOLO sin contexto
Inspirada en algo que hayas encontrado en internet hoy (booktok, bookstagram, Reddit), no inventado

No me propongas nada hasta haber buscado primero. Dime qué encontraste y luego la propuesta."""

print("Preguntando a ChatGPT...")
r = ask(Q, timeout_s=300)
print(r)
