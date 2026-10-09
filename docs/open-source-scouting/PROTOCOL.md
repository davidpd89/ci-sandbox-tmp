# Campana de reutilizacion de software publico

Esta rama organiza encargos independientes para que un agente GPT investigue
software publico existente y reutilice componentes valiosos en el sistema RRSS.
Cada PR hija contiene un unico frente de trabajo y se revisa por separado.

## Mision del agente que tome una PR

1. Leer el mirror y el repositorio oficial RRSS antes de buscar alternativas.
2. Definir el hueco real: comportamiento ausente, duplicado, fragil o costoso.
3. Investigar repositorios publicos y documentacion oficial vigentes en la fecha
   de ejecucion. Comparar todas las opciones creibles y concentrar el analisis
   en proyectos relevantes.
4. Verificar licencia, actividad reciente, mantenedores, issues, seguridad,
   dependencias, compatibilidad Windows/Linux y coste operativo.
5. Elegir una de estas salidas:
   - integrar o adaptar la pieza minima que mejora el sistema;
   - usar una dependencia mantenida en lugar de copiar codigo;
   - extraer un patron y reimplementarlo cuando sea la opcion mas conveniente;
   - conservar lo existente cuando gane la comparacion con evidencia.
6. Si hay cambio, incluir pruebas offline, migracion reversible, documentacion,
   procedencia y medicion antes/despues. Dejar la PR lista para merge.
7. Si aparecen fallos, reproducirlos, investigar alternativas actuales y
   corregirlos en la misma PR con regresiones que ejerciten el comportamiento.

## Criterios de utilidad

- Convertir la investigacion en codigo, pruebas, comparativas o decisiones utiles.
- Reutilizar el componente preciso y mantener clara su procedencia.
- Ajustar el peso de la solucion al tamano del problema.
- Demostrar las mejoras con pruebas, benchmarks o contratos verificables.
- Estudiar APIs, SDK, clientes, integraciones y patrones disponibles.
- Registrar repositorio, commit/tag, licencia y archivos o ideas reutilizados.
- Valorar actividad, comunidad, calidad tecnica y facilidad de evolucion.
- Construir pruebas reproducibles en CI con fixtures controlados.

## Repositorio oficial

El mirror es incompleto. Si hacen falta modulos, fixtures, configuracion o
documentacion, tomar del repositorio oficial RRSS todo el contexto necesario
para evaluar y probar correctamente la mejora.

## PR adicionales nacidas de la investigacion

Despues de investigar e implementar, el agente puede abrir dos PR nuevas cuando
descubra trabajos diferentes, concretos y de alto valor. Cada una debe tener
evidencia, alcance claro y criterio de aceptacion. Los hallazgos con entidad
propia y valor demostrable alimentan asi la siguiente ronda de mejora.

## Entregables minimos

- `docs/research/<tema>.md` con necesidad, candidatos, licencias y decision.
- Implementacion proporcionada o conclusion razonada de continuidad.
- Pruebas y resultado reproducible.
- Riesgos de actualizacion y forma de retirar la integracion.
- Enlaces permanentes a los commits o tags concretos estudiados.

## PR hijas

Las PR 01-09 cubren plataformas. Las restantes cubren capacidades comunes que
pueden beneficiar a varias redes. Se pueden ejecutar en paralelo, pero una PR
debe reutilizar hallazgos ya publicados por otra y coordinar alternativas que
resuelvan el mismo problema.

## Indice de encargos

