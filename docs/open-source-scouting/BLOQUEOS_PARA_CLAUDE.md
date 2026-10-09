# BLOQUEOS PARA CLAUDE — Campaña pública PR #10

Fecha: **2026-10-09**. Estado: **LISTA PARA REVISIÓN, NO PARA MERGE**;
las validaciones G2 (original) y G3 (promoción) son **pendientes**.

## Identidad observada al iniciar

- Mirror público: `davidpd89/ci-sandbox-tmp`, PR
  https://github.com/davidpd89/ci-sandbox-tmp/pull/10 .
- PR #10: `main` ← `research/public-reuse-parent`; SHA inicial
  `fc87f73694201f7df4c435128566f11b95f7b79b`; base
  `60aa837fcbe2933928ee69aa395806a3bd5a74d1`.
- 46 hijas originales #11–#56 y 30 adicionales #57–#86: abiertas; las 76 bases
  `research/public-reuse-parent` al observarlas, cabezas y SHA en
  `children.json`, observado 2026-10-09.
- Original privado: `davidpd89/rrss-davidporto-CODE`, base `main`;
  acceso GitHub de lectura/escritura disponible, no modificado.
- Diferenciar PR #10 del mirror de cualquier PR del original.
- Reviews iniciales de #10: **cero**.
- Check-runs iniciales del SHA `fc87f7...`: `offline (ubuntu-latest)`
  y `offline (windows-latest)` con conclusión **success** según API.
  La consulta simplificada de workflow runs devolvió cero por filtrar
  eventos de PR, por lo que no es una prueba de ausencia de CI.

## Hechos, riesgos y decisiones

1. Cada una de las 76 hijas inicialmente añade solo su
   `docs/open-source-scouting/tasks/<n>-*.md`. No existen solapamientos
   exactos de archivos **en esos 76 diffs iniciales**. Los riesgos de
   cambios compartidos están en `COORDINATION.md`; hay que volver a
   analizar diffs al revisar cada implementación.
2. El README del mirror dice que los snapshots pueden sobrescribirse
   por sincronización. **Prohibir force-push de sincronización sin
   respaldo y comparación del HEAD actual.** Este protocolo no cambia
   la herramienta de sincronización del original.
3. El mirror público contiene rutas `00_OPERATIVO/cache/`, registros
   de error y archivos `tests/__pycache__` preexistentes en el árbol.
   No se ha afirmado que esas rutas contengan secretos ni se ha
   inspeccionado su contenido sensible. **Pendiente: auditoría humana
   por titular del mirror** y posterior saneamiento en PR separada,
   evitando abrir/publicar datos durante el análisis.
4. La documentación `AI_REVIEWER_BRIEF.md` del original es histórica;
   contrastar decisiones con el código vivo y
   `00_OPERATIVO/01_CONTEXTO_UNICO.md`.
5. El script inspecciona texto nuevo y rutas sensibles en la campaña,
   pero **no garantiza ausencia de PII** en fotos, PDF, multimedia,
   bases cifradas o alias no reconocidos; revisión humana obligatoria.
6. GitHub API `GET /pulls` comprueba presencia, bases y HEAD,
   **no permisos reales de APIs sociales** ni autorización de trasladar
   un componente al original.
7. El nombre `mergeable` en respuesta de GitHub **no sustituye**
   revisiones, resolución de conversaciones, checks actualizados,
   reglas de rama ni aprobación humana.

## Ejecución y reproducibilidad

En contenedor local se intentó:

```sh
git ls-remote https://github.com/davidpd89/ci-sandbox-tmp.git refs/heads/research/public-reuse-parent
# fatal: unable to access ... Could not resolve host: github.com
```

No se pudo clonar directamente por DNS en el terminal. Se usó el
conector GitHub autorizado para **leer PR y escribir ficheros en la
rama correcta**. Test específico ejecutado localmente como archivos
sintéticos con Python `unittest`, 15/15 en la primera ola de tests; el
último código incorpora 22 tests cuyo resultado debe confirmarse en CI,
tras arreglar un falso negativo
de `token=...`. **La ejecución remota final y el archivo real del
manifest se deben comprobar por GitHub checks; los resultados locales
no sustituyen los remotos.**

