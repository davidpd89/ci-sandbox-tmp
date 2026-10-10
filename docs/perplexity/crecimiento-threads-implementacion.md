# PR #123 · Resultado verificable (10/10/2026)

## Diagnóstico frente al repositorio oficial

Repositorio oficial: davidpd89/rrss-davidporto-CODE, rama
integracion/crecimiento-2026-10. Verificados directamente:

- tools/threads_api.py (blob 0a86f1e6943d486b45722cd09d0b40248c986861):
  OAuth, lectura de respuestas propias, certificación del contexto del destino
  y ledger de idempotencia YA EXISTEN. El propio módulo documenta que
  threads_keyword_search carece de aprobación para resultados públicos y que
  el permalink web no se convierte automáticamente en media_id API.
- tools/threads_scan.py (blob a188025664ce5ffe0a0d7237e547b9065814503f):
  búsqueda web tanto TOP como RECENT, rotación de términos, búsqueda de
  perfiles, seguidores semilla y persistencia YA EXISTEN. No duplicar.
- tools/threads_pool.py y tools/browser_pool.py: reserva SQLite, first-touch,
  rechazo de spam/política, idioma y límite de antigüedad YA EXISTEN.
- tools/discovery_ranking.py, tools/cross_network_learning.py,
  tools/discovery_terms.py: ranking/medición/catálogo general YA EXISTEN.
- En la rama del espejo faltan algunas mejoras posteriores del oficial
  (p. ej. threads_discovery_quality.py). No se sobrescriben ni se copian por
  la puerta de atrás; Claude debe aplicar este cambio sobre la rama privada
  actual y resolver cualquier delta.

PR relacionadas localizadas: espejo #14 (investigación Threads),
#24 (observabilidad), #66 (ranking de candidatos), #72 (rotación),
#100 (adaptadores de candidatos), #101 (términos), #115 (descubrimiento),
#116 (ranking), #117 (paridad); oficial #72 (rotación todavía sin
adaptadores completos), #73 (contratos API). Se evita abrir PR duplicadas.

## Repositorios comprobados, decisión y atribución

| Fuente | Evidencia a 10/10/2026 | Decisión |
| --- | --- | --- |
| [Egor01KKK/threads-content-research-agent](https://github.com/Egor01KKK/threads-content-research-agent) | Apache-2.0, commit main 981cccd2eb53d44f46cc5675b2388c8c7a6ad758, 13/09/2026; Go >=1.26, Python >=3.10 solo visor opcional; compilación en Windows documentada pero NO probada aquí | **Reutilizar su contrato de exportación** JSON/JSONL/corpus, referenciando docs/OUTPUT-SCHEMA.md. No incorporar el recolector Go ni SSR como dependencia. |
| [Danie1/threads-api](https://github.com/Danie1/threads-api) | MIT, archivado, último push 01/10/2023 | Descartado como dependencia. |
| [dmytrostriletskyi/threads-net](https://github.com/dmytrostriletskyi/threads-net) | Sin licencia declarada, último push 12/10/2023, ingeniería inversa | Descartado; no copiar código. |

El origen público Apache-2.0 conserva copyright y licencia en su repositorio.
Aquí NO se redistribuye su código Go, se implementa un consumidor Python
del esquema publicado; referencia precisa a commit/archivo en el docstring.
Las decisiones de validación y deduplicación son código propio.

Fuentes de plataforma: colección oficial de
[Meta Threads API](https://www.postman.com/meta/threads/documentation/dht3nzz/threads-api)
y [ejemplo de keyword search](https://www.postman.com/meta/threads/request/m9j4i2x/search-for-threads-posts).
La documentación demuestra el endpoint y el permiso,
NO acredita que esté autorizado en la cuenta. La cuota «500/7 días» del
informe no se incorpora: otras referencias públicas difieren y no se
dispone de verificación de cuota aplicable al token real.

## Implementado en esta PR

- tools/threads_research_bridge.py: importa exportaciones **ya obtenidas**
  desde th (JSON/JSONL directo y corpus anidado) sin conexión a Threads.
- Contrato transversal NETWORKS de nueve redes y mapa ADAPTERS explícito:
  solo Threads está soportado; nunca se anuncia compatibilidad ficticia de
  los otros ocho. Usa el adaptador nativo threads_pool.record_posts (que reutiliza browser_pool y mantiene los filtros de campañas de la rama oficial).
- Comprueba URL/host/autor, zona horaria y antigüedad del post sin inventar
  hora cuando falta; deduplica .net/.com, query/fragment y repetidos.
  Conflictos del mismo enlace se descartan en bloque, sin ganador arbitrario. Al importar se limita la entrada a 72 horas y se redondea la edad hacia arriba a horas enteras para preservar el contrato del parser nativo sin declarar frescura inexistente.
- Ejecución por defecto DRY RUN con informe agregado sin texto ni handles.
  Escritura solo a una SQLite local elegida explícitamente con
  --write-pool --db. No publica, sigue, comenta ni cambia la sesión.
  No se añade scheduler ni acceso a credenciales.

### Uso en Python 3.11, Windows o Linux

    python tools/threads_research_bridge.py --input C:\Temp\th-export.jsonl
    python tools/threads_research_bridge.py --input C:\Temp\th-export.jsonl --write-pool --db C:\Temp\threads-import-prueba.sqlite3

La segunda forma **solo crea/actualiza la SQLite explícita indicada**.
Primero comparar las filas de esa base de prueba con el pool real. Nunca
ejecutar el colector Go desde esta PR ni programar el comando
automáticamente. Una exportación de búsquedas públicas incompleta no
equivale a cobertura de todo Threads.

## Pruebas y revisión adversarial

- Pruebas unitarias: tests/test_threads_research_bridge.py, nueve escenarios:
  JSON/JSONL anidado, deduplicación, contradicciones, URL maliciosa, identidad
  y fechas, cobertura real por red, ficheros corruptos o gigantes, SQL
  explícita con mock de threads_pool y salida sin texto de terceros; además, prueba real de reserva SQLite si el checkout contiene threads_pool.
- En arnés local aislado Python: **8 passed, 1 skipped**, compileall sin errores.
  La prueba de integración SQLite con threads_pool real se omite en el arnés aislado, pero queda como test ejecutable sin cuenta ni red cuando se usa el checkout completo.
- Primera pasada detectó error por None tras dos registros incompatibles;
  corregido para que un tercer registro no rehabilite una clave conflictiva.
  Se añadió segunda pasada con casos de URL .net/.com y no filtrado PII.
- Pendiente para Claude: suite completa desde rama privada integrada,
  Python 3.11 Windows/Edge, validación real de threads_pool y browser_pool contra SQLite de
  ensayo, lint, checkout con dependencias, compatibilidad con PR concurrentes,
  comportamiento de colector th en Windows si decide usarlo por separado.
  Ningún token, navegador o acción en red social se probó.

## No hacer

No sustituir discovery actual por keyword_search API sin confirmar scopes,
ni automatizar th sobre la superficie pública SSR no documentada.
No inferir visitas, seguidores o resultados causales desde esta importación.
No merge sin revisión final y comprobación de HEAD.
