# Contrato CI: higiene de cada commit de la PR

## Problema reproducible

En la PR #2, `git diff HEAD^1 HEAD` examina el **árbol final** del merge
sintético. Si un commit de la PR añadió `secrets/operational_state.json`
y otro lo eliminó, el diff final no muestra esa ruta. Sin embargo, el objeto
continúa accesible en el historial Git del repositorio público.

La protección por ruta del árbol final sigue siendo útil y debe mantenerse;
el objetivo de esta PR es cubrir **también** commits intermedios, sin bloquear
las rutas que ya estaban en la rama base y no han sido modificadas.

## Encargo de implementación

1. Comprueba el rango real de commits de una PR con merge commits, PR de
   múltiples commits, rama base que avanza y rebase. No supongas que
   `fetch-depth: 2` permite recorrer toda la historia de la rama.
2. Diseña un mecanismo de fetch mínimo/determinista o justifica
   `fetch-depth: 0` y su impacto en Windows/Ubuntu.
3. Inspecciona rutas A/M/T de **todos los commits relevantes** y no solo el
   delta neto final; renombrados hacia ruta prohibida y borrados históricos
   también deben tener tests. Evita que los archivos en la base disparen
   falsos positivos por mera presencia.
4. Pruebas Git locales sintéticas de añadido-eliminado, typechange, rebase,
   merges y nombres con espacios/saltos de línea. Cero secretos reales.
5. Compara la solución existente `tools/repo_hygiene.py` con código mantenido
   de Git / Gitleaks (MIT, `git log -p`), Betterleaks, y detect-secrets
   (Apache-2.0). Reutiliza sin copiar de más. Licencia, dependencias,
   mantenimiento y Python 3.11/Windows deben quedar documentados.
6. No ejecutes verificaciones de credenciales por red ni acciones sociales.
   Diferencia prevención local antes del push de detección en CI: un secreto
   ya publicado en GitHub requiere retirada/rotación, no solo fallo del test.
7. Conexión explícita con PR #87 (escaneo de contenido) y #2 (rutas al
   integrar) sin duplicar implementación.

La PR debe terminar con código, tests, informe de revisión adversarial y
workflow verde Ubuntu/Windows. No hacer merge. Si falta contexto, consultar
`davidpd89/rrss-davidporto-CODE` rama
`integracion/crecimiento-2026-10`.
