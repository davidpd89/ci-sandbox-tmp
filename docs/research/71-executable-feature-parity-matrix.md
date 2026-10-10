# PR #81 — matriz ejecutable de paridad social

**Corte:** 2026-10-10. **Ámbito:** 9 redes × 7 acciones = **63 celdas evaluables**.  
**Rama:** `research/71-executable-feature-parity-matrix`. **Base:** `research/public-reuse-parent`.

## Problema

### Diagnóstico y código contrastado

En el espejo existe `tools/network_capabilities.py` (8 redes y 6 flags; Instagram ausente). En el repositorio **privado oficial** `davidpd89/rrss-davidporto-CODE`, rama `integracion/crecimiento-2026-10`, el archivo `tools/network_capabilities.py` tiene **el mismo blob** `94c662a61db62de87f731725ead27f536c87dac8`. También se comprobó directamente la declaración `mechanical_round.PIPELINES` de ambos repositorios: las nueve redes están en `CONTENT_QUEUE_NETWORKS`, pero Reddit no tiene un pipeline mecánico propio; la ruta móvil de TikTok pasa por `growth_core.pipeline_for`. No se extrajeron tokens, cookies, cuentas ni estados reales del privado.

La pieza nueva (`tools/executable_feature_parity.py`) inspecciona mediante AST las implementaciones de `scan` / `run` / `main`, ramas de `kind` de ejecutores, claves declaradas en `unfollow_cleanup.ADAPTERS` y `loyalty.HARVEST`; cruza esos indicios con los argv de `mechanical_round.PIPELINES` y verifica la existencia de rutas de código y evidencias. No se importan ejecutores ni se lanzan procesos sociales. La lectura de `PIPELINES` utiliza el mismo módulo que la suite previa: la importación sólo recupera la declaración del orquestador.

**Importante:** una celda **wired** significa «se identifica código de esa acción y un paso conectado a la ronda», **no** que una API, un navegador o el teléfono la ejecuten correctamente. En la capacidad **unfollow** se exige además el argumento `--apply`: la ejecución sin él solo genera un informe y no acredita limpieza operativa. Un **present_not_wired** puede tener una ruta indirecta o independiente que todavía no está probada; **missing** es falta de evidencia bajo los métodos inspeccionados, nunca imposibilidad en una plataforma. **unverifiable** marca ausencia, ilegibilidad o error sintáctico del archivo. La distinción entre `vote` y like y entre `react` y like se conserva en `variant` para no fabricar equivalencias. Un save de Pinterest **no** se presenta como repost. No hay auto-like de publicaciones propias de X en este trabajo.

## Uso reproducible (Python 3.11, Windows/Linux)

```sh
python tools/executable_feature_parity.py
python tools/executable_feature_parity.py --json
python tools/executable_feature_parity.py --markdown
python tools/executable_feature_parity.py --strict
python tools/executable_feature_parity.py --require instagram:follow
python tools/executable_feature_parity.py --require reddit:repost  # retorna 1: gap demostrado
python -m pytest -q tests/test_executable_feature_parity.py
```

`--json` incluye por celda `status`, implementación comprobada, símbolo, variante, etapa de pipeline, archivo de test, configuración existente y fuente de métrica, o `null` cuando no existe evidencia verificable. El campo `tests` incluye una prueba **estructural** nueva y un test legado como *indicio*, no una garantía de cobertura funcional de cada acción. `--strict` falla ante incoherencias de contrato; por diseño no penaliza gaps legítimos. `--require RED:ACCION` sirve como condición estricta para una capacidad concreta. La salida Markdown se genera bajo demanda; no se almacena un snapshot que pueda quedar obsoleto.

**Códigos de la tabla:** W = wired, P = present_not_wired, — = missing, ? = unverifiable. Celdas enlazadas al archivo fuente sólo cuando existe evidencia.

## Alternativas

### Comparativa de reutilización pública (inspección de 2026-10-10)

## Licencias y procedencia

Fuente primaria: https://github.com/pytest-dev/pytest
Fecha de consulta: 2026-10-10
Licencia SPDX: MIT
Referencia inmutable: https://github.com/pytest-dev/pytest/tree/e4f7f174bc4a1686b31639d29a3e211941390979

No se incorpora código fuente ajeno; se reutiliza pytest como dependencia existente.


