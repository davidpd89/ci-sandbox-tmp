# PR #59 — Memoria de no reciprocidad repetida (10/10/2026)

**Ámbito:** sólo `research/49-repeated-nonreciprocity-memory`, espejo público sanitizado. Este documento y los tests no contienen cuentas reales, secretos ni exportaciones del usuario. **Sin merge ni acciones sociales.**

## Diagnóstico y contexto del repositorio oficial

Se consultó `davidpd89/rrss-davidporto-CODE`, rama `integracion/crecimiento-2026-10`. Su `tools/relationship_policy.py` SHA de blob `ca294952069ebab608de677c93a87101b4033b95` es **idéntico** al del espejo antes del cambio. Regla preexistente: enfriamiento fijo de 21 días y exclusión tras 3 `unfollow` por «no devuelve». `tools/scan_common.py` delega `discarded_handles()` en `relationship_policy.blocked_accounts()`, y es consumido por los scans de las redes. `follow_review.py` produce informes; `unfollow_cleanup.py` genera eventos cuando hay confirmación. No se copiaron datos ni módulos nuevos del repositorio privado.

Huecos comprobados: la lógica sumaba cada `unfollow` sin distinguir ciclos duplicados, carecía de evidencia por fila y prioridad histórica, no admitía ventana/expiración configurables y recalculaba sobre CSV sin materialización opcional común. La falta de un `follow` confirmado no demuestra un intento fallido. Tampoco «no se encontró entre seguidores» demuestra falta de reciprocidad.

## Comparación pública, licencias y decisión

