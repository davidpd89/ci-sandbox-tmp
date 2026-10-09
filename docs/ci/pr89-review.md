# PR #89 — Auditoría de higiene del historial de PR (09/10/2026)

## Contrato implementado

- Nuevo `tools/pr_commit_hygiene.py` reutiliza **sin copiar** la política `repo_hygiene.forbidden_path` del espejo y del repositorio oficial (`integracion/crecimiento-2026-10`; comparación directa: idéntico SHA del blob `9987782b1a94a4fd152f0f0cb5e2b42a044d9ae4` en ambas ramas al consultar).
- Git identifica los padres del merge sintético (`HEAD^1` base actual, `HEAD^2` punta real de PR). `git rev-list --parents --topo-order --reverse base..head` elige *todos* los commits alcanzables desde la PR y no desde la base actual. No usa el delta neto de la PR, no presupone historia lineal ni `fetch-depth: 2`.
- Compara cada commit frente a sus padres mediante Git (`diff --no-renames --no-ext-diff --name-only -z --diff-filter=AMT`). Los merges consideran la **intersección** de cambios frente a todos los padres para detectar resoluciones nuevas sin clasificar como aportaciones los ficheros heredados de la base. Los commits propios de cada padre ya se auditan por separado.
- El renombrado hacia destino prohibido aparece como alta mediante `--no-renames`; la baja pura de rutas preexistentes no produce alerta. Un alta seguida de borrado no desaparece del resultado. Nombres con espacios y saltos de línea se tratan con delimitador NUL.
- El verificador **no lee blobs** ni imprime rutas ni contenidos; en fallo publica únicamente SHA abreviado y cantidad. Salidas 0 aprobado, 1 infracción, 2 fallo operativo / historia incompleta.
- Workflow: `pull_request` habilitado y job independiente `pr-history` en Ubuntu y Windows, Python 3.11, checkout de historia completa con `fetch-depth: 0`, `sparse-checkout: tools`, `persist-credentials: false`, permisos `contents: read`. El job de regresiones existente conserva su checkout superficial para ahorrar tiempo.

## Coste de Git y alternativas públicas comprobadas

