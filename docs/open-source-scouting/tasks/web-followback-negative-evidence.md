# Evidencia negativa verificable de followback en X y Threads

Origen: auditoría independiente PR #57, 2026-10-10. **Encargo autónomo de implementación, no autorizado para merge automático.**

## Defecto reproducible en el código existente

* `tools/x_interact.py:follows_me()` devuelve `False` cuando no aparece
  `[data-testid="userFollowIndicator"]`, incluso con perfil parcial.
* `tools/threads_interact.py:profile_info()` devuelve
  `follows_me=False` por ausencia de la línea «Te sigue», aunque esa
  ausencia no prueba necesariamente un negativo.
* `unfollow_cleanup.run()` exige `False` booleano antes de dejar de
  seguir; sirve únicamente si los adaptadores nunca transforman
  `unknown` en `False`.

## Entrega obligatoria

1. Contrato común de lectura trivalente `True | False | None`
   (o estructura `{value, evidence, complete, account_id, observed_at}`),
   con identificador del perfil verificado y fuente de observación.
2. Para cada red, documentar qué evidencia nativa permite **certificar**
   el negativo. Si no existe, devolver `None` y no ejecutar unfollow.
   No interpretar ausencia de selector, DOM incompleto, error de login,
   página redirigida o conteo ausente como negativo.
3. Implementar adaptadores X/Threads aislados de la lógica común, con
   snapshots HTML falsos y tests Playwright offline (sin navegador real):
   positivo, negativo certificado, desconocido, login, perfil equivocado,
   selector cambiado, scroll parcial y error de lectura.
4. Conectar `unfollow_cleanup` conservando el cortacircuitos
   `circuit_breaker.write_preflight` del repo oficial, sin copiar módulos
   privados completos ni modificar estado real.
5. Métrica de cobertura honesta: redes con lectura negativa certificada,
   positivas y desconocidas; los desconocidos no cuentan como negativos.
6. Matriz de Ubuntu/Windows Python 3.11 en CI y runbook para una inspección
   supervisada Edge con cuentas de prueba **sin acciones de follow/unfollow**.
7. Documentar opciones públicas maduras para selectores/esperas y contrato
   (referencias inmutables, licencias, mantenimiento), rollback y medida
   antes/después del falso negativo en fixtures.

## Evitar duplicación

- #57: proyección offline del ciclo y corrección `follow+reply`; no aborda
  la autenticidad de las señales negativas del DOM.
- #108: puente de evidencias hacia ledger #84, no garantiza por sí mismo
  que la observación cruda WEB sea fiable.
- #41/#42: investigación general sobre drift de API/selectores, no
  implementación específica del negativo destructivo.
- #58/#60: reconciliación y máquina de estados; reutilizar su contrato,
  no añadir otra máquina de relaciones.

**Criterio de aceptación:** 0 unfollows autorizados por negativos obtenidos
exclusivamente de ausencia de indicador; ninguna regresión de positivos,
identidad correcta y tests diferenciales X/Threads/otros adaptadores. Sin
sesiones ni claves en fixtures, sin ejecutar acciones reales.
