# Bloqueos para Claude — PR #12 Mastodon (2026-10-09)

## Hechos verificados, no inferencias

- PR espejo: https://github.com/davidpd89/ci-sandbox-tmp/pull/12; `head=research/02-mastodon-fediverse`, `base=research/public-reuse-parent`. El inicio auditado fue `0077e868ddc99ad927fa9add359a07f363c0fd36`.
- Mirror `ci-sandbox-tmp` **público**, escritura posible; oficial `rrss-davidporto-CODE` **privado**, `main` observado en `db0edb9328358e0181e67573fa1bd71c55b04fec`. No confundir numeraciones de PR ni ramas.
- Se ha modificado únicamente `tools/mastodon_interact.py::search_accounts_pages` más tests y documentación de este frente. La función antigua del oficial tiene el mismo desajuste `80` vs `40`, **pero el mirror y el privado no coinciden en muchas otras funciones**.
- Llamada actual principal en `tools/mastodon_growth_scan.py` del mirror: `m.search_accounts_pages(q, limit=40, max_pages=2)`; por tanto, este arreglo cubre regresiones potenciales con `limit>40`, no evidencia de bug sufrido por el flujo actual.
- Se añadieron `tests/test_mastodon_search_contract_p12.py` y `tests/fixtures/mastodon_search_capabilities.json`. Los dos perfiles son **sintéticos**, no certificaciones en vivo.
- CI verificado antes de la ampliación final, en el commit `9f96f8251d137d5ce6c3933e3bd2d10ea8c90ca6`: https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/37978224024, **Ubuntu y Windows correctos**. Confirmar de nuevo CI del HEAD final.
- Fuente del límite 40: https://docs.joinmastodon.org/methods/search/ . Coste: sin nueva dependencia. Sin llamadas a cuentas reales.

## Bloqueos reales

1. **Sin integración en el privado.** La autorización de esta PR cubre trabajar sobre el `head` del mirror, no fusionar ni modificar `main` del privado. Un commit del mirror **no despliega** el código.
2. **Sin evidencia de dos instancias reales.** Los fixtures son reproducibles y reproducen JSON y límites de Mastodon, pero solo hay simulación de capacidades. Validación de una instancia con full-text y otra sin índice requiere un entorno autorizado, sin ejecutar interacción.
3. **Cadena de sincronización.** El README del mirror advierte que el sincronizador lo **sobrescribe**. El parche debe aplicarse selectivamente al privado y regenerar el mirror conforme a su procedimiento. Una copia completa del archivo del mirror perdería trabajo más reciente y podría introducir errores.
4. **Sin validación Windows/Linux contra el privado después del traslado.** El CI de esta rama es útil, pero no sustituye CI en el árbol real.

## Pasos mínimos precisos para Claude / mantenedor

1. Verificar de nuevo las referencias, por ejemplo con `gh pr view 12 -R davidpd89/ci-sandbox-tmp --json baseRefName,headRefName,headRefOid,mergeStateStatus` y `git -C C:\\GIT\\RRSS_DavidPorto rev-parse HEAD` (esta segunda ruta solo existe en la máquina del mantenedor).
2. En el **privado** actualizado, crear rama aislada, nunca modificar `main` directamente. Revisar primero `tools/mastodon_interact.py` y localizar exactamente `search_accounts_pages`. Portar **solo** el bloque modificado del diff de https://github.com/davidpd89/ci-sandbox-tmp/pull/12/files. No sobrescribir el archivo entero.
3. Portar `tests/test_mastodon_search_contract_p12.py` y `tests/fixtures/mastodon_search_capabilities.json` sin incorporar datos operativos. Si los adaptadores difieren, ajustar pruebas a las firmas reales, manteniendo los asserts `40,82` y los offsets `0,40,80`.
4. Ejecutar desde la raíz del privado `python -m compileall -q tools tests` y `python -m pytest tests/test_mastodon_search_contract_p12.py tests/test_mastodon_api_features.py tests/test_mastodon_growth_engine.py -q -p no:cacheprovider`. Ejecutar posteriormente la suite offline completa con las exclusiones reales de ese repositorio (no inventarlas). No usar credenciales ni probar acciones reales.
5. Revalidar por separado Windows y Ubuntu, casos de HTTP 429/timeout, y cómo el `growth_scan` actual consume cuentas. Si la instancia no soporta búsqueda de estados, comprobar que se usa otra superficie, no sugerir que full-text funciona.
6. Verificar y documentar explícitamente que el CI con el HEAD final de la PR #12 pasó en ambos SO. Sin esa evidencia, **no fusionar**.
7. Dejar PR de integración específica en el privado tras revisión humana y respetar la secuencia de sincronización descrita por `00_OPERATIVO/CI_ESPEJO_Y_FLUJO_DE_MERGE.md`. No modificar ramas padre/`main` ni forzar push para resolver este ticket.
8. Revisar los acuerdos con PR **del mirror** #21, #26, #33 y #41; no absorber discovery/ranking, ledger durable ni contrato API transversal en #12.

## Criterios para levantar el bloqueo

- HEAD y base aún coherentes; diff completo revisado, sin secretos o datos identificables.
- CI offline verde del HEAD final en Ubuntu y Windows, sin fallos ocultos.
- Patch mínimo aplicado y probado sobre privado actualizado o justificación explícita para no llevarlo.
- Dos perfiles de instancia simulados **más** evidencia autorizada de variación real, si se exige paridad Fediverse en vivo.
- Revisión humana de impacto, conflictos y alcance. **No ejecutar acciones sociales reales.**

**Veredicto para merge al sistema oficial: BLOQUEADA.** La PR espejo es revisable; no equivale a funcionalidad implementada en producción.
