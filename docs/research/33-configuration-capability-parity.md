# PR #43 — paridad declarativa de configuraciones y capacidades

**Fecha:** 2026-10-10. **Ámbito:** ocho redes de la matriz heredada + Instagram (nueve).
**Entrega:** inventario offline de solo lectura; no se publican ni se ejecutan acciones sociales.
**Origen del espejo:** `davidpd89/ci-sandbox-tmp`, rama `research/33-configuration-capability-parity`.
**Contraste del oficial:** `davidpd89/rrss-davidporto-CODE`,
`integracion/crecimiento-2026-10` (árbol observado `5449513d9b545d0a6a72abf066ab6a779bfdad71`).
No se modifica el oficial ni se traslada su configuración de TikTok al mirror.

Fuente primaria: https://github.com/python-jsonschema/jsonschema/tree/331c38425519b69118d22ebe467ad230fb83a010
Fecha de consulta: 2026-10-10
Licencia SPDX: MIT
Referencia inmutable: https://github.com/python-jsonschema/jsonschema/tree/331c38425519b69118d22ebe467ad230fb83a010

## Problema

El inventario de capacidad declarada del espejo omitía Instagram y no había
una inspección trazable de configuraciones, flags y defaults efectivos.

## Alternativas

Se compararon jsonschema, Pydantic, Dynaconf y Cerberus frente a la
reutilización de `growth_policy` con un inspector sin nuevas dependencias.

## Licencias y procedencia

Las opciones externas tienen licencias MIT o ISC (tabla y commits abajo).
**No se incorpora código externo**, solo se utilizan las funciones ya existentes
del propio proyecto.

## Decisión

Extender el inventario común, validar invariantes de JSON y emitir un informe
offline con procedencia de defaults y estados de wiring. No mutar configuraciones.

## Pruebas

Las suites nuevas usan solo archivos sintéticos temporales; comandos y CI
reproducibles detallados más abajo, incluida la distinción de simulación/canario.

## Retirada

Revertir el módulo de auditoría y sus regresiones, y la incorporación de
Instagram a la matriz. No hay datos que migrar ni librerías que desinstalar.

## Problema real observado

- `tools/network_capabilities.py` inventariaba solo ocho redes a pesar de que
  `tools/mechanical_round.py::PIPELINES` contiene **Instagram** y `CONTENT_QUEUE_NETWORKS`
  incluye las nueve. Se añade Instagram a la misma matriz genérica, sin crear un adaptador paralelo.
- La detección `gpt_writer_scheduled` inspeccionaba `pre` y `post` pese a describirse como
  «programado en pre». Ahora solo cuenta pasos `pre`. No deduce que una red sin escritor
  programado carezca de otra ruta editorial.
- Bluesky y Mastodon leen `growth_config.json` con esquemas distintos, pero
  `growth_policy.py` centraliza los límites de posts y seguidores. Por eso se comparan
  **valores efectivos** y procedencias sin eliminar los alias históricos
  `like_*` / `favourite_*`. No se reescriben presupuestos ni reglas de producción.
- En el mirror existen `SISTEMA_DIARIO_BLUESKY/growth_config.json` y
  `SISTEMA_DIARIO_MASTODON/growth_config.json`; el tercero, TikTok, solo
  consta en el repositorio oficial. El auditor informa `missing_in_checkout`
  (no «desactivado»), sin añadir al espejo la cuenta o los datos operativos.
- `reddit` no figura como pipeline automático y puede usar rutas propias;
  `not_declared` significa que esta auditoría no tiene una configuración de escáner
  registrada para esa red, no que esté inactiva.

## Implementación

- `tools/network_capabilities.py`: nueve redes; corregido falso positivo
  de escritores ubicados en `post`.
- `tools/config_capability_audit.py`: CLI con `--root` y `--json`.
  Lee exclusivamente archivos locales, importa los registros preexistentes
  `PIPELINES`, `ADAPTERS`, `HARVEST` y usa funciones reales de
  `growth_policy`. No importa escáneres de cuentas, ni solicita credenciales.
- Salida estable `schema: 1`, `capabilities`, `pipelines`,
  `configurations`, `wiring`, `environment_names`, `findings`, `errors`.
  Cada red declara `primary_lane` (API, WEB, MOBILE) si tiene pipeline.
  `runs_source=runtime_dynamic_or_default` indica que la cifra definitiva
  puede depender de la rampa: **no** inventa un valor a partir de la ausencia de flag.
- Los estados de `unfollow` / `loyalty` son `wired`,
  `available_not_wired` y `missing`; escritor GPT sin paso pre se representa
  `not_observed_in_pre` (no «imposible»).
