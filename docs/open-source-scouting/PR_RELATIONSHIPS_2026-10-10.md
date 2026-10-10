# Mapa de relaciones entre PR abiertas

Auditoria realizada el 10/10/2026 sobre 106 PR abiertas de
`davidpd89/ci-sandbox-tmp`. El objetivo es que cada agente conozca la fuente
canonica, las dependencias y las familias paralelas antes de desarrollar.

## Resumen ejecutivo

- Cuatro PR apiladas carecen de delta funcional propio: #181, #187, #191 y
  #202. Sus implementaciones viven en #155, #159, #161 y #163.
- #121 repite el objetivo ya implementado en #106 y su delta visible se
  concentra en higiene y artefactos de ejecucion. #106 es la fuente canonica.
- #132 y #143 contienen mejoras posteriores aprovechables, pero deben
  consolidarse en #100 y #99 respectivamente para mantener una sola linea de
  implementacion.
- Las series por plataforma #149-#203 son complementarias a los contratos
  globales #114-#117. Cada serie implementa o valida una red concreta.
- La campana CI #1 y la campana de investigacion #10 son arboles distintos.

## Consolidacion directa

| PR secundaria | Fuente canonica | Diagnostico | Accion recomendada |
| --- | --- | --- | --- |
| [#181](https://github.com/davidpd89/ci-sandbox-tmp/pull/181) | [#155](https://github.com/davidpd89/ci-sandbox-tmp/pull/155) | Rama apilada sin archivos propios; repite DST. | Conservar #155 y cerrar #181 tras guardar cualquier comentario util. |
| [#191](https://github.com/davidpd89/ci-sandbox-tmp/pull/191) | [#161](https://github.com/davidpd89/ci-sandbox-tmp/pull/161) | Rama apilada sin archivos propios; repite Jetstream archive-to-live. | Conservar #161 y cerrar #191. |
| [#187](https://github.com/davidpd89/ci-sandbox-tmp/pull/187) | [#159](https://github.com/davidpd89/ci-sandbox-tmp/pull/159) | Rama apilada sin archivos propios; repite reconciliacion de audiencias. | Conservar #159 y cerrar #187. |
| [#202](https://github.com/davidpd89/ci-sandbox-tmp/pull/202) | [#163](https://github.com/davidpd89/ci-sandbox-tmp/pull/163) | Rama apilada sin archivos propios; repite evidencia contextual. | Conservar #163 y cerrar #202. |
| [#121](https://github.com/davidpd89/ci-sandbox-tmp/pull/121) | [#106](https://github.com/davidpd89/ci-sandbox-tmp/pull/106) | Mismo objetivo; #106 ya contiene el cableado funcional. El delta de #121 mezcla `.gitignore`, caches, SQLite y `pyc`. | Recuperar una mejora de higiene si aporta valor y continuar en #106. |
| [#132](https://github.com/davidpd89/ci-sandbox-tmp/pull/132) | [#100](https://github.com/davidpd89/ci-sandbox-tmp/pull/100) | Hija apilada con mejoras reales y abundante ruido de sincronizacion. | Portar commits funcionales y pruebas a #100; revisar por rutas. |
| [#143](https://github.com/davidpd89/ci-sandbox-tmp/pull/143) | [#99](https://github.com/davidpd89/ci-sandbox-tmp/pull/99) | Hija apilada con memoria/dedupe util y arbol muy amplio. #99 ya documenta un kwargs incompatible pendiente. | Corregir y portar el delta focalizado a #99. |

## Cadenas apiladas

| Coordinacion | Implementacion | Validacion redundante o continuacion |
| --- | --- | --- |
| [#98](https://github.com/davidpd89/ci-sandbox-tmp/pull/98) DST de publicaciones | [#155](https://github.com/davidpd89/ci-sandbox-tmp/pull/155) | [#181](https://github.com/davidpd89/ci-sandbox-tmp/pull/181) redundante |
| [#94](https://github.com/davidpd89/ci-sandbox-tmp/pull/94) recuperacion Jetstream | [#161](https://github.com/davidpd89/ci-sandbox-tmp/pull/161) | [#191](https://github.com/davidpd89/ci-sandbox-tmp/pull/191) redundante |
| [#102](https://github.com/davidpd89/ci-sandbox-tmp/pull/102) snapshots de audiencia | [#159](https://github.com/davidpd89/ci-sandbox-tmp/pull/159) | [#187](https://github.com/davidpd89/ci-sandbox-tmp/pull/187) redundante |
| [#104](https://github.com/davidpd89/ci-sandbox-tmp/pull/104) evidencia contextual | [#163](https://github.com/davidpd89/ci-sandbox-tmp/pull/163) | [#202](https://github.com/davidpd89/ci-sandbox-tmp/pull/202) redundante |
| [#99](https://github.com/davidpd89/ci-sandbox-tmp/pull/99) observaciones de hashtags | [#143](https://github.com/davidpd89/ci-sandbox-tmp/pull/143) | Consolidar en #99 |
| [#100](https://github.com/davidpd89/ci-sandbox-tmp/pull/100) candidatos nativos | [#132](https://github.com/davidpd89/ci-sandbox-tmp/pull/132) | Consolidar en #100 |
| [#106](https://github.com/davidpd89/ci-sandbox-tmp/pull/106) QA final de voz | [#121](https://github.com/davidpd89/ci-sandbox-tmp/pull/121) | Extraer higiene util y conservar #106 |

## Familias globales y por red

### Comentarios y voz

Contrato comun: [#114](https://github.com/davidpd89/ci-sandbox-tmp/pull/114).

- Facebook [#154](https://github.com/davidpd89/ci-sandbox-tmp/pull/154)
- Pinterest [#162](https://github.com/davidpd89/ci-sandbox-tmp/pull/162)
- Reddit [#168](https://github.com/davidpd89/ci-sandbox-tmp/pull/168), junto con el fix de microrrespuestas [#142](https://github.com/davidpd89/ci-sandbox-tmp/pull/142)
- Bluesky [#178](https://github.com/davidpd89/ci-sandbox-tmp/pull/178)
- Mastodon [#188](https://github.com/davidpd89/ci-sandbox-tmp/pull/188)
- TikTok [#194](https://github.com/davidpd89/ci-sandbox-tmp/pull/194)
- Instagram [#199](https://github.com/davidpd89/ci-sandbox-tmp/pull/199)

La calidad del espanol [#119](https://github.com/davidpd89/ci-sandbox-tmp/pull/119)
alimenta el QA final [#106](https://github.com/davidpd89/ci-sandbox-tmp/pull/106).
El cableado de seleccion contextual [#135](https://github.com/davidpd89/ci-sandbox-tmp/pull/135)
consume el contrato de #114 y la evidencia contextual de #104/#163.

### Descubrimiento, hashtags y comunidades

Contrato comun: [#115](https://github.com/davidpd89/ci-sandbox-tmp/pull/115).

- Facebook [#152](https://github.com/davidpd89/ci-sandbox-tmp/pull/152)
- Pinterest [#160](https://github.com/davidpd89/ci-sandbox-tmp/pull/160)
- Reddit [#167](https://github.com/davidpd89/ci-sandbox-tmp/pull/167)
- Bluesky [#176](https://github.com/davidpd89/ci-sandbox-tmp/pull/176)
- Mastodon [#185](https://github.com/davidpd89/ci-sandbox-tmp/pull/185)
- TikTok [#193](https://github.com/davidpd89/ci-sandbox-tmp/pull/193)
- Instagram [#198](https://github.com/davidpd89/ci-sandbox-tmp/pull/198)

La cadena de datos es #99/#143 (observaciones),
[#101](https://github.com/davidpd89/ci-sandbox-tmp/pull/101) (activar terminos)
y despues los consumidores por red. Las investigaciones de crecimiento
[#124](https://github.com/davidpd89/ci-sandbox-tmp/pull/124),
[#125](https://github.com/davidpd89/ci-sandbox-tmp/pull/125),
[#126](https://github.com/davidpd89/ci-sandbox-tmp/pull/126) y
[#127](https://github.com/davidpd89/ci-sandbox-tmp/pull/127) aportan fuentes y
casos de uso para Facebook, Pinterest, Reddit y Bluesky.

### Ranking

Contrato comun: [#116](https://github.com/davidpd89/ci-sandbox-tmp/pull/116).

- Threads [#149](https://github.com/davidpd89/ci-sandbox-tmp/pull/149)
- Facebook [#156](https://github.com/davidpd89/ci-sandbox-tmp/pull/156)
- Pinterest [#164](https://github.com/davidpd89/ci-sandbox-tmp/pull/164)
- Reddit [#170](https://github.com/davidpd89/ci-sandbox-tmp/pull/170)
- Bluesky [#180](https://github.com/davidpd89/ci-sandbox-tmp/pull/180)
- Mastodon [#189](https://github.com/davidpd89/ci-sandbox-tmp/pull/189)
- TikTok [#195](https://github.com/davidpd89/ci-sandbox-tmp/pull/195)
- Instagram [#200](https://github.com/davidpd89/ci-sandbox-tmp/pull/200)

[#100](https://github.com/davidpd89/ci-sandbox-tmp/pull/100) aporta candidatos
nativos; [#103](https://github.com/davidpd89/ci-sandbox-tmp/pull/103) aplica
prioridades relacionales; [#137](https://github.com/davidpd89/ci-sandbox-tmp/pull/137)
evalua politicas alternativas mediante replay.

### Homogeneizacion, tests y herramientas

Contrato comun: [#117](https://github.com/davidpd89/ci-sandbox-tmp/pull/117),
relacionado con la paridad de configuracion
[#43](https://github.com/davidpd89/ci-sandbox-tmp/pull/43).

| Red | Tests y estandarizacion | Herramientas publicas |
| --- | --- | --- |
| Threads | [#150](https://github.com/davidpd89/ci-sandbox-tmp/pull/150) | [#151](https://github.com/davidpd89/ci-sandbox-tmp/pull/151) |
| Facebook | [#157](https://github.com/davidpd89/ci-sandbox-tmp/pull/157) | [#158](https://github.com/davidpd89/ci-sandbox-tmp/pull/158) |
| Pinterest | [#165](https://github.com/davidpd89/ci-sandbox-tmp/pull/165) | [#166](https://github.com/davidpd89/ci-sandbox-tmp/pull/166) |
| Reddit | [#173](https://github.com/davidpd89/ci-sandbox-tmp/pull/173) | [#174](https://github.com/davidpd89/ci-sandbox-tmp/pull/174) |
| Bluesky | [#182](https://github.com/davidpd89/ci-sandbox-tmp/pull/182) | [#184](https://github.com/davidpd89/ci-sandbox-tmp/pull/184) |
| Mastodon | [#190](https://github.com/davidpd89/ci-sandbox-tmp/pull/190) | [#192](https://github.com/davidpd89/ci-sandbox-tmp/pull/192) |
| TikTok | [#196](https://github.com/davidpd89/ci-sandbox-tmp/pull/196) | [#197](https://github.com/davidpd89/ci-sandbox-tmp/pull/197) |
| Instagram | [#201](https://github.com/davidpd89/ci-sandbox-tmp/pull/201) | [#203](https://github.com/davidpd89/ci-sandbox-tmp/pull/203) |

## Relaciones funcionales adicionales

### Tiempo y antiguedad

[#8](https://github.com/davidpd89/ci-sandbox-tmp/pull/8) define antiguedad
comun; [#169](https://github.com/davidpd89/ci-sandbox-tmp/pull/169) porta origen
temporal a X, Pinterest y Threads; #98/#155 resuelve DST de programacion. Son
capas complementarias y comparten `time_utils` y fixtures de bordes temporales.

### Relaciones, audiencia e identidad

- #102/#159 reconcilia snapshots completos de audiencia.
- [#118](https://github.com/davidpd89/ci-sandbox-tmp/pull/118) produce negativos de followback en X y Threads.
- [#120](https://github.com/davidpd89/ci-sandbox-tmp/pull/120) aplica reciprocidad y fidelizacion.
- [#103](https://github.com/davidpd89/ci-sandbox-tmp/pull/103) prioriza relaciones en planificadores.
- [#108](https://github.com/davidpd89/ci-sandbox-tmp/pull/108) registra evidencias en el ledger.
- [#109](https://github.com/davidpd89/ci-sandbox-tmp/pull/109) obtiene enlaces de perfil y [#110](https://github.com/davidpd89/ci-sandbox-tmp/pull/110) resuelve alias y renombres.

Orden recomendado: capturar y reconciliar (#102/#159), resolver identidad
(#109/#110), registrar eventos (#108), calcular reciprocidad (#118/#120) y
consumir la prioridad (#103).

### Experimentacion

[#107](https://github.com/davidpd89/ci-sandbox-tmp/pull/107) produce
exposiciones/resultados; [#111](https://github.com/davidpd89/ci-sandbox-tmp/pull/111)
estratifica por cola; [#137](https://github.com/davidpd89/ci-sandbox-tmp/pull/137)
evalua politicas; [#91](https://github.com/davidpd89/ci-sandbox-tmp/pull/91)
acredita identidad de ensayos y [#183](https://github.com/davidpd89/ci-sandbox-tmp/pull/183)
anade diagnostico de colisiones sobre #91.

### Bluesky y Jetstream

La recuperacion archive-to-live #94/#161 se relaciona con
[#136](https://github.com/davidpd89/ci-sandbox-tmp/pull/136) (puente JSONL),
[#175](https://github.com/davidpd89/ci-sandbox-tmp/pull/175) (indice de cursor),
[#95](https://github.com/davidpd89/ci-sandbox-tmp/pull/95) (estado/replay) y
[#146](https://github.com/davidpd89/ci-sandbox-tmp/pull/146) (confirmacion de
visibilidad AppView). Deben compartir cursor, identidad de evento y fixtures de
handoff.

### Campana CI

[#1](https://github.com/davidpd89/ci-sandbox-tmp/pull/1) es el padre de
[#8](https://github.com/davidpd89/ci-sandbox-tmp/pull/8),
[#87](https://github.com/davidpd89/ci-sandbox-tmp/pull/87),
[#88](https://github.com/davidpd89/ci-sandbox-tmp/pull/88),
[#89](https://github.com/davidpd89/ci-sandbox-tmp/pull/89),
[#91](https://github.com/davidpd89/ci-sandbox-tmp/pull/91),
[#92](https://github.com/davidpd89/ci-sandbox-tmp/pull/92),
[#93](https://github.com/davidpd89/ci-sandbox-tmp/pull/93) y
[#96](https://github.com/davidpd89/ci-sandbox-tmp/pull/96). #89 cubre commits
intermedios de PR y #93 commits transitorios de push: comparten motor de rango,
pero prueban eventos diferentes. #183 depende directamente de #91.

## Secuencia practica de revision

1. Resolver las siete consolidaciones directas.
2. Aprobar contratos comunes #114-#117 antes de duplicar interfaces por red.
3. Integrar cada familia por una red piloto y ejecutar sus contratos comunes.
4. Portar el mismo contrato al resto de redes mediante sus PR especificas.
5. Ejecutar la matriz #117/#43 para detectar gaps tras cada grupo.
6. Actualizar este mapa cuando una PR se fusione, se cierre o produzca una hija.
