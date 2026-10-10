# Colas, idempotencia y recuperación tras caídas

Fuente: informe de Perplexity (https://www.perplexity.ai/search/95399af9-55cd-4c62-bfea-86284b5509f4), generado 10/10/2026.

Investigación: colas de acciones sociales idempotentes y recuperables en Python

Resumen. Para el sistema de crecimiento social multired, la arquitectura más robusta y sencilla es un outbox transaccional sobre SQLite en modo WAL, con acciones persistidas antes de ejecutarlas, claves de idempotencia por red, reintentos con backoff, estados explícitos y bloqueo de fichero para coordinar procesos en Windows. Esta combinación evita perder acciones tras una caída y evita comentar dos veces el mismo post.
sqlite
+2

Hallazgos
Repositorio / patrón	Licencia	Qué reutilizar	Integración en el sistema	Riesgos técnicos	Tests propuestos
sandeepyadav1478/sqloutbox — outbox transaccional en SQLite para Python/asyncio 
github
	Revisar LICENSE en el repositorio antes de copiar código	Modelo de outbox persistente, worker de entrega, configuración y flujo de reintento	Base conceptual para social_actions en SQLite: una fila por acción candidata, con network, action_type, target_url, idempotency_key, status, attempts, next_run_at	Diseñado para un solo proceso; no adoptar su scheduler sin adaptarlo a workers por red	Inserción y recuperación tras kill; duplicados con la misma clave; reintento tras error HTTP
Smixi/python-outbox — implementación educativa del patrón outbox 
github
	Revisar licencia; el propio autor indica que no está mantenido ni recomendado para producción 
github
	Separación entre productor, almacenamiento del evento y publicador	Útil como referencia de arquitectura, no como dependencia	Mantenimiento detenido; no usar directamente	No aplica como dependencia; usar solo para comparar diseño
temporalio/sdk-python — durable execution y orquestación de workflows 
github
	MIT 
github
	Actividades reintentables, workflows duraderos, señales y recuperación automática	Opción futura si el sistema pasa a múltiples máquinas o necesita orquestación compleja; cada acción social puede ser una Activity con reintentos	Requiere servidor Temporal; añade infraestructura y latencia frente a SQLite local	Workflow que reinicia tras fallo; Activity con idempotencia; replay determinista
temporalio/samples-python — ejemplos oficiales 
github
	Revisar licencia del repositorio	Patrones de activities, retries y arranque local con temporal server start-dev	Referencia para migrar el worker de acciones a durable execution si crece el volumen	No sustituye al outbox local; es una alternativa operativa más pesada	Ejecutar samples en Windows/Python 3.11 y medir coste operativo
WoLpH/portalocker — bloqueo de ficheros multiplataforma 
github
	Revisar LICENSE en GitHub	portalocker.Lock como context manager; soporte Windows, Linux, macOS; locks exclusivos sin dependencias extra 
pypi
	Lock global scheduler.lock para impedir que dos procesos recojan la misma acción; lock por red si se paraleliza	Los shared locks en Windows requieren el extra win32; un lock de fichero no protege frente a procesos que no lo respetan 
pypi
	Dos procesos compiten por el mismo lock; liberación tras excepción; timeout y adquisición fallida
filelock — locking multiplataforma con LockFileEx en Windows 
py-filelock
	Revisar licencia en el repositorio	FileLock sencillo, alias multiplataforma y lock respaldado por SQLite para lectores/escritor 
py-filelock
	Alternativa más ligera a portalocker para un único lock de scheduler	Menos opciones que portalocker para semáforos, PID files o Redis	Misma batería que portalocker; comprobar comportamiento al morir el proceso
SQLite WAL — modo journaling recomendado 
sqlite
	Dominio público / documentación oficial	PRAGMA journal_mode=WAL, synchronous=NORMAL, checkpoints y busy_timeout	Persistencia local de cola, resultados, métricas y deduplicación	En WAL, synchronous=NORMAL puede perder las transacciones más recientes tras un corte eléctrico, aunque no corrompe la base 
sqlite
	Simular corte a mitad de transacción; verificar integridad con PRAGMA integrity_check; probar concurrencia lector/escritor
Patrón Transactional Outbox — microservices.io 
microservices
	Contenido web de referencia	Secuencia: escribir negocio + evento en la misma transacción; un relay posterior publica	Núcleo del diseño: guardar la acción y su contexto en una transacción, ejecutarla después y marcar resultado	Garantiza at-least-once, no exactly-once: la red puede recibir duplicados si el ACK se pierde 
softwaremill
	Verificar que una acción nunca se ejecuta sin estar persistida; verificar que un fallo tras ejecutar deja estado recuperable
Patrón Saga — microservices.io 
microservices
	Contenido web de referencia	Secuencia de transacciones locales con compensaciones	Para acciones compuestas: descubrir post → validar → comentar → registrar resultado → actualizar ranking	Una saga mal diseñada puede dejar estados intermedios; cada paso necesita compensación o reanudación	Fallo en cada paso; reanudación desde el último estado; compensación de acciones parciales
py-saga — implementación asíncrona del patrón Saga 
github
	Revisar licencia en GitHub	Modelo de saga asíncrona y eventual consistency	Referencia para modelar pipelines de varias redes; probablemente preferible implementar una saga propia mínima sobre SQLite	Dependencia poco consolidada frente a una implementación interna acotada	Tests de compensación, reanudación y duplicados
saga-framework-python — framework de sagas 
github
	Revisar licencia en GitHub	Abstracción de transacciones distribuidas	Solo como inspiración; el caso de uso del proyecto es más simple	Madurez y mantenimiento por verificar	No adoptar sin auditoría de código y licencia
Recomendación

Implementar un motor propio mínimo, no depender de un framework pesado:

SQLite como cola durable. Una tabla social_action_outbox almacena cada acción antes de ejecutarla. El patrón transaccional garantiza que la intención de actuar sobrevive a una caída: si el proceso muere antes de publicar, la fila permanece y el worker la recupera después.
microservices
+1

WAL + synchronous=NORMAL + busy_timeout. WAL permite que lecturas de descubrimiento y escrituras de acciones convivan mejor; synchronous=NORMAL es seguro frente a corrupción en WAL, aunque puede perder la última transacción ante corte eléctrico. Para acciones sociales, ese compromiso es adecuado; para eventos críticos puede usarse FULL.
sqlite
+1

Idempotencia por clave estable. Cada acción debe tener idempotency_key = sha256(network + action_type + target_id + author_account + day_bucket + content_hash). Antes de ejecutar, comprobar la clave; después de ejecutar, guardar el resultado aunque la respuesta de la red sea ambigua. El outbox ofrece entrega at-least-once, por lo que la deduplicación en el consumidor es obligatoria.
softwaremill
+1

Estados explícitos. Usar al menos: pending, claimed, executing, succeeded, failed_retryable, failed_permanent, skipped_duplicate, compensated. Nunca borrar una acción al fallar: archivarla con diagnóstico.

Lock de fichero para el scheduler. En Windows, portalocker es la opción más completa: soporta Windows, Linux y macOS, funciona como context manager y sus locks exclusivos no requieren dependencias adicionales. Usarlo para un lock de scheduler y, si se paraleliza, un lock por red.
pypi
+1

Sagas ligeras para acciones compuestas. No hace falta Temporal al principio. Una saga puede ser una fila padre campaign_run con pasos en action_steps; cada paso guarda status, attempt, result_payload y compensation_status. Las sagas resuelven consistencia eventual mediante secuencias de transacciones locales.
microservices

Esquema mínimo propuesto
sql
CREATE TABLE social_action_outbox (
  id INTEGER PRIMARY KEY,
  network TEXT NOT NULL,
  action_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  target_url TEXT,
  author_account TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  next_run_at TEXT,
  claimed_by TEXT,
  claimed_at TEXT,
  result_json TEXT,
  error_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX idx_outbox_dispatch
ON social_action_outbox(status, next_run_at, network);

CREATE TABLE action_steps (
  id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL,
  network TEXT NOT NULL,
  step_name TEXT NOT NULL,
  status TEXT NOT NULL,
  attempt INTEGER NOT NULL DEFAULT 0,
  input_json TEXT,
  output_json TEXT,
  compensation_status TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
Plan de implementación en PR pequeñas
PR 1 — Núcleo SQLite y WAL

Crear módulo growth/storage/db.py.

Abrir SQLite con journal_mode=WAL, synchronous=NORMAL, busy_timeout=5000 y foreign_keys=ON.

Crear tablas social_action_outbox y action_steps.

Tests: migración limpia, reapertura, integrity_check, escritura y lectura concurrente.

PR 2 — Outbox idempotente

Añadir enqueue_action() con clave de idempotencia determinista.

Rechazar duplicados mediante INSERT ... ON CONFLICT(idempotency_key) DO NOTHING.

Tests: mismo target y contenido produce una sola fila; distinto día o cuenta produce filas distintas.

PR 3 — Dispatcher con recuperación

Implementar claim_next_action(network) con transacción corta.

Al arrancar, recuperar filas en claimed o executing cuyo claimed_at sea anterior a un lease.

Tests: matar el proceso tras claim y comprobar que la acción vuelve a pending; matar tras ejecución pero antes de marcar éxito y comprobar deduplicación.

PR 4 — Reintentos y clasificación de errores

Backoff exponencial con jitter: next_run_at = now + base * 2 ** attempts + jitter.

Clasificar errores en retryable, permanent y unknown.

Tests: error 429/5xx reintenta; error de validación pasa a failed_permanent; error desconocido reintenta con límite.

PR 5 — Locks en Windows

Integrar portalocker.Lock alrededor del dispatcher.

Crear locks/scheduler.lock y locks/{network}.lock.

Tests en Windows: dos procesos no despachan la misma acción; liberación correcta tras excepción; timeout configurable.

PR 6 — Sagas ligeras

Añadir campaign_run y pasos encadenados.

Cada paso debe ser reanudable y registrar salida antes del siguiente.

Tests: fallo en descubrimiento, validación, ejecución y registro; reanudación desde el último paso completado.

PR 7 — Métricas y limpieza

Guardar por acción: latencia, intentos, resultado, red, hora y tipo de contenido.

Archivar acciones terminadas tras N días; conservar agregados para ranking.

Tests: el archivo no pierde métricas; el outbox no crece indefinidamente.

Aplicación a todas las redes
Red	Acción principal	Adaptación del outbox
X	Responder, citar, seguir perfiles relevantes	target_id = tweet/status ID; idempotencia por tweet + cuenta + tipo
Threads	Responder a posts del nicho	target_id = thread/post ID; evitar repetir hilo ya trabajado
Facebook	Comentar publicaciones y grupos relevantes	target_id = post/group ID; separar cuenta y página en author_account
Pinterest	Guardar, comentar o crear pin contextual	target_id = pin/board ID; payload incluye imagen y enlace
Reddit	Comentar hilos y seguir comunidades	target_id = submission/comment ID; registrar subreddit y reglas específicas
Bluesky	Responder posts y seguir autores	target_id = AT URI/CID; conservar DID del autor
Mastodon	Responder toots y seguir perfiles	target_id = status ID + instancia; la instancia forma parte de la clave
TikTok	Comentar vídeos y descubrir creadores	target_id = video ID; registrar hashtags y sonido
Instagram	Comentar posts y seguir creadores	target_id = media ID; separar interacción orgánica de interacción por campaña

El mismo motor sirve para todas: cambia el adaptador de ejecución, no la cola, la idempotencia ni la recuperación.

Decisión técnica

Recomendación principal: SQLite + WAL + outbox propio + portalocker + sagas ligeras.

Cuándo subir a Temporal: si aparecen varios workers distribuidos, horarios complejos, dependencias entre campañas o necesidad de observabilidad avanzada. Temporal ofrece workflows duraderos, reintentos y recuperación automática de fallos intermitentes, con SDK Python bajo licencia MIT.
github
+1

Fuentes

Transactional Outbox — microservices.io: 
https://microservices.io/patterns/data/transactional-outbox.html
microservices

Transactional Outbox e idempotencia — SoftwareMill: 
https://softwaremill.com/microservices-101/
softwaremill

Outbox, WAL y CDC — artículo técnico: 
https://dkbalachandar.wordpress.com/2026/10/06/the-transactional-outbox-pattern-reliable-event-publishing-in-microservices/
dkbalachandar.wordpress

SQLite WAL y durabilidad: 
https://www2.sqlite.org/draft/matrix/compile.html
sqlite

SQLite WAL en Python: https://dev.to/ranaweerasupun/why-sqlite-is-perfect-for-edge-device-data-logging
dev

sqloutbox: 
https://github.com/sandeepyadav1478/sqloutbox
github

python-outbox: 
https://github.com/Smixi/python-outbox
github

Temporal Python SDK: 
https://github.com/temporalio/sdk-python
github

Temporal samples: 
https://github.com/temporalio/samples-python
github

portalocker: 
https://github.com/WoLpH/portalocker
github

portalocker en PyPI: 
https://pypi.org/project/portalocker/
pypi

filelock: 
https://py-filelock.readthedocs.io/en/latest/
py-filelock

Saga pattern: 
https://microservices.io/patterns/
microservices

py-saga: 
https://github.com/serramatutu/py-saga
github

saga-framework-python: 
https://github.com/prashaanpillay/saga-framework-python
github
