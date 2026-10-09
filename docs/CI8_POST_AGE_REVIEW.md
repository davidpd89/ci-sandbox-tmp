# CI #8 — Antigüedad de destinos: revisión técnica y evidencia (09/10/2026)

## Alcance y fuentes

PR #8, exclusivamente en `ci/post-age-policy`, base `ci/test-campaign-parent`. La política de partida de `tools/post_age_policy.py` se cotejó con `davidpd89/rrss-davidporto-CODE` en `integracion/crecimiento-2026-10`: **blob SHA 0c9f99fe12bd8447dfcfbe11dfb890b44e071852 idéntico** antes de estos cambios. `tools/conversation_turn_policy.py` importa la política de edad como punto común antes de aplicar el contrato de hilo. Se revisaron los nueve ejecutores del mirror (X, Threads, Facebook, Pinterest, Reddit, Bluesky, Mastodon, TikTok móvil e Instagram) y `reddit_comments.py` para su segunda acción de comentario.

No existe `docs/open-source-scouting/PROTOCOL.md` en esta rama al consultar GitHub: 404. Se utilizó el protocolo de CI existente en `docs/CI_TEST_CAMPAIGN.md`; este faltante no impide la implementación.

El trabajo es **simulado y offline**. Cero acciones en redes, credenciales, datos personales o cambios sobre el estado operativo real. Ningún merge.

## Hallazgos corregidos

1. **Fecha del encolado confundida con antigüedad del destino (alta):** el valor `created_at` de la raíz podía dar un resultado `edad_ok` para acciones como `repost` o `like` y ocultar un X snowflake antiguo. Ahora **ni `created_at` ni `createdAt` raíz certifican antigüedad en ninguna acción**. Las fechas `target_created_at`, `post_created_at` y las fechas propias de `post`/`record` siguen admitidas; las formas inequívocas de proveedor `created_utc`, `create_time`, `created_time`, `published_at` se conservan. Adaptadores que entreguen `createdAt` plano deben pasarlo como `post_created_at` o `record.createdAt`: posible trabajo de integración para Claude.
2. **Identificador auxiliar oculta el destino (media):** `_target_ref` priorizaba `status_id` incluso en X/Bluesky; una notificación con ID no decodificable podía impedir recuperar la edad de la URL del post. Ahora se seleccionan los campos en orden específico por red y se prueban referencias sucesivas hasta lograr una fecha.
3. **TID no conforme (baja):** se valida el primer carácter del TID ATProto según el formato vigente (13 caracteres y prefijo restringido). Un TID inválido no autoriza una respuesta.
4. **Bypass de Reddit en hilos propios (alta):** `run_replies` utilizaba `reply_in_thread` sin el control temporal de `reddit_execute`. Se extrae `created-timestamp` (con alternativa `time[datetime]`) del comentario entrante, se conserva como `post_created_at` en el plan y se llama al gate común **dentro de `reply_in_thread` y antes de abrir el editor**. Solo las respuestas recientes de follow-up (7 días), con contenido entrante y sin cierre social, pueden continuar. El script de Reddit deberá verificarse sobre Edge real porque el DOM puede variar.
5. **Desvíos de planificación/comentario secundario Reddit (alta):** `build_plan` descartaba el timestamp del post antes de llegar a `reddit_execute`, provocando `edad_desconocida` y perdiendo volumen útil. Ahora propaga el campo, y no gasta trabajo de redacción en fechas desconocidas. Además, `_publish_profile_comment` enviaba un objeto sin `kind` a `check_execution`, saltándose el límite; ahora declara `kind=comment` y la antigüedad se comprueba también allí.
6. **Regresión fija en todas las redes:** `tests/test_post_age_policy_adversarial.py` añade pruebas de contaminación por fecha de cola, fuentes anidadas, referencias auxiliares, TIDs falsos, límites exactos de 3/7/21 días, follow-up de 7 días, timestamps futuros/inválidos y resúmenes agregados sin texto. `tests/test_reddit_age_contract.py` agrega siete casos de propagación, ruta directa, fechas ausentes, ruta de perfil y extracción DOM, sin navegador conectado.

## Evaluación de código público a fecha de hoy

