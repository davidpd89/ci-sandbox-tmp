# PR #20 — Investigación e implementación: calendario de publicaciones (09/10/2026)

## Hueco real

Se han leído el encargo, el protocolo y los módulos content_queue.py,
content_queue_alert.py, content_publisher.py, run_content_queue.py y round_queue.py.
Se contrastó el espejo con la rama integracion/crecimiento-2026-10
del repositorio oficial. El lector content_queue.py coincide exactamente
(blob d40e8c3efacf8811fc7aa4384dbec7ae9d83d120); el publicador del
oficial es posterior al del espejo. No se ha trasladado código privado.

La cola existente ya analiza fichas para nueve redes. Le faltaba una vista
temporal uniforme en UTC que detectara cambios de hora ambiguos o
inexistentes, solapamientos de la misma red y textos potencialmente
repetidos. No sería útil crear otro publicador.

## Comparación de software público comprobado el 09/10/2026

| Proyecto | Referencia fija y mantenimiento comprobado | Licencia y compatibilidad | Decisión |
| --- | --- | --- | --- |
| APScheduler | https://github.com/agronholm/apscheduler/tree/a660860d841c5426ec3b7ed2d4ada8fe168710f1 ; commit 08/10/2026 | MIT, master Python >=3.10, puede correr en Windows con Python 3.11 | No añadir scheduler residente: duplica el Programador de Windows |
| croniter | https://github.com/pallets-eco/croniter/tree/4be99c39c411485e89598a19e8de52a276291c89 ; 25/09/2026, release julio | MIT, Python >=3.9, pure Python | No hace falta parser cron: fichas son fechas puntuales |
| Postiz | https://github.com/gitroomhq/postiz-app/tree/91c91f633a0175fb3914dba64c932928c514b72a ; 09/10/2026 | AGPL-3.0; Node/Next/Nest/Temporal, no módulo Python pequeño | No portar la plataforma; conservar el patrón por red |
| Mixpost Lite | https://github.com/inovector/mixpost/tree/df57648b866310446703f5294350552b62735df5 ; 16/03/2026 | MIT; Laravel/PHP | Coste de reemplazo superior a beneficio |
| Lector existente | https://github.com/davidpd89/ci-sandbox-tmp/blob/research/10-publication-scheduling/tools/content_queue.py | Python 3.11 stdlib; zoneinfo y tzdata en CI | Reutilizar scan_items() y _ya_resuelto() |

No se ha copiado código de terceros, no hay licencia derivada nueva ni
dependencia runtime. Las referencias quedan fijadas a commits, no a HEAD
variable. Falta prueba de mantenimiento sostenido futuro, que no se promete.

## Solución

Se añade tools/publication_calendar.py. Genera JSON read-only por stdout:

    python tools/publication_calendar.py
    python tools/publication_calendar.py --network x --network bluesky
    python -m unittest discover -s tests -p test_publication_calendar.py -v

Cada ficha se identifica mediante id estable basado en red y ruta relativa;
no se exportan copies completos ni rutas absolutas. Se muestra hora local,
instante UTC, estado, carril, opt-in descriptivo, número de medios,
fingerprint y diagnósticos. Estados: due, future, stale, review, invalid,
resolved. Vigencia por defecto 14 días, sin cambiar parámetros del ejecutor.

Resolver hora local usando roundtrip UTC/zoneinfo rechaza los dos casos
DST problemáticos, en vez de elegir un offset al azar. Los avisos
possible_duplicate y slot_collision no borran contenidos ni reservan
posts: son señales para revisión editorial dentro de la misma red.

El mapa WEB X/Threads/Pinterest, API Facebook/Instagram/Bluesky/Mastodon/Reddit,
MOBILE TikTok describe el canal probable de publicación. No equivale
al reparto WEB/API/MOBILE de las rondas de interacción: Facebook e Instagram,
por ejemplo, disponen de adaptadores API de publicación. No afirma que esos
adaptadores estén activos. auto_opt_in es información, nunca permiso.

## Validación y segunda revisión adversarial

Las pruebas offline sintéticas cubren nueve redes, hora Madrid en verano
e invierno, dos transiciones DST de 2026, duplicados intra/interred,
colisiones por minuto, estados negativos/manuales, campos vacíos, medios,
vencimiento, rutas portátiles, determinismo y CLI JSON.

Antes: no había calendario UTC cruzado con detección de colisiones;
después: contrato de reporte reproducible. No se reclama un aumento de
rendimiento ni idempotencia real exactly-once del publicador. Para ello
haría falta una reserva transaccional independiente del calendario.

Segunda revisión: se corrigió el estado «no lista», «lista manual» y
«lista negra», que no deben clasificarse como una orden publicable.
Se evitó confundir coincidencias de contenido entre redes con duplicados.
Se separó la lógica de presentación de cualquier adaptador ejecutor.
El parser real aún no admite aclarar un fold DST dentro de las fichas;
debe resolverse editorialmente antes de ejecutar una publicación en esa hora.

Pendiente de Claude: Windows 3.11 en CI si el último workflow no concluye,
comprobación de los adaptadores operativos y un canario supervisado
separado de estas pruebas. No hubo acción real en redes.

Rollback: revertir los nuevos módulo, tests, workflow e informe.
No se crea estado persistente, no hay migración ni escritura de ficheros.
