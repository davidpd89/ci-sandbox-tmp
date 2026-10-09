# Coordinación e integración — campaña pública #10

Actualizado: 2026-10-09. **Mirror público:** `davidpd89/ci-sandbox-tmp`.
**Original privado:** `davidpd89/rrss-davidporto-CODE`. No son intercambiables.
Fuente de números, SHA de referencia y relaciones: [children.json](children.json).
El alcance inicial #11–#56 fue ampliado en vivo el 2026-10-09 con #57–#86;
se preservan las 46 originales y se exige integridad del nuevo bloque.
El índice textual de 46 PR está en [PROTOCOL.md](PROTOCOL.md).

## Ciclo de trabajo y puntos de fallo

`entrada/lectura → filtros y permisos → selección/plan → preflight de ejecución
→ confirmación externa → ledger/estado → métricas y recuperación`.

Rutas verificadas en **original**, no inferidas del mirror: `tools/scan_common.py`,
`tools/growth_common.py`, `tools/bluesky_scan.py`,
`tools/mastodon_growth_flow.py`, `tools/facebook_execute.py`,
`tools/content_queue.py`, `tools/run_content_queue.py`,
`tools/mobile_runtime.py`, `00_OPERATIVO/02_FLUJOS/crecimiento-organico.md`
y `.github/workflows/validate-social-tools.yml`. El flujo de control editorial y
publicación sigue `00_OPERATIVO/01_CONTEXTO_UNICO.md`: **nunca publicar sin revisión**.

Comprobar: duplicados en entrada y ledger; credenciales y scopes de lectura;
candidatos desactualizados; permisos/restricciones de plataforma; acciones con
confirmación ambigua; reintentos que duplican escritura; errores parciales;
cancelación e idempotencia; métricas después de fallo; reinicio/restauración.
Estos puntos son **áreas de inspección**, no bugs declarados ni funciones
demostradas por el mirror.

## Matriz de dominios y colisiones

El **número se refiere exclusivamente a las PR del mirror**.
Las rutas son posibles zonas de contacto, NO una afirmación de que ya estén
modificadas. Al empezar una hija hay que consultar `GET /pulls/{n}/files` de
todas las hermanas relacionadas; volver a hacerlo antes de promover.

| PR mirror | Dominio y archivos de riesgo | Coordinación y criterio de orden |
|---|---|---|
| 11–19 | Adaptadores `tools/{red}_*.py`, `SISTEMA_DIARIO_*/` y tests de red | Pueden avanzar en paralelo; consumir contratos comunes aprobados, nunca compartir sesiones |
| 20, 26, 39, 49, 55 | Programación, colas, concurrencia, tiempo, releases; `tools/content_queue.py`, `tools/run_content_queue.py`, ledger/SQLite | 26 y 49 establecen invariantes antes de migrar 20; 39 revisa locks; 55 define rollback |
| 21, 22, 25 | Descubrimiento, respuestas, relaciones; `tools/scan_common.py`, `tools/growth_common.py`, `tests/test_*reply*.py` | Elegir un contrato compartido; no duplicar políticas ni contadores |
| 23, 24, 32, 46, 47, 48 | Métricas, panel, datos, reconciliación, alertas, backup; `tools/*metrics*.py`, CSV/SQLite | Congelar esquema y claves con 32; 46 verifica reconciliación antes de panel/alertas |
| 27, 38, 42, 43 | Navegador/móvil, fugas, selectores y capacidades; `tools/mobile_runtime.py`, `tools/cdp_health.py` | 27 aporta límites de sesión; 38 maneja cierre; 42 pruebas visuales; 43 declara degradación |
| 28, 51, 53 | Contenido, evaluación editorial, fixtures; `tools/*content*.py`, render y archivos de test | 53 debe producir datos sintéticos; 51 no debe introducir corpus privado al mirror |
| 29, 37, 54, 56 | Agentes, costes, documentación; `00_OPERATIVO/02_FLUJOS/`, runbooks | 29 define contratos y límites; 54 mide; 56 actualiza documentación ejecutable |
| 30, 33, 34, 35, 36, 52 | Test harness, paridad, mutaciones, modelos, caos, E2E shadow; `tests/`, CI | 30 fija contratos; 33/35/36 añaden controles aislados; 52 valida sin efectuar acciones |
| 31, 41, 45, 55 | Privacidad, API drift, calidad, dependencias; CI, requisitos, licencias | 31 revisa higiene antes de cualquier porte; 41 vigila contratos; 55 registra versiones |
| 40, 44, 50 | Migraciones, arquitectura, Unicode; esquema, imports y normalización | 44 fija propiedad por módulo; 40 requiere compatibilidad hacia atrás; 50 prueba datos ES-ES |

| 57–62, 65, 68, 71, 84, 85 | Relaciones/followback/unfollow, antigüedad, identidad, estado, ledger; `tools/growth_common.py`, registros y pruebas de relaciones | Un único estado canónico; #60 y #84 coordinan claves e idempotencia antes de #57/#58/#59 |
| 63–66, 70 | Descubrimiento de hashtags, comunidades, reciprocidad, ranking, autores de engagement | Coordinar con #21, #25 y filtros compartidos; evitar contar la misma cuenta dos veces |
| 67, 69, 77, 78 | Persistencia de repost, fidelización, conversación y cadencia | Coordinar con #22/#25/#49 y ledger #84; límites de contexto por usuario |
| 72–76, 79, 80 | Benchmark, corpus humano, contexto, muletillas, voz local, experimentos | No mover conversaciones ni muestras reales al mirror; fixtures de redacción inventados, #51/#53 |
| 81–83, 86 | Paridad ejecutable, drift de configuración, rondas y embudo | Coordinar #33/#41/#43, #20/#26 y #23/#24; separar métricas observadas de inferidas |