| Opción y revisión examinada | Licencia, actividad, compatibilidad | Adecuación a esta PR |
| --- | --- | --- |
| [pytest-dev/pytest @ e4f7f174](https://github.com/pytest-dev/pytest/tree/e4f7f174bc4a1686b31639d29a3e211941390979) | MIT; desarrollo activo en octubre de 2026; Python ≥3.10; Windows/Linux | **Elegido:** ya es dependencia de `requirements-ci.txt`; tests offline parametrizables, sin añadir dependencias |
| [pact-foundation/pact-python @ 65835e95](https://github.com/pact-foundation/pact-python/tree/65835e95e0c54bcb886e4b709cc487b086986360) | MIT; versión 3.4.0 publicada en septiembre de 2026; Python ≥3.10; Windows/Linux | Contratos HTTP proveedor-consumidor; añade FFI y flujo de mock server sin valor para demostrar wiring local de navegador/móvil |
| [schemathesis/schemathesis @ c3f36963](https://github.com/schemathesis/schemathesis/tree/c3f36963d4cba0b7efd24a750a7298bc69bef1e5) | MIT; activo en octubre de 2026; Python ≥3.10, Windows compatible | Diseñado para OpenAPI/GraphQL, añade dependencias y exige pytest ≥9 en la revisión examinada; no aborda ejecutores CDP/ADB |
| Código existente: [inventario del espejo](../../tools/network_capabilities.py) | Propio; sin dependencias externas | **Se conserva**, sin alterar su interfaz ni pisar PR #43 (paridad de configuración); la nueva matriz es complementaria |

## Decisión

**Decisión:** continuar con el código propio del orquestador y reutilizar el patrón de tests de pytest ya disponible. No se copia código externo ni se incorporan dependencias nuevas: el coste de instalación, licencias añadidas y superficie de actualizaciones es cero.

## Pruebas

- **Verificación sintáctica local:** `python -m py_compile` de la implementación y tests, aprobada sobre el prototipo de la misma lógica.
- **Pruebas sintéticas locales:** cuatro casos aislados aprobados para estados missing/wired/unwired, AST inválido, rutas Windows y docstrings engañosos (sin tocar ninguna cuenta).
- **CI del mirror:** `.github/workflows/validate-social-tools.yml` ejecuta `compileall` y la suite `pytest` en Ubuntu + Windows/Python 3.11 para cada push; el resultado del HEAD se debe revisar antes de integrar.
- **Afirmaciones pendientes:** no se verificaron Windows real, Edge CDP, Instagram real ni móvil/ADB. Los tests prueban cableado estático, no presencia de candidato, éxito de acciones, ni métrica efectivamente registrada en un entorno real.
- **Huecos ya visibles en el código:** `unfollow_cleanup.ADAPTERS` sólo declara Bluesky/Mastodon/Threads/X, y `loyalty.HARVEST` sólo Bluesky/Mastodon; los otros sitios tienen ausencia de esa conexión común (sin implicar ausencia de todos sus mecanismos alternativos). Reddit carece de `PIPELINES[reddit]` aunque tiene ejecutor autónomo. Pueden añadirse adaptadores sin cambiar el contrato de la matriz.
- **Riesgos de mantenimiento:** las ramas de acción se leen mediante AST, por lo que refactorizaciones que escondan los tipos de acción bajo builders dinámicos pasarán a P/—; añadir un manifest de funciones comprobables por inyección será la evolución natural. La columna de métricas apunta a la fuente del código, **no** a CSV real, porque no debe leerse estado operativo.
## Retirada

**Retirada reversible:** quitar `tools/executable_feature_parity.py`, `tests/test_executable_feature_parity.py` y este documento. Ni el pipeline, ni las tres colas (WEB/API/MOBILE), ni la base de datos existente se modifican.

## Segunda revisión adversarial

Se comprobó expresamente que un string en una docstring no demuestra un tipo de acción, que una ruta Windows se normaliza antes del cruce de argv, que el adaptador de unfollow se vincula sólo a la red nombrada, que Reddit voto/Pinterest reacción no se convierten silenciosamente en likes equivalentes y que un archivo con sintaxis inválida no se marca como wired. Se verificó el solapamiento con las PR [#43](https://github.com/davidpd89/ci-sandbox-tmp/pull/43) (configuración/capacidades) y [#82](https://github.com/davidpd89/ci-sandbox-tmp/pull/82) (drift): ninguna es dependencia obligatoria y no se duplicaron sus modificaciones.

**Próximo canario supervisado, fuera de la prueba simulada:** comparar los resultados estáticos con los resultados reales de `metricas.csv` y los logs de una ronda controlada por Claude, para distinguir acciones confirmadas, saltadas y fallos. Este PR no inicia ese proceso.