| Candidato | Evidencia | Licencia / mantenimiento / integración | Veredicto |
| --- | --- | --- | --- |
| [MarshalX/atproto](https://github.com/MarshalX/atproto) — ATProto Python | TID y modelos de records; último commit consultado 02/10/2026; [versión PyPI 10/09/2026](https://pypi.org/project/atproto/) | MIT, Python >=3.9 y <3.15, portable a Windows y Python 3.11; SDK extenso con dependencias y superficie de red | **Referente de estructuras**, no incorporar un cliente y dependencias al verificador offline para descodificar 13 caracteres. |
| [AT Protocol — TID](https://atproto.com/specs/tid) | Especificación canónica del alfabeto, 13 caracteres y prefijo válido | Especificación, no biblioteca copiada | Se adapta el **contrato** de validación; implementación local trivial, sin copiar código. |
| [snowflake-id](https://pypi.org/project/snowflake-id/) | Paquete estable generador/lector genérico, lanzamiento 1.0.2 (sin evidencia de revisión reciente equivalente a SDK ATProto) | MIT, Python 3.8–3.12 / Windows 3.11 compatible en principio; su epoch y bit-layout **no son** automáticamente los de X | No añadir dependencia para dos operaciones de desplazamiento: la continuidad local gana por menor acoplamiento. |
| [Mastodon docs](https://github.com/mastodon/documentation/blob/main/content/en/api/guidelines.md) | IDs opacos; pueden representar estados federados llegados con demora | Fuente oficial, no biblioteca copiada | **No usar ID de Mastodon como fecha fiable del contenido**. Conservar fecha de API. |

No se ha trasladado código de terceros; no hay licencia incorporada ni obligación de atribución de fragmentos copiados. Las referencias son de especificación/comparación. No se introducen dependencias: compatible con Windows y Python 3.11 por biblioteca estándar.

## Contrato operativo

- `comment`, `reply`, `quote`: 3 días; follow-ups a mensajes entrantes, 7; `repost`/`boost`: 7; `like`/`react`/`vote`: 21.
- `follow`: no tiene destino-post y no lleva límite de antigüedad. La política de X de **no auto-like** debe seguir tratándose en su PR propia (#53), sin ampliar el alcance de #8.
- Sin fecha: respuestas/texto devuelven `edad_desconocida` y no se envían; reacciones no textuales conservan compatibilidad y deben contar como desconocidas, **no** como frescas confirmadas. Esta elección evita inventar fechas o vaciar por completo las colas.
- En X el snowflake del post puede dar el tiempo del ID; en Bluesky el TID sirve para identificar viejos, pero un TID nuevo **no certifica** un reply sin fecha explícita. El shortcode de Threads es estimación empírica no documentada; no debe tratarse como certeza independiente de los datos de plataforma.

## Segunda revisión adversarial

1. **¿Puede una cola creada hoy rejuvenecer un post de hace dos meses?** Reproducido y corregido para `created_at` y `createdAt` en la raíz; test fijo de reply/repost/like.
2. **¿Puede la referencia auxiliar tapar un snowflake viejo de la URL?** Corregida selección/fallback; test con `status_id` no decodificable y URL vieja.
3. **¿Sirve cualquier rkey de 13 caracteres como TID?** No: se verifica el prefijo del estándar; prueba con `kkkk...`.
4. **¿Qué ocurre exactamente en el umbral y un segundo después?** Pruebas sin reloj del sistema; a igualdad del umbral se admite, un segundo después se clasifica antiguo.
5. **¿Se preserva fidelización sin necroposting?** Ventana de follow-up 7 días comprobada en las nueve redes; sigue sujeta a validación de conversación en `conversation_turn_policy`.
6. **¿Puede pasar texto sin fecha por una red menos probada?** El chequeo compartido rechaza unknown text; las pruebas de fuentes anidadas y fechas inválidas abarcan todas las redes.
7. **¿Estamos validando la acción real o solo el texto de su invocación?** El test preexistente de ejecutores es parcialmente **estático**. El bypass concreto de Reddit se corrigió con tests que prueban que no se alcanza ninguna interacción de navegador en fechas inválidas. El CI offline cubre ejecutores con mocks, pero no equivale a canario móvil/Edge ni a demostración de que cada futura ruta secundaria llamará siempre a `check_execution`.
8. **¿Desplazamos deuda a otra PR?** No duplicar [#61](https://github.com/davidpd89/ci-sandbox-tmp/pull/61), ya dedicada a investigación general de paridad de antigüedad. El orden de merge de #8 y #61 requiere revisión por Claude.

## Validación y límites de aceptación

Workflow: `.github/workflows/validate-social-tools.yml`, Python 3.11 en la matriz disponible, compila `tools`/`tests` y ejecuta pytest offline con exclusiones de la campaña. Evidencia específica del nuevo HEAD y conclusión se adjuntará al comentario final de la PR; **no inferir resultado verde por que el job esté lanzado**.

Pendiente para Claude: Windows 3.11 real, Edge, móvil TikTok, fuentes de tiempo plano que los productores necesiten transformar a `post_created_at`, códigos de `saltado_*` y colas independientes WEB/API/MOBILE bajo concurrencia real. La ejecución en entorno CI no sustituye un canario supervisado sin escritura automática. No tocar cuenta oficial ni copiar este cambio al repo privado antes de revisión. No se garantiza cobertura absoluta.
