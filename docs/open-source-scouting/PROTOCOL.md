# Campana de reutilizacion de software publico

Esta rama organiza encargos independientes para que un agente GPT investigue
software publico existente y evite reinventar componentes del sistema RRSS.
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

## Dos PR adicionales como maximo

Despues de investigar e implementar, el agente puede abrir hasta dos PR nuevas
si ha descubierto trabajos diferentes, concretos y de alto valor. Cada una debe
tener evidencia, alcance acotado y criterio de aceptacion. Abrirlas unicamente
cuando el hallazgo tenga entidad propia y valor demostrable.

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
