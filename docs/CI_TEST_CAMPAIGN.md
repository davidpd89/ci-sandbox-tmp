# Campana de pruebas RRSS

Esta rama es el punto de integracion de una campana de PR independientes para
encontrar fallos antes de trasladar cambios al repositorio oficial. Las PR hijas
se abren contra esta rama, no unas contra otras, para que cada resultado pueda
revisarse y fusionarse por separado.

## Objetivos

- Detectar diferencias de comportamiento entre redes sociales.
- Probar efectos laterales, reintentos, idempotencia y confirmacion de acciones.
- Someter colas, CSV, locks y estados a corrupcion, concurrencia y recuperacion.
- Encontrar duplicacion y contratos que conviene centralizar.
- Medir rutas lentas con presupuestos holgados y reproducibles.
- Recuperar pruebas utiles que existan en el repositorio oficial pero falten en
  el mirror.

## Linea base

Ejecucion local con Python 3.11 antes de abrir las PR:

- 1691 pruebas superadas.
- 5 pruebas omitidas.
- 8 fallos conocidos que el workflow actual excluye expresamente.
- 668 subpruebas superadas.

Los ocho fallos conocidos no se consideran una nueva regresion. Cada PR hija
debe ejecutar sus pruebas nuevas y la misma seleccion offline que GitHub
Actions. Un descubrimiento se convierte en una asercion reproducible; si exige
un cambio, la propia PR incluye la correccion y una prueba de regresion.

## PR hijas

| Bloque | Riesgo que cubre | Resultado esperado |
| --- | --- | --- |
| Contrato del mirror | CI incompleta, secretos, dependencias o rutas ausentes | El snapshot puede validarse de forma autonoma |
| Paridad entre redes | Una red omite una proteccion presente en las demas | Matriz de capacidades y contratos comparables |
| Efectos laterales | Imports que conectan, escriben o lanzan procesos | Imports offline, rapidos y deterministas |
| Estado y concurrencia | Doble accion, CSV truncado, lock perdido, replay | Recuperacion e idempotencia demostradas |
| Observabilidad | Fallos silenciosos y metricas que no explican causa | Codigos y eventos accionables |
| Arquitectura y rendimiento | Copias divergentes y rutas lentas | Presupuestos y duplicacion visibles en CI |
| Publicacion y contenido | Formatos, limites y enlaces distintos por red | Contratos de payload por plataforma |

## PR abiertas

| PR | Bloque | Resultado de la primera ronda |
| --- | --- | --- |
| [#2](https://github.com/davidpd89/ci-sandbox-tmp/pull/2) | Contrato del mirror | Reactiva higiene con `fetch-depth: 2` y valida PR en Windows/Ubuntu |
| [#3](https://github.com/davidpd89/ci-sandbox-tmp/pull/3) | Aprendizaje entre redes | Exige control, madurez, procedencia y verificacion externa |
| [#4](https://github.com/davidpd89/ci-sandbox-tmp/pull/4) | Ranking de descubrimiento | 23 tests y 2315 subtests contra muestras pequenas y datos incompletos |
| [#5](https://github.com/davidpd89/ci-sandbox-tmp/pull/5) | CSV multiproceso | Corrige cinco fallos: lock, cabecera, recuperacion y handle abierto |
| [#6](https://github.com/davidpd89/ci-sandbox-tmp/pull/6) | KPI y anomalias | Conecta la alerta de caida sostenida con el panel de canarios |
| [#7](https://github.com/davidpd89/ci-sandbox-tmp/pull/7) | Seguridad TikTok | Evita reintentar follows pendientes y alerta sesiones sin progreso |
| [#8](https://github.com/davidpd89/ci-sandbox-tmp/pull/8) | Antiguedad comun | Aplica una politica a todas las rutas, incluida Instagram y Reddit secundario |
| [#9](https://github.com/davidpd89/ci-sandbox-tmp/pull/9) | Duplicacion AST | Localiza seis copias exactas e impide que la deuda aumente |

Todas las ramas anteriores han terminado en verde tanto en `ubuntu-latest`
como en `windows-latest`. La PR #8 ejecuto ademas la suite local completa:
1702 passed, 5 skipped y las 8 exclusiones conocidas del mirror.

## Regla sobre el repositorio oficial

El mirror es un entorno de CI, no la unica fuente de codigo. Si una prueba
necesita modulos, fixtures, documentacion o configuracion que no estan en este
snapshot, hay que traer la version minima necesaria desde el repositorio
oficial RRSS, conservar su estructura y dejar constancia en la PR. No se debe
rebajar una prueba solamente porque al mirror le falte contexto.

## Criterios de merge

1. La prueba reproduce un riesgo real y tiene un nombre que explica el contrato.
2. No usa cuentas, credenciales ni red publica.
3. Funciona en Ubuntu y Windows con Python 3.11.
4. No depende del orden de ejecucion ni deja estado compartido.
5. Un fallo nuevo incluye diagnostico, alternativa investigada y correccion, o
   queda documentado como deuda concreta con un caso reproducible.
6. La descripcion de la PR indica que puede tomarse codigo adicional del
   repositorio oficial RRSS si hace falta.

## Orden de integracion

Primero se integra el contrato del mirror. Despues pueden entrar en paralelo
paridad, efectos laterales y estado. Observabilidad, arquitectura/rendimiento y
publicacion pueden apoyarse en esos contratos, pero cada PR debe seguir siendo
revisable de forma aislada.
