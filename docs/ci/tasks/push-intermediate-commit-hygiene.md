# CI: detectar rutas sensibles en commits intermedios de push

## Encargo para GPT

**PR de implementación** derivada de la revisión adversarial de [#88](https://github.com/davidpd89/ci-sandbox-tmp/pull/88). Leer contratos de #88 y [#89](https://github.com/davidpd89/ci-sandbox-tmp/pull/89) antes de cambiar código.

**Fallo reproducible:** en un único push a `main` se añaden dos commits: el primero crea `runtime/metricas.csv`, el segundo lo elimina. El resultado final de `git diff before HEAD` no muestra ese fichero, pero su blob sigue accesible por Git. #88 detecta solo diferencias entre snapshots; #89 investiga *commits intermedios de PR*, no pushes.

### Entregable obligatorio

1. Dejar **código ejecutable + tests sintéticos + documentación de integración + informe de segunda revisión adversarial** en esta rama. No limitarse a investigación.
2. Reutilizar el clasificador `repo_hygiene.violations_for_paths`, y preferentemente una única función común de escaneo de historial que #89 pueda compartir; **no copiar** un detector de rutas o reinventar Git. Comprobar estado de #88/#89 en GitHub al iniciar y coordinar integración para evitar colisiones de workflow.
3. Obtener rango real de `push` con `github.event.before` y `after`, nunca `HEAD^1`. En FF recorrer los commits nuevos, incluyendo merges y sus padres relevantes, con `git rev-list` + `git diff-tree -m --root --diff-filter=AMT --no-renames -z` o alternativa demostrablemente equivalente. Examinar añadidos y borrados intermedios sin penalizar rutas históricas que no se tocaron. Mostrar solo rutas y SHA acotados, nunca contenido.
4. Determinar comportamiento de pushes forzados no-FF donde `before` es accesible, `before` ausente, nuevas ramas con cero SHA y merges; hacer explícitos coste, límites del grafo Git y tratamiento de `before` inaccesible. No aprobar en silencio si no es posible verificar.
5. Tests reales con repos temporales: añadido y eliminado dentro del mismo push, varios commits seguros, deuda histórica no tocada, renombre a prohibido, cambio de tipo, merge con segundo padre, fuerza divergente, shallow/missing-before, Linux/Windows/Python 3.11.
6. Comparar código público mantenido a fecha de ejecución: Git nativo, posibles proyectos de escaneo mantenidos como Gitleaks/Betterleaks/detect-secrets; licencias, mantenimiento, dependencias y compatibilidad Windows/Python 3.11. Reutilizar lo compatible con atribución; continuidad gana si aporta menor complejidad con evidencia.
7. Integrar suite de dos sistemas operativos sin credenciales persistidas, sin acceso a cuentas, sin publicar ni modificar datos reales. Diferenciar simulación offline de canario supervisado.

### Separación de alcance

- #88: higiene de **árbol final** de push + semántica de evento.
- #89: higiene del **historial de PR**.
- Esta PR: higiene del **historial intermedio de push** y reutilización de núcleo común cuando #89 avance.
- #87: secretos por **contenido**; #92: aislamiento del validador confiable; #90: actionlint. No duplicarlos.

Base obligatoria `ci/test-campaign-parent`. No hacer merge: Claude coordinará el orden #2 → #88/#89 → esta PR. No añadir secretos, credenciales, operaciones reales de redes sociales ni estado operativo.
