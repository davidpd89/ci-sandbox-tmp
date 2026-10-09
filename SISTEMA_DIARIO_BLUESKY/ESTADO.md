# Estado — Bluesky (leer esto primero, no los demás archivos)

**Añadido 22/09, mismo patrón que X/Threads/Instagram**: en una sesión rutinaria, este
archivo debería bastar para arrancar sin releer `REGLAS.md`/`CUENTAS_VIGILAR.md`/
`COMUNIDAD.md`/`PENDIENTES.md` enteros. **Lo actualiza Claude al cerrar cada sesión**
(automático vía `tools/bluesky_execute.py`) — si lleva varias sesiones sin tocarse,
desconfiar y revisar los archivos completos.

## Fidelización, reposts y comentarios (07/10 noche) — leer primero

- **Reposts**: máx. 3/día y solo `curated` (cuentas fieles que nos comentan/repostean, con post de nicho); el tope vive en `bluesky_execute.run_plan` (`repost_policy.guard`). Los 37 reposts automáticos de hoy se borraron.
- **Fidelización** (`tools/loyalty.py bluesky`, paso `post` de la ronda): cosecha de notificaciones a `00_OPERATIVO/inbound_interacciones.csv`, like al último post de quien nos da algo, follow de vuelta, respuesta a su comentario y comentario de primer paso (texto de ChatGPT). Plan: `bluesky_loyalty_plan.json`. Medida: `python tools/loyalty.py report`.
- **Comentarios**: `tools/api_comment_writer.py bluesky --reset` (paso `pre`) escribe las decisiones de la ronda con ChatGPT; sigue pausado mientras exista `00_OPERATIVO/respuestas_en_revision.flag`.

## Escala y autoauditoría (05/10) — leer primero

Objetivo de David: aprovechar la API (~10.000 acciones/día; hoy ~1.000) con calidad y variación. **Antes de tocar nada lee `cache/audit_latest.md`** (lo regenera cada ronda:
líneas `GAP:` con su acción correctiva) y `python tools/volume_ramp.py` (etapa y tabla). Plan, diagnóstico y piezas: `00_OPERATIVO/PLAN_BLUESKY_ESCALA_2026-10-05.md`.
Cada ronda mecánica hace: plan normal → oleada de semillas editoriales/escritores → oleada de follow-back → autoauditoría + decisión diaria de la rampa.

## Reserva persistente de candidatos (05/10 noche) — `tools/bluesky_pool.py`

El cuello de botella medido NO era la cuota de la API sino la **oferta de cuentas nuevas** (3.337 distintas en toda la semana) y un fallo de orden en el motor (594 de 1.000 perfiles
de la shortlist sin ningún post cargado). Ya corregido: la shortlist verifica los huecos (`_vet_shortlist_gaps`), lee los feeds en paralelo y la reserva `cache/pool.sqlite3`
(tarea horaria `RRSS_pool_minero`) acumula likers/reposters/seguidores/seguidos de ~134 semillas hispanohablantes (`python tools/bluesky_pool.py stats|top|mine`). El scan la ofrece
como fuente `pool` y atribuye cada acción a su fuente **first-touch** (`src=` del motivo). Plan de la ronda de la etapa 2: 381 → ~1.100 acciones. Detalle y consulta E a GPT:
`00_OPERATIVO/PLAN_BLUESKY_ESCALA_2026-10-05.md`. Si la autoauditoría marca `RESERVA` o «sin ningún post», es lo primero que hay que mirar.

## Rendimiento del ejecutor (05/10)

Medido: ~11 s por acción (3 peticiones por like, handle resuelto dos veces, dudas/parones del 15 %). Ahora `prefetch` en lotes de 25 + caché de DID + preflight en paralelo + dudas 6 %/parones 1 % desde la etapa 3.
Si una ronda vuelve a ir despacio, medir primero el tiempo por acción (registro/ledger) antes de culpar a la API: la cuota son 1.666 escrituras/hora.

## Respuestas (20-40 al día, a mano) y reposts

El volumen mecánico son likes + follows; **lo que escribe la IA son las replies** (lo que más conversación y follow-back da) y se hacen 20-40 buenas al día, no un porcentaje artificial.
`python tools/bluesky_reply_queue.py --n 40` lista las ocasiones del último scan (post en español del nicho, ≤3 días, 60-280 caracteres, sin enlaces ni peticiones de opinión, cuenta de 30-5.000
seguidores y sin reply nuestra en 30 días); se escriben siguiendo el menú de formatos de `00_OPERATIVO/GUIA_VOZ_REPLIES.md` (reacción corta, pregunta suelta, dato, opinión de una frase;
observación+pregunta ≤25 %), `python tools/bluesky_reply_queue.py plan decisiones.json` construye el plan y `python tools/bluesky_execute.py plan_replies.json` lo ejecuta.
Reposts automáticos: ≤8 por ronda (≈1,5 % del volumen), solo posts claramente del nicho (≥2 términos), explícitamente en español, ≤3 días, de cuentas de 30-5.000 seguidores
(`auto_repost_per_round`, lo fija la rampa); los repost siguen con su TTL (`bluesky_cleanup_ttl.py`).

