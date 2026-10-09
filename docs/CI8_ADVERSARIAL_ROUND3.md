# PR #8 — Tercera revisión adversarial y trazabilidad de fechas (09/10/2026)

Este complemento de `docs/CI8_POST_AGE_REVIEW.md` revisa el trabajo **después** de la primera matriz verde. El problema principal no era el comparador de días, sino la pérdida del dato entre el escáner y el ejecutor.

## Hallazgos comprobados y correcciones sobre la propia PR #8

1. **Bluesky, decisiones compactas → plan ejecutable:** `bluesky_growth_scan.py` expone `shortlist[].posts[].created_at` obtenido del registro del post, pero `bluesky_build_plan.build` descartaba ese campo. Ahora se proyecta como `post_created_at` para reply/quote/like/repost. Sin la corrección, las respuestas perdían una fecha explícita, y un TID reciente no bastaba para autorizarlas. Regresión en `tests/test_plan_age_provenance.py`.
2. **Mastodon, decisiones compactas → plan ejecutable:** `mastodon_growth_scan.py` trae `created_at` del status de API, pero `mastodon_build_plan.build` lo perdía. Los status ID federados locales son opacos para inferir el momento del post original. Ahora `post_created_at` viaja hasta `conversation_turn_policy.check_execution`; tests para post nuevo/viejo/sin fecha.
3. **Bluesky, automatismo sin modelo:** `bluesky_growth_scan._build_output` creaba likes y reposts automáticos omitiendo la fecha; ahora arrastra `post_created_at` de los posts ya hidratados, incluso pasando por `repost_pool`. Reforzados dos tests del escáner real para comprobar el dato en auto-like y auto-repost.
4. **No confundir `indexedAt` con `createdAt`:** la hora de indexación de ATProto puede ser posterior a la fecha de publicación. `_created_at` ya no la usa como sustituto cuando falta `record.createdAt`. Sin fuente de publicación, conservar desconocido; no asignar artificialmente la fecha de escaneo.
5. **X, conflicto de referencias:** se prioriza `url`/permalink —el destino real del ejecutor— sobre el `target_post_id` auxiliar, para que un ID reciente no rejuvenezca una URL vieja. Test con ID reciente y URL antigua. La recuperación desde ID sigue funcionando cuando no hay fecha deducible de la URL.
6. **Limpieza:** eliminado `_snowflake_mastodon`, un decodificador muerto que contradecía el criterio correcto de no inferir fecha fiable de IDs federados de Mastodon.

## Mapa de procedencia real, no suposiciones

| Red / cola | Fuente de antigüedad vista en el espejo | Ruta hacia el control | Cobertura actual y límite |
| --- | --- | --- | --- |
| Bluesky / API | `record.createdAt` del post hidratado, TID de su URI | `bluesky_growth_scan` → `bluesky_build_plan` (manual) o `auto_plan` → `bluesky_execute` | **Fecha propagada** manual y automática. TID solo no certifica respuesta reciente. |
| Mastodon / API | `status.created_at` | `mastodon_growth_scan` → `mastodon_build_plan` → `mastodon_execute` | **Fecha propagada**. No inferirla del ID local federado. |
| X / WEB | Snowflake en URL validada; reserva `browser_pool` guarda observación | `x_build_plan` / `x_replies` → `x_execute` | Edad deducible de URL de status; `like_latest` sin URL sigue `edad_desconocida`. |
| Threads / WEB y API | Reserva `threads_pool`: edad visible estimada, `first_seen` de captura, permalink, o API con fecha cuando exista | `threads_build_plan` → `threads_execute` | Falta una transformación **verificable** para comentario/reply desde edad visual. Investigar en #62, no confundir primera observación con publicación. |
| Facebook / WEB | `browser_pool.age_hours` de la captura si existe; a menudo solo `first_seen` | `facebook_build_plan` → `facebook_execute` | Comentarios sin fecha no se publican; mejora de origen temporal a #62. |
| Pinterest / WEB | Información del pin si la fuente la aporta | `pinterest_growth` → control compartido | Fecha desconocida no equivale a post fresco; exige prueba con datos reales del DOM. |
| Reddit / WEB | `shreddit-post.created-timestamp` y `shreddit-comment.created-timestamp` | `reddit_comments.build_plan/run_replies` → `reddit_execute/reply_in_thread` | **Propagado y protegido** en esta PR. Validar variante real de DOM en Edge. |
| TikTok / MOBILE | Shortlist/captura móvil puede carecer de fecha verificable | `tiktok_build_plan` → `tiktok_mobile_execute` | No inventar fecha desde escaneo; investigación #62 y canario móvil supervisado. |
| Instagram / WEB | Plan de crecimiento actual mayormente `follow` | `instagram_build_plan` → `instagram_execute` | Follow no tiene post objetivo; si se habilita comentar/reaccionar, requerirá fecha de contenido. |