- Validación explícita de versión, tipos y rangos de presupuestos, nombres
  duplicados de superficies, contradicción de alias de edad, flags booleanos,
  raíz JSON, claves duplicadas incluso anidadas, y `NaN/Infinity` no válidos.
  Se respeta que `0` puede desactivar determinados presupuestos opcionales.
- Descubrimiento AST de nombres de variables de entorno en `tools/*.py`
  (sin leer `os.environ` ni imprimir valores/defaults) y de campos de config
  sin literal visible en scanner/utilidades de crecimiento. **Estos últimos
  son candidatos a revisión, no prueba de orfandad**: acceso indirecto y
  otras herramientas pueden usarlos.
- Diferencias de política común se marcan como informativas, porque un
  override específico de plataforma puede ser deliberado. Ficheros ausentes
  tampoco rompen CI en un espejo sanitizado. Config JSON inválida devuelve código 2.

### Vista de capacidades a partir de `mechanical_round.PIPELINES`

| Red | Carril principal declarado | Config scan en mirror | Evidencia |
|---|---|---|---|
| Bluesky | API | presente | scanner + JSON |
| Mastodon | API | presente | scanner + JSON |
| X | WEB | no declarada aquí | pipeline navegador |
| Threads | WEB | no declarada aquí | pipeline navegador |
| Facebook | WEB | no declarada aquí | pipeline navegador |
| Instagram | WEB | no declarada aquí | pipeline navegador (omitida antes) |
| Pinterest | WEB | no declarada aquí | pipeline navegador |
| Reddit | sin pipeline en `mechanical_round` | no declarada aquí | vía alternativa por revisar |
| TikTok | MOBILE | ausente en mirror, presente en oficial | `growth_core.pipeline_for` |

Una red puede incorporar **más** carriles aparte del principal; las tres colas WEB/API/MOBILE
siguen siendo independientes. Esta tabla **no** garantiza éxito de publicación ni permisos remotos.

La política común se confirma en los JSON inspeccionados: edades de adquisición 21 días
y de comunidad 45 días para Bluesky/Mastodon mediante alias respectivos. La función
`growth_policy.follow_max_followers()` unifica 20.000 como predeterminado; sobrescrituras
explícitas mantienen precedencia. No se activan controles ausentes automáticamente.

## Investigación comparada (proyectos públicos, estado a 2026-10-10)

