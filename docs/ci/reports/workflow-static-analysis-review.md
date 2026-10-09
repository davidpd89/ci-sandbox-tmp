# PR #90 — Análisis estático de workflows: implementación y revisión adversarial

Fecha: 2026-10-09. Rama: `ci/workflow-static-analysis`. Base: `ci/test-campaign-parent`.
Encargo: [#90](https://github.com/davidpd89/ci-sandbox-tmp/pull/90). Sin merge.

## Alcance auditado

- Mirror `davidpd89/ci-sandbox-tmp`, HEAD inicial `0cc80f7d5b059a89e8d19ef2176958220463862f`: un workflow activo, `.github/workflows/validate-social-tools.yml`. Las pruebas de contrato de la #2 no están aún en esta base; no se han copiado ni modificado sus exclusiones ni sus cambios de permisos.
- Oficial privado `davidpd89/rrss-davidporto-CODE`, rama `integracion/crecimiento-2026-10`, HEAD consultado `5449513d9b545d0a6a72abf066ab6a779bfdad71`: `validate-social-tools.yml` y `validate-production-kits.yml`. La primera aplica selectores de runners según destino y pruebas de higiene en PR. La segunda usa `checkout@v4` y `setup-python@v5` (referencias no inmovilizadas), asunto **no cubierto por actionlint**. No se ha trasladado código/dato privado al mirror.
- `docs/open-source-scouting/PROTOCOL.md`: no existía en la base ni en el HEAD de #90 consultados; se siguió íntegramente el encargo específico y se documentan fuentes.
- Otras PR abiertas comprobadas: #31 (cadena de suministro), #2 (contrato CI), #87–#89 y #92 (higiene y confianza). Esta implementación **no las duplica**.

## Comparación de implementaciones públicas (09/10/2026)

| Opción | Evidencia | Idoneidad |
| --- | --- | --- |
| [rhysd/actionlint](https://github.com/rhysd/actionlint), [MIT](https://github.com/rhysd/actionlint/blob/v1.7.12/LICENSE.txt) | v1.7.12 (30/03/2026), artefactos Linux y Windows x86_64, descargas SHA256 en [release oficial](https://github.com/rhysd/actionlint/releases/tag/v1.7.12). Valida sintaxis, expresiones, eventos, jobs, claves y matrices. | **Elegido** como control obligatorio y de bajo ruido. Binario Go ya compilado; Python 3.11 solo orquesta. |
| [zizmorcore/zizmor](https://github.com/zizmorcore/zizmor), [MIT](https://github.com/zizmorcore/zizmor/blob/main/LICENSE) | v1.30.1 (09/09/2026), `--offline`, binarios Windows y Linux. Inspecciona seguridad de workflows: referencias, inyección, permisos. | Complemento, no sustituto del parser de actionlint. Integrarlo como gate indiscriminado duplicaría el alcance transversal de #31 y exigiría gestionar hallazgos previos. |
| Continuar solo con tests de cadenas YAML | Barato, sin dependencias. | Insuficiente: no comprueba la gramática completa de GitHub Actions, eventos ni expresiones. |
| Descargar un instalador de `latest`, Docker `latest` o añadir parser YAML casero | Sin mejora sobre el binario verificado. | Rechazado por versionado mutable, paridad Windows deficiente o mantenimiento duplicado. |

## Diseño implementado

- `.github/workflows/workflow-static-analysis.yml`: workflow independiente que se ejecuta en **cada PR, push a main/ci/test-campaign-parent y lanzamiento manual** (evita duplicar push y PR en ramas de trabajo) con matriz `ubuntu-latest`/`windows-latest`, permisos `contents: read`, `persist-credentials: false` y acciones de checkout/setup-python por SHA completo. No introduce acciones sociales ni accede a estados operativos.
- `tools/ci_actionlint.py`: descarga exclusivamente el activo `v1.7.12` para x86_64 Linux o Windows desde el proyecto upstream. Verifica SHA256 del **archivo de release completo antes de extraer**, valida tipo/tamaño del miembro extraído, no descomprime rutas arbitrarias, comprueba la versión ejecutable y analiza **todos** los `*.yml` y `*.yaml` de `.github/workflows/`. Si no hay archivos o falla descarga/integridad/lint, retorna no cero.
- SHA256 archivo Linux: `8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8`.
- SHA256 archivo Windows: `6e7241b51e6817ea6a047693d8e6fed13b31819c9a0dd6c5a726e1592d22f6e9`.
- Sin paquetes Python adicionales. `-shellcheck= -pyflakes=` apaga reglas externas de shell y Python, **no** el análisis de expresiones, esquema o YAML, y evita diferenciales del runner.
- `tests/test_ci_actionlint.py`: tests de instalador y extracción sintética sin red, rutas/symlinks manipulados, hash erróneo, arquitectura no compatible, fail-closed, argumentos como lista sin `shell=True`, ausencia de escrituras sobre un fichero operativo sintético y fixtures sin secretos.
- `--selftest`: con el binario real, valida **válido**, **evento inválido**, **expresión inválida**, **clave desconocida**, **YAML roto** y **acción no inmovilizada**. El último caso debe ser aceptado por actionlint, para dejar verificable su límite, no para reclamar un detector inexistente.

## Ejecución, reversión y mantenimiento

- Comando local o CI: `python -m unittest discover -s tests -p test_ci_actionlint.py -v`; luego `python tools/ci_actionlint.py --selftest`. También admite `--archive /ruta/release.zip` para uso offline del artefacto oficial íntegro (mismo SHA256 requerido), sin credenciales.
- GitHub Actions ejecutó ambos jobs de validación real Ubuntu y Windows con resultado **success** en [run 37988510511](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/37988510511), commit `306b1f378968b4eafcfc133853f1ea87e776e527`. Ejecutó además tests de aislamiento actualizados, con pasos de lint correctos, en [run 37988572828](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/37988572828), commit `7ff2b47db1352f4411b9cb42105323a10164bdee`. Verificar otra vez el HEAD final en CI.
- Coste nominal de descarga: ~2,35 MB Linux y ~2,48 MB Windows por ejecución, sin cache ni dependencias complejas. Tiempo máximo configurado: 5 min por job; la duración real depende del runner.
- Actualizaciones: cambiar versión **y ambos SHA256** después de verificar el release en su origen, ejecutar suite y canario GitHub; no usar `latest`. Compatibilidad explícita en runners x86_64; otras arquitecturas dan fallo claro.
- Rollback: revertir commits que introducen `workflow-static-analysis.yml`, `ci_actionlint.py` y tests. No hay migraciones ni escrituras de estado de colas; el resto de CI conserva su contrato.

## Segunda revisión adversarial

1. **¿Cobertura al editar otro workflow?** Se pasan todos los workflows al ejecutable, no solo el fichero modificado. Disparadores independientes de `paths:` y de la suite grande. Sí.
2. **¿Se ejecuta si el propio workflow linter queda sintácticamente roto?** No necesariamente: el motor de GitHub puede no programar un workflow malformado. Es un límite de confianza/validación del propio checker; #92 aborda ejecución de verificadores confiables fuera del código de PR. No se oculta.
3. **¿Una acción `uses: owner/action@v4` provoca error?** No. actionlint no valida inmovilización por SHA. Test sintético explícito de esta no-cobertura. Los workflows propios nuevos usan SHA; una regla de pin obligatoria corresponde a la capa de seguridad de #31, idealmente con zizmor y una baseline revisada. No improvisar parser ni regular expresiones YAML.
4. **¿Depende de Internet o ejecuta shell de PR?** La primera descarga requiere disponibilidad de GitHub Releases (fallo cerrado). Después se analiza contenido local; no se invocan comandos de `run:`, shells, clientes de redes ni rutas de estado. La descarga verificada ejecuta el binario auditado externo, que no deja de ser una dependencia de terceros.
5. **¿Windows y Ubuntu reales?** Ambos comprobados en runners de GitHub Actions con binario real. El PC Windows privado, Edge y móvil no se requieren para este lint; no se han probado ni se infieren.
6. **¿Licencia o procedencia?** Se reutiliza el ejecutable upstream MIT sin copiar fuentes. Se conserva atribución a rhysd y enlaces de licencia en este informe. Para redistribuir el binario fuera del cache efímero debe acompañarse del aviso MIT.
7. **¿Inyección de salida o secretos?** La invocación Python usa `subprocess.run([...])` sin shell y tests negativos con nombre hostil. Fixtures sintéticos sin credenciales. Los errores de lint pueden citar líneas del YAML analizado: mantener prohibición independiente de secretos reales en repositorio (#87); este linter **no** los escanea.
8. **¿Duplicación del repo privado?** Solo se hizo lectura para comparar dos workflows. No se alteró el proyecto privado, no se importaron ficheros privados ni se abrió PR allí. La suite y las colas WEB/API/MOBILE siguen independientes.

**Resultado:** implementación separable, sin migraciones de estados y con CI real en ambas plataformas; su requisito de gate confiable y la detección de acciones sin SHA quedan expresamente fuera del alcance de actionlint. Antes del merge Claude debe revisar resultados CI del último HEAD y orden de integración respecto a #2/#92. No se proponen PR nuevas: #31 y #92 ya reciben los hallazgos que merecen trabajo propio.
