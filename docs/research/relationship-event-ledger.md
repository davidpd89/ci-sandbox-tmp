# CI 84 — Ledger común de relaciones: implementación y auditoría

Fecha de investigación: **2026-10-10**. Rama exclusiva `research/74-relationship-event-ledger`; no merge.

## Problema

El estado actual de acciones es mutable y no permite reconstruir historias relacionales.

## Alternativas

Se contrastaron event sourcing completo, sqlite-utils, sqlite-chronicle y SQLite estándar; la tabla de candidatos más abajo detalla actividad y ajuste al problema.

## Licencias y procedencia

Fuente primaria: https://github.com/simonw/sqlite-utils
Fecha de consulta: 2026-10-10
Licencia SPDX: Apache-2.0
Referencia inmutable: https://github.com/simonw/sqlite-utils/tree/6bc1d33d583c54bd69fbdd2071117e2d38c354a1

No se copian fragmentos; se aplica el patrón SQLite documentado. Otros candidatos figuran en la comparativa.

## Decisión

Implementar almacenamiento mínimo con `sqlite3` estándar, sin dependencia nueva; mantener el ledger de reservas inalterado.

## Pruebas

Suite offline en Ubuntu y Windows Python 3.11, con importación sintética, concurrencia, rollback y proyección de seguimiento. Evidencia de los runs asociada a cada HEAD.

## Retirada

Retirar solo la base secundaria tras cerrar conexiones; no modificar ni eliminar los registros operativos.

## Objetivo y necesidad

Almacenar historial relacional verificable sin interferir en el ledger operativo.

## Inventario comprobado y necesidad

