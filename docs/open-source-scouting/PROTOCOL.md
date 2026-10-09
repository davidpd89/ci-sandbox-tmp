# Campana de reutilizacion de software publico

> **Puerta operativa vigente (2026-10-09):** Este protocolo es de la
> campaña **pública** `davidpd89/ci-sandbox-tmp`, PR padre #10 hacia
> `main`. Las hijas originales #11–#56 y la ampliación #57–#86 apuntan a `research/public-reuse-parent`.
> La PR padre nunca fusiona automáticamente hijas ni las implementa.
> El manifiesto verificado es [children.json](children.json); plantilla verificable
> de evidencias [RESEARCH_TEMPLATE.md](RESEARCH_TEMPLATE.md); la coordinación,
> comprobaciones y tres puertas están en [COORDINATION.md](COORDINATION.md).
> Si otra sección parece autorizar traslado indiscriminado de código privado,
> prevalecen la revisión humana y las reglas estrictas de privacidad.
>
> Comprobación offline: `python tools/validate_open_source_campaign.py`.
> Comprobación online explícita: `python tools/validate_open_source_campaign.py --live`
> (opcional `GITHUB_TOKEN` en entorno, jamás pegarlo en ficheros).
> Pruebas: `python -m unittest discover -s tests -p test_open_source_campaign.py -v`.
> El workflow aislado es `.github/workflows/validate-public-reuse.yml`.
> El éxito de este validador NO garantiza seguridad integral ni autoriza un merge.

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
   procedencia y medicion antes/despues. Dejar la PR lista para revision; nunca
   declarar aptitud de merge basada solamente en mergeable=true.
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

El mirror es publico e incompleto; el oficial es privado. Se permite consultar
el original por una conexion autorizada, pero NUNCA copiar indiscriminadamente
modulos, historiales, capturas, perfiles, bases de datos ni configuraciones.
Clasificar todo artefacto antes de su traslado. Solo se incorporan piezas con
licencia/propiedad y redistribucion comprobadas, datos sinteticos y revision
humana. Un mirror sin un modulo NO demuestra que falte en el original.

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

La primera ola comprende 46 hijas #11–#56; la segunda, 30 hijas #57–#86,
incorporadas el 2026-10-09. El validador exige que la primera ola permanezca
íntegra y que el índice y el manifiesto cubran todas las PR nuevas sin huecos.

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
| [#57](https://github.com/davidpd89/ci-sandbox-tmp/pull/57) | Ciclo de followback en todas las redes |
| [#58](https://github.com/davidpd89/ci-sandbox-tmp/pull/58) | Reconciliacion diaria de unfollow |
| [#59](https://github.com/davidpd89/ci-sandbox-tmp/pull/59) | Memoria de reciprocidad repetida |
| [#60](https://github.com/davidpd89/ci-sandbox-tmp/pull/60) | Maquina de estados de relaciones |
| [#61](https://github.com/davidpd89/ci-sandbox-tmp/pull/61) | Antiguedad de posts en todas las redes |
| [#62](https://github.com/davidpd89/ci-sandbox-tmp/pull/62) | Fuente fiable de fecha de publicacion |
| [#63](https://github.com/davidpd89/ci-sandbox-tmp/pull/63) | Expansion inteligente de hashtags |
| [#64](https://github.com/davidpd89/ci-sandbox-tmp/pull/64) | Grupos, comunidades y nichos |
| [#65](https://github.com/davidpd89/ci-sandbox-tmp/pull/65) | Senales explicitas de reciprocidad |
| [#66](https://github.com/davidpd89/ci-sandbox-tmp/pull/66) | Ranking de cuentas y posts candidatos |
| [#67](https://github.com/davidpd89/ci-sandbox-tmp/pull/67) | Persistencia de notificaciones de repost |
| [#68](https://github.com/davidpd89/ci-sandbox-tmp/pull/68) | Ciclo de interacciones reversibles |
| [#69](https://github.com/davidpd89/ci-sandbox-tmp/pull/69) | Fidelizacion desde engagement entrante |
| [#70](https://github.com/davidpd89/ci-sandbox-tmp/pull/70) | Discovery desde likes y comentarios |
| [#71](https://github.com/davidpd89/ci-sandbox-tmp/pull/71) | Priorizacion diaria de relaciones |
| [#72](https://github.com/davidpd89/ci-sandbox-tmp/pull/72) | Benchmark de comentarios por red |
| [#73](https://github.com/davidpd89/ci-sandbox-tmp/pull/73) | Corpus de escritura humana propia |
| [#74](https://github.com/davidpd89/ci-sandbox-tmp/pull/74) | Comentarios anclados al contexto |
| [#75](https://github.com/davidpd89/ci-sandbox-tmp/pull/75) | Repeticion y frases prefabricadas |
| [#76](https://github.com/davidpd89/ci-sandbox-tmp/pull/76) | Lenguaje nativo de cada plataforma |
| [#77](https://github.com/davidpd89/ci-sandbox-tmp/pull/77) | Continuidad de conversaciones |
| [#78](https://github.com/davidpd89/ci-sandbox-tmp/pull/78) | Momento y cadencia de respuestas |
| [#79](https://github.com/davidpd89/ci-sandbox-tmp/pull/79) | Calidad de voz y espanol |
| [#80](https://github.com/davidpd89/ci-sandbox-tmp/pull/80) | Experimentos de contenido y comentarios |
| [#81](https://github.com/davidpd89/ci-sandbox-tmp/pull/81) | Matriz ejecutable de paridad |
| [#82](https://github.com/davidpd89/ci-sandbox-tmp/pull/82) | Drift de capacidades y configuracion |
| [#83](https://github.com/davidpd89/ci-sandbox-tmp/pull/83) | Orquestacion de crecimiento diario |
| [#84](https://github.com/davidpd89/ci-sandbox-tmp/pull/84) | Ledger comun de relaciones |
| [#85](https://github.com/davidpd89/ci-sandbox-tmp/pull/85) | Identidad entre redes |
| [#86](https://github.com/davidpd89/ci-sandbox-tmp/pull/86) | Embudo de comunidad y trafico |