| Candidato | Evidencia y mantenimiento al 10/10/2026 | Python 3.11 / Windows / licencia | Decisión |
| --- | --- | --- | --- |
| Código existente `relationship_policy.py` + `sqlite3` stdlib | Ya comparte normas por red; `sqlite3` estándar de CPython 3.11 ofrece transacciones, parámetros SQL y `BEGIN` implícito | Sí / sí / licencia Python y código propio | **Conservar e integrar**, sin nueva dependencia |
| [simonw/sqlite-utils 4.2.1](https://github.com/simonw/sqlite-utils/tree/28dc6278cc03a9245325d056e6986818544abc68) | Release 13/08/2026; upstream activo 09/10; incorpora migraciones y transacciones | Soporta 3.11; multiplataforma; **Apache-2.0** (LICENSE verificado) | Interesante si el esquema crece, pero excesivo para una tabla y una proyección pequeña; no se copiaron archivos |
| [networkx/networkx 3.7](https://github.com/networkx/networkx/tree/c7845e90bc0c5b9f470b9a3695256bdbf3b38bd6) | Release 21/09/2026, activo 06/10; grafos complejos | **BSD-3-Clause**; 3.7 requiere Python >=3.12, por tanto **no compatible** con objetivo 3.11 | No importar, la memoria es una relación (red, cuenta), no un grafo |
| [subzeroid/instagrapi 3.0.21](https://github.com/subzeroid/instagrapi/tree/618804d49486ef5f7ec92d3463a3057c4183d35d) | Release 09/10/2026; activo; cliente de Instagram | Python 3.10+, multiplataforma; **MIT**, confirmado en LICENSE | No ofrece memoria genérica ni cubre otras 8 redes; sin necesidad de importarlo |
| [ricardojoserf/instagram-followers-bot](https://github.com/ricardojoserf/instagram-followers-bot) | Repositorio de follow/unfollow por plataforma, sin prueba de un motor de memoria común | Licencia de reutilización **no verificada** | Descartado; ninguna pieza copiada |

Ningún módulo de tercero se ha copiado o adaptado. Patrones usados: eventos confirmados, SQLite transaccional, idempotencia, proyección por identidad de cuenta. La procedencia del código nuevo es propia; la bibliografía anterior informa la decisión técnica.

## Entregable

- `tools/relationship_memory.py`: dataclasses `Event`, `Policy`; `events_from_rows`, `decision`, `decisions_from_rows`; `RelationshipMemory` para importar de forma **explícita** CSV sintéticos o aprobados, consultar eventos y sustituir un origen transaccionalmente. La clave es **(red, origen, fila)**, nunca el handle desnudo a través de redes. Identidades federadas conservan `@dominio`.
- `tools/relationship_policy.py`: `blocked_accounts()` se apoya en la proyección pura de eventos; `blacklist()` y `follow_memory_ranking()` leen la misma política. La interfaz `scan_common.discarded_handles()` no cambia, de modo que los adaptadores que ya pasan por ese filtro reciben el comportamiento nuevo sin hacer E/S extra. El ranking común expone la penalización para integrarla en ordenadores de candidatos; **no se afirma** que todos los ordenadores individuales la apliquen ya.
- `tests/test_repeated_nonreciprocity_memory.py`: regresiones de límites de fechas, dos y tres intentos, duplicados, omisiones, confirmación de followback, bloqueos persistentes, procedencia, migración reversible, paridad sintética de las nueve redes y comparación de embudo.

**Norma por defecto:** primer fallo confirmado 21 días de espera; segundo, 42 días (máximo configurable 84); tercero, exclusión sin caducidad. Una oportunidad se acredita por ciclo `follow` confirmado → `unfollow` «no devuelve» confirmado, nunca por ausencia inferida. Un registro histórico de unfollow sin su follow de origen cuenta *a lo sumo una vez* (compatibilidad prudente), y un `unfollow` permanente sin fecha permanece excluido. Una señal entrante explícita `reciprocated` / `followback_verified` limpia la racha, pero no levanta bloqueos permanentes.

**Configuración opcional**, leída de `00_OPERATIVO/reciprocidad_politica.json` sin cambiarlo en esta PR, campo global `memoria_reciprocidad` o sobreescritura en `redes.<red>.memoria_reciprocidad`: `initial_days`, `multiplier`, `cap_days`, `max_failures`, `ban_days` (null: sin vencimiento), `lookback_days` (null: toda la historia), `penalty_per_failure`. Ejemplo **no aplicado**: `{"memoria_reciprocidad":{"initial_days":21,"multiplier":2,"ban_days":180}}`.

La migración SQLite es *opt-in*: `RelationshipMemory("ruta_nueva.db").import_csv("bluesky", "ruta_sintetica.csv")`. Sólo escribe el archivo indicado; no genera acciones, no lee credenciales, no toca estados reales. Repetir la importación produce el mismo historial; un CSV corregido sustituye atómicamente sólo su origen. Para revertir: retirar la integración de `blocked_accounts` y borrar exclusivamente la base auxiliar creada durante una prueba; el registro CSV original no se altera. No se crea ni conecta una base operativa nueva en esta PR.

## Medición (sintética, NO canario)

El test `test_synthetic_volume_and_conversion_proxy` fija 12 perfiles y **etiquetas de devolución inventadas**, todas entre enero y octubre de 2026: 4 nuevas cuentas, 3 con una experiencia fallida, 2 con dos, 2 con tres y una bloqueada. La espera fija de 21 días deja **9 candidatas / 3 éxitos etiquetados (33,3 %)**; la espera adaptativa deja **7 / 3 (42,9 %)**. Se evitan 2 nuevas ofertas repetidas sin perder los 3 éxitos de esa muestra, pero **no existe medida de conversión real ni inferencia causal**. En producción se necesitan cohortes por red y fechas comparables (PR #23 / #66), con denominadores de follows confirmados y nuevos seguidores verificados.

## Verificación, revisión adversarial y límites

Comando local: `python -m unittest discover -s tests -p test_repeated_nonreciprocity_memory.py -v`; en el prototipo local se ejecutaron **10/10 pruebas satisfactorias** antes de subir los archivos. La batería final versionada añade la integración con `relationship_policy` y la comparación sintética; su ejecución en CI de la PR deberá confirmarse por separado. No se probaron Windows vivo, Edge, móvil ni cuentas externas.

**Segunda revisión adversarial:** (1) impide contar el mismo unfollow dos veces; (2) no convierte un `saltado_ya_no_seguido` con motivo «no devuelve» en exclusión permanente; (3) no acepta un `followback` genérico como devolución verificada; (4) preserva descartes heredados sin fecha; (5) comprueba que una migración fallida no borre el origen; (6) cierra conexiones SQLite explícitamente; (7) evita que Instagram y X compartan memoria sólo por tener igual handle.

**Pendientes para Claude, sin hacer merge aquí:** ejecutar batería versionada + tests históricos `test_scan_common_history.py`, `test_relationship_policy_parity.py` y `test_unfollow_cleanup.py` en Python 3.11/Windows; revisar la importación explícita del histórico y reconcile con PR #58, #60 y #84 antes de introducir SQLite en operación; confirmar qué adaptadores externos pasan por `discarded_handles` y conectar el delta de ranking a PR #66. Sólo después plantear un canario supervisado de lectura sin modificación social.

No se abren PR adicionales: ciclo de estado (#57/#60), reconciliación (#58), ranking (#66) y ledger (#84) ya están encargados y una PR nueva duplicaría alcance.