| Candidato | Procedencia fija | Licencia | Estado y compatibilidad | Decisión |
|---|---|---|---|---|
| [python-jsonschema/jsonschema](https://github.com/python-jsonschema/jsonschema/tree/331c38425519b69118d22ebe467ad230fb83a010) | `v4.25.1` → `331c384`; versión posterior 4.26.0 anunciada 2026-01-07 | MIT | activo (actualización GitHub 2026-10-07); Python y Windows | Apropiado si se estabiliza un esquema formal compartido. Aquí los esquemas de red **no** son idénticos. |
| [pydantic/pydantic](https://github.com/pydantic/pydantic/tree/001dea020e0809844e5b17666432c9135a976f46) | `v2.13.5` → `001dea0` (2026-08-28) | MIT | activo; Python 3.11 + Windows, dependencia nativa `pydantic-core` | Excesivo para inventario estático; evitar conversiones de tipos silenciosas. |
| [dynaconf/dynaconf](https://github.com/dynaconf/dynaconf/tree/455ee38569d76cd3707c73209b660cf60bd97b29) | `455ee385`, 2026-08-19; release 3.3.5 en 2026-08 | MIT | activo, orientado a layering de entornos; Python 3.11/Windows | No añadir precedencias dinámicas que cambien las rondas existentes. |
| [pyeve/cerberus](https://github.com/pyeve/cerberus/tree/83f5dada76aa3179ef21b677a7f4235bf20c1566) | `83f5dada`, 2026-10-01 | ISC | activo en rama 1.3.x; validar versiones concretas antes de introducirlo | Ligero, pero nueva dependencia no aporta valor tangible frente a unas invariantes tipadas. |
| Código local | `growth_policy.py` y `network_capabilities.py` existentes | código propio | Python 3.11 Windows/Linux, stdlib | **Elegido:** reutilizar funciones reales y registros sin reimplementar los límites. |

No se copia ningún archivo ni fragmento de los proyectos externos; no se exige
añadir licencias de terceros al repositorio. Los enlaces apuntan a árboles/commits
estudiados, no a `main` mutable. Revisión de dependencias: no se añade ninguna;
la única dependencia de la auditoría es Python 3.11 y código local ya usado.

## Pruebas y medición

Ejecutar (Windows PowerShell o Linux) desde raíz:

```sh
python -m pytest -q tests/test_network_capabilities.py tests/test_config_capability_audit.py -p no:cacheprovider
python tools/config_capability_audit.py --json
python tools/config_capability_audit.py
```

Regresiones sintéticas cubren nueve redes, Instagram, pre/post de escritor,
carriles, procedencia de defaults y overrides, diferencias voluntarias, JSON
duplicado, `NaN`, booleanos numéricos, flags, ausencia de archivos, raíz
inválida, candidatos a huérfanos y nombres de entorno sin datos sensibles.
El workflow general existente ya ejecuta pytest en Ubuntu y Windows 3.11 sobre
los pushes de la rama. **La prueba en CI y el canario del sistema oficial
deben comprobarse en el HEAD final**; una prueba offline no demuestra conexión
real a un dispositivo, Edge o plataformas externas.

**Antes/después verificable:** redes del inventario 8 → 9; falsos positivos
posibles del escritor en `post`: permitidos → excluidos; visibilidad de
procedencia de configuración: inexistente → declarativa por nueve redes.
No se atribuye mejora de crecimiento a una auditoría estática.

## Segunda revisión adversarial y correcciones

1. **JSON de raíz no objeto:** `validate_config` ya detectaba el error,
   pero el informe podía continuar con `.get` y caer en `AttributeError`.
   Corregido: invalida y continúa sin leer campos (regresión añadida).
2. **`NaN`/infinito:** el `json.loads` predeterminado acepta extensiones
   no estándar. Se rechazan explícitamente incluso en campos no numéricos.
3. **Carriles desconocidos:** Reddit no hereda API por defecto si carece de pipeline;
   devuelve `null`. Instagram se deriva del flag `browser` real.
4. **Valores por defecto:** una ronda no declarada no se rellena con un número
   potencialmente incorrecto; se informa de que el orquestador lo calcula.
5. **Falsa orfandad:** referencias literales nunca se presentan como hallazgo
   confirmado. No se han borrado configuraciones por esa heurística.
6. **Datos sensibles:** se reportan nombres de entorno, nunca sus valores,
   se evita incluir el JSON privado de TikTok, y los errores de parseo
   no vuelcan contenido de los archivos.
7. **Activación y retrocompatibilidad:** los formatos de `build_matrix()` y
   `gaps()` permanecen estables, salvo añadir Instagram. El contrato no
   obliga a que todas las plataformas implementen cada función.

**Limitaciones:** comparación AST incompleta ante claves dinámicas, no se
validan todas las opciones de cada scanner, la precedencia de la rampa
`volume_ramp` solo se documenta y no se ejecuta, y un paso programado
puede fallar al ejecutarse. Revisar en Windows vivo y canario supervisado
tras integración en oficial; no se realizan aquí acciones sociales.

**Rollback:** revertir commits de `config_capability_audit.py`, su test y
la ampliación de la matriz, sin migración de estado ni dependencias.
**Coordinación:** el inventario base procede de la PR #47 del **repo oficial privado**,
no necesariamente de la #47 del mirror; los tests operativos aludidos en su docstring
son del **repo oficial**, no de la PR #73 del mirror. En el mirror, #30 cubre
contratos/tests y #26 colas. No duplicar esos alcances.
**Integración:** pendiente del controlador; **no merge**.


## Revisión independiente del controlador (2026-10-10)

- Se evita atribuir un escritor genérico a otra red cuando el argumento de red
  no coincide. El escritor específico de TikTok sigue reconocido sin parámetro.
- Los límites de conteo y los overrides enteros de la política compartida ya
  no admiten fracciones que los consumidores truncarían con `int()`.
- Las rutas de configuración con symlink colgante se clasifican como inválidas,
  no como configuración ausente. Pruebas sintéticas adicionales y contrato de
  cobertura frente a `CONTENT_QUEUE_NETWORKS`.
- Pendiente fuera del alcance declarativo: derivar matrices efectivas de todas
  las rutas de ejecución y validar la consistencia del registro cuando `--root`
  apunta a otro checkout; coordinar con #81 y #82 antes de duplicar.

- Tercera pasada: se reconocen referencias `os.environ["CLAVE"]` y
  `os.environ.setdefault("CLAVE", ...)` sin evaluar valores; cuando `--root`
  apunta a otro checkout sin inyección completa de registros, el informe avisa
  de la procedencia local de los pipelines en vez de ocultar esa mezcla.


## Actualización sobre base sincronizada y respuesta a revisión (10/10/2026)

**Base incorporada sin reescritura de historial:** `research/public-reuse-parent`
@ `250ccb019fb8683311df48c7d02d6c6d2b73a47b` (incluye el
commit `737fc01` que Claude trajo del repositorio oficial).
Se conservan íntegros los `tools/` y `tests/` de esa base;
el diff propio sigue limitado a seis archivos. Esta operación es **merge de
la base dentro de la rama de PR**, no un merge de la PR hacia su base.
Comprobar que `behind_by=0` en el HEAD final; la base puede seguir avanzando.

**Cambio de compatibilidad determinante:** la base sincronizada contiene
`discovery_graph.NETWORKS` y
`network_policy_contracts.TEXT_EXECUTION_ROUTES` para **ocho redes**;
ampliar directamente `network_capabilities.NETWORKS` a nueve provocó
cuatro fallos reales en CI: `test_discovery_graph` y tres verificaciones
de `test_pr73_policy_runtime` (falta de ruta certificada Instagram).
No debe añadirse una ruta ficticia de ejecución para callar esos tests.
La solución distingue:
- `network_capabilities.INVENTORY_NETWORKS`: **nueve** redes en el inventario
  declarativo y en `build_matrix()`, incluida Instagram.
- `network_capabilities.NETWORKS`: las **ocho** redes con contrato de
  ejecución de texto/descubrimiento vigente. Mantiene retrocompatibilidad
  con los validadores de seguridad introducidos por la base, sin afirmar
  que Instagram ejecuta un control no verificado.
- El auditor recorre expresamente `INVENTORY_NETWORKS`, no el subconjunto
  operativo. Hay regresión que comprueba que la lista de rutas de texto y
  `discovery_graph` coinciden con las redes operativas, a la vez que
  Instagram permanece inventariada.

**Portabilidad con el oficial:** eliminado el supuesto «TikTok JSON ausente».
El test de checkout comprueba `SISTEMA_DIARIO_TIKTOK/growth_config.json`
si existe, y exige `valid`; si no existe, exige
`missing_in_checkout`. Los límites efectivos de Bluesky/Mastodon
se comparan contra las funciones **reales** de `growth_policy`, no con
valores hardcoded susceptibles de overrides. Fixture sintético cubre
TikTok presente y ausente sin publicar su JSON de cuenta.

**Dos raíces y procedencia:** el argumento `--root` sigue siendo una
vista de *archivos*; para inventariar registros de otro checkout es
obligatorio inyectar explícitamente
`pipelines`, `cleanup_adapters`, `harvesters`.
Sin ello se emite `registry_from_local_checkout`. Una regresión usa
dos raíces con configuraciones y pipelines sintéticos divergentes,
comprueba diferencias observables y comprueba el aviso si se omite la
inyección. El soporte para cargar automáticamente registros Python
ajenos queda intencionadamente excluido por riesgo de importar/ejecutar
un checkout no confiable; no es requisito para utilizar la herramienta
en su propio repo.

**Coordinar y no duplicar:** las PR #81 y #82 del mirror ya figuran
**cerradas sin merge en el mirror**, con nota de Claude de haberlas
trasplantado al oficial (commit `89469ebd`); #117 también figura
**cerrada sin merge en mirror** e integrada en oficial (commit
`26376b6f`). `tools/executable_feature_parity.py` y
`tools/social_plan_contract.py` ya existen en la rama oficial y cubren
contratos distintos. La presente PR solo aporta inventario declarativo
y validación de JSON/procedencia; no reemplaza esos contratos de
ejecución ni los habilita automáticamente. El mapa #204 informa las
dependencias, no se edita desde esta rama.

**Segunda pasada adversarial tras sincronizar:** regresiones de la base
aplicadas **sin desactivarlas**; no se alteraron certificados, el ledger,
POST→ACK→TTL, reglas de antigüedad ni likes en X. Cualquier afirmación
de que hay nueve redes **operativamente certificadas** se rechaza por
la ausencia comprobable de una ruta de texto de Instagram en el
contrato actual; esta PR solo prueba nueve filas de inventario.

**Verificación exigida al controlador:** CI del HEAD final Ubuntu/Windows
Python 3.11; `python tools/network_capabilities.py --json` y
`python tools/config_capability_audit.py --json` sin acciones; si se
trasplanta al oficial, repetir las suites en rama temporal con sus
configuraciones completas. Edge/CDP/Android y canario supervisado siguen
fuera del alcance de tests offline, no bloquean la incorporación de
un **inventario read-only**, pero tampoco certifican ejecución remota.