Comandos reproducibles en clon local con acceso Git:

```sh
python -m unittest discover -s tests -p test_open_source_campaign.py -v
python tools/validate_open_source_campaign.py
python tools/validate_open_source_campaign.py --live
python -m compileall -q tools/validate_open_source_campaign.py tests/test_open_source_campaign.py
```

En las hijas (con ref base de Git disponible):

```sh
GITHUB_BASE_REF=research/public-reuse-parent python tools/validate_open_source_campaign.py --changed-base <SHA_BASE> --child-head <SHA_HEAD_HIJA>
```

Si el SHA de base ya ha cambiado, NO inventar uno: consultar
`GET /pulls/{n}` y obtener base actual, no reutilizar el inicial.

## Pasos concretos de Claude

1. Comprobar HEAD actual de #10 y #11–#56, comentarios/reviews/threads,
   `GET /commits/<SHA>/check-runs` y los nuevos jobs
   `campaign gate (ubuntu-latest)` y `campaign gate (windows-latest)`.
2. Ejecutar los cuatro comandos anteriores en clon limpio del
   **mirror**, con red sólo para `--live`. Inspeccionar todos los
   cambios y salidas tras el último commit.
3. Revisar `tools/validate_open_source_campaign.py` como adversario:
   regex PII incompletas, seguridad de rutas, API paginada y
   detección de fichas sin pruebas.
4. Auditar en un entorno autorizado los ficheros preexistentes de
   `cache/` y `__pycache__`; preparar saneamiento separado
   **sin copiar sus contenidos a tickets o logs públicos**.
5. Para cada hija, comparar su diff vivo con ramas relacionadas y
   aplicar puertas G1/G2/G3. Escribir informe de licencia/commit y
   resultado de suite original de forma que no revele contenido
   privado; mantener `PROMOTION_TEMPLATE.json` en estado bloqueado
   hasta autorización.
6. Si cualquier PR hija reclama merge pero sólo contiene ficha de
   tarea, bloquear G1 hasta que exista prueba/evaluación. No usar
   el verde de la PR padre como prueba de hijas.
7. No fusionar padre, hijas ni main automáticamente. No publicar
   contenido ni interactuar con cuentas.

## Revisión de aislamiento de diff

La rama base puede avanzar mientras una hija trabaja. La CI recibe
\`github.event.pull_request.head.sha\` y compara ese head contra el ancestro
común con la base, no contra el merge artificial del checkout. Comprobar
el test \`test_child_diff_uses_merge_base_not_merge_commit\`: el padre
NO puede satisfacer por sí solo las pruebas y el informe requeridos
para una hija. Revalidar siempre los checks tras cambiar el base/head.

## Incidencias abiertas

| ID | Puerta | Severidad | Bloqueo / condición de desbloqueo |
|---|---|---|---|
| GOV-01 | G1 | Media | Clon Git por DNS no disponible en entorno local; ejecutar en CI y releer checks finales |
| GOV-02 | G1/G3 | Alta | Inspección de higiene preexistente en mirror público requiere persona autorizada |
| GOV-03 | G2 | Alta | No se ejecutó suite global sobre el repositorio original; validar compatible por hija |
| GOV-04 | G3 | Alta | No hay revisión humana ni manifiesto real de promoción aprobado |
| GOV-05 | G1 | Media | Revalidar SHA/reviews/checks tras cambios futuros por sincronización de mirror |
| GOV-06 | G1 | Media | Las hijas sólo llevan fichas iniciales: falta implementación/evaluación verificable |
| GOV-07 | G1 | Media | Expansión simultánea de #57–#86: se añadió al índice/manifiesto; revalidar cambios de base, nuevos checks y conflictos de código |

Cada nueva incidencia: `ID, fecha, mirror PR, SHA head, puerta,
archivos afectados, reproducción/resultado (sin datos sensibles),
propietario y criterio exacto de cierre`. No se asignan falsos OK.
