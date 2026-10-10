# PR #97 — Auditoría de historial de push en ramas de trabajo

**Fecha:** 10/10/2026. **Base:** ci/test-campaign-parent. **Estado:** código y tests, sin merge ni acciones sociales. **Predecesor técnico:** PR #93, commit fijo [636786baf5facce2d6457f6bf5c0dc5aed02fd5c](https://github.com/davidpd89/ci-sandbox-tmp/commit/636786baf5facce2d6457f6bf5c0dc5aed02fd5c). Se importa su núcleo Git y el clasificador de rutas, **no se copian** en esta rama.

## Resultado implementado

- tools/work_branch_push_hygiene.py: valida que el evento sea un push de branch distinto de main, SHA completos y de mismo formato, flags created/deleted/forced booleanos y coherentes, event.after/GITHUB_SHA/HEAD, ref Git válida, historial completo y disponibilidad de objetos. Sin HEAD^1.
- **Actualización FF:** Git nativo y el núcleo #93 inspeccionan cada commit de after ^ before, incluido el segundo padre de merge y reintroducciones por resolución del merge.
- **Reescritura:** compara ancestry por Git, exige que before exista y recorre nuevo rango. Si el SHA anterior no está disponible: código de error 2, nunca verde.
- **Creación:** before=0 no implica que toda la historia sea nueva. Utiliza merge-base(after, origin/main) y escanea solo commits divergentes; apunta a historia ya existente => created-existing. Historial orphan se recorre desde la raíz. Si la ref default o sus objetos faltan, falla.
- **Borrado:** after=0, HEAD/GITHUB_SHA deben ser el commit default de GitHub; exige SHA anterior accesible. No se atribuyen blobs nuevos a una eliminación.
- **Salida:** 0 limpio, 1 rutas sensibles detectadas y 2 verificación incompleta. Nunca muestra rutas ni contenido.
- Workflow de Actions específico en push a **todas las ramas excepto main**, y pruebas offline en pull_request. Dos runners (Windows/Ubuntu) Python 3.11. Usa checkout y setup-python fijados por commit SHA, historial sin shallow, permiso contents:read, persist-credentials:false. No usa concurrency que cancele una verificación antigua. Main sigue cubierto por #93; no duplica la inspección de #88/#89 ni #92.
- Mientras #93 no esté fusionada, el workflow obtiene el checkout de código Git de #93 en .ci97-pr93-core al SHA fijo. No se añade ese código a la PR. Tras integrar #93, **retirar el checkout extra**, revisar importaciones y repetir los tests.

## Pruebas y revisión adversarial

25 tests sintéticos en tests/test_work_branch_push_hygiene.py: add-delete en un push, pushes separados, force-push/objeto anterior perdido, nueva rama desde commit antiguo de main, nueva divergencia y orphan, merge con segundo padre, merge que resucita ruta histórica, deuda no tocada vs modificada, espacios y NUL, borrado de ref, flags incoherentes, SHA inconsistentes, refs ilegales, referencia default inexistente, shallow, errores de ancestry/merge-base, eventos JSON malformados sin fuga de rutas.

**Suite local previa:** 23/23 en Linux Python 3.13, Git 2.47.3, con stand-in *solo local* del clasificador. **Evidencia CI confirmada sobre HEAD de código `956fb5195e30d67ea1b07a3b68162e3902b3f2b6`:** [workflow push 38008577659](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/38008577659), **23/23 en Ubuntu y Windows Python 3.11**, y escaneo del evento real `push` limpio en ambas plataformas; [workflow pull_request 38008582496](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/38008582496), **23/23 en ambos runners** (solo tests simulados para PR). Estas ejecuciones verifican el adaptador con el núcleo #93 real. No demuestran el canario de alta-baja remoto; sigue pendiente. El commit de esta actualización documental crea un HEAD nuevo que debe volver a comprobarse. No confundir la prueba sintética de una función con la prueba real de llegada de webhook push. El resultado de Actions debe añadirse después de leer los runs del HEAD.

