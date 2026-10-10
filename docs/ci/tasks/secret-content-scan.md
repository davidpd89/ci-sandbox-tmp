# CI: escaneo de secretos por contenido

## Objetivo

Cerrar la limitación demostrada en la PR #2: `tools/repo_hygiene.py` bloquea
rutas y nombres sensibles, pero no detecta un secreto pegado dentro de un
archivo permitido.

## Contrato de implementación

- Ejecutar sobre cambios de PR del mirror, sin reabrir deuda histórica ajena al diff.
- Funcionar en GitHub-hosted Ubuntu y Windows con Python 3.11.
- No usar credenciales reales ni fixtures que parezcan secretos válidos.
- No verificar credenciales contra servicios externos ni realizar acciones de red social.
- Mantener permisos de GitHub Actions de solo lectura y acciones/dependencias fijadas.
- Añadir pruebas sintéticas de positivo, negativo, baseline/histórico y rutas renombradas.
- Documentar falsos positivos, licencia, mantenimiento y rollback.

## Reutilización obligatoria

Comparar a fecha de ejecución al menos:

- Gitleaks CLI (MIT; no asumir que Gitleaks-Action comparte licencia).
- Yelp detect-secrets (Apache-2.0).
- TruffleHog (AGPL-3.0; desactivar cualquier verificación remota si se evaluara).
- Continuidad del comprobador local, si sigue siendo la opción más segura y simple.

No se debe escribir un scanner casero si una opción pública compatible gana la
comparación. Si se integra software externo, respetar atribución/licencia y
evitar descargas no fijadas o `latest`.

## Contexto

La evidencia de partida está en
`docs/reviews/PR_2_MIRROR_PR_CONTRACT.md` de la PR #2. Si el mirror carece de
contexto, consultar `davidpd89/rrss-davidporto-CODE`, rama
`integracion/crecimiento-2026-10`, y traer solo lo mínimo necesario.
