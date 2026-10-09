# Mastodon / Fediverse — búsqueda de cuentas sin saltos (PR #12)

Consulta: **2026-10-09 (Europe/Madrid)**. Alcance: solo `tools/mastodon_interact.py::search_accounts_pages` y pruebas offline. **Sin tráfico ni escrituras contra cuentas reales**. El espejo es público y anonimizado; no se copiaron datos del repositorio privado.

## Diagnóstico y prueba de reproducción

Fuente de trabajo: espejo `davidpd89/ci-sandbox-tmp`, rama `research/02-mastodon-fediverse`, head inicial `0077e868ddc99ad927fa9add359a07f363c0fd36`. Código comparable del privado `davidpd89/rrss-davidporto-CODE`, `main` en `db0edb9328358e0181e67573fa1bd71c55b04fec` al consultar; **no son snapshots idénticos**.

La función anterior calculaba `page_size=min(limit,80)`, mientras `search()` reduce `limit` a 40. En una petición de 80, Mastodon entrega como máximo 40 y el paginador interpreta `40 < 80` como fin: no solicita el siguiente `offset`. El problema no aparece cuando se llama con el valor por defecto 40, de ahí que la regresión existente con `limit=1` no lo descubriera.

Evidencia de contrato: [GET /api/v2/search](https://docs.joinmastodon.org/methods/search/) admite **hasta 40 por categoría**, `offset` requiere autenticación y los estados textuales dependen del índice instalado; no promete búsqueda global del Fediverse. El código propio ya permite `resolve=true` para URL remota y rechaza conversiones automáticas del ID numérico de otra instancia.

Caso sintético determinista en `tests/fixtures/mastodon_search_capabilities.json`:

| Perfil | Respuestas simuladas compatibles con JSON search v2 | Anterior (por lógica) | Nuevo esperado |
| --- | --- | --- | --- |
| `indexada.example` (búsqueda full-text disponible) | 40, 40 (una cuenta solapada), 3; offsets 0/40/80 | 40 cuentas; offset [0] | 82 cuentas únicas; offsets [0,40,80] |
| `sinindice.example` (sin full-text; backend ignora offset) | 40, repetición 40; offsets 0/40 | 40, offset [0] | 40 sin duplicados, parada tras offset [0,40] |

**Advertencia:** son *perfiles contractuales sintéticos*, no resultados capturados de dos servidores disponibles públicamente. No demuestran comportamiento en vivo ni compatibilidad general con forks ActivityPub.

## Flujo real y quién consume este resultado

`tools/mastodon_growth_flow.py prepare` → `mastodon_growth_scan.py` (Collector, superficies de búsqueda/cuentas/hashtags/stream y filtrado) → `mastodon_interact.py` (`search`, `search_accounts_pages`, REST paginado; resolución de URLs remotas) → shortlist → `mastodon_build_plan.py` (selección editorial; `status_id` **local**) → `mastodon_execute.py::_preflight_plan/run_plan` (sin escrituras antes de validar y detectar acciones repetidas; consulta de estado y confirmación) → ledger y registro/métricas/recuperación existentes. `mastodon_remote.py` explora algunos servidores remotos por separado, con identidades `acct@host` y su propio almacenamiento. 

Fallos principales: autenticación/429 bloquean acciones; una búsqueda de estados sin índice no debe invalidar todas las superficies; respuestas malformadas de búsqueda de cuentas **fallan cerradas**, para no acreditar cobertura falsa; varias URLs que resuelven al mismo status local **no** originan doble acción. La idempotencia durable y la política transversal pertenecen a la PR #26, no a esta.

En otros adaptadores, distinguir ID de origen del ID operativo local y realizar deduplicación antes de escribir es una pauta reusable; **no se modifica código compartido** en esta PR.

## Comparativa y decisión

| Baseline | Candidato 1 | Candidato 2 | Elección | Motivo | Riesgo residual |
| --- | --- | --- | --- | --- | --- |
| REST propio con `requests`; bug de stride; 0 dependencias nuevas | [Mastodon.py v2.2.2](https://github.com/halcy/Mastodon.py/tree/v2.2.2), **MIT**, publicado 2026-08-03; capa Python completa | [Megalodon v10.3.0](https://github.com/h3poteto/megalodon/tree/v10.3.0), **MIT**, publicado 2026-04-18; cliente JS/TS multi-servidor | **C: adaptar el contrato con cambio mínimo**, sin incorporar SDK | Una línea de límite + comprobación/dedupe cubre el fallo; sustituir todo el transporte aumenta superficie y dependencias | Los forks y los backends de búsqueda no obedecen todos idénticamente; falta ejecución real autorizada |

Se comprobó actividad pública de Mastodon.py y Megalodon, incluyendo releases; **no se incorporaron ni se copiaron sus fuentes**. Mastodon.py v2.2.2 declara `requests`, `python-dateutil` y `decorator` como dependencias obligatorias en [pyproject.toml](https://github.com/halcy/Mastodon.py/blob/v2.2.2/pyproject.toml). Para el bug preciso, migrar cliente completo añadiría más superficie de actualización que valor. Megalodon es TypeScript y requeriría otro runtime, improcedente para una función Python pequeña. Licencias de ambos: MIT. SDK no adoptado: sin dependencias transitivas nuevas en este cambio.

Puntos de verificación de terceros: [origen y commit de distribución Mastodon.py v2.2.2](https://github.com/halcy/Mastodon.py/tree/b9f2effbb5a9f07ebca3807466f4130e69b1614c), [releases Megalodon](https://github.com/h3poteto/megalodon/releases/tag/v10.3.0), [licencia Mastodon.py](https://github.com/halcy/Mastodon.py/blob/v2.2.2/LICENSE), [licencia Megalodon](https://github.com/h3poteto/megalodon/blob/v10.3.0/LICENSE). No se ha llevado a cabo una auditoría exhaustiva de advisories para versiones que no se instalan. Regla de selección y cadena de suministro: [OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Software_Supply_Chain_Security_Cheat_Sheet.html).

Capacidades investigadas, sin ampliar alcance: [paginación Link](https://docs.joinmastodon.org/api/guidelines/), [streaming y host configurable](https://docs.joinmastodon.org/methods/streaming/), [filtros v2](https://docs.joinmastodon.org/methods/filters/), [bookmarks](https://docs.joinmastodon.org/methods/bookmarks/), [notificaciones](https://docs.joinmastodon.org/methods/notifications/), [rate limits](https://docs.joinmastodon.org/api/rate-limits/). No se presupone paridad entre Mastodon, GoToSocial u otras variantes. Los límites por defecto publicados (300/5 minutos para REST por cuenta e IP) **no sustituyen las cabeceras observadas de la instancia**; un servidor puede tener una política distinta.

## Riesgos, coste, control y reversión

- **Acceso/TOS:** únicamente REST oficial y tokens autorizados. Sin scraping, saltos de restricciones ni respuestas automáticas.
- **Privacidad:** fixtures con dominios reservados `.example` y handles sintéticos; nunca se incorpora CSV operativo, tokens, snapshots de seguidores, ni identidades reales del repositorio privado.
- **Coste:** no hay coste monetario ni instalación de software. Si se pide `limit=80`, ahora puede haber peticiones adicionales porque antes el paginador terminaba prematuramente. Respetar `X-RateLimit-*` y cortes existentes; no inventar mediciones de tiempo o cuota.
- **Riesgo lógico:** la deduplicación usa IDs *del servidor consultado* solo durante la paginación; jamás fusionar IDs numéricos provenientes de **dos hosts distintos**. El límite de páginas permanece acotado por el argumento `max_pages`.
- **Reversión:** revertir únicamente el diff de `tools/mastodon_interact.py::search_accounts_pages` del commit [`3b32b62`](https://github.com/davidpd89/ci-sandbox-tmp/commit/3b32b62b6ad251cba00f4d7d924930b05a679174). No hay cambios de base de datos ni flags que migrar. La pérdida de cobertura anterior reaparecería.
- **Espejo / código privado:** el README del espejo indica que un sync de CI puede **sobrescribir sus archivos**. Antes de llevar el cambio a producción, aplicar el parche mínimo y las regresiones (sin anonimización inversa) sobre el `main` privado actualizado; después regenerar el mirror conforme al procedimiento oficial. No hacer merge de la rama de investigación contra `main` del espejo ni interpretar el verde del espejo como validación del privado.

## Verificación y revisión adversarial

Archivos de pruebas:
- `tests/test_mastodon_search_contract_p12.py`: offsets exactos y truncamiento, cuenta repetida por backend que ignora offset, ausencia de índice textual, JSON ausente/malformado, timeout de segunda página, URLs remotas con misma cola numérica e ID local distinto, y dos alias remotos para el mismo ID local (rechazo en preflight).
- `tests/fixtures/mastodon_search_capabilities.json`: dos capacidades sintéticas; generan el JSON de `/api/v2/search` durante la prueba.

Comandos **existentes** en el workflow del espejo: `python -m pip install --disable-pip-version-check -r requirements-ci.txt`, `python -m compileall -q tools tests`, `python -m pytest tests -q -p no:cacheprovider` con exclusiones documentadas en `.github/workflows/validate-social-tools.yml`. Windows y Ubuntu. No se ha lanzado publicación, ronda real ni autenticación. Las comprobaciones de CI se informarán según sus resultados, no por asumirlos.

Dos pasadas de revisión del diff:
1. Corrección e integridad: se evitó mantener `limit=80` tras el clamp; se añadieron cuentas únicas por ID local y excepciones por forma de respuesta inesperada; se acotó a `max_pages`.
2. Arquitectura/privacidad: se evitó portar el archivo privado completo; no se tocan `scan_common`, queues, rate-limiter, estado persistente, ni módulos de otras redes.

Objeciones adversariales y defensa:
1. **Backend devuelve siempre la página inicial pese a avanzar offset.** Corte si toda la página repite IDs; no genera nuevas recomendaciones.
2. **URL remota comparte el número de status con otra instancia.** Resolución del ID de estado local antes de planificar; dos aliases al mismo ID quedan rechazados en preflight. Se prueba sin POST.
3. **La página 2 falla por timeout o cambia de forma.** El error se propaga; no se presenta el lote parcial como completo. Se prueba con respuesta equivocada y excepción simulada.

Pendiente sin inventar: validación con dos instancias autorizadas y capacidades reales, pruebas tras portar al privado, decisión de integración de las PR hermanas.

## Colisiones y coordinación

Las cuatro PR del **espejo** estaban abiertas y sus diffs examinados contienen únicamente el fichero de encargo: [#21](https://github.com/davidpd89/ci-sandbox-tmp/pull/21) descubrimiento/ranking (mismo consumo de candidatos), [#26](https://github.com/davidpd89/ci-sandbox-tmp/pull/26) ledger/idempotencia, [#33](https://github.com/davidpd89/ci-sandbox-tmp/pull/33) tests comparativos y [#41](https://github.com/davidpd89/ci-sandbox-tmp/pull/41) drift de contratos externos. No se trasplanta código. Orden propuesto: integrar este contrato de Mastodon en el privado tras refrescar rama, reejecutar pruebas, y después reconciliar los contratos genéricos cuando lleguen #21/#26/#33/#41. Las numeraciones del mirror no identifican las PR del privado.

**Dictamen provisional: LISTA PARA REVISIÓN (no mergeada), supeditado a CI y a portar/validar en el privado.** Si no puede verificarse la compatibilidad con el privado antes de fusionar, elevar a **BLOQUEADA para merge efectivo**.
