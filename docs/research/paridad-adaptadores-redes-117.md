# PR #117 — puente de contratos de planes nativos en nueve redes

**Fecha:** 10/10/2026. **Rama:** research/perplexity-paridad-adaptadores-redes. **Base:** research/public-reuse-parent. **No merge.**

## Qué se ha verificado

Se contrastó el informe de Perplexity con el repo oficial privado davidpd89/rrss-davidporto-CODE en su rama integracion/crecimiento-2026-10, HEAD **5449513d9b545d0a6a72abf066ab6a779bfdad71** (solo lectura), con el espejo público y con las PR de paridad. Se inspeccionaron directamente los ejecutores bluesky_execute, mastodon_execute, x_execute, threads_execute, facebook_execute, instagram_execute, reddit_execute, pinterest_growth y **tiktok_mobile_execute** (no fiarse del obsoleto tiktok_execute para el flujo móvil).

Hallazgos aplicados:
- Nueve redes usan planes listados, pero tienen vocabularios distintos. Mastodon tiene favourite y boost; Reddit tiene vote; Pinterest tiene react/save; Facebook usa index para objetivos propios; X/Threads usan like_latest. Igualar estas acciones por nombre fabricaría atribución.
- El ejecutor Facebook admite index=0 implícito. El móvil de TikTok exige URL para like/comment, no basta text_fragment. Son dos incompatibilidades descubiertas en la segunda revisión y corregidas.
- Un fragmento de texto, un índice de feed, un handle, reply_to_id o status_id local **no es un ID global de post**. La salida marca target_portable=False. Las URL solo se consideran transportables si son HTTPS y del dominio permitido de esa red (Mastodon admite hosts federados).
- tools/network_capabilities.py en el HEAD oficial sigue enumerando ocho redes. **No se modifica aquí**: la PR #43 ya añade Instagram y corrige su detección de tareas; la #81 añade matriz ejecutable de 63 celdas y la #82 cubre drift. Tampoco se duplica #100 (candidatos), #103 (prioridad) ni #108 (evidencia relacional).

## Investigación y decisión de reutilización

