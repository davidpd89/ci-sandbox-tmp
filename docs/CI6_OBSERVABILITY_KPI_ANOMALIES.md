# PR #6 — KPI y alertas de caídas sostenidas

Fecha de revisión: 2026-10-09  
Rama: `ci/observability-kpi-anomalies`  
Base: `ci/test-campaign-parent`

## Alcance comprobado

La PR no contiene actualmente una sección `## Encargo para GPT` en su cuerpo ni añade
un documento de tarea independiente. Tampoco existe
`docs/open-source-scouting/PROTOCOL.md` en esta rama. Por ello se tomó como contrato
el cuerpo vigente de la PR y `docs/CI_TEST_CAMPAIGN.md`, sin ampliar el alcance a
otras PR.

Se consultó el repositorio oficial privado
`davidpd89/rrss-davidporto-CODE`, rama `integracion/crecimiento-2026-10`, únicamente
para comprobar contratos reales de CSV y compatibilidad de los canarios. No se ha
copiado contenido privado, credenciales ni datos de cuentas a este mirror.

## Hallazgos y correcciones

1. **Replay de rondas idénticas.** El detector de caídas podía interpretar tres
   copias idénticas de una sola ronda como tres muestras válidas del día. Se
   deduplican ahora únicamente filas completas idénticas antes de satisfacer
   `MIN_ROUNDS_PER_DAY`. No se deduplican rondas distintas por red, tipo o fecha.
2. **CSV con columnas extra.** `dict(zip(...))` truncaba silenciosamente filas legacy
   con más columnas de las esperadas. Esas filas pasan a contarse como malformadas y
   no aportan confirmaciones.
3. **Cabeceras nombradas inválidas.** Cabeceras duplicadas o que no contienen los
   campos semánticos mínimos se marcan como cobertura desconocida
   (`cabecera_invalida`), nunca como cero.
4. **Compatibilidad con los esquemas reales.** La segunda revisión detectó que los
   CSV oficiales usan `texto_usado` y que Reddit usa `subreddit`/`hilo_url`.
   La validación nombrada exige solo `fecha`, `tipo` y `resultado`, que son los
   campos necesarios para el KPI; el formato legacy sin cabecera sigue siendo
   posicional.
5. **Karma de Reddit no son seguidores.** El esquema oficial de Reddit expone
   `karma_visible`, no `seguidores`. El informe devuelve ahora
   `followers_net = null` y `sin_columna_seguidores` en vez de reinterpretar la
   segunda columna. En CSV nombrados de otras redes se localiza `seguidores` por
   nombre, no por posición.

Todos los fixtures añadidos son sintéticos. Las herramientas siguen siendo de solo
lectura y no ejecutan acciones sobre redes.

## Comparación de reutilización pública

Se revisaron proyectos públicos mantenidos a fecha 2026-10-09 antes de decidir si
sustituir el detector local:

| Proyecto | Licencia | Mantenimiento/compatibilidad | Coste y riesgo | Decisión |
| --- | --- | --- | --- | --- |
| [River](https://github.com/online-ml/river) | BSD-3-Clause | Activo; Python >=3.11; declara Windows | NumPy/SciPy/Narwhals y build Rust/Maturin para una regla de 9 días | No integrar: sobredimensionado para un umbral determinista y auditable |
| [PyOD](https://github.com/yzhao062/pyod) | BSD-2-Clause | Activo; Python >=3.9, incluye 3.11 | Suite amplia de ML; tuvo una corrección de seguridad reciente relacionada con deserialización insegura | No integrar: superficie y dependencias muy superiores al problema |
| [NAB](https://github.com/numenta/NAB) | MIT | Poco activo frente a los anteriores; documentación centrada en Python 3.6; Windows no soportado oficialmente | Benchmark completo y detectores complejos | No compatible con el objetivo de CI Windows/Python 3.11 |
| [Prometheus Python client](https://github.com/prometheus/client_python) | Apache-2.0 AND BSD-2-Clause | Activo; Python >=3.9, incluye 3.11 | Excelente para instrumentación, pero no resuelve la lectura forense de estos CSV ni la regla de caída | No integrar en esta PR; añadiría arquitectura sin resolver el contrato |

La continuidad con biblioteca estándar (`csv`, `statistics.median`, `zoneinfo`)
gana la comparación: cero dependencia nueva, comportamiento determinista, soporte
Python 3.11/Windows ya cubierto por CI y una superficie mucho menor. No se ha copiado
código de terceros, por lo que esta PR no incorpora nuevas obligaciones de
atribución/licencia.

## Segunda revisión adversarial

La revisión se hizo contra los esquemas reales del repositorio oficial después de la
primera corrección. Esa pasada encontró y corrigió dos regresiones que los fixtures
originales no detectaban: rechazo excesivo de aliases de cabecera y conversión
potencial de karma de Reddit en seguidores.

Casos adversariales cubiertos tras la revisión:

- ausencia de muestra, ronda saltada, ocupada o con error no se convierte en cero;
- un solo día malo no genera alerta;
- un replay idéntico no fabrica el mínimo diario de rondas;
- filas extra, cabeceras duplicadas, fechas inválidas y errores de lectura no
  fabrican métricas;
- pendientes, omisiones, fallos y resultados desconocidos permanecen separados;
- la procedencia solo se cuenta cuando existe una atribución explícita;
- un KPI sin columna semántica fiable queda como ND, no como cero ni como otra métrica;
- la deduplicación de interacciones se limita a filas idénticas, porque el legacy no
  posee IDs de evento estables.

## Validación

Run de código `37980425674`, Python 3.11:

- Ubuntu: `1734 passed, 9 skipped, 8 deselected, 665 subtests passed`.
- Windows: `1737 passed, 6 skipped, 8 deselected, 665 subtests passed`.
- `python -m compileall -q tools tests`: correcto en ambos runners.
- Dos warnings preexistentes por una secuencia de escape en
  `tools/android_shell.py`; no pertenecen a esta PR.

No se ejecutó un canario supervisado contra cuentas reales, Edge, móvil ni una red
viva. Esas comprobaciones quedan fuera del entorno hermético y deben mantenerse
separadas de estos tests. El repositorio oficial también contiene una evolución más
reciente del registro central de códigos de alerta; Claude debe reconciliarla al
trasladar estos cambios, sin importar refactors ajenos a esta PR.

## Auditoría adicional independiente — 09-10-2026

Se repitió la revisión sin dar por suficientes los checks verdes anteriores, y se
contrastaron los lectores con los productores de `tools/round_queue.py` y
`tools/relationship_policy.py` del repositorio oficial. El productor de rondas
persiste `fecha,red,inicio,fin,minutos,estado,confirmadas,saltadas,fallos,codigo`.
La columna `confirmadas` es un *desglose* textual; no se debe usar el código de
salida como prueba de éxito. La cosecha entrante solo está instrumentada para
Bluesky/Mastodon en este contrato.

### Fallos adicionales encontrados y corregidos

1. **Informe incompleto presentado como cifra cierta.** En filas salientes
   malformadas, los recuentos positivos observados se conservan solo como cota
   inferior y un cero no verificable se transforma en `null`.
   `outbound_coverage=registro_parcial_filas_invalidas` explicita el problema.
2. **Cosecha parcial o no atribuible.** Las entradas corruptas no se ignoran para
   fabricar cero comentarios. Ahora hay cobertura por red: un fallo atribuible
   a Bluesky no borra los datos correctos de Mastodon. Las entradas sin red
   identificable dejan ambas como parciales; las de redes no cosechadas no
   contaminan las dos fuentes instrumentadas.
3. **CSV vacío, cabecera sola o sin eventos de hoy.** La mera existencia física
   del fichero no prueba que hoy se haya cosechado o registrado nada:
   `sin_observaciones_del_dia` devuelve KPI desconocido. Un evento de
   verificación pendiente hoy sí puede demostrar cero confirmaciones anotadas;
   un like entrante hoy permite observar cero comentarios *registrados*, sin
   afirmar que no hubo comentarios en la plataforma.
4. **Defectos históricos.** Si la fecha válida de la fila está fuera del día
   consultado, no degrada la cobertura actual aunque sobren o falten columnas.
   Una fecha ilegible sigue siendo incertidumbre real.
5. **`fin` inválido.** El detector ya no admite una hora imposible como evidencia
   positiva de una ronda. El defecto invalida solo la red afectada.
6. **Zona horaria del detector.** El reloj por defecto usa explícitamente
   `Europe/Madrid`, con independencia de que el runner o servidor esté en UTC.
   Si falta tzdata no deduce arbitrariamente otro día.
7. **Contadores corruptos y fechas programáticas.** Un `metricas.csv` con miles
   de dígitos ya no provoca la excepción de `int` de Python 3.11 ni inutiliza
   el informe de otras redes. `build_report()` acepta correctamente un
   `datetime` con zona y lo proyecta al día de Madrid.

Las pruebas añadidas usan exclusivamente archivos temporales sintéticos; la
lectura continúa sin red, sin publicación y sin escrituras sobre estados reales.

### Nueva exploración de reutilización pública

Repositorios y versiones consultados el 09-10-2026:

| Componente candidato | Licencia y actividad comprobadas | Python 3.11 / Windows / dependencias | Decisión aplicada |
| --- | --- | --- | --- |
| [Frictionless](https://github.com/frictionlessdata/frictionless-py) | MIT; commit del 08-10-2026; activo | Declara Python 3.11 y plataforma independiente; incluye petl, attrs, marko, Jinja2 y más | No incorporar framework completo para validar tres campos CSV; útil como referencia para la PR #46 |
| [ruptures](https://github.com/deepcharles/ruptures) | BSD-2-Clause; actividad en mayo de 2026 | Compilación Cython, NumPy y SciPy; dependencia mayor que el detector | No sustituir la mediana robusta de 9 días por detección general de rupturas |
| [anomalyzer](https://github.com/PredictabilityAtScale/anomaly-detection) | MIT; commit del 01-10-2026; versión 0.1.0 alfa | Python >=3.11; Pydantic 2 y tzdata en Windows | Alternativa emergente para series largas; no resuelve la calidad de los CSV ni justifica integración ahora |

**Conclusión técnica de reutilización:** se conserva la implementación con
biblioteca estándar y los tests del proyecto. No se ha copiado ni adaptado código
de terceros. Las opciones evaluadas tienen licencia compatible, pero el coste
en dependencias, madurez o complejidad supera el beneficio para este contrato
pequeño y auditable.

### Límites para la integración de Claude

- Los CSV legacy no tienen IDs de evento ni snapshot de completitud. Los KPI
  registrados no equivalen a ACK remoto ni miden conversión causal.
- El sistema oficial, ya con cambios posteriores, debe reconciliar
  `alert_codes.py` y `round_canaries.py` al portar el diff. No copiar
  ciegamente todo el archivo del espejo sobre la rama oficial.
- El KPI de seguidores es la variación desde la observación previa disponible
  (hasta siete días); no debe presentarse como crecimiento estrictamente diario.
- La cobertura se limita a las ocho redes del contrato original de la PR #6.
  Instagram y fuentes futuras necesitan instrumentación/contrato propios; no
  añadir ceros ficticios por esta ausencia.
- Los ocho tests previamente excluidos por el workflow de la rama padre siguen
  fuera de esta validación; ninguna cifra de CI implica garantía absoluta.
- Quedan pendientes las pruebas supervisadas de Windows operativo y los
  consumidores reales (panel, Edge, móvil). Aquí solo se ha verificado CI
  hermética en Windows/Ubuntu y Python 3.11.

Las investigaciones adyacentes ya existen como PR abiertas: #24, #46 y #47,
verificadas nuevamente. No procede abrir una PR duplicada.

## Trabajo adicional

No se abrieron PR nuevas: los huecos adyacentes ya están cubiertos por PR abiertas,
en particular #24 (dashboard/observabilidad), #46 (calidad y reconciliación de datos)
y #47 (alertas/simulación de incidentes). Abrir otra PR aquí duplicaría alcance.

No se ha hecho merge.
