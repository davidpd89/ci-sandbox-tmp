# CI 27 — propiedad fiable del navegador y del Android compartidos

Fecha de contraste: **2026-10-10**. Rama: `research/17-browser-mobile-automation`; base: `research/public-reuse-parent`.

## Problema
El bloqueo Android previo permitía retirar un marcador por TTL aun con propietario vivo y dejaba una carrera entre reclamadores. El resultado era exclusión no garantizada para un mismo teléfono.

## Alternativas
Comparados Playwright/CDP, Appium, UIAutomator2, portalocker y continuidad del bloqueo compartido existente: se conserva Playwright y mobilecli, y se reutiliza el guard OS propio ya probado en Edge.

## Licencias y procedencia
Fuente primaria: https://github.com/davidpd89/ci-sandbox-tmp/blob/4da0584f270bdbec6cf37286cc86396a08e11bab/tools/action_ledger.py
Fecha de consulta: 2026-10-10
Licencia SPDX: NOASSERTION
Referencia inmutable: https://github.com/davidpd89/ci-sandbox-tmp/blob/4da0584f270bdbec6cf37286cc86396a08e11bab/tools/action_ledger.py

La referencia primaria es código del **mismo repositorio**, no material externo relicenciado. GitHub no proporciona una licencia SPDX para ese código propio. Los repositorios externos estudiados se clasifican más abajo, con sus licencias verificadas. No se copia código externo.

## Decisión
Añadir un parámetro de ruta opcional a `action_ledger.exclusive` y usarlo para mobile sin alterar el bloqueo de Edge ni introducir bibliotecas.

## Pruebas
`tests/test_browser_mobile_owner.py` y las suites existentes. Simulación offline de procesos concurrentes, TTL, caída, compatibilidad de marcadores y liberación; CI Ubuntu/Windows Python 3.11.

## Retirada
Revertir las modificaciones de `tools/action_ledger.py` y `tools/mobile_runtime.py`. Detener todos los runners de versiones mixtas antes del cambio; no eliminar `.oslock` durante ejecución.

---

## Diagnóstico basado en código

En el mirror público (`tools/mobile_runtime.py`, antes de este cambio), `mobile_session_lock` escribía `PID:time_ns` con `O_EXCL` y borraba un fichero cuando `age > stale_after` **aunque el PID siguiese vivo**. Una ronda larga o una suspensión del portátil podía liberar Android en falso y autorizar dos workers simultáneos. Dos reclamadores también podían competir entre lectura, `remove` y `O_EXCL`.

El mirror ya contenía `action_ledger.exclusive()` para Edge: guard advisory del sistema operativo mantenido durante todo el turno, serialización de reclamaciones, comprobación de PID/identidad de proceso, protección del marcador y limpieza sin borrar el lock de otro propietario. En el repo oficial `davidpd89/rrss-davidporto-CODE`, rama `integracion/crecimiento-2026-10`, se verificaron además `tests/test_edge_cdp_session_safety.py`, `tools/instagram_mobile_interact.py` y las rutas TikTok mobile. **La implementación oficial no se copió al mirror**: se modificaron solo módulos ya presentes.

## Candidatos públicos y decisión