| Fuente y SHA fijado | Licencia contrastada | Actividad observada | Decisión |
| --- | --- | --- | --- |
| [Postiz @ 91c91f6](https://github.com/gitroomhq/postiz-app/tree/91c91f633a0175fb3914dba64c932928c514b72a) | AGPL-3.0 | 09/10/2026, TypeScript | Inspiración de interfaz/proveedor, sin copiar código ni dependencia |
| [Mixpost @ df57648](https://github.com/inovector/mixpost/tree/df57648b866310446703f5294350552b62735df5) | MIT | 16/03/2026, PHP/Vue | No encaja como componente de Python |
| [social-media-kit @ f18aa88](https://github.com/terrytangyuan/social-media-kit/tree/f18aa88fb9020666a1efcffd12aada372547490c) | MIT | 13/01/2026, TypeScript | No cubre nueve redes, no se incorpora |
| [AdsLibrary @ 1ead5b3](https://github.com/soxoj/AdsLibrary/tree/1ead5b3b6b055901233059f02c203ce38c1beb53) | Metadatos sin SPDX; archivo Licensce.txt con texto de permiso tipo MIT y copyright no coincidente | 12/07/2026, Python | **Patrón aplicado** de AdSource/SourceCapabilities de AdsLibrary/core/base.py; implementación nueva propia sin copiar fuente ajena ante dudas de procedencia |
| [atproto @ 4c17895](https://github.com/MarshalX/atproto/tree/4c17895c97f6d42ecb9c41dc5c2fb450ab9c6ac8) | MIT | 02/10/2026, Python >=3.9,<3.15, clasificador OS-independent | SDK viable para Bluesky, pero sería un cambio de cliente ya existente: reservar a #11 |
| [RESPX @ 57d8c29](https://github.com/lundberg/respx/tree/57d8c29705fdbbaeb5cd216f1ea3bb0386d7ba16) | **BSD-3-Clause** (corrección al informe) | commit 23/04/2026; setup.py Python >=3.8 y OS-independent | Adecuado para mocks HTTPX; aquí no hay transporte HTTPX que simular, no añadir dependencia |
| [Flare @ 834353b](https://github.com/DimensionDev/Flare/tree/834353b116db4e718dbdcb6c9c65723f673a52b1) | AGPL-3.0 | 09/10/2026, Kotlin | No reutilizar código |
| [socialmediascheduler @ 27d0dcc](https://github.com/Masterjx9/socialmediascheduler/tree/27d0dcc1c50524a161ddf78f41d6a13a491487c4) | MIT | 05/04/2026, TypeScript | Calidad/cobertura insuficiente frente al proyecto actual |

No se copian líneas de ningún repositorio externo. Se reutiliza la **separación de capacidades declaradas y modelo normalizado** de AdsLibrary, y se conservan los clientes y flujos probados del propio proyecto. La dependencia de producción añadida es **cero**.

## Código integrado en esta PR

- tools/social_plan_contract.py: dataclasses inmutables de capacidades, acciones, incidencias y resultados; ReadOnlyAdapter como Protocol; AdapterRegistry con rechazo de duplicados; nueve PlanAdapter de lectura; proyección con familia y kind nativo sin colapsar semánticas; marcador de identidad portable; observación de resultados con éxito solo para confirmado/publicado **exactos**. Errores desconocidos nunca implican reintento seguro.
- CLI puramente local para diagnosticar un plan JSON existente. Devuelve solo agregados (red, número de acciones, incidencias, kind y objetivos sin identidad portable); nunca publica el texto de comentarios ni objetivos.
- tests/test_social_plan_contract.py: 14 tests con fixtures sintéticos que abarcan las nueve redes, casos positivos/negativos, sinonimia falsa, tipos incorrectos, texto vacío, identidad contextual, URLs no fiables, resultados no confirmados y salida sin datos identificables.

Ejecutar desde la raíz:
    
    python -m pytest -q tests/test_social_plan_contract.py
    python -m compileall -q tools/social_plan_contract.py tests/test_social_plan_contract.py
    python tools/social_plan_contract.py bluesky RUTA_LOCAL_A_PLAN_FINAL.json

El CLI devuelve 0 si el plan fue interpretable íntegramente, 1 si hubo incidencias y 2 para archivo/JSON/esquema inválido. **No es un preflight para permitir escrituras** ni certifica que la API/navegador acepte el destino; los ejecutores conservan sus propios gates.

## Resultados y revisión adversarial

Punto de partida: cero puentes homogéneos de **planes finales nativos** en la base de la PR; la matriz actual trata cableado/presencia de capacidades, no traducción de planes. Nuevo estado: nueve proyectores offline y un resultado normalizado de observación, preservando vocabulario y procedencia.

**Pruebas locales del prototipo equivalente:** 14 tests aprobados (Python 3.13/Linux, 35 subtests), sin conexiones externas. En la última pasada se añadieron pruebas de falso dominio (bsky.app.evil.example), bool como index, status no confirmado y requerimiento URL móvil. La validez Windows/Python 3.11 se infiere de la sintaxis/stdlib, **no se acredita como ejecutada** sin CI de ese HEAD. No se probaron la suite completa del repo privado, Edge/CDP, Android/ADB ni sesiones reales.

**Tercera revisión:** comprobada la lista estricta de acciones de TikTok móvil y el default de índice de Facebook contra sus ejecutores oficiales; desestimada la sugerencia de sustituir el core por Postiz o de agregar RESPX a tests que no envían HTTP. No se añaden mecanismos de programación ni se llaman APIs.

## Integración y rollback

El módulo es un **puente de lectura opt-in**; no está conectado a los nueve procesos de ejecución ni transforma planes en comandos. Claude podrá consumir project() desde el ranking y observe() desde un adaptador de logs, conservando las tres colas WEB/API/MOBILE y el bloqueo/validación propios de cada ejecutor. La importación del módulo no crea archivos ni abre sesiones. Para revertir, eliminar solo tools/social_plan_contract.py, tests/test_social_plan_contract.py y este documento; no hay migraciones ni datos persistidos.

Pendiente solo de Claude: verificaciones CI Windows/Ubuntu Python 3.11 sobre el HEAD, suite completa privada, revisión de fuentes reales de salida por red, Edge y Android bajo supervisión. **No hay publicación, like, comentario, follow ni merge**.
