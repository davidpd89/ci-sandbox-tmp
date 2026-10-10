# Ingesta comprobable de enlaces entre perfiles en nueve redes

Origen: [PR #85](https://github.com/davidpd89/ci-sandbox-tmp/pull/85) aporta un grafo de identidad offline, pero `Profile.links_observed` hoy depende de captura externa sin adaptadores.

## Encargo para GPT

Implementar (no investigar solamente) extractores y normalizadores **de solo lectura** de enlaces declarados, URL exacta de perfil, metadatos de web y evidencia de procedencia para X, Threads, Facebook, Pinterest, Reddit, Bluesky, Mastodon, TikTok e Instagram usando datos sintéticos. Reutilizar `tools/cross_network_identity.py` de #85 tras revisar su HEAD; no copiar el grafo ni alterar ejecutores. Fuente por red: API/WEB/MOBILE, id de perfil, momento de captura y evidencia en cada dirección. `links_observed=True` solo cuando ambas afirmaciones provienen de vistas públicas del actor correspondiente; invalidar capturas incompletas y rotas.

Investigar en GitHub código mantenido de parsers de enlaces, `rel=me`, AT Protocol, WebFinger y APIs públicas; comparar licencia y compatibilidad con Windows/Python 3.11; elegir la mínima reutilización con atribución. No realizar peticiones en tests; usar fixtures locales y validación de identidad `network|handle` del núcleo. Separar enlaces declarados de mera coincidencia de dominio y no mezclar cuentas distintas en plataformas.

Criterios: pruebas con URLs de perfil válidas/inválidas, alias y redirecciones simuladas, enlaces cruzados recíprocos/unidireccionales, redes sin metadatos, evidencias expiradas, errores parciales. Al menos un caso y adaptador documentado por las nueve redes, sin inventar acceso donde no exista. Añadir `docs/research/` con comparativa (SPDX, commit/tag), resultados de tests Windows/Ubuntu, revisión adversarial y reversión. No tocar estados reales, no escribir en redes, no merge; Claude controla la integración.
