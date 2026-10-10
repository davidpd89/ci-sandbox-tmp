# Observabilidad RRSS: panel offline y exportación saneada (10/10/2026)

## Problema

Se ha leído el encargo de la [PR #24](https://github.com/davidpd89/ci-sandbox-tmp/pull/24), el protocolo y el código existente tanto del mirror como de la rama oficial
\`integracion/crecimiento-2026-10\`. El mirror **no es una copia fiel de la punta del oficial**:
\`tools/round_queue.py\` (mirror blob \`985b4ecac4dcad446a1782c67d8f1ff0b72795ae\`;
oficial \`73bb2dce69a9e091f7ac2252189e48cdfe2b5078\`),
\`tools/circuit_breaker.py\` (mirror \`1e739ac822c895e123bea879b0296a11bfb2f9e1\`;
oficial \`436a53f5ecd63718294328db236c8cd286d31440\`).
\`tools/health_panel.py\` coincide (blob \`311748797bc529e8fb6a4e20c995d52f219334ad\`).
Se usa aquí la superficie común leída del oficial, sin copiar datos, fixtures reales ni ejecutar herramientas conectadas.

Ya existen fuentes operativas: \`00_OPERATIVO/tiempos_rondas.csv\` (una fila por ejecución:
\`fecha,red,inicio,fin,minutos,estado,confirmadas,saltadas,fallos,codigo\`),
\`SISTEMA_DIARIO_<RED>/registro_interacciones.csv\` (\`resultado\`),
\`SISTEMA_DIARIO_<RED>/cache/breaker.json\` (\`fails,open_until,reason\`),
\`mech_<fecha>_<hora>.log\` (\`[TIEMPO_ETAPA]\`),
y \`00_OPERATIVO/_cola_respuestas/pending.json\` (diccionario de entradas con \`network\`).
\`health_panel.py\` ofrece métricas de interacción, pero su CLI está restringida a Bluesky y
Mastodon y mezcla un informe con consulta remota de seguidores. \`daily_review.py\` es un
informe operativo limitado. **No había un panel homogéneo offline, sanitizado y
reutilizable para las nueve redes.**

## Alternativas

Consulta de repositorios, licencias y actividad en GitHub; enlaces fijados a la revisión
observada, no a \`main\` flotante. Compatibilidad es del producto, no una validación
del despliegue concreto en Edge, Windows o móvil.

| Candidato | Revisión/actividad consultada | Licencia y Python/Windows | Decisión |
|---|---|---|---|
| [Streamlit](https://github.com/streamlit/streamlit/commit/0d955fd90749006f206fb6c18cd3fd2808b9e791) | Commit 10/10/2026, no archivado | Apache-2.0; funciona con Python 3.11/Windows | No adoptar ahora: servidor, dependencias y superficie adicionales frente a dos archivos estáticos |
| [Plotly Dash](https://github.com/plotly/dash/commit/8f3f73557b91a0bc8a269c1193bd0b93490f309d) | Commit 09/10/2026, no archivado | MIT; Python 3.11/Windows | No adoptar ahora: callbacks/servidor no aportan al contrato de lectura offline |
| [prometheus/client_python](https://github.com/prometheus/client_python/commit/9cd073cb4dc6ee617eadf02dcdec94e0225eff0a) | Commit 15/09/2026; release 0.26.0 (24/07/2026) | Proyecto Apache-2.0; distribución reciente declara Apache-2.0 AND BSD-2-Clause; Python >=3.9/Windows | No añadir exporter/servidor: aporta instrumentación en vivo, no resuelve ingestión de CSV legacy ni privacidad del mirror |
| [Textual](https://github.com/Textualize/textual/commit/5e5b7ef58b8c5572c13a3ff9027d756623661495) / [Rich](https://github.com/Textualize/rich/commit/9d8f9a372cc5916fd4781fec207ced7ddac2f08f) | Commits 09/10/2026 y 23/06/2026; repos activos | MIT, Python 3.11/Windows | Buena terminal local; no genera automáticamente artefacto HTML estático reutilizable sin ejecutable |

## Licencias y procedencia

Fuente primaria: https://github.com/prometheus/client_python/commit/9cd073cb4dc6ee617eadf02dcdec94e0225eff0a
Fecha de consulta: 2026-10-10
Licencia SPDX: Apache-2.0
Referencia inmutable: https://github.com/prometheus/client_python/commit/9cd073cb4dc6ee617eadf02dcdec94e0225eff0a

No se ha incorporado código externo. La referencia acredita la comparación con una alternativa mantenida; las fuentes y licencias de las otras alternativas están en la tabla precedente. La adaptación utiliza únicamente datos del proyecto y la biblioteca estándar.

**Resultado aplicado:** continuidad con las fuentes ya existentes y los módulos de biblioteca
estándar de Python (\`csv\`, \`json\`, \`datetime\`, \`statistics\`, \`html\`). Ninguna línea
copiada de los candidatos externos; no se añade dependencia, servidor, licencia vendorizada,
CDN, sesión, credencial, telemetry remoto ni aplicación persistente. No se introducen costes
ni mantenimiento de dependencias. En una fase posterior Prometheus puede ser útil para
telemetría en proceso, con consentimiento y almacenamiento privado, pero no supera este
alcance de exportación con evidencia actual.

## Decisión

\`tools/observability_dashboard.py\` admite siempre un origen y destino explícitos:

\`\`\`powershell
python tools/observability_dashboard.py --root "RUTA_DATOS_SINTETICOS" --output "RUTA_SALIDA" --as-of 2026-10-10T12:30 --days 7
\`\`\`

Salida: \`dashboard.json\` (esquema 1, contrato legible por otras herramientas) y
\`dashboard.html\` (HTML estático con tablas, cobertura y tendencias por fecha).
Ninguno consulta Internet, GitHub, APIs sociales, Edge o ADB. No se modifican los
archivos de origen. La salida usa reemplazos atómicos por archivo. **Estos son
artefactos saneados, no un canario supervisado ni evidencia de acciones reales.**

Nueve adaptadores por red comparten un único contrato de salida: X, Threads, Facebook,
Pinterest, Reddit e Instagram figuran bajo WEB; Bluesky/Mastodon bajo API; TikTok bajo
MOBILE. Estas colas describen el canal tecnológico, **no prueban que hoy todas las
redes tengan ejecutor de ronda habilitado**. El \`round_queue.py\` leído programa
actualmente WEB: X/Threads/Facebook/Pinterest, API: Bluesky/Mastodon, MOBILE: TikTok.
Instagram y Reddit aparecen para cobertura estructural futura, con observaciones
desconocidas hasta disponer de datos.

Campos por red: confirmaciones, fallos, omisiones y verificaciones pendientes
**del registro** (sin atribuir cada confirmación a una ronda);
rondas por estado \`ok/parcial/error/saltada/ocupada\`, latencia media y p95;
recuentos de pendientes *vigentes* en cola compartida de respuestas (TTL de 36 horas); estado del breaker (sin razón
literal); fases temporizadas \`pre/scan/plan/execute/post/bulk\`; cobertura, avisos pasivos (breaker abierto, rondas con error/parciales y verificaciones inciertas) y tendencia
de confirmaciones por día. No se infieren confirmaciones del \`codigo=0\` ni de la
columna \`confirmadas\` del CSV de rondas: esta última guarda un **diccionario textual
de desglose**, no el total numérico y no tiene identidad de evento. Se cuentan
filas de registro, no objetivos ni resultados remotos verificados mediante API.
La fuente compartida \`pending.json\` mide respuestas pendientes, **no publicaciones
propias programadas ni pendientes de verificación**.

Semántica: \`null\`/«—» si falta una fuente; \`0\` si la fuente existe y tiene cero
eventos en la ventana. Un breaker inexistente queda \`sin_datos\`, nunca «cerrado».
Los avisos de auth/rate/fallos no se deshabilitan: el panel solo los observa.
Se usa la hora local del estado legacy (el consumidor puede fijar \`--as-of\`),
ventana inclusiva de 1–31 días y muestras p95 por nearest-rank.

## Pruebas

\`python -m pytest tests/test_observability_dashboard.py -q -p no:cacheprovider\`
crea fixtures sintéticos en directorios temporales, sin red. Cubre nueve redes,
separación de tres colas, CSV con BOM, cabeceras requeridas, día fuera de ventana, ronda parcial/ocupada,
desglose histórico que no se suma como confirmación, ausencia ≠ cero, breakers
abiertos/expirados/ilegibles, pendientes con TTL y lectura inmutable, avisos no bloqueantes, logs y falta de exfiltración de cadenas
privadas. El workflow de CI existente ejecuta Python 3.11 en Windows y Linux;
**no** demuestra Edge real, móvil Android, estado productivo ni frescura de datos.

El exportador usa exclusivamente campos y etiquetas numéricas de lista cerrada.
Nunca serializa \`cuenta\`, \`target\`, \`texto_usado\`, \`reason\`, URL o contenido
completo de log; descarta archivos demasiado grandes y limita logs procesados.
El HTML es estático, no ejecuta código de terceros. *La lista de exclusión es una
garantía de diseño y prueba sintética, no una certificación de privacidad sobre
todas las evoluciones futuras del esquema.* Los artefactos solo deberían publicarse
tras revisión humana de datos reales; no se configura publicación automática.
No hay endpoints de salud activos ni alertas push: son trabajos separados de esta
fotografía pasiva y se han dejado explícitos, no simulados.

Medición antes/después: antes \`health_panel\` tenía salida analítica enfocada en dos
redes; después el contrato del dashboard incluye **9/9 redes y 3/3 clases de cola**.
Nuevas dependencias = **0**; servicios persistentes = **0**; red necesaria para
generar salida = **0**. El número de observaciones reales en cada red es variable
y la herramienta muestra cobertura en vez de inferir que existen datos.

Retirada: dejar de invocar el CLI y borrar \`tools/observability_dashboard.py\`,
\`tests/test_observability_dashboard.py\`, este documento y los dos artefactos
generados. No hay migración de esquema ni escritura al ledger/colas.
Integración en el repo oficial pendiente de la revisión de Claude: comprobar
contratos de archivos de la punta oficial y ensayar primero con copia anonimizadora,
nunca sobre datos de producción.

## Autorrevisión adversarial

1. **Falso éxito por \`returncode=0\`**: no se usa; conteos separados por fuente.
2. **Saltos o rondas ocupadas adulteran rendimiento**: estados separados, no se
   equiparan a éxito ni a fallo.
3. **Contenido privado en JSON/HTML**: allowlist estricta, razones/textos/handles
   ignorados y test de cadenas centinela.
4. **Breaker ausente confundido con cerrado**: estado \`sin_datos\`.
5. **Ventana de fechas sesgada**: fechas inclusivas y \`--as-of\` reproducible.
6. **Fuente CSV incompleta, BOM y números NaN/inf**: cabeceras obligatorias y validación
   sin atribuir conteos faltantes.
7. **Snapshots no sincronizados**: JSON y HTML se reemplazan individualmente
   (no como transacción doble); publicar ambos juntos solo tras comprobar
   \`as_of\` y \`schema_version\`. No hay servidor para consultas atómicas.

## Retirada

No hay migración, dependencia ni servicio que revertir. Eliminar el exportador, el test, esta investigación y los artefactos estáticos si se decide retirar la funcionalidad; la fuente local queda intacta. El despliegue es opt-in y no instala tareas programadas.

## Casos aún por comprobar con el controlador

- Windows 3.11 vivo, permisos y bloqueo de fichero en carpetas reales, Edge real,
  móvil y tasas de generación/lectura con los volúmenes efectivos.
- Que el repositorio oficial no cambie campos/nombres de CSV/JSON antes de integrar.
- Necesidad futura de persistencia de eventos históricos idempotentes para
  atribución de una confirmación a una ronda; no debe inferirse de estas vistas.
