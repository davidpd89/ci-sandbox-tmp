# Revisión adversarial y cobertura de la PR padre #10

Fecha: 2026-10-09. Repositorio público `davidpd89/ci-sandbox-tmp`.
Este informe NO aprueba el merge. Cada fila se fundamenta en rutas,
consultas GitHub o pruebas identificables; no se interpreta
`mergeable=true` como integración autorizada.

## Cobertura verificable

| Criterio del padre | Evidencia | Estado |
|---|---|---|
| Base/head del padre | API GitHub PR #10, `main ← research/public-reuse-parent` | Pasa en consulta, revalidar SHA |
| 46 hijas originales | `children.json` + índice `PROTOCOL.md`; tests `test_valid_snapshot`, `test_missing_child` | Pasa |
| Segunda ola #57–#86 | PR GitHub 57–86, manifiesto de 76, tests `test_contiguous_extension_preserves_initial_wave` y `test_extension_gap_fails` | Pasa en consulta |
| Enlaces y ramas | `check_metadata` y `check_live`; `--live` usa GitHub REST. Test de URL falsa y PR ausente | Pasa sintético; volver a ejecutar vivo |
| Naming, duplicaciones | `test_bad_head_or_base`, `test_duplicate_child`, `test_duplicate_objective_and_related` | Pasa |
| Solapamientos iniciales | API `/pulls/{n}/files` para #11–#86: una ficha diferente por PR | Pasa en estado inicial; futuro pendiente |
| Matriz y dependencias | `COORDINATION.md`, `children.json[].related_prs` | Pasa como planificación; conflictos futuros pendientes |
| No aceptar fichas vacías | `check_child_deliverables` + tests de investigación insuficiente | Pasa control formal; calidad semántica requiere persona |
| Procedencia/licencia | `RESEARCH_TEMPLATE.md` y campos exigidos de fuente, SPDX, referencia inmutable y fecha | Pasa formato; licencias reales pendientes por hija |
| Secretos y fixtures | `check_privacy`, tests de secreto, email, ruta y symlink sintéticos | Pasa sintético; clasificación humana pendiente |
| CI independiente | `.github/workflows/validate-public-reuse.yml` Ubuntu/Windows con token solo lectura | Implementado; consultar job del último SHA |
| Pruebas negativas | `tests/test_open_source_campaign.py`: huecos, duplicado, URL, base, leak, symlink, paginación | Pasa local prototipo; suite actual en CI |
| Compatibilidad con original (G2) | `00_OPERATIVO/...` consultado; no se ejecutaron tests privados | Pendiente |
| Promoción/rollback (G3) | `PROMOTION_TEMPLATE.json` no aprobado, `COORDINATION.md` | Protocolo pasa; autorización pendiente |
| Reviews, checks, conflictos finales | GitHub PR #10 y checks por SHA, revisión humana | Pendiente |
| Sin merge ni acciones RRSS | No hay API de redes, permiso Actions limitado a lectura, ningún merge ejecutado | Pasa en cambios de esta PR |

## Autorrevisión 1: corrección, seguridad y datos

**Objeción 1: una ampliación legítima deja la campaña entera en rojo.**
Reproducción real: 30 PR nuevas #57–#86 hicieron fallar el primer
`expected 46 children` en GitHub Actions. Corrección: exigir
#11–#56 pero aceptar rango consecutivo adicional con paridad
índice/manifiesto y URL/cabezas correctas. Se añadieron tests para
76 entradas, hueco y duplicado.

**Objeción 2: el scanner bloquea su propio código.**
Reproducción real de CI sobre el diff del padre: 
`FAIL: tools/validate_open_source_campaign.py: possible secret`.
La regex atravesaba el salto de línea tras `if token:`.
Corrección: tras `:`/`=` admitir espacios horizontales, no saltos
de línea. Inspección local: cero coincidencias sobre su fuente;
la credencial sintética sigue detectándose. Test de autorregresión.

**Objeción 3: un fixture con symlink podría apuntar fuera del
checkout.** Corrección preventiva: rechazar symlinks y rutas
resueltas fuera de la raíz, más test hostil. No imprimir datos
sensibles. Sigue faltando revisión humana para material multimedia
y PII semántica imposible de capturar por regex.

## Autorrevisión 2: concurrencia, arquitectura y mantenimiento

**Objeción 4: la paginación de la API deja de funcionar al superar
100 PR.** `replace('page=1', ...)` modificaba además
`per_page=100`. Corrección: construir explícitamente
`&page=<n>` y comprobar en test simulado 101 elementos que
`per_page` permanece constante.

**Objeción 5: el mirror puede ser sobrescrito y sus SHAs quedar
obsoletos.** Mitigación: SHA capturado por cada hija; en
`--live` un SHA nuevo se informa como advertencia, no como
aprobación. Para promover, consultar SHA actual, reviews y
checks actualizados; impedir sincronización con force-push
sin respaldo/lease. El padre no cambia el script privado que
sincroniza el espejo.

**Objeción 6: que los tests del mirror pasen no significa que el
original funcione o que una API permita esa automatización.**
Mitigación: G2 privada separada y revisión de permisos/ToS por
hija. G3 exige licencia, limpieza y aprobación humana. No se ha
declarado el sistema completo validado.

**Objeción 7: trabajar en paralelo provoca ediciones del mismo
contrato.** Los 76 diffs iniciales solo editan fichas únicas.
La matriz identifica `scan_common`, ledger, scheduler, media,
configuración, tests y adaptadores como superficies potenciales.
Antes de merge, volver a leer diffs de las PR hermanas y elegir
una interfaz ganadora; el padre jamás fusiona hijas automáticamente.

## Limitaciones residuales y cierre

La CI comprueba metadata, rutas y evidencias **estructurales**, no la
exactitud jurídica de una licencia, veracidad de una fuente, PII en
imágenes, eficacia de una mejora social ni aprobación del dueño.
Al faltar G2/G3 y review humano, el veredicto del padre es
**LISTA PARA REVISIÓN (no mergeada)**, condicionado a checks actuales.
Si los checks remotos del último SHA fallan, el estado pasa
a **BLOQUEADA** hasta corregirlos.