| Candidato y commit inspeccionado (10/10/2026) | Licencia | Actividad / compatibilidad | Decisión |
|---|---|---|---|
| [Playwright Python `ae494b2`](https://github.com/microsoft/playwright-python/tree/ae494b214c39ade743293e29129dc45b6dcce578) | Apache-2.0 | Push 09-10-2026; Python 3.11/Windows; dependencia ya presente | **Conservar** conexión CDP actual: locators, esperas y tracing son vías de mejora, pero sustituir el control de sesiones no corrige la carrera móvil |
| [Appium Python Client `4a4c46b`](https://github.com/appium/python-client/tree/4a4c46b64812e10885d80db3f60fbea9ea9a7b67) | Apache-2.0 | Push 08-10-2026; versión 5.3.x declara Python 3.11; requiere infraestructura Appium/driver | No integrar: coste de despliegue alto para un único Android con mobilecli funcional |
| [openatx/uiautomator2 `6de6d4c`](https://github.com/openatx/uiautomator2/tree/6de6d4ce6e944998544e3f71aab5dbb31bd663f8) | MIT | Push 05-10-2026; cliente Python y agente Android; exige instalación y mantenimiento en dispositivo | Evaluar para selectores nativos en trabajo independiente; **no** arregla propiedad de sesiones concurrentes |
| [portalocker `c490bea`](https://github.com/wolph/portalocker/tree/c490bea3973b9840a3c18610edac5d00700075dd) | BSD-3-Clause | Push 2026-09-19; Python >=3.10, Windows/Unix; locks exclusivos sin extra de win32 | Patrón apropiado, **no adoptar dependencia**: el guard equivalente ya existe y está ensayado en `action_ledger` |
| [mobilecli `aca77be`](https://github.com/mobile-next/mobilecli/tree/aca77be99c33cce93695f3b4b7c6e7d2cb879875) | Declaración GitHub `NOASSERTION`; revisar licencia del tag antes de copiar | Push 04-10-2026; runtime usado con versión fijada 1.0.17 | Mantener cliente del proyecto; **no copiar** código upstream ni modificar versión |

Se consultaron repositorios, estado de archivo, últimas revisiones y licencias en GitHub. No se incorpora código de terceros: la reutilización seleccionada es **interna al proyecto**, de `tools/action_ledger.py`. No hay nueva dependencia, binario, token, perfil o sesión.

## Cambio implementado

- `action_ledger.exclusive(..., lock_path=...)`: ruta explícita opcional, creación de directorio y parser compatible con `PID:timestamp` heredado. Sin `lock_path`, sigue usando `rrss_lock_<name>.lock` y `RRSS_LOCK_DIR` para el turno de Edge, sin migración de sus marcadores.
- `mobile_runtime.mobile_session_lock`: conserva `MOBILE_SESSION_LOCK`, `DEFAULT_LOCK_PATH`, API pública y excepción `MobileSessionBusy`, pero delega la autoridad exclusiva al mismo guard OS de Edge.
- El fichero `<ruta>.oslock` permanece como coordinación del sistema operativo. **No borrar ese fichero** durante uso normal. El guard permanece abierto durante todo el `with` y queda libre tras caída del proceso.
- El TTL deja de justificar el robo de una sesión viva. El PID antiguo `PID:timestamp` se respeta mientras viva; se reclama si está muerto. Un marcador parcial de menos de 60 s se conserva.
- La migración no cambia acciones ni planificadores: TikTok e Instagram, cuando usan `mobile_session_lock`, coordinan el mismo dispositivo; X/Threads/Pinterest/Reddit/Facebook mantienen `browser_session`; las tres colas WEB/API/MOBILE siguen separadas.

## Medición reproducible: comportamiento antes/después

La métrica prioritaria no es ms de una UI que no tenemos en CI, sino **entradas indebidas al dispositivo** durante un turno vivo. Escenario: un propietario conserva sesión; se envejece artificialmente su marcador (mtime=1) y otro intenta entrar con `stale_after=0`.

| Prueba offline | Versión anterior (evaluación estática de la rama de partida) | Ahora, contrato automatizado |
|---|---|---|
| Recuperación por antigüedad aun con PID vivo | Rama `if age > stale_after: os.remove(path)`: **permitía 1/1 robo** | `test_live_owner_not_stolen_after_expiration`: **0/1** |
| Dos procesos simultáneos | Exclusión de creación `O_EXCL` pero lectura/eliminación sin guard OS | `test_interprocess_contention_then_release`: segundo proceso rechazado |
| Crash sin TTL | Recuperación por PID muerto con carrera de reclamadores | `test_crashed_owner_is_recovered_without_ttl`: adquisición tras caída |
| Migración legado | `PID:timestamp` | `test_legacy_live_pid_colon_marker_is_respected` y `test_legacy_dead_pid_colon_marker_recovered` |

**No se atribuyen** mejoras de velocidad, aumento de conversiones, ni ejecución Android/Edge real: el CI no usa redes ni dispositivos. El coste es un fichero `.oslock` y un lock OS nativo durante la sesión, sin dependencias nuevas.

Para replicar en Windows y Ubuntu con Python 3.11:
```shell
python -m pytest -q tests/test_browser_mobile_owner.py tests/test_mobile_runtime.py tests/test_r8_live_owner_lock.py
```
La suite incluye pruebas de subprocesos, marcadores viejos y corruptos, PID heredado, excepciones, sustitución del fichero y ruta personalizada. Hay CI existente con matriz Windows/Ubuntu; **consultar sus resultados por SHA**. Las pruebas son simuladas y offline, no canarios supervisados.

## Segunda revisión adversarial

1. **Marcador antiguo vivo**: se comprueba el PID, no solo el TTL, incluso si el tiempo del fichero es muy viejo.
2. **Reclamadores concurrentes**: el guard OS permanece durante toda la sesión y no puede entrar un segundo reclamador del mismo recurso; prueba con proceso separado.
3. **Crash y recuperación**: la caída libera el guard OS; el marcador legado se puede reclamar si PID muerto.
4. **Identidad y sustitución**: se conserva el token de nacimiento (si el OS lo facilita); la limpieza no elimina un archivo de otro propietario.
5. **Compatibilidad**: la API móvil, la ruta `MOBILE_SESSION_LOCK`, el contrato `RoundBusy`/ `MobileSessionBusy` y Edge sin ruta personalizada permanecen.
6. **Límites**: proceso de control antiguo que no use guard OS se detecta mediante su PID; un PID reciclado con marcador legacy sin nacimiento puede bloquear por exceso de cautela, nunca autorizar dos sesiones. La coordinación es **por ruta**: workers configurados con rutas distintas para el mismo móvil no se excluirán mutuamente.

## Rollback / adopción

Revertir los dos cambios de código y el test si fallan canarios. El formato `PID time birth` de `action_ledger` es legible en la versión actual; un runtime móvil antiguo lee el PID anterior al `:` y **no** podrá hacerlo con ese formato, por lo que **no mezclar versiones de runners** durante la transición. Detener los workers existentes y arrancar el conjunto actualizado; no borrar locks con proceso vivo. El fichero `.oslock` puede quedar inerte tras rollback.

**Canario pendiente para Claude**: un Windows 3.11 real con Edge CDP compartido, un Android autorizado conectado y dos runners coordinados con la misma ruta de lock. Medir esperas, estados de ocupado, recuperaciones y ausencia de navegación paralela; sin escrituras sociales en este encargo.
