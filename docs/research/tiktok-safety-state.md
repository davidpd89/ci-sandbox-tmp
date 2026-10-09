# PR #7 — Estado seguro e idempotencia en TikTok

Fecha de revisión: 2026-10-09.

## Alcance

Esta PR valida y corrige únicamente la barrera de seguridad local de TikTok y el
flujo de follow móvil del mirror. No publica, sigue, responde ni borra nada en
TikTok durante las pruebas. No usa cuentas, credenciales, cookies, móvil real ni
datos reales.

Contratos comprobados:

1. una revisión manual no desaparece al vencer el cooldown;
2. un JSON ilegible o semánticamente inválido falla cerrado y se conserva;
3. si falla `os.replace`, el estado anterior permanece intacto;
4. una acción que pudo ocurrir se registra antes del tap y no se reintenta tras
   un crash;
5. el uso diario se deduplica por acción/objetivo y por `intent_id`;
6. una alerta de falta de progreso no prolonga la sesión.

## Contexto leído

La PR partía del commit `43e6f3e028497fdbd2dfac7becd443137426987f`.
El mirror no contenía antes `tools/tiktok_safety.py`, por lo que se contrastó
la implementación con el repositorio oficial privado
`davidpd89/rrss-davidporto-CODE`, rama
`integracion/crecimiento-2026-10`.

Blobs oficiales consultados durante esta revisión:

- `tools/tiktok_safety.py`:
  `761b8a55553d1101599da39859690ab3e5b4b3a5`;
- `tools/tiktok_bulk_follow.py`:
  `f9a40fbac651f24dfe42b9f09187ee907c2131fe`;
- `tests/test_tiktok_safety.py`:
  `535ec93cf1c50d1dff7baa58c5938eacac6aafac`.

La ruta `docs/open-source-scouting/PROTOCOL.md` no existe en la rama de esta
PR ni en `ci/test-campaign-parent`. Para cumplir el mandato de reutilización se
leyó la versión de la campaña de investigación presente en
`research/09-tiktok`, blob
`b0499c112471d4889b860d6c31dbf05a24ce8329`.

Mientras se trabajaba, `ci/test-campaign-parent` avanzó con el commit
`087087b46ee7d36836282157b9e89848fdf157fa`, que solo indexa las PR de la
campaña en `docs/CI_TEST_CAMPAIGN.md`. No toca los archivos de esta PR y GitHub
sigue marcándola como mergeable; no se incorporó ese commit ajeno al alcance.

## Fallos encontrados y corrección

### 1. El camino real podía ignorar un estado corrupto

El `cooldown_left()` histórico capturaba `ValueError/OSError` y devolvía
cero. Por tanto, un JSON roto podía interpretarse como «sin pausa» aunque
`tiktok_safety` pretendiera fallar cerrado.

Se eliminó esa semántica duplicada: `cooldown_left()` y
`start_cooldown()` delegan ahora en la barrera compartida. El `main()`
distingue `SafetyBlocked` de `SafetyStateError` y no toca el móvil en ninguno
de los dos casos.

### 2. Un follow-limit podía degradar una revisión manual

La primera versión de `_restrict_follow()` respetaba una pausa global solo
mientras `until` siguiera en el futuro. Si había `manual_review=true`, el
plazo vencía y después llegaba un `follow_limit`, podía sustituirse el estado
global por una pausa solo de follows sin revisión manual.

Ahora `manual_review=true` tiene prioridad permanente hasta una intervención
explícita. Un `follow_limit` posterior no reescribe ese estado. Además,
`manual_review` con un tipo distinto de booleano/null se considera corrupción,
no una falsedad permisiva.

### 3. El scope podía ocultar corrupción semántica

La segunda revisión detectó que un estado JSON bien formado con
`scope="follow"` y un `until` inválido podía permitir likes/comentarios:
la excepción se evitaba al devolver antes de interpretar la fecha.

`_read()` valida ahora de entrada `until`, `day` y `strikes`, además de
`scope` y `manual_review`. Un estado semánticamente imposible falla cerrado
con independencia del tipo de acción solicitado. También se rechaza un
`pendiente_aprobacion` sin objetivo.

### 4. Existía una ventana de duplicación entre tap y registro

En la rama inicial se hacía primero `nav.c.tap(...)` y el CSV se escribía solo
si la UI confirmaba «Siguiendo». Si el proceso, el móvil o el transporte fallaba
después del tap pero antes de confirmar, el siguiente arranque no tenía memoria
del intento y podía repetirlo.

