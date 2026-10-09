# Campana de reutilizacion de software publico

Esta rama organiza encargos independientes para que un agente GPT investigue
software publico existente y evite reinventar componentes del sistema RRSS.
Cada PR hija contiene un unico frente de trabajo y se revisa por separado.

## Mision del agente que tome una PR

1. Leer el mirror y el repositorio oficial RRSS antes de buscar alternativas.
2. Definir el hueco real: comportamiento ausente, duplicado, fragil o costoso.
3. Investigar repositorios publicos y documentacion oficial vigentes en la fecha
   de ejecucion. Comparar opciones creibles; no completar cuotas con proyectos
   irrelevantes.
4. Verificar licencia, actividad reciente, mantenedores, issues, seguridad,
   dependencias, compatibilidad Windows/Linux y coste operativo.
5. Elegir una de estas salidas:
   - integrar o adaptar la pieza minima que mejora el sistema;
   - usar una dependencia mantenida en lugar de copiar codigo;
   - extraer un patron y reimplementarlo cuando la licencia impida copiar;
   - no cambiar codigo si ninguna opcion supera lo existente.
6. Si hay cambio, incluir pruebas offline, migracion reversible, documentacion,
   procedencia y medicion antes/despues. Dejar la PR lista para merge.
7. Si aparecen fallos, reproducirlos, investigar alternativas actuales y
   corregirlos en la misma PR. No ocultarlos con skips ni mocks vacios.

## Reglas contra el relleno

- Una lista de enlaces no completa el encargo.
- No copiar repositorios enteros ni credenciales, perfiles, cookies o datos.
- No introducir una plataforma pesada para resolver una funcion pequena.
- No afirmar que algo es mejor sin prueba, benchmark o contrato verificable.
- Respetar APIs oficiales, limites y politicas de cada plataforma.
- Registrar repositorio, commit/tag, licencia y archivos o ideas reutilizados.
- Preferir proyectos mantenidos y con una comunidad real; documentar descartes.
- Mantener CI hermetica: ninguna prueba debe tocar cuentas o red publica.

## Repositorio oficial

El mirror es incompleto. Si hacen falta modulos, fixtures, configuracion o
documentacion, tomar del repositorio oficial RRSS solo lo necesario. No rebajar
una prueba ni duplicar una solucion porque el snapshot no incluya el contexto.

## Dos PR adicionales como maximo

Despues de investigar e implementar, el agente puede abrir hasta dos PR nuevas
si ha descubierto trabajos diferentes, concretos y de alto valor. Cada una debe
tener evidencia, alcance acotado y criterio de aceptacion. Si no hay nada que
merezca una PR, no debe abrir ninguna. Nunca crear seguimiento por cumplir.

## Entregables minimos

- `docs/research/<tema>.md` con necesidad, candidatos, licencias y decision.
- Implementacion minima o conclusion razonada de no adopcion.
- Pruebas y resultado reproducible.
- Riesgos de actualizacion y forma de retirar la integracion.
- Enlaces permanentes a commits/tags usados, no solo a la portada del repo.

## PR hijas

Las PR 01-09 cubren plataformas. Las restantes cubren capacidades comunes que
pueden beneficiar a varias redes. Se pueden ejecutar en paralelo, pero una PR
debe reutilizar hallazgos ya publicados por otra y evitar portar dos soluciones
para el mismo problema.