Las relaciones explícitas por hija constan en `children.json[].related_prs`.
En el estado inicial (2026-10-09) **las 76 PR solo añaden sus propias fichas
`docs/open-source-scouting/tasks/*.md`**. Cero colisiones de archivo observadas
en el diff inicial, NO garantía de ausencia de futuras colisiones semánticas.

### Orden recomendado, no cadena obligatoria

1. **Preflight**: padre #10, inventario y privacidad de #31/#53; contratos #30/#32/#40/#44. No es necesario mergearlos para trabajar en paralelo.
2. **Interfaz común**: coordinar #21/#22/#26/#43 y estabilizar firma/esquemas antes de que hijas de red consuman esos cambios.
3. **Adaptadores de plataformas**: #11–#19 individualmente y bajo permiso; no exigir que las nueve redes cambien juntas.
4. **Sistemas transversales**: #20/#23/#24/#25/#27/#28/#29, en función de contratos ya probados.
5. **Robustez y observabilidad**: #33–#56, agrupando colisiones reales, pruebas de regresión y runbooks.

**Cada integración se decide individualmente.** Prioridad es por dependencia
verificada, no por número. Si dos PR editan el mismo contrato, bloquear la
segunda hasta comparar diffs y repetir CI; no cherry-pick masivo.

## Tres puertas independientes

**G1 — Mirror:** base/head/commit vigentes; diff pequeño y sin artefactos
privados; `children.json` e índice coherentes; CI Linux/Windows confirmado
para SHA actual; revisión sin objeciones pendientes; pruebas offline de la hija
y comparación antes/después; licencias/procedencia. Un `mergeable=true`
NO equivale a G1 aprobada.

**G2 — Original privado:** inspección autorizada de módulos existentes;
compatibilidad de imports, API, flags, políticas, schema, tests y dependencias;
shadow/dry-run; pruebas de regresión relevantes y suite general disponible;
cero acciones reales; revisión humana del contexto original. El CI del mirror
**no** valida esta puerta.

**G3 — Promoción:** clasificación de archivos, propiedad/licencia SPDX,
revisión de información personal y secretos, manifestación de rutas y SHA,
plan de migración y retirada, autorización humana explícita. Prohibido copiar
bases, historiales, capturas de cuentas, cookies, credenciales, `.env`,
perfiles o fixtures reales. Usar [PROMOTION_TEMPLATE.json](PROMOTION_TEMPLATE.json)
como plantilla *no aprobada*; guardar el manifiesto concreto únicamente en
la ubicación autorizada del original si pudiera revelar rutas privadas.

**Ninguna puerta hace merge automático ni ejecuta interacción en RRSS.**

## Checklist por hija

- [ ] Releer PR #10 y la hija: URL, SHA, head, base, estado, reviews, threads y checks **del SHA final**.
- [ ] Comparar archivos modificados con `related_prs`; resolver choques o bloquear con propietario y ruta.
- [ ] Aportar `docs/research/<tema>.md`: Problema, Alternativas, Licencias y procedencia, Decisión, Pruebas, Retirada.
- [ ] Fuente primaria con URL/tag/commit, fecha de consulta, permisos de uso, licencias SPDX y avisos; dependencias transitivas y CVEs cuando proceda.
- [ ] Cambio de código mínimo + test offline, o decisión D con control automatizado pertinente; no basta la ficha de scope.
- [ ] Antes/después con el mismo fixture, casos negativos, timeout, retries, idempotencia y regresiones compartidas si aplican.
- [ ] Ejecutar `python -m unittest discover -s tests -p test_open_source_campaign.py -v` y `python tools/validate_open_source_campaign.py` en el mirror.
- [ ] Ejecutar `GITHUB_BASE_REF=research/public-reuse-parent python tools/validate_open_source_campaign.py --changed-base <SHA_BASE>` para la hija (Git local); `--live` consulta enlaces/ramas.
- [ ] G2 y G3 verificadas por separado; no publicar ni fusionar sin aprobación humana.

CI de GitHub: `.github/workflows/validate-public-reuse.yml`, sin secretos
externos, usa permisos de solo lectura, Ubuntu y Windows. En G1: `--live`
verifica enlaces reales y ramas vía API; fallos de red dan fallo, no una
aprobación simulada. El SHA cambiado de hija es **aviso**: invalida cualquier
aprobación anterior y exige nueva revisión de checks.

## Incidencias y recuperación

Cada bloqueo lleva `PR mirror / SHA / ruta / puerta G1-G3 / severidad /
comando y salida resumida / propietario / decisión / condición de desbloqueo`.
Registrar incidentes concretos en [BLOQUEOS_PARA_CLAUDE.md](BLOQUEOS_PARA_CLAUDE.md);
nunca pegar credenciales ni salidas identificables.

Antes de promover, registrar componentes, hash, licencia, flags default-off,
migraciones, señales de salud, smoke test, propietario, comando de reversión
y punto de recuperación. En fallo: **deshabilitar flag → detener escrituras
→ comprobar ledger/idempotencia → restaurar estado aprobado → repetir tests
→ solicitar revisión humana**. No asumir rollback automático de datos.