Se introdujo `tap_reserved_follow()` en las tres rutas
(`followers`, `mutual`, `followback`):

1. genera `intent_id`;
2. escribe y hace `fsync` de `pendiente_verificacion`;
3. añade el objetivo al conjunto local de no-reintento;
4. solo entonces ejecuta el tap;
5. una confirmación posterior cierra el mismo `intent_id`.

Si el tap queda incierto, el pending se conserva y bloquea el replay. Si falla
la escritura previa, el tap no se ejecuta.

### 5. El éxito en memoria podía adelantarse al ACK persistente

`Session.ok()` actualizaba contadores/conjunto antes de escribir el registro.
Ante un fallo de disco, la ejecución actual podía parecer exitosa sin ACK
durable.

Ahora escribe el cierre primero. Solo después incrementa `followed` y actualiza
`done`. El pending anterior sigue siendo la fuente conservadora si el ACK
falla.

### 6. Estado y cuota podían cambiar mientras se esperaba el lock móvil

El preflight anterior se calculaba antes de `mobile_session_lock()`. Otra fase
podía consumir cuota o activar una restricción durante la espera.

Tras adquirir el lock se revalidan: barrera compartida, CSV, objetivos ya
intentados y presupuesto. Las señales terminales se convierten en estado local
antes de liberar el lock.

### 7. Compatibilidad de cierres

El plegado de intents acepta `pendiente_aprobacion` como cierre de follow
privado y lo cuenta una sola vez en la fecha de apertura. La revisión
adversarial detectó además que ese estado no estaba en `followed_before()`:
una solicitud privada ya enviada podía dejar de formar parte del conjunto
histórico de no-reintento al día siguiente. Ahora también se conserva como
objetivo ya intentado.

## Reutilización pública evaluada

| Candidato | Evidencia fija | Licencia | Estado a 2026-10-09 | Windows / Python 3.11 | Coste y seguridad | Decisión |
| --- | --- | --- | --- | --- | --- | --- |
| `wolph/portalocker` | commit `c490bea3973b9840a3c18610edac5d00700075dd` — https://github.com/wolph/portalocker/commit/c490bea3973b9840a3c18610edac5d00700075dd | BSD-3-Clause | Activo; 4.4.0 preparado el 2026-09-19 | Declara Windows y Python 3.11; base sin dependencias obligatorias | Buen candidato si varios procesos deben bloquear el mismo fichero; añade una abstracción que esta PR no necesita porque el writer móvil ya se serializa con `mobile_session_lock` | No adoptar aquí. El problema general de locks/concurrencia ya está cubierto por PR #39/#26 y el CSV multiproceso por #5 |
| `untitaker/python-atomicwrites` | commit `4183999d9b7e81af85dee070d5311299bdf5164c` — https://github.com/untitaker/python-atomicwrites/commit/4183999d9b7e81af85dee070d5311299bdf5164c | MIT | Archivado y declarado «Unmaintained» desde 2022 | Documenta Windows, pero reconoce garantías limitadas | Su propio README recomienda `os.replace`/`os.rename` de Python 3 para la mayoría de casos; el patrón de temp en el mismo directorio + fsync + replace coincide con la solución ya presente | No añadir dependencia ni copiar código. Se mantiene stdlib |
| `grantjenks/python-diskcache` | commit `ebfa37cd99d7ef716ec452ad8af4b4276a8e2233` — https://github.com/grantjenks/python-diskcache/commit/ebfa37cd99d7ef716ec452ad8af4b4276a8e2233 | Apache-2.0 | No archivado, pero el último commit del repo localizado es 2024-03-03 | README declara Windows; matriz publicada llega explícitamente hasta Python 3.10 | Introduce SQLite/filesystem y una superficie mucho mayor; además existen PR abiertas sobre CVE-2025-69872 relacionadas con deserialización pickle (#361/#363/#364) | Rechazado para un estado JSON pequeño y auditable |

No se ha copiado código de esos proyectos. La elección es conservar la solución
stdlib y portar únicamente comportamiento ya existente en el repositorio
oficial RRSS. No hay una licencia de terceros que incorporar a los fuentes de
esta PR.

## Pruebas

Workflow del mirror:
https://github.com/davidpd89/ci-sandbox-tmp/actions/workflows/validate-social-tools.yml

Se ejecuta exactamente el workflow offline, sin red hacia redes sociales:

- `python -m compileall -q tools tests`;
- suite completa de pytest con las ocho exclusiones conocidas del mirror;
- matriz Ubuntu + Windows, Python 3.11.

