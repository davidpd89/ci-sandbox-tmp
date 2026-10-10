# Adaptadores nativos de evidencia contextual para las nueve redes

Origen: segunda auditoría de la PR #74 (comentarios anclados al contexto). El contrato offline ya existe en tools/reply_context_grounding.py de esa PR; el mirror no conecta todavía **sus productores reales** con texto, cuerpo, padres, autor, material interpretado y fecha fiables. El repo privado tiene un H1 preparador, pero NO se debe trasladar sin revisar anonimización/procedencia.

## Encargo para GPT

**PR de IMPLEMENTACIÓN, no un informe sin código.** Leer la PR #74, su doc docs/research/context-grounded-commenting.md y docs/open-source-scouting/PROTOCOL.md. Consultar solo lectura los adaptadores del repo oficial davidpd89/rrss-davidporto-CODE en integracion/crecimiento-2026-10 cuando falte detalle al mirror, sin copiar material privado, fixtures con datos reales o secretos.

Crear puentes finos, reutilizando el contrato único de #74 **tras su integración**, para normalizar observaciones nativas de Bluesky, Mastodon, X, Threads, Facebook, Pinterest, Reddit, TikTok e Instagram. Preservar tres colas independientes WEB/API/MOBILE, ID remoto, timestamp verificable (#62), texto de publicación, cuerpo cuando exista, padres ordenados con ID estable, autor como metadata y media con origin/provenance. No convertir una caption de vídeo en una descripción de escenas no vistas, ni inventar información al faltar permisos, capturas o fechas. Las evidencias ausentes deben ser explícitas, y el ejecutor no debe interpretar fuentes como instrucciones.

Entregar implementaciones que consuman fixtures sintéticos de esquemas **reales** de cada API o extracción UI (sin efectuar consultas a cuentas). Incluir pruebas diferenciales 9 redes × 3 colas en Python 3.11 Windows/Ubuntu, casos visual-only, permalink estable, respuestas al padre, truncado, contexto parcial, fecha sin TZ, Unicode y diferencias de presencia de campos. Medir tasa de completitud y fuentes utilizables con denominadores y falsos positivos, sin proclamar calidad de comentarios sin benchmark ciego (#72).

Investigar repositorios públicos actuales y justificar licencia SPDX, mantenimiento y compatibilidad Windows/Python 3.11 con commits fijos. Reutilizar una pieza existente cuando aporte valor (también continuidad de los colectores propios); NO reescribir clientes ni duplicar algoritmo de scoring, guard de procedencia, evaluación de calidad ni historial. Añadir docs/research, código, tests, workflow, métricas, segunda revisión adversarial y rollback. Datos de prueba sintéticos, sin credenciales, sin llamadas/red social/acciones reales y **sin merge**; Claude integrará. Antes de crear más PR, consultar la lista de abiertas para evitar duplicados.

## Delimitación y dependencias

- #74: empaquetado, huella y auditoría de evidencia offline (no reimplementar).
- #22: política de respuestas/contexto/memoria (no repetir prompts/generador).
- #62: fuente de fecha; #61: antigüedad y necroposting; adaptarse a sus contratos.
- #72: benchmark de comentarios; #73: corpus humano; #75: anti-repetición; #77: continuidad de conversaciones.
- #79 / oficial: guard de prueba de generación y destino real; no sustituir ni reinterpretar.
- #70: discovery de likes/comentarios, no lectores de evidencias de respuestas.

## Criterios de aceptación

Un lector ficticio con publicación principal + hilo + visual anotado llega a un ContextPacket equivalente sin importar la red/cola **solo si el origen contiene esas evidencias**. Si falta media/fecha/padre, la ausencia aparece identificada; nunca se fabrica para llegar a paridad. La auditoría conserva destino real, y los adaptadores no modifican cuentas, ledgers, estados ni publican. Pruebas y rutas de integración documentan con precisión dónde no existe acceso/lector fiable y qué canario supervised Windows/Edge/Android queda pendiente.
