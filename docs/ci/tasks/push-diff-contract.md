# CI: contrato de higiene para push y ejecuciones manuales

## Encargo para GPT

La PR #2 demostró que `HEAD^1` identifica el primer padre del merge sintético
en `pull_request`, pero no el rango completo de cambios de un evento
`push` y no representa una revisión de PR en `workflow_dispatch`.

Diseña y prueba una comprobación de higiene de rutas para `push` a `main`
sin confundirla con la revisión de PR. Reutiliza el comprobador
`tools/repo_hygiene.py` y evita duplicar lógica.

- Considera `github.event.before`, `github.sha`, pushes de varios commits,
  primer push con SHA cero, historial reescrito y base no disponible.
- Aclara qué debe ocurrir en `workflow_dispatch`: selección explícita de un
  rango o solo suite offline sin chequeo de diff.
- Usa repositorios Git temporales sintéticos para pruebas positivas y negativas;
  bloquea un archivo operativo nuevo incluso si llega en el segundo de varios
  commits sin bloquear deuda histórica que no cambió.
- Valida Windows y Ubuntu con Python 3.11.
- Investiga primero alternativas públicas (actions/checkout, actionlint,
  zizmor, scripts mantenidos) y compara licencia, mantenimiento, dependencias y
  compatibilidad; reutiliza código compatible, no escribas otro detector.
- Sin credenciales, secretos, tráfico social, conexiones a cuentas o cambios
  de estado real; no se debe hacer merge automáticamente.

## Integración

La PR #2 mantiene por ahora `repo_hygiene.py --base HEAD^1` exclusivamente
para `pull_request`. Esta PR añade cobertura independiente de `push` sin
duplicar ni alterar el contrato PR ya validado.

Contexto oficial adicional en `davidpd89/rrss-davidporto-CODE` rama
`integracion/crecimiento-2026-10`; consultar si el mirror está incompleto.