La matriz verde inmediatamente anterior al último ajuste de no-reintento fue
https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/37980823809:

- Ubuntu: **1707 passed, 8 skipped, 8 deselected, 2 warnings,
  668 subtests passed**;
- Windows: **1710 passed, 5 skipped, 8 deselected, 2 warnings,
  668 subtests passed**.

El resultado del HEAD definitivo se deja también en la revisión/conversación de
la PR para no modificar este archivo después de cada ejecución y crear una
cadena infinita de runs por commits solo documentales.

Las regresiones nuevas cubren, entre otras cosas, crash después del write-ahead,
ACK con fallo de disco, downgrade de revisión manual, corrupción semántica
aunque el scope permita otra acción, cooldown corrupto, deduplicación de intents,
`pendiente_aprobacion`, no-retry de follow privado, las tres rutas de follow y
deadline inmutable ante la alerta de no progreso.

## Segunda revisión adversarial

Se volvió a leer el diff completo como si fuera una revisión independiente.
Los defectos detectados en esa pasada fueron la degradación de
`manual_review`, la ventana tap→registro, el orden memoria→ACK, la falta de
revalidación bajo lock, el bypass de una fecha inválida por `scope=follow` y
el posible reintento de `pendiente_aprobacion`. Todos tienen regresión
específica y están corregidos.

Riesgos residuales que esta PR no puede demostrar:

- GitHub Actions valida Windows real de runner, pero no la estación Windows,
  Edge ni el Xiaomi usados en producción.
- No se ejecutó canario móvil ni una cuenta de TikTok: por mandato, todas las
  pruebas son sintéticas/offline.
- `fsync` del fichero temporal + `os.replace` protege frente a fallos de
  proceso y reemplazos fallidos; no se promete durabilidad absoluta frente a
  pérdida física de energía/controladora. `python-atomicwrites` tampoco ofrece
  una garantía universal en Windows.
- El read-modify-write del JSON no incorpora un lock de fichero propio para
  escritores externos al lock móvil. Investigar la concurrencia global no se
  duplica aquí porque ya existen las PR #39 (carreras/deadlocks), #26
  (colas/idempotencia/recuperación) y #5 (CSV multiproceso).

## Retirada / rollback

No hay dependencia ni migración de formato obligatoria. Para retirar este
cambio se pueden revertir los commits de esta PR. Las filas con `intent_id`
siguen siendo CSV legible y el parser mantiene compatibilidad con filas legacy
sin ID. No se debe borrar un `pendiente_verificacion` como parte de un rollback:
su conciliación debe ser explícita porque representa una acción potencialmente
ejecutada.

## PR adicionales

No se abre ninguna. Los huecos derivados tienen ya trabajo abierto y específico:
#19 (reutilización pública TikTok), #26 (idempotencia/recuperación), #39
(concurrencia) y #5 (CSV multiproceso). Crear otra PR duplicaría alcance.

## Tercera revisión independiente — correcciones de control (09/10/2026)

- El campo `manual_review` pasaba la validación si era `0`, `1`,
  `0.0` o `1.0` por la igualdad booleana implícita de Python. Un `1`
  se podía interpretar como valor permitido sin activar la revisión manual
  (se comprueba `is True`). Ahora se exige el tipo `bool` real y se
  prueba con JSON numérico.
- El presupuesto de la sesión se comprobaba contra `followed` (ACK
  confirmados), pero no contra las reservas previas al tap. Tras un intento
  incierto, se podía abrir otra intención aunque el presupuesto fuera uno.
  Ahora `attempted` cuenta las reservas persistidas y limita la sesión;
  `followed` sigue siendo la métrica de éxito, no de consumo.
- El bulk tenía un `COOLDOWN_PATH` independiente que ignoraba el override
  `RRSS_TIKTOK_COOLDOWN_PATH` utilizado por la barrera y otras rutas.
  Usa el mismo valor importado desde `tiktok_safety`, con regresión offline.

Estas correcciones se limitan al alcance de la PR y preservan el formato del
CSV. Se validan con regresiones offline y CI; un canario móvil y la aplicación
en otras redes siguen fuera de alcance. Para evolución común consultar las PR
#5 (CSV multiproceso), #26 (idempotencia) y #39 (concurrencia). SQLite dispone
de transacciones atómicas y `portalocker` de locks multiplataforma, pero
introducirlos aquí sin migración de todos los escritores dividiría el contrato;
se propone evaluar una interfaz común de reserva-ACK con adaptadores por red.