| PR | Encargo |
| --- | --- |
| [#11](https://github.com/davidpd89/ci-sandbox-tmp/pull/11) | Bluesky y AT Protocol |
| [#12](https://github.com/davidpd89/ci-sandbox-tmp/pull/12) | Mastodon y Fediverse |
| [#13](https://github.com/davidpd89/ci-sandbox-tmp/pull/13) | X |
| [#14](https://github.com/davidpd89/ci-sandbox-tmp/pull/14) | Threads |
| [#15](https://github.com/davidpd89/ci-sandbox-tmp/pull/15) | Facebook |
| [#16](https://github.com/davidpd89/ci-sandbox-tmp/pull/16) | Instagram |
| [#17](https://github.com/davidpd89/ci-sandbox-tmp/pull/17) | Pinterest |
| [#18](https://github.com/davidpd89/ci-sandbox-tmp/pull/18) | Reddit |
| [#19](https://github.com/davidpd89/ci-sandbox-tmp/pull/19) | TikTok |
| [#20](https://github.com/davidpd89/ci-sandbox-tmp/pull/20) | Publicacion y programacion |
| [#21](https://github.com/davidpd89/ci-sandbox-tmp/pull/21) | Descubrimiento, escucha y ranking |
| [#22](https://github.com/davidpd89/ci-sandbox-tmp/pull/22) | Respuestas, contexto y memoria |
| [#23](https://github.com/davidpd89/ci-sandbox-tmp/pull/23) | Analitica, atribucion y experimentos |
| [#24](https://github.com/davidpd89/ci-sandbox-tmp/pull/24) | Dashboard y observabilidad |
| [#25](https://github.com/davidpd89/ci-sandbox-tmp/pull/25) | Comunidad, CRM y fidelizacion |
| [#26](https://github.com/davidpd89/ci-sandbox-tmp/pull/26) | Colas, idempotencia y recuperacion |
| [#27](https://github.com/davidpd89/ci-sandbox-tmp/pull/27) | Navegador y movil |
| [#28](https://github.com/davidpd89/ci-sandbox-tmp/pull/28) | Contenido, media y assets |
| [#29](https://github.com/davidpd89/ci-sandbox-tmp/pull/29) | Agentes, skills y orquestacion |
| [#30](https://github.com/davidpd89/ci-sandbox-tmp/pull/30) | Testing, fuzzing y contratos |
| [#31](https://github.com/davidpd89/ci-sandbox-tmp/pull/31) | Seguridad, privacidad y supply chain |
| [#32](https://github.com/davidpd89/ci-sandbox-tmp/pull/32) | Datos, almacenamiento e informes |
| [#33](https://github.com/davidpd89/ci-sandbox-tmp/pull/33) | Pruebas diferenciales entre redes |
| [#34](https://github.com/davidpd89/ci-sandbox-tmp/pull/34) | Mutation testing sobre logica critica |
| [#35](https://github.com/davidpd89/ci-sandbox-tmp/pull/35) | Pruebas con modelos y maquinas de estado |
| [#36](https://github.com/davidpd89/ci-sandbox-tmp/pull/36) | Chaos testing y fault injection |
| [#37](https://github.com/davidpd89/ci-sandbox-tmp/pull/37) | Profiling y presupuestos de rendimiento |
| [#38](https://github.com/davidpd89/ci-sandbox-tmp/pull/38) | Fugas de recursos y ciclo de vida |
| [#39](https://github.com/davidpd89/ci-sandbox-tmp/pull/39) | Carreras, concurrencia y deadlocks |
| [#40](https://github.com/davidpd89/ci-sandbox-tmp/pull/40) | Esquemas, migraciones y compatibilidad |
| [#41](https://github.com/davidpd89/ci-sandbox-tmp/pull/41) | Drift y contratos de APIs externas |
| [#42](https://github.com/davidpd89/ci-sandbox-tmp/pull/42) | Selectores y regresion visual |
| [#43](https://github.com/davidpd89/ci-sandbox-tmp/pull/43) | Paridad de configuracion y capacidades |
| [#44](https://github.com/davidpd89/ci-sandbox-tmp/pull/44) | Arquitectura y acoplamiento |
| [#45](https://github.com/davidpd89/ci-sandbox-tmp/pull/45) | Code review, codigo muerto y complejidad |
| [#46](https://github.com/davidpd89/ci-sandbox-tmp/pull/46) | Calidad de datos y reconciliacion |
| [#47](https://github.com/davidpd89/ci-sandbox-tmp/pull/47) | Alertas y simulacion de incidentes |
| [#48](https://github.com/davidpd89/ci-sandbox-tmp/pull/48) | Backup, restore y recuperacion |
| [#49](https://github.com/davidpd89/ci-sandbox-tmp/pull/49) | Horarios, zonas y DST |
| [#50](https://github.com/davidpd89/ci-sandbox-tmp/pull/50) | Unicode, locale y codificacion |
| [#51](https://github.com/davidpd89/ci-sandbox-tmp/pull/51) | Evaluacion ciega de contenido humano |
| [#52](https://github.com/davidpd89/ci-sandbox-tmp/pull/52) | Ronda end-to-end en shadow mode |
| [#53](https://github.com/davidpd89/ci-sandbox-tmp/pull/53) | Generacion de fixtures sinteticos |
| [#54](https://github.com/davidpd89/ci-sandbox-tmp/pull/54) | Optimizacion de tokens, llamadas y coste |
| [#55](https://github.com/davidpd89/ci-sandbox-tmp/pull/55) | Dependencias, releases y rollback |
| [#56](https://github.com/davidpd89/ci-sandbox-tmp/pull/56) | Documentacion ejecutable y runbooks |
