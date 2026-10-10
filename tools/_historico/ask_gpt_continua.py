"""Pide continuación a GPT (ya está buscando desde la llamada anterior)."""
import sys
from ask_chatgpt_rrss import ask

# GPT ya recibió la pregunta y dijo "voy a buscar" — ahora pedimos que continúe
r = ask(
    "Continúa con la búsqueda y dame los 5 conceptos con frases humanas reales encontradas. "
    "Y luego los hashtags frescos que no usamos.",
    timeout_s=420
)
print("=== RESPUESTA COMPLETA ===")
print(r)
