# PR #9: presupuesto de duplicación AST entre redes

Investigado el 09/10/2026. Alcance: solo los cuerpos de funciones no triviales
de tools/<red>_*_scan.py, *_build_plan.py, *_execute.py y *_interact.py
(incluye growth_scan y mobile_interact). Nueve redes. No importa ni
ejecuta los módulos: lectura local del árbol AST, sin redes ni cuentas.

## Contrato y ejecución

~~~console
python -m pytest tests/test_architecture_audit.py -q
python tools/architecture_audit.py --tools tools --baseline tests/fixtures/architecture_duplicates.json --module-manifest tests/fixtures/architecture_scanned_modules.json
~~~

La segunda orden devuelve código de salida 0 si el presupuesto se respeta,
1 si aparece una copia no presupuestada y error si el código no se puede
analizar o falta el directorio. El test integra el workflow offline
existente en Ubuntu y Windows, Python 3.11.

- Detecta cuerpos exactos con ast.parse, ast.dump y SHA-256 (prefijo de
  16 caracteres). No depende de espacios, comentarios, líneas o nombre de
  la función externa.
- Omite docstring inicial; mantiene el umbral heredado de tres sentencias
  directas y de tamaño AST para no inventar deuda que no estaba en el
  baseline. Omite agrupaciones que no involucren al menos dos redes.
- Los seis grupos históricos no cambian. Para cada huella, la identidad
  permitida es (red, archivo, nombre de función) y su multiplicidad.
  Una entrada nueva no puede ocupar un hueco liberado por una eliminada.
- Reducir o eliminar copias pasa sin actualizar baseline; desplazar líneas
  o reescribir el docstring tampoco genera regresión.
- La salida JSON muestra únicamente huella, redes, nombre de archivo,
  nombre de función y línea. Ante sintaxis inválida, el error contiene
  archivo y número de línea, sin imprimir la línea de fuente.
- Baseline duplicado, directorio inexistente o sin módulos válidos: error.
  La cobertura de las nueve redes del mirror se comprueba con test propio.

La baseline se modifica únicamente tras revisión consciente de una nueva
deuda, no para hacer verde una CI. Las abstracciones comunes en módulos no
ligados a redes quedan fuera del detector: centralizar no está penalizado.

## Prueba adversarial, segunda revisión

**Ataque anterior:** baseline con 2 copias (X y Threads), borrar la de
Threads y añadir una igual en Reddit. Antes continuaba en 2 y pasaba.
**Ahora:** falla por una aparición nueva en Reddit, aunque el total
sea idéntico. Hay tests para el reemplazo, crecimiento, reducción,
variación de docstring, desplazamiento de líneas, copia únicamente dentro
de la misma red, salida determinista, ausencia de texto sintético privado,
errores de parseo saneados, baseline repetido y ausencia de fuentes.

Una segunda lectura crítica conserva límites explícitos:

1. El umbral inicial no cubre funciones con menos de tres sentencias
   **directas**, aunque su control de flujo sea complejo. Expandirlo
   requiere medir y revisar un nuevo conjunto de hallazgos.
2. La identidad no distingue métodos homónimos en clases distintas
   del mismo archivo si su multiplicidad no cambia. Una función renombrada
   o desplazada de archivo puede provocar un falso positivo revisable.
3. No detecta clones parciales ni renombrado de variables internas.
   El SHA truncado a 64 bits tiene riesgo teórico de colisión.
4. Solo escanea Python directamente dentro de tools, no subpaquetes;
   las nueve redes presentes no prueban identidad con el repo privado.

## Comparación con código público vigente

