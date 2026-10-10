# X — reutilización pública: decisión de continuidad tras sincronizar la base

**Revisión:** 2026-10-10 · **PR:** [#13](https://github.com/davidpd89/ci-sandbox-tmp/pull/13) · **Base de reconstrucción:** `research/public-reuse-parent@250ccb019fb8683311df48c7d02d6c6d2b73a47b`.

Esta PR **no reemplaza el ejecutor de X**. La investigación anterior nació cuando el espejo no contenía el código operativo vigente. La base ya incorporó `tools/` y `tests/` del repositorio oficial; el controlador y Claude detectaron que portar el antiguo `x_execute.py` degradaría protecciones. La corrección adecuada es **descartar esos cambios** y conservar investigación aplicable y una prueba de compatibilidad entre componentes existentes. La historia anterior permanece disponible en los SHAs y comentarios de la PR, pero no forma parte del diff propuesto.

## Problema

El antiguo diff de #13 introducía `x_pending_guard.py` y modificaba `x_execute.py` para detener escrituras tras resultados remotos inciertos, añadir `fsync`, filtrar por alias y mantener cuarentena CSV. Sobre la base **anterior** solucionaba errores; sobre la **actual** era una implementación redundante y, en algunos puntos, regresiva:

- `tools/x_execute.py` vigente (blob `a808b848c553239aa30073392c509b8c888dac29`) detiene el resto ante `quote=unverified` y `XWriteUnverified`, distingue `possible_write` tras un tap y separa errores previos. Conservar `circuit_breaker`, `x_automation_policy` (ningún auto-like), `reply_writer` y `_pool_post_status`.
- `_append_registro` valida cabecera preexistente y ya escribe con `flush()` y `os.fsync()`. A diferencia del guard antiguo, `x_acquisition_audit.read_history` bloquea cuando falta o está dañado el CSV (`HistoryReadError`) y el CLI filtra por historial **antes de abrir Edge**.
- El contrato POST→ACK→TTL, los certificados de las rutas y el ledger del repositorio privado no pueden sustituirse por un CSV paralelo. Dos procesos o un crash entre tap y persistencia requieren un mecanismo durable aparte.

**Comparación contra el oficial:** se contrastó la rama privada `integracion/crecimiento-2026-10` por el conector de GitHub. Se comprobó que el blob operativo de `x_execute.py` coincide con el incorporado al espejo sincronizado. Claude confirmó que la corrección de alias X ya fue incorporada al privado mediante `a2ad6a78`, originada en [#171](https://github.com/davidpd89/ci-sandbox-tmp/pull/171) (PR cerrada sin merge al espejo). **No duplicar #171**: su despliegue y futura sincronización de la base son responsabilidad del integrador.

## Alternativas

| Estrategia | Evidencia / encaje | Decisión |
| --- | --- | --- |
| A. Reaplicar el guard y el ejecutor originales de #13 | No entiende bien la diferencia entre fallo certificado antes del tap y `XWriteUnverified`; podría permitir registro inexistente y perder políticas del privado | **Descartar** |
| B. Cambiar ahora CDP por Tweepy 4.17.0 | MIT, Python ≥3.9, wheel universal, mantenimiento/release 2026-07-02; API distinta, sin exactly-once | No necesario |
| C. Cambiar ahora CDP por XDK oficial Python | MIT, paquete 0.10.x Alpha; Python ≥3.8, `requests`, `requests-oauthlib` y `pydantic`; integración OAuth y API separada | No necesario |
| D. Introducir `sqlite-durable-workflow` como outbox | MIT, v0.2.0, API 0.x, componentes para lease/fencing y `DeliveryUnknownError`. Proyecto muy nuevo, con historial/comunidad reducidos y verificación Windows aún pendiente | Candidato para evaluación aislada; **no dependencia de esta PR** |
| **E. Conservar la implementación sincronizada** | Ya dispone de separación de fase, registro durable hasta `fsync`, historial que falla cerrado, deduplicación y filtros; sin dependencia nueva | **Elegida** |

El cliente Node [node-twitter-api-v2](https://github.com/PLhery/node-twitter-api-v2/tree/f185e7ee8060a394e5ea1d7b62b52e9600156dcf) (Apache-2.0) añadiría runtime Node al pipeline Python 3.11; tampoco resuelve el ACK ambiguo. [Durable Workflow Python](https://github.com/durable-workflow/sdk-python) podría orquestar tandas mayores, pero sería una migración independiente. En los casos evaluados **no se copia código OSS ni se añaden dependencias**.

## Licencias y procedencia

Fuente primaria: https://github.com/tweepy/tweepy
Fecha de consulta: 2026-10-10
Licencia SPDX: MIT
Referencia inmutable: N/A (sin codigo incorporado)

Referencias examinadas: [Tweepy v4.17.0, commit c1978d6](https://github.com/tweepy/tweepy/tree/c1978d643ecce491929084e4290b35f57e4921ad); [XDK Python (pyproject)](https://github.com/xdevplatform/xdk-python/blob/main/pyproject.toml) (MIT, Alpha); [sqlite-durable-workflow v0.2.0](https://github.com/eatdrop/sqlite-durable-workflow/tree/v0.2.0) (MIT, 0.x); [Node client](https://github.com/PLhery/node-twitter-api-v2/tree/f185e7ee8060a394e5ea1d7b62b52e9600156dcf) (Apache-2.0). La actividad pública no equivale a compatibilidad probada ni a idempotencia operativa. Windows/Python 3.11 de SDKs descartados no se ha ejecutado localmente; Tweepy declara wheel universal, XDK declara Python 3.11. Sin redistribución de terceros.

## Decisión

**Conservar el código actual y retirar del diff los duplicados**, sin nuevo guard CSV, nueva máquina de estados, modificación del ejecutor ni cambios al ledger/TTL. Se mantiene un test de integración offline que atraviesa el escritor **real** del CSV (`x_execute._append_registro`) y el lector/filtro **real** (`x_acquisition_audit.read_history/filter_known_plan`):

- Quote con `pendiente_verificacion` persistida: distinto `kind`, mismo ID → omitido; otro post → elegible.
- Follow incierto y `like_latest` incierto: la identidad por cuenta evita un replay sin bloquear otras cuentas.
- `no_intentado` o `parada:` antes del tap: no se falsea un ACK, no se consume candidato.
- `saltado_ya_comentado` observado: el historial impide una respuesta repetida sin atribuir una escritura nueva.
- Historial inexistente: error explícito, no un conjunto vacío permisivo.

El test no abre navegador, no usa perfiles de producción y no añade rutas de escritura. Aporta una **prueba entre módulos reales**, frente a las antiguas extracciones AST aisladas.

## Pruebas

`python -m compileall -q tools tests` y `python -m pytest tests/test_x_oss_reuse_parity.py -q -p no:cacheprovider`, más la suite offline de `.github/workflows/validate-social-tools.yml` y el gate `validate-public-reuse.yml` en Ubuntu/Windows 3.11. La prueba usa `TemporaryDirectory`, fechas/usuarios/URLs ficticios y mocks de una ruta de registro CSV; no efectúa ninguna acción remota.

**Comparación del mismo fixture:** antes de reconstruir la PR, los tests antiguos verificaban `x_pending_guard` aislado (no compatible con la base); después, se prueban producción→disco→auditor→siguiente planificación sin tocar la implementación vigente. No se atribuyen números de CI de una SHA antigua al HEAD reconstruido: comprobar y anotar los runs finales en la conversación de #13.

## Retirada

Revertir exclusivamente el commit del informe/test nuevo; no hay cambios de esquema, ni migraciones, ni flags, ni nuevo SDK, ni datos de producción. El código operativo vigente queda intacto. No hay que migrar CSV ni reinstalar dependencias.

## Resolución de revisiones

- **Claude 6096195626 / 6096634557 / 6096780812 / 6096792195 / 6097170278 / 6097362909 / 6097562086 / 6099660775:** aceptadas. Se rebasa la base nueva **descartando** el código antiguo; no se introduce el guard paralelo, se mantiene el contrato POST→ACK→TTL y se usan los servicios existentes. Los fixes de alias ya están recogidos por #171 y por el privado.
- **Hilos 4235505672 y 4235505679:** primer hallazgo ya resuelto por manejo de fase `possible_write` del ejecutor nuevo. El segundo (durabilidad pre-tap, multiproceso y dual-write) pertenece al ledger/capacidad compartida; no se subsana con el guard antiguo. La prueba integrada asegura solo lo que de verdad se puede verificar offline.
- **Perplexity 6098810770:** es correcto exigir reconciliación y no reintentar una entrega incierta. No es válido prometer que un test que hace fallar `os.fsync` **tras** el tap garantice por sí solo la ausencia de replay si aún no existía intención durable antes del efecto. La sugerencia de `TooManyRequests.reset_time` sirve para un futuro adaptador API, no para el ejecutor actual; no instalar Tweepy/XDK solo para tests `skipif` de una integración inexistente. Fuzzing y contratos multired pertenecen a la arquitectura compartida, no a nueve guardias locales.
- **Mapa de relaciones 6098631106:** enlace a #171 y a los contratos de identidad comunes #109/#110, fuentes #100, ranking #116 y mapa #204. No se crean PR duplicadas.
- **Revisión anterior del controlador:** sus tests sobre el *antiguo* snapshot eran correctos para aquel entorno; su conclusión de integración ya no lo es tras 52 commits de sincronización. Los checks de la antigua SHA no validan el nuevo árbol.

**Límites para Claude:** solo lectura en Windows/Edge real con perfil autorizado; validación del CSV histórico/SQLite contra el oficial mediante datos sintéticos; doble proceso y crash click→ACK en el ledger compartido. No se promete exactly-once ni se han tocado cuentas, claves o estados reales. No hacer merge sin la revisión del controlador.
