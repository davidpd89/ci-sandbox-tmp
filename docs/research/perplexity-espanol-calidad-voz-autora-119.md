# PR #119 — adaptador optativo a LanguageTool local (10/10/2026)

## Problema y ausencia de duplicados

Se inspeccionaron el informe Perplexity de esta rama, la PR pública [#79](https://github.com/davidpd89/ci-sandbox-tmp/pull/79) y la rama oficial privada `integracion/crecimiento-2026-10` (entre otros, `tools/reply_writer.py`, blob `5d76b1da2e4666aa2c2fc96877eaff8695e6f78e`). La #79 ya aporta auditoría es-ES con nueve redes, offsets, máscara de citas y revisión A/B; NO copiarla ni añadir otro preflight. El escritor oficial ya valida longitud, repetición y prueba de procedencia antes de publicar. Los controles vigentes y las rutas de salida permanecen intactos.

**Incremento de #119:** `tools/languagetool_local.py`, cliente mínimo de `POST /v2/check` solo para **servidor instalado expresamente en loopback**, reutilizando el motor público LGPL-2.1 mediante su protocolo, sin vendorización ni cliente GPL adicional. Devuelve reglas y sugerencias para revisión editorial; NO aplica cambios, veta respuestas, arranca procesos, lee corpus personal ni accede a redes sociales. Por defecto `endpoint=None`: no hay petición HTTP. La API común acepta las nueve redes y un transporte inyectable en pruebas. La cobertura de contrato no significa que cada publicador esté conectado: la herramienta es de revisión offline.

## Alternativas — referencias primarias y decisiones

| Recurso verificado | Licencia del repositorio | Actividad observada y Python 3.11 / Windows | Resolución |
| --- | --- | --- | --- |
| [LanguageTool](https://github.com/languagetool-org/languagetool/commit/170f9698d9b15bc0cde1094156bc60d0007ca7e0) | LGPL-2.1 (núcleo; recursos pueden diferir) | Commit **170f9698** de 09/10/2026; activo; Java 17 al compilar, servidor JVM local en Windows; cliente aquí solo stdlib Python 3.11 | **Reutilizar API HTTP local**, sin copiar código ni instalar motor en runtime |
| [PUCP-Metrix](https://github.com/iapucp/pucp-metrix) | **MIT** en su archivo LICENSE (corrección del informe de Perplexity que indicaba CC BY-NC-SA 4.0; comprobar separadamente datasets/modelos) | último push 20/08/2026; `requires-python >=3.12` en pyproject | **Descartar integración Python 3.11** sin fork/migración; no justificar dependencia pesada |
| [pystylometry](https://github.com/craigtrim/pystylometry) | MIT | último push observado 09/04/2026; Python >=3.9 en PyPI; mantenimiento pequeño; métodos de autoría requieren corpus válido | No implantar scoring de voz con microcomentarios sin evaluación humana |
| [sentence-transformers](https://github.com/huggingface/sentence-transformers) | Apache-2.0 | push 08/10/2026; Python >=3.10; PyTorch/modelos pesados | No cargar pesos para comprobar tildes ni afirmar que embeddings miden voz |
| [Binoculars](https://github.com/ahans30/Binoculars) | BSD-3-Clause | código sin push desde 14/05/2024; modelos pesados, español no calibrado | No usarlo para marcar respuestas como «IA» |
| [TinyStyler](https://github.com/zacharyhorvitz/TinyStyler) | Verificar todos los artefactos y pesos antes de usar | sin push desde 18/11/2024; no validado para estos microtextos en español | No introducir autogeneración o reescritura de producción |
| [GLTR español](https://github.com/luciayn/AI-generated-Text-Detection-with-GLTR-based-approach) | MIT | sin push desde 30/11/2024; enfoque experimental | No aporta puntuación fiable sin corpus español |

Las fechas de push y las licencias se comprobaron mediante metadatos de GitHub a 10/10/2026; las licencias de modelos/datasets, versiones Java instaladas y experiencia real en Windows **no** se validaron. Cualquier dependencia externa permanece sin instalar por esta PR. Referencia de despliegue LT: [servidor HTTP de LanguageTool](https://github.com/languagetool-org/languagetool-org.github.io/blob/master/http-server.md).

## Licencias y procedencia

Fuente primaria: https://github.com/languagetool-org/languagetool
Fecha de consulta: 2026-10-10
Licencia SPDX: LGPL-2.1
Referencia inmutable: https://github.com/languagetool-org/languagetool/commit/170f9698d9b15bc0cde1094156bc60d0007ca7e0

No se vendorizan fuentes de terceros. Se reutiliza el motor LanguageTool exclusivamente a través del contrato HTTP público. La atribución y la licencia del motor corresponden a su repositorio y versión, no al adaptador Python original de esta PR.

## Decisión

Adoptar cliente optativo de gramática local para la revisión editorial de nueve redes; evitar integración automática en publicación y duplicados de la #79. No añadir JVM, pesos o dependencias a las rondas.

## Contrato y ejecución

La salida `audit(text, network, endpoint=None)` contiene `schema_version, network, changed=false, status, findings`. Cada finding incluye índices Python `start/end`, `rule_id`, `category` y un máximo de tres sugerencias. Los offsets UTF-16 de Java se traducen a índices de código Unicode en Python: un emoji antes de una tilde no desplaza el fragmento incorrectamente. Los offsets que dividen un par UTF-16 se descartan. URLs, citas, hashtags, menciones y Markdown se protegen contra recomendaciones espurias. Límite respuesta 1 MiB y 500 findings, timeout 1,5 s, no redirects, no proxies y dirección literal 127.0.0.1 o ::1.

Comprobación determinista sin LanguageTool instalado (NO publica):

```powershell
python -m unittest discover -s tests -p test_languagetool_local.py -v
python tools/languagetool_local.py --network x --text "Cuantos libros?"
```

Uso opcional **solo cuando Claude haya instalado un servidor LanguageTool local**:

```powershell
python tools/languagetool_local.py --network x --endpoint http://127.0.0.1:8081/v2/check --text "Me gusto el libro."
```

No pasa por la cola real de `reply_queue` ni cambia el publicador. Para habilitarlo dentro de una interfaz de revisión humana futura hay que portarlo como módulo independiente y adjuntarlo a la auditoría #79 sin modificar los criterios de publicación ni duplicar validaciones.

## Pruebas — resultado y revisión adversarial

Pruebas sintéticas locales en Python **3.13.5**: **8 passed**, 0 fallos tras corregir una desviación revelada por las pruebas (el rango 127/8 incluía 127.0.0.2; se restringió a direcciones literales exactas). Cobertura por red **9/9 en contrato** y tests para Unicode/emoji, máscara de contenido ajeno, respuesta malformada, límite de tamaño, conexión caída, entrada inválida y no invocación por defecto. `compileall` OK. **NO** se ejecutó el motor JVM, Windows/Edge/móvil ni la suite completa Python 3.11 del privado. No se ha demostrado mejora real de naturalidad, ortografía del motor, seguidores ni resultados sociales.

Segunda pasada: proxy por defecto podía desviar HTTP; desactivado con `ProxyHandler({})`, y también se bloquean redirecciones. No se devuelven errores HTTP con el texto propio en la salida. Tercera pasada: la #79 ya ofrece ortografía y es-ES; se mantiene este cliente **estrictamente opcional**, sin integrarlo de forma redundante en la ruta caliente. Desinstalación: eliminar los tres archivos añadidos; ninguna migración.

## Retirada

Eliminar el cliente, su test, el workflow aislado y este documento. Sin migraciones, cambios de esquema ni efectos en producción.

## Pendiente de Claude

Rebasar manualmente sobre la rama privada actual, no copiar `reply_writer.py` desde el espejo; comprobar servidor LanguageTool real en Windows + Java, compatibilidad Python 3.11, contraste de falsos positivos con textos propios autorizados y suite completa del repositorio privado. No aprobar cambios editoriales automáticamente. Sin merge ni acciones reales en redes, sin secretos ni datos personales en la PR.
