# Gobierno e integración de 46 PR de reutilización pública

Consulta de fuentes: **2026-10-09**. Ámbito: mirror público
`davidpd89/ci-sandbox-tmp`, PR #10, `research/public-reuse-parent`.
El original `davidpd89/rrss-davidporto-CODE` es **privado**. Esta
investigación no licencia su código ni habilita su redistribución.

## Problema

Antes: el índice de `PROTOCOL.md` listaba 46 URLs sin verificador,
matriz de colisiones ni exigencia de separación de las tres puertas. La
redacción original daba pie a copiar fixtures privados a un mirror público.
El README del mirror informa además de sincronizaciones con sobrescritura
de ramas; hay que tratar los SHA como volátiles y bloquear revalidaciones
basadas en commits viejos.

Reproducción sin acciones reales: eliminar la línea #11 del índice, cambiar
el URL de #12, duplicar #13 en el manifiesto o colocar un campo de credencial con valor sintético en un fixture de prueba.
El test offline debe fallar en cada caso. Un enlace sintácticamente válido
pero con 404 se detecta con `--live` (API real o inyección de respuesta
sin esa PR), no únicamente con expresiones regulares.

## Alternativas

| Aspecto | Baseline | A: herramienta CLI externa | B: SDK de GitHub | C: stdlib + REST (elegida) |
|---|---|---|---|---|
| Índice/ramas | Inspección manual | `gh pr list` + scripts | PyGithub y API | JSON estático + urllib opcional |
| Instalación CI | Ninguna | Requiere CLI y autenticación | Dependencia Python | Python 3.11, sin dependencias |
| Offline | No automatizado | Parcial | Parcial | Determinista |
| Riesgo | Omisiones humanas | Versiones CLI, permisos | Supply chain adicional | Regex limitadas, API, snapshot |
| Decisión | Insuficiente | No necesaria | No necesaria | Adoptar |

**Elección C:** reimplementar el mínimo contrato como script Python sin
dependencias. No copiar código OSS ni traer paquetes innecesarios. Un
`gh` instalado localmente puede ayudar a un operador, pero no forma parte
de la cadena de confianza del validador. Coste monetario incremental
de dependencias: cero; consumo GitHub Actions y GitHub API sujeto a los
límites, disponibilidad y políticas vigentes, no se inventan cuotas.

## Licencias y procedencia

- Código del validador escrito para esta campaña; **no procede de OSS ajeno**.
  No se modifica ni se supone la licencia del repositorio oficial.
- Los *datos de PR* provienen de GitHub REST `GET /repos/{owner}/{repo}/pulls`,
  consultados el 2026-10-09; URL canónica, títulos, referencias y SHA
  observados están registrados en `docs/open-source-scouting/children.json`.
- Bibliotecas de terceros incorporadas: **ninguna**. Si una hija integra
  componentes OSS, su evidencia exige repositorio, tag/commit permalink,
  archivos efectivamente utilizados, SPDX, `LICENSE`/NOTICE, licencia
  transitiva, política de acceso, fecha, advisories y compatibilidad con
  redistribución. `NOASSERTION` no equivale a permiso de copia.
- Fuente oficial SPDX: https://spdx.org/licenses/ (revisada 2026-10-09;
  listado 3.29.0 de 2026-09-16).
- Referencias GitHub: https://docs.github.com/en/rest/pulls/pulls ,
  https://docs.github.com/en/pull-requests/reference/status-checks ,
  https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches ,
  https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target
  (consultadas 2026-10-09).
- Riesgo de supply chain/OWASP:
  https://cheatsheetseries.owasp.org/cheatsheets/Software_Supply_Chain_Security_Cheat_Sheet.html
  y https://github.com/OWASP/Software-Component-Verification-Standard/blob/master/en/0x14-V5-Component_Analysis.md
  (consultados 2026-10-09).

## Decisión

La campaña debe disponer de tres puertas sin mezclarlas: validación del
mirror (G1), integración comprobada en original privado (G2) y promoción
con privacidad y autorización (G3). G1 es automática solo parcialmente:
`mergeable=true` no prueba revisión, rama protegida, éxito de checks ni
paridad con el original. Las decisiones individuales A/B/C/D pertenecen
exclusivamente a las hijas; el padre adopta **C para el control de campaña**.

El script usa comparación exacta del dominio del repo, la cohorte mínima de 46 PR originales y ampliaciones consecutivas (76 verificadas el 2026-10-09),
unicidad de números/objetivos/ramas, ramas prefijadas, títulos, SHA con
formato válido, bases, relaciones sin referencias externas, privacidad
por regex y exclusión de rutas sensibles, más revalidación de GitHub
cuando se solicita `--live`. En una PR hija al padre, exige un informe
`docs/research/*.md` con apartados definidos y una prueba bajo `tests/`;
no acepta una ficha inicial como implementación terminada.

## Pruebas

Ejecutar desde raíz:

```sh
python -m unittest discover -s tests -p test_open_source_campaign.py -v
python tools/validate_open_source_campaign.py
python tools/validate_open_source_campaign.py --live
# Solo cuando el checkout Git tiene la referencia base:
GITHUB_BASE_REF=research/public-reuse-parent python tools/validate_open_source_campaign.py --changed-base <SHA_BASE>
```

CI: `.github/workflows/validate-public-reuse.yml`, Python 3.11,
Ubuntu y Windows, privilegios de solo lectura. No llama a redes sociales.
El test unitario usa fixtures generados y respuestas simuladas.

Medición local del primer prototipo: **15 pruebas**; primera ejecución,
**14 correctas y 1 fallo** al no detectar `token=...`. Tras corrección
del patrón de secreto, **15/15 correctas** (suite específica).
Una ampliación simultánea de #57–#86 hizo fallar correctamente la suposición inicial de un total fijo; se cambió a integridad de rango con 46 obligatorias. La suite dedicada incorpora después 22 casos unitarios; se exige confirmación CI de ese resultado, distinta de los 15 tests locales iniciales. No se ha ejecutado en este entorno la suite completa del repo privado.
Los checks remotos solo se consideran realizados cuando GitHub confirma
su resultado para el SHA final.

## Riesgos, límites y control adversarial

1. Un token mal formado, PII sin arroba o un dato identificable visual no
   necesariamente coincide con las regex. Exigir revisión humana,
   clasificación y nunca transportar dumps. Este control es parcial.
2. GitHub puede tener PR nuevas y datos paginados o cambiantes: consulta
   por páginas y falla cerrada si hay errores. Un cambio en SHA se marca
   como aviso, jamás como aprobación. Cambios de base/URL/título/estado
   bloquean el gate hasta refrescar instantánea.
3. Tests del mirror verde no equivalen a funcionamiento privado.
   Inspeccionar original antes de portar; prohibidas acciones reales.
4. `pull_request_target` puede elevar privilegios ante PR no confiables.
   La CI nueva usa `pull_request` y token solo lectura; no secretos
   externos ni artefactos de PR reutilizados privilegiadamente.
5. Los SHA de actions deben revisarse en releases de confianza al
   actualizar y no prometer seguridad solo por estar fijados.
6. Un validador de evidencia comprueba estructura, no autenticidad de
   fuentes, licencias ni cobertura: requiere revisor independiente.

## Retirada

Eliminar el workflow dedicado, script, tests y manifiesto mediante un
revert revisado del padre. No es necesaria migración de base de datos.
Si se promueve una pieza de una hija: flag inicialmente desactivado,
copia de recuperación aprobada, operación en shadow, stop en fallo,
rollback explícito y conciliación de ledger; documentar en el original.
La campaña no se fusiona ni publica automáticamente.