Segunda revisión adversarial realizada:
1. Detectado falso positivo cuando before=0 y main ya contenía deuda antigua; solucionado mediante merge-base y pruebas de punta antigua.
2. Detectado riesgo de falso negativo si before de un force-push desaparecía; se exige commit_id o fallo explícito.
3. Detectado que repo_hygiene.ROOT de un checkout externo apuntaba al repositorio equivocado; adaptador define ROOT del propio evento.
4. Detectadas salidas limpias posibles sin comprobar shallow al crear/borrar rama; comprobación previa global.
5. Detectada confusión entre exit 1 (no ancestor/no merge-base) y exit 128 (Git roto); separadas con _git_predicate y regresiones.
6. Eliminado concepto de «último check verde implica que ningún push histórico fue rojo». Los runs se auditan por evento independiente.
7. Revisión del controlador: un `force-push` que rebobina a un ancestro deja el rango `after ^ before` vacío. No debe generar error espurio, pero tampoco dar verde si el nuevo árbol reintroduce una ruta sensible. La rama #97 comprueba el delta A/M/T de `before` a `after` usando el núcleo #93, con dos nuevas regresiones. La CI histórica 23/23 documentada arriba corresponde al HEAD anterior; ejecutar la nueva versión con 25 casos antes de integrarla.

## Reutilización y mantenimiento contrastados el 10/10/2026

| Proyecto | Licencia y referencia vigente | Compatibilidad y decisión |
| --- | --- | --- |
| [Git](https://git-scm.com/docs/git-rev-list), rev-list, diff-tree, merge-base | GPLv2, ejecutable externo; no se incorpora fuente | Windows/Ubuntu con Git nativo; **reusar núcleo #93**, no reescribir DAG |
| [Gitleaks](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1) | MIT, release 8.30.1 del 21/03/2026 | Binarios Windows/Linux; secretos de **contenido**, complementa #87, no sustituye el contrato evento/rutas |
| [Betterleaks](https://github.com/betterleaks/betterleaks/releases/tag/v1.9.0) | MIT, estable 1.9.0 del 29/09/2026; RC 2.0.0 del 30/09 | Windows/Linux por binario Go; no se añade dependencia para escaneo de rutas |
| [Yelp/detect-secrets](https://github.com/Yelp/detect-secrets/releases/tag/v1.5.0) | Apache-2.0, versión 1.5.0 del 06/05/2024 | Compatible con Python 3.11; detecta contenido y mantiene baseline, no los eventos de force-push |
| [actions/checkout](https://github.com/actions/checkout/releases/tag/v7.0.1) | MIT, versión 7.0.1, SHA 3d3c42e5aac5ba805825da76410c181273ba90b1 | Acción existente reutilizada, commit fijo |
| [actions/setup-python](https://github.com/actions/setup-python) | MIT, SHA 5fda3b95a4ea91299a34e894583c3862153e4b97 | Python 3.11 en ambas matrices, reutilizada |

Fuentes de comportamiento: [GitHub Workflows](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflows), [push event](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows) y [git-rev-list](https://git-scm.com/docs/git-rev-list). El protocolo de scouting existe en research/public-reuse-parent, pero **no** en esta rama/base; se consultó su criterio sin alterar otras PR. Del oficial privado integracion/crecimiento-2026-10 se comprobó únicamente README e inventario de workflows: no se copia contenido ni estado privado.

## Límites, coste, canario y rollback

Un workflow ejecutado **después del push** no previene una publicación inicial ni elimina datos de clones/objetos/cachés. GitHub evalúa presencia de workflows en el SHA/ref del evento; la ausencia inicial del workflow, un evento que nunca se disparó o un run omitido **no es recuperable retrospectivamente por este chequeo**. Los registros son temporales. El force-push limpio puede generar un run verde posterior al rojo original: el control de integridad debe revisar histórico de runs y huecos, no solo el check actual.

Si el before de un rewrite fue eliminado y no puede descargarse sin credenciales, se devuelve error 2. En creación desde una rama previa aún no integrada en main, es posible revisar de nuevo su deuda: se privilegia una señal conservadora sobre silenciar rutas.

**Canario supervisado pendiente:** en un repositorio de prueba público y con datos exclusivamente sintéticos, disparar push de dos commits (alta y baja de secrets/transient.json), comprobar run push rojo y sus SHA; force-push después y verificar que el primer run siga visible. Repetir created, deleted y before inaccesible. Esto **no se ha ejecutado**. No se utilizan credenciales de redes sociales.

**Coste:** dos jobs por push no-main, límite 12 min/job, segundo checkout de #93 temporal. **Orden de integración para Claude:** #2 → #93 → #97, coordinar con #88/#89 y #92/#96; no merge automático. **Rollback:** retirar workflow/adaptador #97 sin modificar #93 ni estados reales. Confirmar el caso de workflow ausente en una rama antes de habilitar afirmaciones sobre cobertura completa.