## Última sesión

2026-10-07. sin acciones confirmadas. Detalle: `registro_interacciones.csv`.


## Métricas actuales (de `metricas.csv`, última fila)

Seguidores: 445. Siguiendo: 2410. Posts: 231.


## Pendientes reales (detalle completo en `PENDIENTES.md`)

Ninguno abierto a fecha 22/09 — ver `PENDIENTES.md` para el historial resuelto
(contraseña de aplicación, corrección de mínimos copiados de X).

## Recordatorios operativos (versión corta; razonamiento completo en `REGLAS.md`)

- **API directa, sin navegador.** El ejecutor usa pausas cortas de 3-8s y detiene
  todo el lote ante 429; no necesita imitar tiempos humanos de Playwright.
- **Presupuesto de calidad, no cuota mínima.** No existe escala operativa 0-12.
  Follows y texto pasan por `CRITERIOS_DIARIOS.md`; los likes mecánicos filtrados
  pueden salir en `auto_plan`.
- Límite de caracteres: **300**, NO 280 de X.
- "Citar" es un post propio con `embed` al original, no un botón de menú — cuenta
  para el límite de 300 caracteres igual que cualquier post.
- Nunca duplicar frases entre las 5 redes (`python tools/check_duplicate_phrase.py`).
- `searchPosts` SIEMPRE exige `BLUESKY_APP_PASSWORD` (a diferencia de profile/thread,
  que sí funcionan sin sesión).
- Verificar tildes y "ñ" antes de publicar (mismo chequeo que X/Threads/Instagram,
  `_check_spanish_orthography` ya integrado en `post()`/`reply_to()`/`quote()`).
- Bio/foto/enlaces: mantenimiento estándar de Claude, sin esperar aprobación para
  corregir un dato objetivamente desactualizado.

## Oleada de semillas editoriales/escritores (05/10) — `tools/bluesky_seed_wave.py`

Segunda fuente curada, además de las ~160 consultas por palabra clave del motor de crecimiento: **directorio de editoriales, librerías, escritores, reseñadores y clubes**
(`bluesky_seeds.json`, descubierto con `searchActors` —handles reales, nunca adivinados— y clasificado por la biografía) → se siguen las propias semillas (8/día) →
de cada semilla del día (12, la menos reciente primero; se aparcan las que dan <2 comentaristas) se leen sus últimos posts con respuestas (≤120 días) y se verifica a cada comentarista
(≤90 días, en español, del nicho, 15-12.000 seguidores, sigue a ≥40, sin política/ligue/activismo/negocio, no seguido ya) → **follow + like a su comentario** (la combinación que más
follow-back da: 26 % frente a 8,5 % del follow solo). Corre sola tras cada ronda mecánica (`PIPELINES["bluesky"]["post"]`; su fallo no tumba la ronda).
Primer día: 40 semillas halladas (editoriales como Atticus/Walden/Hela/Akane/Valdemar…), 26 acciones (17 follows).

## Pipeline diario — motor de crecimiento

1. Ronda normal:
   `python tools/bluesky_growth_flow.py prepare --strict`.
   Ronda profunda:
   `python tools/bluesky_growth_flow.py prepare --deep 20 --strict`.
2. El flujo genera `growth_state.json`, `growth_ai.json` y
   `growth_report.json`. La ronda cubre búsquedas externas aunque
   notifications/timeline ya tengan material, protege 110/280 lecturas para
   revisión/frontier y puede recorrer hasta 3 olas productivas del grafo.
3. La IA comprueba `readiness` y revisa primero `lane=acquisition`. El shortlist
   es de 150 perfiles (100 de adquisición, 50 de comunidad; ver `growth_config.json`);
   perfiles/posts recientes se enfrían para no repetir la misma ronda.
   **Follows (02/10):** el `auto_plan` solo sigue por encima de score 20 (9 de 119
   oportunidades). Después ejecutar `python tools/bluesky_followback_wave.py` y
   `python tools/bluesky_execute.py bluesky_follow_wave.json`: sigue a cuentas con
   bio de nicho que siguen a gente de vuelta (25 follows el 02/10 → mejor palanca
   de crecimiento que likes sueltos).
4. Guardar decisiones por ID y construir:
   `python tools/bluesky_growth_flow.py build decisions.json`.
5. Ejecutar una sola vez:
   `python tools/bluesky_execute.py plan.json`.
6. Si aparece un bug: registrar y terminar; mantenimiento separado.

**Regla de cierre:** cobertura + captación fresca + presupuesto. `--strict` devuelve
error si la ronda no alcanza cobertura o cantera nueva suficiente. Nunca "ya tengo
8 candidatos" ni "ya hice varios likes".

**Legacy:** `tools/bluesky_scan.py` queda solo para diagnóstico/regresión rápida; no
es el disparador diario.

## 06/10/2026
Post fijado nuevo: presentación con foto, web y enlaces a los dos libros (`tools/bluesky_pin.py`, idempotente). Ronda manual 08:33: 322 confirmadas, 1 fallo (502 de createRecord; ahora se reintenta). Recolectores Jetstream/gustos: arreglado el bloqueo de SQLite. Fuente `domain` rota por dominios de libros.