| Alternativa | Licencia, mantenimiento y compatibilidad | Veredicto |
| --- | --- | --- |
| [Git rev-list / diff](https://git-scm.com/docs/git-rev-list), [diff-tree](https://git-scm.com/docs/git-diff-tree) | Git GPL-2.0 (ejecutable del runner; no se redistribuye ni adapta código Git). Mantenido; instalado en Windows y Ubuntu. Sin bibliotecas adicionales de Python. | **Elegido**. Resuelve el problema de topología y nombres exactamente; reutilización por CLI, no parser propio. |
| [Gitleaks](https://github.com/gitleaks/gitleaks) | MIT, línea v8.30.1 publicada marzo 2026 y actividad posterior; Go/binaries para Windows/Linux. Escanea *contenido* del parche/historial con reglas. | Complemento a cargo de #87; no sustituye la política de rutas. Sin dependencia Go nueva aquí. |
| [Betterleaks](https://github.com/betterleaks/betterleaks) | MIT; versión estable v1.9.0 de 29/09/2026 y v2 RC 30/09/2026; binarios Go Windows/Linux. Motor para contenido, filtros y validación de credenciales opcional. | Interesante para #87, pero mayor superficie y alcance distinto; no se activa validación de credenciales por red. |
| [Yelp/detect-secrets](https://github.com/Yelp/detect-secrets) | Apache-2.0; v1.5.0 anuncia Python 3.11 y mecanismos de baseline; soporte Windows documentado. Releases menos recientes que Betterleaks. | Útil para secretos por contenido, no para reglas de rutas transitorias del DAG. No se instala. |
| Continuidad `repo_hygiene.py` | Código del propio proyecto; ya contiene la política de nombres adaptada a las nueve redes. | **Reutilización ganadora**. No se duplican listas ni decisiones por red. |

Fuentes: [checkout y fetch-depth](https://github.com/actions/checkout), [documentación Git de rangos](https://git-scm.com/docs/rev-list-options), [Betterleaks releases](https://github.com/betterleaks/betterleaks/releases), [Gitleaks releases](https://github.com/gitleaks/gitleaks/releases), [detect-secrets releases](https://github.com/Yelp/detect-secrets/releases). Consultadas el 09/10/2026. No hay código externo copiado: únicamente invocaciones de la CLI Git.

`fetch-depth: 0` tiene un coste mayor que `2`; se limita al job específico, con checkout disperso solo para `tools`. Garantiza commits antiguos y ramas con merges/rebases sin heurísticas de profundidad. La base pública del espejo ronda 10 MB según metadatos GitHub del 09/10/2026; si crece, evaluar un fetch blobless con DAG completo y pruebas equivalentes **antes** de optimizar.

## Pruebas y evidencia

- `python -m unittest discover -s tests -p test_pr_commit_hygiene.py -v`: **11 casos sintéticos** en Git local Linux: añadido+borrado con diff final vacío; ruta heredada y modificación; borrado benigno; renombrado; typechange de Git sin privilegios NTFS; espacios/salto de línea; merge de base; resolución de merge; rebase; merge sintético; y refs erróneas.
- También se comprobó que `tools/repo_hygiene.py` del espejo coincide con la versión de la rama privada citada. No se exportaron credenciales ni archivos operativos.
- GitHub Actions ejecuta `pr-history` en Ubuntu/Windows y la suite offline de CI por separado; [ejecución asociada](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/37988118432). Consultar conclusiones finales de los cuatro jobs (ningún resultado debe interpretarse como probado antes de su cierre).
- No se hizo canario sobre GitHub con secretos ni sobre redes sociales; todo test que escribe objetos Git usa directorios temporales con datos ficticios. Windows/PowerShell real queda cubierto por CI, no por equipo local; Edge y móvil no corresponden a esta función.

## Doble revisión adversarial

**Primera pasada:** el diff final de #2 permite altas borradas; comparar únicamente con primer padre del merge provoca falsos positivos por rutas heredadas del nuevo base. Corrección: recorrido del DAG y contraste con todos los padres para merges. Confirmado por tests sintéticos.

**Segunda pasada:** nombres con salto de línea rompen salida delimitada por líneas; tests sobre symlinks del filesystem se saltan en Windows; mostrar la ruta en logs puede filtrar datos; profundidades pequeñas fallan en PR largas; borrados puros no deben bloquear limpiezas. Correcciones: NUL, typechange a través del índice Git, solo SHA+contador en logs, profundidad completa y filtro AMT. Si Git no proporciona un historial válido, salir con fallo operativo.

**Límites conocidos:** la política detecta rutas, no tokens incrustados en ficheros permitidos ni cambios que solo quedaron en commits inaccesibles de la rama actual tras force-push. CI llega **después del push**: si llegó un secreto real al remoto debe retirarse del historial accesible y rotarse; un check rojo no revierte publicación. Dado que el workflow y script viven en la PR, su inmutabilidad frente a cambios maliciosos es alcance de **#92**, no una garantía que reivindique #89.

## Interdependencias y traspaso a Claude

- #2 mantiene control del árbol final; #89 añade la dimensión temporal, no lo reemplaza.
- #87 escanea contenido y debería usar las revisiones correctas sin copiar el parser de caminos.
- #88 controla rango de push; #93, **ya abierta**, incorpora commits intermedios de push. Reutilizar de #89 `changes` y política de rutas al coordinar integración, sin copiar listas.
- #92 revisa confianza del verificador. #90 aporta análisis estático del workflow.
- Los cambios de workflows realizados en distintas ramas hijas requieren resolución explícita de conflictos en la integración; no sustituir job de #2 por el de #89.
- No se ha abierto nueva PR: las separaciones identificadas ya tienen propietario. **No hacer merge hasta confirmación del workflow verde y revisión de Claude.**
