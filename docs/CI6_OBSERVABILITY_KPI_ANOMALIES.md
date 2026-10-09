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

## Trabajo adicional

No se abrieron PR nuevas: los huecos adyacentes ya están cubiertos por PR abiertas,
en particular #24 (dashboard/observabilidad), #46 (calidad y reconciliación de datos)
y #47 (alertas/simulación de incidentes). Abrir otra PR aquí duplicaría alcance.

No se ha hecho merge.
