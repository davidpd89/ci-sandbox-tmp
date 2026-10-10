# PR #69 — Fidelización desde engagement entrante

Fecha: 10/10/2026. Rama: research/59-inbound-engagement-loyalty.
Fuente primaria: https://github.com/chatwoot/chatwoot/tree/e212425e7b1814614bdf8b0beea42ce689baad5c
Fecha de consulta: 2026-10-10
Licencia SPDX: MIT
Referencia inmutable: N/A (sin codigo incorporado)
Nota: MIT solo para la parte comunitaria de Chatwoot; enterprise/ excluido.

## Problema y contraste con repositorio oficial

Consultado en modo lectura el privado davidpd89/rrss-davidporto-CODE, rama integracion/crecimiento-2026-10, HEAD 5449513d9b545d0a6a72abf066ab6a779bfdad71. No se copió código, datos, configuraciones ni cuentas privadas al mirror.

- tools/loyalty.py: cosecha y premios de Bluesky y Mastodon conectados a tools/mechanical_round.py.
- tools/relationship_policy.py: CSV inbound con **una** fila por red/cuenta/tipo/día. NO contabiliza todos los eventos separados del mismo día.
- tools/loyalty_events.py: eventos individuales verificados X/Threads identificados por (network,event_id) en SQLite, sin escribir premios.
- PR [#25](https://github.com/davidpd89/ci-sandbox-tmp/pull/25): fichas/hilos CRM, no reemplazar. #70: discovery, #71: priorización global. Esta PR cubre exclusivamente scoring de engagement entrante y colas de revisión, sin escribir estados ni automatizar acciones.

Hueco reproducible: falta una proyección común que trate eventos identificados y el registro diario sin sumar ambos, puntúe recencia/frecuencia/profundidad/diversidad/recurrencia, dé oportunidades editoriales y mida visitas recurrentes por red.

## Alternativas

| Fuente pública, commit fijo | Licencia | Actividad observada | Decisión |
| --- | --- | --- | --- |
| [Chatwoot e212425](https://github.com/chatwoot/chatwoot/tree/e212425e7b1814614bdf8b0beea42ce689baad5c) | [MIT fuera de enterprise](https://github.com/chatwoot/chatwoot/blob/e212425e7b1814614bdf8b0beea42ce689baad5c/LICENSE) | commit 09/10/2026 | Modelo de inbox/contacto; Rails/Redis/DB excesivos para proyección de Python |
| [Monica 6e6ec21](https://github.com/monicahq/monica/tree/6e6ec217457e946e330ba7cd3b28107f4332c7b1) | AGPL-3.0 | commit 24/09/2026 | Inspiración de memoria de relaciones, PHP/Laravel no encaja como componente Python |
| [Mautic bc46b64](https://github.com/mautic/mautic/tree/bc46b64883255608e5b14a41987c207de9535616) | [GPL-3.0-or-later](https://github.com/mautic/mautic/blob/bc46b64883255608e5b14a41987c207de9535616/LICENSE.txt) | commit 09/10/2026 | Patrón de puntuación multiseñal; servicio PHP no encaja |
| [erxes bfe129a](https://github.com/erxes/erxes/tree/bfe129a372211b90744b36d599f0614ff5da70de) | AGPLv3 con condición adicional de SaaS, EE separada: [licencia](https://github.com/erxes/erxes/blob/bfe129a372211b90744b36d599f0614ff5da70de/LICENSE.md) | commit 09/10/2026 | Suite Nx/TypeScript de mayor complejidad; no se importa |
| Continuar Python stdlib del RRSS | Sin terceros nuevos | Compatible Python 3.11 | **Elegido**: sin servicio residente, dependencia ni estado adicional |

## Licencias y procedencia

No se han incorporado fragmentos ajenos. Las licencias no autorizan genéricamente copiar las partes EE; ninguna depende aquí de ellas. No hay nuevas dependencias transitivas. Mantenimiento observado no equivale a garantía de seguridad futura. Compatibilidad de la solución nueva prevista para Python 3.11 Windows y Ubuntu, probada por CI.

## Decisión

El entregable es tools/inbound_loyalty_priority.py, con tests/test_inbound_loyalty_priority.py y workflow propio.

- Adaptador CSV diario existente más JSON opcional de eventos individuales con event_id, sin rutas predeterminadas a estados reales. ID individual deduplicado por red/ID; CSV diario por red/persona/tipo/día, con prevalencia del evento individual para evitar doble cómputo. Colisiones contradictorias rechazadas. Identidades por actor_id cuando consta y alias de handle solo si no ambiguo.
- Nueve redes: X, Threads, Facebook, Pinterest, Reddit, Bluesky, Mastodon, TikTok e Instagram. Normaliza like/favourite, repost/boost, follow, comment, reply, mention, save/bookmark. La capacidad **de procesar** un tipo no afirma que ya exista colector para ese tipo/red.
- Score explicable, sin modelo entrenado: recencia 0–6, frecuencia 0–10, profundidad por tipo 0–12, diversidad 0–8, recurrencia por días distintos 0–8. Satura spam repetitivo. Propuestas: reply_review/context_review solo para ref y answered=False, thank_review ante follow, actividad diversa o recurrente, visit_recent_review para post original verificado, nicho español y edad no mayor a 7 días.
- Colas WEB (X, Threads, Facebook, Pinterest, Instagram), API (Bluesky, Mastodon), MOBILE (TikTok) y UNASSIGNED (Reddit, sin afirmar adaptador). Cuotas por cola y rotación entre redes dentro de la cola para evitar monopolio. Ninguna propuesta contiene texto listo para publicar ni acción ejecutable; prohibido convertirla sin revisión/preflight en un plan de ejecución. No hay auto-like X.
- Outbound confirmado puede evitar agradecer o visitar repetidamente dentro de 7 días y cerrar solo la propuesta de reply con el **mismo target_ref**. Los fallos o pendientes jamás suprimen acciones. Las fuentes de cobertura de cada red son complete/partial/unknown, default unknown.
- Métrica descriptiva por red: repetidores con >=2 días distintos entre cuentas con primera entrada anterior al día de referencia; tasa null sin cohorte elegible. NO es atribución de seguidores, causalidad ni retención de cohortes completas. Los snapshots parciales sesgan valores.

Ejemplo (únicamente archivos sintéticos):

    python tools/inbound_loyalty_priority.py --as-of 2026-10-10 --observations fixtures/events.json --legacy-csv fixtures/inbound.csv --outbound fixtures/confirmed.json --posts fixtures/posts.json --coverage fixtures/coverage.json

Si faltan ambas entradas de observaciones, el CLI falla explícitamente. No lee ni crea estado del RRSS automáticamente.

## Antes/después en fixture sintético

Dos filas de CSV duplicadas de la misma cuenta/tipo/día + dos eventos individuales distintos de ese mismo día: una suma ingenua ofrecería **4**, esta proyección conserva **2** (evidencia de desduplicación, no ganancia real). Con tres perfiles X de score alto y uno Facebook de score menor, cupo WEB=2: ordenación ciega da X/X; rotación da X/Facebook. Test reproducible para ambos casos. Sin pruebas de nuevos seguidores reales ni reclamaciones comerciales.

## Pruebas, segunda revisión adversarial y límites

Comando reproducible: python -m unittest discover -s tests -p test_inbound_loyalty_priority.py -v

Workflow .github/workflows/research-inbound-loyalty.yml con ubuntu-latest y windows-latest, Python 3.11, checkout/setup-python fijados por SHA, permisos de contenido de solo lectura. Verificar ejecución del último HEAD, no extrapolar ejecuciones previas.

1. Problema detectado: el CSV diario sobrecontaba likes si se combinaba con eventos de ID; corregido con precedencia de eventos y tests de replay/colisiones.
2. Problema detectado: ignorar el primer follow perdía un agradecimiento de revisión; corregido, sin generar acciones.
3. Problema detectado: un ranking global monopolizaba WEB con una red; corregido con rotación por redes y regresión de equidad.
4. Otros ataques sintéticos: fechas futuras, necroposting, target antiguo, contradicciones de event_id, cambio de handle, ausencia de answered, contexto parcial, estado outbound no confirmado, X sin auto-like, límites de cola, orden determinista, CSV corrupto y paridad de nueve redes.
5. Cobertura residual: no se ha probado Edge, móvil, Windows físico del usuario, API real, disponibilidad de likes/guardados en todas las redes, ni canario supervisado. Un ID aportado por el colector no prueba por sí solo su procedencia; esta debe verificarse en el adaptador. Las propuestas son **para revisión**, no autorizaciones de respuesta.

## Retirada

**Default-off**: ningún módulo del orquestador ni ejecutor importa esta proyección, sin escritura a base de datos, CSV o colas existentes. No hay migración. Rollback: eliminar script, tests, documento y workflow. Claude debe validar la procedencia y cobertura por red, evaluar en shadow mode privado y canario supervisado separado, mantener el preflight de edad/identidad y conectar con #25/#70/#71/#77/#84/#85 sin duplicar sus funciones. No tocar repo privado ni fusionar desde esta PR.

No se abren PR adicionales: los huecos relacionados ya tienen trabajos propios en las PR citadas.