La política no garantiza ningún límite para las reacciones cuya fecha es desconocida, por decisión de compatibilidad/volumen ya presente en #8; **sí** registra `edad_desconocida` en vez de `edad_ok`. Esta decisión merece revisión explícita de producto por Claude y no debe presentarse como prevención completa de necroposting para todos los kinds.

## Paridad adicional confirmada con el repositorio oficial privado

La inspección posterior de `integracion/crecimiento-2026-10` confirmó que el **repositorio oficial ya tenía parte del traspaso temporal** que faltaba al mirror. Se portó al espejo solo el contrato de datos `post_created_at` (sin dependencias/cliente/red), por lo que no se ha escrito una lógica paralela distinta:

- `bluesky_build_plan`: admite `created_at`, `createdAt` o `record.createdAt` de la entrada; se conservan preferencias del repo oficial.
- `mastodon_build_plan`: `post_created_at` de `created_at` del status.
- `threads_build_plan`: `build` admite `created_at`/`created_time` de candidato; `build_from_pool` y `build_replies` conservan `created_at` si la fuente lo aporta. **El pool histórico actual no aporta por sí solo esta fecha**, no afirmar frescura en ausencia de ella.
- `facebook_build_plan`: `build` y `build_from_pool` conservan un timestamp de origen **cuando aparece en la fila**, sin convertir `first_seen` en publicación.
- `tiktok_growth_scan` y `tiktok_build_plan`: el campo procedente del vídeo (`created_at` / `create_time` / `created_time`) cruza filas → shortlist → auto-like y decisión editorial. **No crea** fechas para vídeos sin metadatos.
- Tests añadidos: `test_other_network_age_provenance.py` (incluida reconstrucción sintética de shortlist TikTok), más `test_plan_age_provenance.py` para el fallback de records ATProto.

Los módulos del repositorio oficial pueden tener otros cambios independientes; **no** se han copiado indiscriminadamente. La paridad completa debe contrastarse en una PR de integración del repositorio privado tras revisión, y la cobertura real de fechas ausentes corresponde a [#62](https://github.com/davidpd89/ci-sandbox-tmp/pull/62).

## Reutilización pública actual, con decisión técnica

- [Especificación TID ATProto](https://atproto.com/specs/tid): alfabeto, bits y primer carácter comprobados, además de advertencia de que un TID es un reloj lógico manipulable por el cliente. Documento de referencia, sin código copiado.
- [MarshalX/atproto](https://github.com/MarshalX/atproto) y [PyPI](https://pypi.org/project/atproto/): SDK Python mantenido (último commit GitHub consultado 02/10/2026; PyPI 10/09/2026), MIT, Python 3.11/Windows. Útil para **hidratar records** en un trabajo de adaptador/red de #62, pero añadir todo el cliente a la política pura offline sería acoplamiento innecesario.
- [Implementación de referencia bluesky-social/atproto](https://github.com/bluesky-social/atproto): MIT/Apache-2.0; referencia de `createdAt` y `indexedAt`. Como es TypeScript, no se copia al Python del verificador.
- [`browser_pool.py` interno](../tools/browser_pool.py): ya ofrece `estimated_age_hours`, pero toma **12 horas por defecto si la edad inicial es desconocida**. Esa estimación solo sirve para ranking/filtrado aproximado; nunca convertirla en timestamp verificable de publicación para el guard de texto. Prioridad de reutilización interna antes de añadir bibliotecas.

No se tomó código ajeno ni se agregó paquete: biblioteca estándar + contratos de datos existentes vencen en claridad, dependencias y compatibilidad Windows/Python 3.11. Reutilización futura a través de adaptadores específicos, centralizando el veredicto.

## Validación y límites para Claude

Contratos sintéticos y de reloj fijo: `tests/test_plan_age_provenance.py`, `tests/test_post_age_policy_adversarial.py`, tests de `bluesky_growth_scan`, suites anteriores y matriz `.github/workflows/validate-social-tools.yml`. El identificador/URL del workflow final debe citarse en la conversación de PR **tras** verificarse contra el HEAD final; el verde anterior del 925d44 no valida estos nuevos commits.

La nueva revisión no ejecuta acciones ni importa credenciales. Falta probar el origen temporal de Threads, Facebook, Pinterest y TikTok cuando la plataforma solo ofrece edad relativa; existe trabajo relacionado **#62 «fuente fiable de fecha de publicación»**, mientras **#61** estudia antigüedad multired. No abrir una tercera PR de investigación sobre lo mismo. Antes de transportar el parche al repositorio privado, comparar los builders allí y verificar las colas WEB/API/MOBILE con fixtures procedentes de cada escáner, sin datos reales de cuentas. Revisión real de Edge, TikTok móvil y redes como canario supervisado sigue **pendiente**, no simulada ni demostrada en CI.