Se consultó mediante conector GitHub el repositorio **privado** `davidpd89/rrss-davidporto-CODE`,
rama `integracion/crecimiento-2026-10`, commit
[`5449513d9b545d0a6a72abf066ab6a779bfdad71`](https://github.com/davidpd89/rrss-davidporto-CODE/commit/5449513d9b545d0a6a72abf066ab6a779bfdad71)
**solo en lectura**. En particular:

- `tools/action_ledger.py`: SQLite `actions(kind,target)`, estados
  `reserved/confirmed/failed/uncertain/holdout/skipped_policy`, reserva y
  liquidación con `BEGIN IMMEDIATE`. Conserva **una fila mutable por objetivo**:
  no debe sustituirse ni alterarse porque evita duplicaciones de ejecución.
- `tools/growth_attribution.py`: lee `registro_interacciones.csv`, campos
  `fecha/cuenta/tipo/resultado/texto_usado` y followers; agrupa acciones
  por cuenta con información no siempre completa. `saltado_ya_*` es distinto
  de una nueva acción confirmada; combinarlo sin etiqueta crea atribuciones falsas.
- `tools/mechanical_round.py`: orquestación y colas de varias plataformas;
  algunos ejecutores comparten primitivos, otros mantienen formatos verticales.
- `tests/test_action_ledger.py`: las pruebas vigentes protegen reservas,
  `holdout`, `uncertain`, repetición y concurrencia.

**Hueco observado**: existe protección operativa, pero no un historial
relacional común, con procedencia e idempotencia duradera, para consultas de
secuencia, conversión madura y depuración. Esta PR añade un **segundo almacén**;
no cambia el estado del ejecutor ni presume conocer outcomes ausentes.

## Candidatos y licencia (repositorios públicos, commits inmutables verificados el 10/10)

**Repositorio fuente:** https://github.com/pyeventsourcing/eventsourcing (SPDX: BSD-3-Clause); https://github.com/simonw/sqlite-utils (SPDX: Apache-2.0); https://github.com/simonw/sqlite-chronicle (SPDX: Apache-2.0). **Código local nuevo:** sin fragmentos de terceros.

| Alternativa | Revisión comprobada / actividad | Licencia | Windows/Python 3.11 | Decisión |
| --- | --- | --- | --- | --- |
| [`pyeventsourcing/eventsourcing`](https://github.com/pyeventsourcing/eventsourcing/tree/575d42c10a821828639b90178ed56703abe9c9f1) | `575d42c` 19/08/2026; proyecto amplio, agregados, versiones, proyecciones y adaptador SQLite | BSD-3-Clause, en `pyproject.toml` | Python >=3.11; no se verificó un runner Windows de esa revisión | Exceso de superficie para la bitácora relacional: **no importar dependencia** |
| [`simonw/sqlite-utils`](https://github.com/simonw/sqlite-utils/tree/6bc1d33d583c54bd69fbdd2071117e2d38c354a1) | `6bc1d33` 22/09/2026; release 4.2.1, 13/08/2026; migraciones/transacciones | Apache-2.0 | Python >=3.10; soporte 3.11 documentado; Windows pendiente de CI de esta tarea | CLI de exploración/consultas útil, pero dependencia runtime innecesaria |
| [`simonw/sqlite-chronicle`](https://github.com/simonw/sqlite-chronicle/tree/ee8d2a1db5090d14279f0acb56b5d46a5c50e44c) | `ee8d2a1` 16/06/2026; triggers sobre una tabla *mutable* | Apache-2.0 | No verificada en Windows | Guarda cronología de mutaciones, **no** eventos de dominio append-only |
| [SQLite nativo](https://www.sqlite.org/isolation.html) vía `sqlite3` estándar | API de aislamiento, transacción de escritor único y [WAL](https://www.sqlite.org/wal.html) documentados; sin runtime nuevo | SQLite: public domain | Biblioteca estándar Python 3.11 y matriz de CI aquí | **Elegido**: heredar el patrón `BEGIN IMMEDIATE`, UNIQUE y WAL sin copiar código externo |

**Procedencia:** se reutiliza la semántica de *single writer*, claves únicas,
triggers y proyecciones de solo lectura, no archivos fuente de terceros.
No existe código copiado sujeto a cabeceras de atribución. Se conservan los
enlaces/SHAs para reevaluar una dependencia si aumentan los requisitos.
La licencia y la actividad no garantizan automáticamente compatibilidad operativa.

## Contrato entregado

Módulo: [`tools/relationship_event_ledger.py`](../../tools/relationship_event_ledger.py).

- Nueve namespaces independientes: `x`, `threads`, `facebook`,
  `pinterest`, `reddit`, `bluesky`, `mastodon`, `tiktok`, `instagram`.
  Tres productores/colas: `WEB/API/MOBILE`. Los nueve aceptan exactamente el
  mismo esquema. **No** se infiere ejecución real en nueve redes.
- Campos obligatorios: red, cola, sujeto canónico, tipo, outcome, UTC,
  precisión temporal, origen y ID estable del origen. Opcionales:
  correlación y destino. `digest` y `event_id` SHA-256 derivados de identidad
  de procedencia, no del nombre visual. Los identificadores de URLs preservan
  mayúsculas relevantes en paths; las cuentas normalizan `@` y casefold.
- Tipos: `follow/unfollow/like/comment/reply/repost/visit/followback`.
  Outcomes distinguen `confirmed/observed/uncertain/failed/skipped/unverified`,
  más observaciones de seguimiento `present/absent`; ninguna observación
  equivale a efectuar una acción. `saltado_ya_*` se registra como `observed`
  pero **no** cuenta como follow nuevo.
- Append-only con triggers que rechazan `UPDATE` y `DELETE`, versión de
  esquema `PRAGMA user_version=1`, claves únicas, índices de historial y
  cohorts, transacciones `BEGIN IMMEDIATE`, WAL y `busy_timeout`.
  Replay exacto devuelve `replayed`; reuso divergente del mismo source ID
  aborta el lote (no sobrescribe hechos).
- `append_many`: validación previa y **una transacción por exportación**
  — ningún evento de la importación queda escrito cuando un registro tardío
  falla la validación o colisiona.
- `reconcile_followers`: todos los presentes observados, ausentes **solo**
  con `complete=True`, snapshot ID estable y hora UTC explícita. Una captura
  parcial no fabrica bajas. No infiere unfollow remoto.
- `history(red,sujeto)` devuelve el historial ordenado y `conversion(...)`
  presenta `eligible/observed/positive/negative/unknown`. La tasa usa solo
  observados, nunca convierte *missing* en `False`, ni llama éxito a un
  `follow` incierto. Último snapshot posterior al follow, exclusión de
  unfollows confirmados; mínimo de antigüedad parametrizable.
- No se persiste `texto_usado`, cookies, tokens, cabeceras de cuenta ni
  respuestas completas de APIs. La procedencia se almacena como ID lógico.
  No existe código de llamadas a redes; **no** se hace auto-like en X.

## Migración vertical concreta: `registro_interacciones.csv`

Los CSV históricos se conservan **intactos**. Tras efectuar una copia sintética
o exportación explícita, el importador acepta el formato que analiza
`growth_attribution.py`: `fecha,cuenta,tipo,resultado,texto_usado,url`.
`favourite/vote` normalizan a `like`, `boost/quote` a `repost`;
`follow+reply` produce dos eventos correlacionados. Un tipo desconocido
no se inventa: se informa en `ignored`. Se identifica el archivo por un
`--source-id` inmutable (cambiar versión si se reordena o modifica).

Prueba local *sin cuentas*, sustituyendo el fichero por datos sintéticos:

```bash
python tools/relationship_event_ledger.py --db /tmp/relaciones-demo.sqlite \
  --csv /tmp/interacciones-demo.csv --network bluesky --queue API \
  --source-id fixture-v1
python -m unittest discover -s tests -p test_relationship_event_ledger.py -v
```

En Windows, sustituir las rutas por las de un directorio temporal y ejecutar
el comando en una sola línea. Importar cada exportación de cualquier red
cambiando `--network`, `--queue` y `--source-id`. Se migra **el
contrato de una ruta vertical** para las nueve variantes sobre fixtures;
los productores reales aún **no están conectados** a esta nueva API.

Las fechas históricas solo con día se codifican como 12:00 UTC y
`precision=day` para identificar expresamente la aproximación (no hay hora
real). Las fechas con hora sin zona se rechazan, evitando inferencias DST.
No utilizar esa hora sintética para medir latencias de respuesta.

## Evidencia y método de prueba

Regresiones: [`tests/test_relationship_event_ledger.py`](../../tests/test_relationship_event_ledger.py).
Matriz automatizada [`.github/workflows/relationship-event-ledger.yml`](../../.github/workflows/relationship-event-ledger.yml),
Ubuntu/Windows Python 3.11 sin credenciales ni dependencias externas.
Casos: nueve redes/tres colas, Unicode, URLs sensibles a mayúsculas,
normalización UTC y fallo DST, dos eventos correlacionados,
replay y conflicto, trigger append-only, bloqueo de la DB operativa,
concurrencia de doce escritores, integridad de lote ante error y replay
de 500 eventos, doble importación CSV, huella de minimización de datos,
`unknown` de snapshot parcial, evidencia positiva/negativa de snapshot
completo, madurez temporal, unfollow y re-follow.

**Comparación estructural**, no benchmark cronometrado ni medida de producción:
importar 500 eventos con la primera implementación requería hasta 500
conexiones/BEGIN/COMMIT y lecturas WAL; con `append_many` requiere una
conexión/BEGIN/COMMIT. `500:1` es reducción de transacciones del diseño,
**no** aceleración empírica x500 ni comprobación de carga productiva.
La prueba hace 500 inserts + 500 replays y comprueba contadores.
La suite automática será evidencia definitiva al quedar los runs asociados
al HEAD final; no atribuir resultados verdes a un commit posterior.

## Segunda auditoría adversarial

1. **Riesgo identificado y corregido:** importación fila a fila dejaba estado
   parcial tras una fila inválida, ralentizaba y reabría SQLite continuamente;
   se añadió `append_many` con prevalidación + rollback integral y regresiones.
2. **Riesgo identificado y corregido:** `@@` normalizaba a identidad vacía
   tras `lstrip`; ahora se rechaza. URL/AT-URI no se reduce a minúsculas.
3. **Resultado no confirmado no suma conversión.** `saltado_ya_seguido`
   y `incierto` se conservan distintos de `confirmado`.
4. **Snapshots parciales conservan desconocidos**, sin mezclar una ausencia
   de feed con un abandono real. Un snapshot completo es una **afirmación
   del productor**, todavía no verificada en los nueve sistemas reales.
5. **Limitación actual:** no hay integración con nueve emisores productivos,
   ni reconciliación del ledger operativo, ni evaluaciones reales de
   retención. Es un contrato y migrador probado offline; la integración
   debe incorporar ACK/evidencia y distinguir simulación de canario supervisado.
6. **Limitación operativa:** WAL requiere disco local compartido por procesos,
   no unidad de red; la portabilidad entre Windows y Linux queda supeditada
   a ejecución verde de la matriz; Edge real, móvil y API de cada plataforma
   no se prueban. Datos sintéticos; ninguna acción social.
7. **Revisión de seguridad de datos:** sin escrituras en fichero origen ni
   logs que serialicen contenido de comentarios; un operador debe elegir
   rutas y versiones de exportación sin datos secretos. Identidades públicas
   conservadas en DB local: restringir permisos de fichero y backups.

## Rollback y evolución

No se altera `tools/action_ledger.py`, su SQLite, los CSV originales ni
los planificadores. Reversión: detener el importador, conservar/exportar la
nueva base si interesa auditoría y retirar **solo la base secundaria**
(y sus archivos WAL/SHM con conexiones cerradas). No hay migración
destructiva. Antes de cambiar esquema, añadir migraciones versionadas
repetibles (el `user_version` actual rechaza futuras versiones desconocidas).

**Dependencia de integración** para Claude: enumerar productores por red y cola
que emitan confirmaciones estables; mapear IDs y correlaciones entre reservas,
confirmaciones, lectores y snapshots *sin* atribuir acción a los skips.
Sin pruebas con actores reales ni canario supervisado, la paridad es
de contrato/fixtures, no de cobertura productiva.
