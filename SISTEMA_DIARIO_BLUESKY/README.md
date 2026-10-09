# Sistema diario — Bluesky

Tercera pata del mismo sistema que `../SISTEMA_DIARIO_X/` y
`../SISTEMA_DIARIO_THREADS/` — mismos principios de fondo (Rama 1/Rama 2,
reciprocidad con mes de margen, checklist anti-IA, verificar antes de dar
por bueno), aplicados desde el primer día en vez de aprendidos a base de
corregir errores como en X.

## Diferencia real de fondo con X y Threads: aquí se automatiza por API, no por navegador

`tools/x_interact.py` y `tools/threads_interact.py` controlan un Edge real
vía CDP porque X/Threads no dan alternativa razonable y además detectan
bots agresivamente. **Bluesky es distinto de verdad**: corre sobre AT
Protocol, una API abierta y documentada pensada exactamente para esto.
`tools/bluesky_interact.py` habla HTTP/JSON directo (librería `requests`,
sin Playwright, sin perfil de Edge, sin CDP) — más simple, más robusto, sin
la fragilidad de bot-detection que ya dio tantos dolores de cabeza en X.

**Autenticación**: `BLUESKY_HANDLE` y `BLUESKY_APP_PASSWORD` en el `.env` de
la raíz del repo. La contraseña de aplicación se genera en bsky.app
→ Configuración → Privacidad y seguridad → Contraseñas de aplicación — NUNCA
la contraseña real de la cuenta (igual de importante que nunca haber tocado
las cookies de sesión reales de X). David la genera y la pega él mismo en
`.env`, exactamente igual que ya están `PEXELS_API_KEY`/`PIXABAY_API_KEY`.
La sesión autenticada ya forma parte del flujo operativo; `PENDIENTES.md` conserva
el histórico y las decisiones que todavía requieran intervención de David.

Sin esa contraseña, `bluesky_interact.py profile <handle>` y
`bluesky_interact.py thread <url>` ya funcionan (lectura pública, sin
sesión). Todo lo demás (`search`, `notifications`, `timeline`, y cualquier
acción de escritura: `reply`/`like`/`repost`/`quote`/`follow`/`unfollow`/
`post`) necesita la sesión autenticada.

## Identidad y publicación

No fijar aquí un handle literal: `tools/bluesky_interact.py health` resuelve el DID
autenticado y muestra el handle real de la sesión. La publicación/programación propia
es manual/nativa. Metricool está cancelado y no forma parte del flujo operativo.

## Orden de lectura recomendado — ronda diaria

Para minimizar contexto, leer solo:

1. **`ESTADO.md`** — estado actual resumido.
2. **`CRITERIOS_DIARIOS.md`** — qué decide el script y qué necesita IA.
3. **`PROCESO.md`** — motor de crecimiento, cobertura y comandos.

Abrir `REGLAS.md`, `CUENTAS_VIGILAR.md`, `COMUNIDAD.md` o `PENDIENTES.md` solo
si el caso concreto lo exige. El antiguo
`SISTEMA_DIARIO_GPT investigation/BLUESKY.md` fue borrado tras incorporar su
contenido útil: **no buscarlo ni intentar reconstruirlo durante una ronda diaria**.

`../00_OPERATIVO/REDES/bluesky/estrategia.md` es contexto editorial secundario,
no lectura obligatoria de cada sesión.

El contrato general de crecimiento vive en
`../00_OPERATIVO/02_FLUJOS/crecimiento-organico.md`.

Para una sesión profunda existe un recolector Jetstream opcional
(`tools/bluesky_jetstream_collect.py`): escucha durante una ventana sin IA y deja
una cache local para el growth scan. Dependencia separada en
`requirements-bluesky-jetstream.txt`, no requerida para el resto del repo.

Investigación técnica y repos públicos revisados:
`INVESTIGACION_GROWTH_2026-09-29.md`.

Bluesky lo implementa mediante `tools/bluesky_growth_flow.py`, que orquesta
`bluesky_growth_scan.py` y deja preparados el estado completo, la vista compacta
para IA y el informe de readiness. El antiguo `tools/bluesky_scan.py` es
diagnóstico, no la ronda diaria.

Ronda normal:

```
python tools/bluesky_growth_flow.py prepare --strict
```

Ronda profunda, aprovechando Jetstream + taste local antes del scan:

```
python tools/bluesky_growth_flow.py prepare --deep 20 --strict
```

Tras la decisión de Claude:

```
python tools/bluesky_growth_flow.py build decisions.json
python tools/bluesky_execute.py plan.json
```

`--strict` no exige N acciones. Exige que la exploración esté completa y que el
shortlist alcance el objetivo de captación fresca; si no, devuelve error en vez de
presentar una ronda repetitiva como éxito.

## Compartido con X y Threads, no duplicado aquí

- **Checklist anti-IA y frases prohibidas**: `../SISTEMA_DIARIO_X/FRASES_PROHIBIDAS.md`
  (aplica igual, es sobre cómo suena un texto, no sobre la red).
- **`tools/check_duplicate_phrase.py`**: comprueba un fragmento de texto
  contra los tres `registro_interacciones.csv` (X, Threads, Bluesky) a la
  vez, no solo el de esta carpeta — **usarlo siempre antes de aprobar una
  respuesta/cita**, ver "No duplicar entre redes" en `REGLAS.md`. Nació el
  21/09 a petición explícita de David al extender el sistema a Bluesky:
  "sobre todo el tema de no duplicar comentarios hay que tener cuidado con
  eso."
- **Las dos ramas** y el **mes de margen de reciprocidad**: mismo marco
  exacto que `../SISTEMA_DIARIO_X/REGLAS.md` ("Las dos ramas"), aplicado
  aquí desde el día 1.
