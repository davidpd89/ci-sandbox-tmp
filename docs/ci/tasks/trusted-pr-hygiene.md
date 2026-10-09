# CI: verificador de higiene de PR independiente del código revisado

## Fallo de modelo de confianza

La PR #2 ejecuta `repo_hygiene.py` del checkout del **merge sintético**.
Una PR que cambie el workflow o `tools/repo_hygiene.py` puede alterar el
comportamiento de su propio validador. Un resultado verde no es por sí mismo
una prueba inmutable del contrato si ambos provienen de la rama propuesta.

## Encargo para GPT — implementación y pruebas

- Diseña un pequeño check de rutas **anclado a código de confianza** de
  `ci/test-campaign-parent` (o arquitectura equivalente), independiente de
  la lógica de PR que se está validando.
- No eleves permisos para ejecutar código de un fork; ningún
  `pull_request_target` podrá hacer checkout y ejecutar scripts del head.
  Si usas ese evento, limita el job a checkout del código **base**, token
  `contents: read`, inspección de metadatos/diff de Git, sin pip/pytest del
  head ni descargas no verificadas. Considera alternativas más sencillas
  frente a `pull_request_target`.
- Define un test sintético en el que la PR cambia o elimina
  `repo_hygiene.py` y su YAML, y demuestra que el check **independiente**
  sigue revisando los nombres de archivo.
- Mantén las pruebas funcionales actuales del merge en #2: esto es una
  capa adicional, no sustitución de Ubuntu/Windows.
- Explora soluciones públicas activas `actionlint`, `zizmor`, prácticas
  oficiales de GitHub para eventos de PR, licencias, mantenimiento y
  compatibilidad Windows/Python 3.11; reutiliza herramientas disponibles.
- Evalúa required status checks/branch protection sin presuponer permisos
  administrativos ni imponer reglas de volumen de redes; deja a Claude los
  cambios de repositorio que no se puedan aplicar con el conector.
- Realiza pruebas sin cuentas sociales, tokens reales, datos de producción ni
  acciones WEB/API/MOBILE. Explica por qué un check verde no evita exposición
  pasada de secretos públicos (trabajos #87/#89).

Final: código, pruebas, informe adversarial, runners verdes; sin merge.
Consulta el repo oficial `davidpd89/rrss-davidporto-CODE`
(`integracion/crecimiento-2026-10`) si falta contexto.