| Opción | Licencia y mantenimiento verificados el 09/10/2026 | Encaje y decisión |
| --- | --- | --- |
| Python 3.11 stdlib ast/hashlib | Biblioteca estándar PSF, Windows/Linux, sin dependencia añadida | **Elegida**: conserva el contrato AST exacto con una corrección pequeña. No se copia código externo. |
| [jscpd v5.4.1](https://github.com/kucherenko/jscpd/releases/tag/v5.4.1) | MIT; publicado el 09/10/2026, motor Rust, binarios Windows/Linux y paquete Python | **Ofrece baseline real** con `--fail-on-new-clones` y [`--baseline-from-ref`](https://github.com/kucherenko/jscpd/blob/master/docs/rust.md). Excelente alternativa para clones parciales, pero su presupuesto por huella de tokens no protege las identidades AST (red/archivo/función) de este contrato. Se mantiene como opción complementaria, no dependencia obligatoria. |
| [Pylint R0801](https://github.com/pylint-dev/pylint/blob/main/pylint/checkers/symilar.py) | GPL-2.0; activo 09/10/2026 | Similaridad de líneas, no grupos AST; los informes pueden exponer código. No se trasplanta GPL. |
| [pycode_similar](https://github.com/fyrestone/pycode_similar) | MIT; último push observado 05/06/2023 | Normalización AST de similitud/plagio; mantenimiento débil y sin presupuesto por identidades. No se integra. |

Se contrastaron repositorios, licencias y fechas mediante GitHub público.
Referencias inmutables para revisión: jscpd
[release v5.4.1](https://github.com/kucherenko/jscpd/releases/tag/v5.4.1)
(publicada el 09/10/2026; binarios Windows x64 y ARM64 en assets);
Pylint [86808dc](https://github.com/pylint-dev/pylint/commit/86808dc60f5a2e4aeb44bc215af99be0de0d9a3e);
pycode_similar [34ecc94](https://github.com/fyrestone/pycode_similar/commit/34ecc94ebe77a9405fbfdf121e7463bebe8e5645).
El paquete [jscpd en PyPI](https://pypi.org/project/jscpd/) ofrecía
**5.4.0** al consultar el 09/10/2026 (Python >=3.8 y wheels Windows/Linux);
no se presupone que el tag GitHub 5.4.1 ya estuviese distribuido por PyPI.
No se instalaron ni probaron los candidatos externos en Windows.

## Espejo frente al repositorio oficial

Se consultó por el conector GitHub autorizado
davidpd89/rrss-davidporto-CODE, rama integracion/crecimiento-2026-10,
el 09/10/2026. Históricamente el original tenía 40 módulos elegibles y el espejo 39: faltaba `tools/instagram_mobile_interact.py`.
**Revalidación 10/10/2026:** tras sincronizar `research/public-reuse-parent` con el original, ambos inventarios coinciden en **39 ficheros elegibles**. Ahora el espejo también contiene ese módulo. La diferencia histórica queda resuelta en el snapshot; no garantiza que futuras sincronizaciones mantengan paridad.

**Límite de aceptación:** la baseline de seis grupos certifica solo el
mirror. Claude debe ejecutar este detector sobre una copia local del
código oficial actualizado; revisar cualquier grupo extra sin aumentar
automáticamente la baseline y decidir si necesita una importación mínima
sanitizada, con propiedad y redistribución verificadas. No se ha probado
móvil ni Edge real. El protocolo de scouting no existe en esta rama; se
consultó docs/open-source-scouting/PROTOCOL.md de la rama
research/public-reuse-parent, que exige esta distinción.

Rollback: revertir los commits de esta PR; runtime social, estados,
colas WEB/API/MOBILE y baseline histórico permanecen intactos.


## Revisión adicional: identidades léxicas y línea base

Tras reproducir un bypass nuevo, el informe utiliza `Clase.metodo` y
`funcion_externa.funcion_interna` como nombres cualificados. Antes se podía
eliminar `Primera.verificar` y añadir `Segunda.verificar` dentro del mismo
archivo: al compartir el nombre corto `verificar` y el digest del cuerpo, el
presupuesto no detectaba el reemplazo. Los nombres de las seis funciones
históricas son de nivel superior, de modo que esta corrección no modifica los
fingerprints ni exige reescribir el snapshot.

También se comprueba la estructura de la línea base: huellas hexadecimales
de 16 caracteres, dos redes distintas por grupo, procedencia de archivo
coherente con la red, líneas positivas y listado de redes consistente.
Una baseline inválida falla con un error genérico, sin emitir contenido de
funciones. Las pruebas incluyen renombrado léxico, funciones anidadas y siete
alteraciones malformadas.

El detector no se sustituye por `jscpd` porque mide cuerpos AST exactos,
sin dependencia de binarios descargados ni nombres de cuenta, mientras que
`jscpd` resulta más potente para clones parciales y similitud de tokens. La
decisión de continuidad está sustentada por el contrato concreto de la PR;
los hallazgos fuera de ese contrato deben investigarse de forma separada.


## Endurecimiento de la baseline (REV 9, 10/10/2026)

Las ocurrencias del mismo grupo deben tener localizaciones únicas
(`red, archivo, nombre cualificado, línea`). Una fila repetida literalmente
en el JSON no es un nodo AST adicional, pero antes incrementaba el contador
de copias admitidas para esa identidad. Esto permitía gastar una concesión
duplicada cuando aparecía otra definición homónima en una línea diferente.
Ahora se rechaza esa baseline malformada. Se conserva el soporte legítimo
para dos definiciones homónimas situadas en líneas distintas, y la
comparación de regresiones sigue ignorando desplazamientos de línea.
Hay dos pruebas sintéticas específicas; las seis huellas existentes no
cambian.


## Revisión 10/10/2026: integridad del inventario y base sincronizada

La comprobación antigua de nueve redes era insuficiente: al borrar un segundo
módulo de una red, las otras funciones de esa red podían seguir cubriendo
el test, y la desaparición de su duplicación se consideraba una reducción
legítima. Se añade `tests/fixtures/architecture_scanned_modules.json`
con los **39 nombres elegibles**, contrastados con los listados actuales
del mirror sincronizado y del repositorio oficial. No se copia código del
original: únicamente se versionan nombres ya publicados en el mirror.

`--module-manifest` rechaza módulos esperados que desaparezcan, pero acepta
nuevas incorporaciones, que siguen sujetas al presupuesto AST de copias.
La revisión de una retirada intencional actualiza el manifiesto en un commit
explícito. Pruebas: supresión de un módulo sin perder su red, alta aditiva,
manifiesto corrupto, CLI y verificación contra el árbol completo.
El test de inventario se ejecuta en CI en Ubuntu/Windows Python 3.11.

Los controles de duplicación e inventario son genéricos para las nueve redes:
no alteran sus adaptadores, colas ni políticas operativas. El antiguo
comentario sobre desajuste 39/40 documenta un estado anterior al commit de
sincronización `737fc01`; no debe seguir tratándose como brecha actual.
