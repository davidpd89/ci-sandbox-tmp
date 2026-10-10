# PR #79 — calidad lingüística y voz (10/10/2026)

## Problema

Rama: research/69-spanish-voice-locale-quality. Se leyó el encargo, PROTOCOL.md y el código del espejo; el contexto adicional de `davidpd89/rrss-davidporto-CODE` en `integracion/crecimiento-2026-10` incluye `tools/reply_quality_metrics.py`, `reply_blind_review.py`, `reply_research_eval.py` y `reply_context_trial.py`. No se copió código privado. En el espejo ya están `spellcheck_es.py`, `check_language_variety.py`, `reply_corpus_lint.py` y `reply_writer.py`. El primero detecta algunas tildes faltantes; los otros miden repetición/cadencia. Falta un diagnóstico **común y no destructivo** de apertura de interrogación/exclamación, calcos, variantes es-ES, codificación y preservación de spans ajenos.

**Implementación:** `tools/spanish_voice_quality.py`: `audit(text, network, queue, locale)`, nueve redes (X, Threads, Facebook, Pinterest, Reddit, Bluesky, Mastodon, TikTok, Instagram), colas WEB/API/MOBILE, offsets por puntos de código, lista de códigos y niveles, `changed=false`. No es corrector general ni filtro de naturalidad. Solo revisa reglas acotadas y reutiliza el corrector de tildes ya presente si la dependencia está instalada; devuelve `accent_check=unavailable_or_disabled` cuando no lo está. Acepta `es` sin imponer localismos peninsulares. Citas entre comillas, títulos, enlaces Markdown, URLs, correos, hashtags, menciones y código inline se enmascaran sin mover índices. Ninguna sugerencia reescribe nombres, citas ni formatos. `advisory` centraliza los avisos de códigos (sin texto ni URL), tolera fallos del corrector y del logger sin bloquear.

`tools/reply_writer.py`: invoca el auditor solo después de superar la validación preexistente. Propaga `queue` **solo si el origen del candidato la conoce**, no etiqueta arbitrariamente todo como WEB; el publicador asigna API o WEB por su adaptador real. Emite **códigos de aviso, nunca el contenido auditado**, sin bloquear respuesta, alterar candidatos ni actuar en redes. `reddit_micro` reutiliza el adaptador de Reddit. Las nueve redes pueden llamar a `audit` desde los demás productores. Integración activa ya verificada por código compartido de `reply_queue`: los productores que usan `rw.write_replies`; no se afirma que todos los publicadores o caminos manuales estén conectados. El publicador común `content_publisher.py` también invoca `_voice_diagnostics` para sus siete adaptadores (Bluesky, Mastodon, X, Threads, Facebook, Instagram, Pinterest), tanto en vista previa como antes del envío; es solo informativo y no modifica los siete publicadores ni las colas. Para Reddit/TikTok y caminos manuales queda la API común y el escritor de respuestas, sin fingir paridad de puntos de integración. No se modifica la cola WEB/API/MOBILE ni los preflights de seguridad.

`tools/spanish_voice_blind.py`: revisión A/B emparejada con semilla, orden estable y fichero de clave aparte. Cada caso incluye el mismo contexto y dos textos; la posición de cada alternativa se contrabalancea (diferencia izquierda/derecha ≤1), se obtiene con semilla criptográfica secreta por defecto y las preferencias quedan vacías hasta que un revisor humano puntúe `left/right/tie/both_bad`. `score` no acepta opiniones ausentes. `tools/spanish_voice_eval.py` mide avisos en antes/después sintéticos y genera los dos ficheros ciegos opcionalmente. No confunde menos avisos con ser más humano.

## Alternativas

Se contrastaron herramientas públicas actuales con la continuidad de los módulos internos ya instalados.

## Licencias y procedencia

Fuente primaria: https://github.com/barrust/pyspellchecker
Fecha de consulta: 2026-10-10
Licencia SPDX: MIT
Referencia inmutable: https://github.com/barrust/pyspellchecker/commit/f72172c4ddb3d1c3464cf500cc2420a4831a2b55

### Comparativa aplicada (contraste adicional al 10/10/2026)

El código de pyspellchecker a `f72172c` exige Python >=3.10 según su pyproject y su licencia MIT está confirmada en LICENSE. La alternativa de motor de gramática completo incluye LanguageTool (núcleo LGPL-2.1) y dos clientes Python, pero es una carga adicional para comentarios cortos: el motor local precisa JVM; un cliente HTTP no aporta reglas por sí mismo.

| Candidato complementario | Referencia inmutable verificada | Licencia / mantenimiento | Encaje |
|---|---|---|---|
| [LanguageTool núcleo](https://github.com/languagetool-org/languagetool/commit/170f9698d9b15bc0cde1094156bc60d0007ca7e0) | `170f969` (09/10/2026) | LGPL-2.1, proyecto activo; requiere entorno Java | Gramática completa, útil fuera de la ruta caliente, no sustituto ligero |
| [pyLanguagetool](https://github.com/Findus23/pylanguagetool/commit/e29f87dae8cdaa9fc87bc5e7192edae3d286c596) | `e29f87d` (13/04/2025) | MIT, menor actividad reciente | Cliente HTTP/API, no corrige localmente por sí mismo; no adoptado |

### Primera comparación

| Opción | Versión de referencia comprobada / actividad | Licencia | Compatibilidad y coste | Decisión |
|---|---|---|---|---|
| [pyspellchecker](https://github.com/barrust/pyspellchecker/commit/f72172c4ddb3d1c3464cf500cc2420a4831a2b55) | `f72172c`, 23/07/2026, repo activo | MIT | Python >=3.10, Windows y español; dependencia **ya declarada** `pyspellchecker>=0.8,<1` | **Reutilizar** el `check_missing_accents` existente sin copiar diccionario; solo aviso contextual |
| [symspellpy](https://github.com/mammothb/symspellpy/commit/3566f13f16284ebe613910191828dff43de4e2ba) | `3566f13`, 21/08/2026, activo | MIT | Python 3.11/Windows, motor rápido; requiere corpus español propio y añade dependencia/diccionario | No adoptar de momento; coste de falsos positivos y datos |
| [language_tool_python](https://github.com/jxmorris12/language_tool_python/commit/6c935da8ef739b22d62c13cd682cb9a2922e4f98) | `6c935da`, 03/10/2026, activo | GPL-3.0-only | Python 3.11/Windows; servidor local requiere Java 17 y recursos/descarga, API remota no apta para modo offline | No incorporar al camino crítico; candidato para evaluación editorial aislada |
| [wordfreq](https://github.com/rspeer/wordfreq/commit/912caf64b657478d1dff1138efdc078947d54bb1) | `912caf6`, 04/01/2025 | Documentación anuncia Apache-2.0 desde 3.0.3; metadatos GitHub NOASSERTION | Python 3.11; frecuencia léxica no identifica registros ni puntuación | No añadir; datos/frecuencia no equivalen a corrección |

No hay código externo vendorizado. Procedencia: reutilización de la API interna de `tools/spellcheck_es.py`, que a su vez usa pyspellchecker MIT. El auditor de reglas y el generador ciego están escritos específicamente para esta PR. Los repos examinados son públicos y su estado/licencia se inspeccionaron el 10/10/2026. Las métricas de comunidad no sustituyen las pruebas de compatibilidad en nuestro entorno.

## Decisión

Conservar y reutilizar el corrector de tildes ya instalado; añadir diagnósticos pequeños de stdlib, sin motor Java ni corpus nuevo. No se copia material externo en el árbol. Los componentes se pueden desactivar sin migración.

## Pruebas

```powershell
python -m unittest discover -s tests -p test_spanish_voice_quality.py -v
python tools/spanish_voice_eval.py tests/fixtures/spanish_voice_pairs.json
python tools/spanish_voice_quality.py --network x --queue WEB --text "Cuantos tomos tiene?"
New-Item -ItemType Directory -Force "$env:TEMP\rrss_revision79" | Out-Null
New-Item -ItemType Directory -Force "$env:TEMP\rrss_clave79" | Out-Null
python tools/spanish_voice_eval.py tests/fixtures/spanish_voice_pairs.json --blind-prefix "$env:TEMP\rrss_revision79\revision79" --blind-key-dir "$env:TEMP\rrss_clave79"
```

Fixture propia sintética: **9 pares / 9 redes**. Auditor sin diccionario (reglas deterministas): **10 avisos antes / 0 después**. Es un caso de regresión construido para comprobar las reglas, no una ganancia real de 100 % ni un benchmark de publicaciones. Tests: 30 casos unitarios sintéticos (paridad 9×3, citas, offsets, UTF-8, calcos, tildes inyectadas, preguntas, comparación A/B, fallos de esquema); CI Windows/Ubuntu Python 3.11 en `.github/workflows/spanish-voice-quality.yml`. La evidencia reproducible se obtiene con Python 3.11 en GitHub Actions; no se atribuyen pruebas locales adicionales no registradas. **Preferencia humana antes/después: pendiente** de al menos dos revisores independientes con clave oculta, sin mostrar el nombre de variante, sin inferir consenso de un scoring de reglas.

## Segunda revisión adversarial

1. **Falso positivo por dialecto:** checar/carrito/carros pueden ser legítimos en una cita o texto dirigido a América. Corregido: máscara de cita y severidad `hint` en `es-ES`, jamás autocorrección ni bloqueo.
2. **Fuentes y formato alterados:** normalizar Unicode en el texto o sustituir tildes en nombres altera offsets/portadas. Corregido: solo reportar NFC, conservar índices, proteger URLs, hashtags, menciones, títulos y enlaces Markdown. El formato nativo sigue intacto.
3. **Confundir heurística con verdad:** pyspellchecker puede generar falsos positivos en formas verbales y nombres. Corregido: usar módulo ya existente, incluir la disponibilidad en salida, señales como hipótesis editoriales y no contar tildes en el benchmark determinista.
4. **Sesgo A/B:** comparaciones sin mismos posts, elección inventada o clave visible contaminan el resultado. Corregido: pares con contexto común, IDs únicos, clave aparte, decisión vacía por defecto y excepción si falta un voto. Revisión humana aún no realizada.
5. **Interferencia con crecimiento:** nuevo preflight impediría comentarios sanos. Corregido: diagnóstico posterior a `valid_reply`, informativo, excepción del auditor aislada; ninguna operación de escritura remota ni modificación de colas.
6. **Defecto reproducido del benchmark:** los avisos de casos sucesivos de la misma red se sobrescribían en `by_network`; ahora acumula contadores y casos. Regresión: dos casos de X deben sumar 2, no 1.
7. **Revisión ciega manipulable y semilla predecible:** antes se podía editar red/contexto/variantes del formulario después de generar la clave y se escribía la clave junto a la revisión. Además, la semilla CLI era pública y fija, por lo que un revisor técnico podía reconstruir los lados. Corregido: huella SHA-256 por pareja, validación estricta, clave y revisión en directorios distintos fuera del repo, sin sobrescritura; semilla criptográfica no persistida por defecto y contrabalanceo de posición. `--seed` queda solo para reproducir tests sintéticos. No confundir huella local con cifrado ni anonimización.
8. **Markdown y texto protegido:** la exclamación de `![portada](...)` generaba un falso positivo; los bloques de código delimitados con tres acentos graves o virgulillas podían etiquetar signos dentro del código como errores lingüísticos. Corregido con pruebas específicas.
9. **Cola inferida incorrectamente:** las llamadas sin dato de origen antes se declaraban WEB, aunque la salida podía ser API o MOBILE; ahora devuelven `queue: null`, y el escritor propaga información explícita. Las fichas del publicador diferencian WEB/API.
10. **Seguridad operativa de CI:** el workflow original estaba sin acciones inmovilizadas, permisos explícitos ni instalación del diccionario; se fijaron los SHA de acciones ya usados por el espejo, `contents: read`, sin persistir credenciales, Python 3.11, prueba del diccionario real y timeout.
11. **Alcance parcial:** originalmente faltaban las fichas de publicación; corregido en esta PR conectando siete adaptadores de `content_publisher.py` al mismo auditor, sin bloqueo. Reddit/TikTok, publicadores directos y edición manual siguen precisando inventario de puntos de salida; no atribuir cobertura universal a una función que acepta nueve redes.

## Retirada y pendientes para Claude

Revertir los commits de integración en `reply_writer.py` y `content_publisher.py` para volver exactamente a la lógica anterior (los módulos nuevos no tienen efectos por importación). Los tests y reportes se pueden retirar independientemente. No hay esquema, DB, fichero operativo ni credenciales modificados. Ejecutar la suite global del mirror y de la rama privada tras integrar; verificar en Windows vivo con tildes, consolidador de logs, Edge real y móvil en **canario supervisado**, no en prueba simulada; repetir evaluación ciega con corpus propio/autorizado y seguimiento de preferencia humana. Ninguna acción real de redes fue realizada por esta PR. En las pruebas de integración se simula `reply_writer` y el diagnóstico del publicador sin sesiones, clientes sociales ni escrituras operativas.

**Práctica ciega real:** en evaluación con personas, NO introducir `--seed` (el programa la genera con `secrets`). La clave debe guardarse separada y nunca remitirse a los evaluadores. Para reproducibilidad con corpus enteramente sintético se admite `--seed demostracion`, sin presentarlo como evaluación ciega real. La suite solo prepara los materiales; no se han recogido votos humanos ni se ha medido concordancia entre revisores.

## Compatibilidad comprobada con el repositorio oficial (requiere portabilidad manual de Claude)

Nueva comparación al 10/10/2026 sobre `davidpd89/rrss-davidporto-CODE` / `integracion/crecimiento-2026-10`:

- `tools/reply_writer.py` oficial, **blob SHA `5d76b1da2e4666aa2c2fc96877eaff8695e6f78e`**, difiere de la versión del espejo: procesa IDs duplicados con fail-closed, construye proof de procedencia y `mark_gpt(written, network=net, source=origin, prompt_hash=fingerprint)` puede denegar la salida. **No sustituir el módulo oficial por el archivo de esta PR.** Insertar solo una llamada a `spanish_voice_quality.advisory(written, network=..., queue=origin.get("queue"), log=log, ...)` tras comprobar el proof de autoría y antes/después del `out[item_id] = written`, sin debilitar ninguna condición.
- `tools/content_publisher.py` oficial, **blob SHA `f5120bb2141f29e88549497c09ec438b02ebc22d`**, incluye `circuit_breaker.write_preflight` no presente en el mirror. **No sobrescribir ni eliminar ese preflight**. Tras `item = ready[0]` insertar una llamada a `_voice_diagnostics` (o directamente `advisory`) en ambos caminos, vista previa y publicación, sin cambiar `apply`, sesiones ni comprobación del circuito.
- Los módulos nuevos de auditoría, evaluación, tests y CI pueden integrarse como nuevas piezas; los cambios sobre escritor y publicador del mirror deben **portarse como hunk mínimo**, rebasados sobre el código privado más reciente. La suite verde en mirror no equivale a aprobación de integración en privado. Claude debe repetir tests de procedencia, circuit breaker y guardias de escritura del repositorio oficial.

**Bloqueo para integración real:** no se probaron Edge vivo, móvil ni la rama oficial rebasada, porque aquí solo se hicieron commits en el espejo público y no hubo acciones sociales. La PR #106 ya cubre las rutas de salida pendientes; no abrir una PR duplicada.

**Autorrevisión sucesiva:** los defectos anteriores fueron detectados en una segunda revisión, corregidos en la misma rama y regresados en CI. En particular los formularios ciegos no se deben subir al repositorio; revisar y clave deben permanecer fuera de él y bajo distintos directorios. Esta suite no valida contenido real ni interpreta matices de registro de cada red.

**Límites conocidos:** no valida semántica, contexto conversacional, concordancia general, contenido multimedia ni naturalidad; los regex se restringen deliberadamente a señales de alta precisión. El detector de tildes no es infalible. Las pruebas de esta PR son offline y sintéticas.

## Revisión independiente REV 79 — 10/10/2026

Se añadió una pasada adversarial independiente tras `b09e5dc`, sin alterar salidas ni introducir llamadas a redes:

- Las aperturas de interrogación y exclamación ahora se rastrean por separado. Antes `¡¿De verdad?!` y `¿¡En serio!?` generaban falsos positivos por limpiar el estado al primer cierre. La secuencia `¿Algo...?` también perdía la apertura al encontrar el primer punto. Se corrigió con regresiones de combinación, elipsis y preguntas sucesivas sin apertura.
- El enmascarado de bloques Markdown cercados ahora admite fin de línea CRLF de Windows. La prueba usa caracteres `\\r\\n` reales en tiempo de ejecución, sin modificar la longitud ni los índices.
- Un `queue` de origen desconocido o mal tipado ya no desactiva el auditor compartido: `advisory` lo clasifica como desconocido (`None`) antes de `audit`, sin atribuir transportes ficticios. La API estricta `audit` sigue rechazando colas inválidas y el escritor/publicador no se alteran.

**Condiciones de integración:** esta PR sigue aportando solo auditoría informativa. La integración del código del espejo no debe sobrescribir `tools/reply_writer.py` ni `tools/content_publisher.py` del repositorio oficial; portar únicamente llamadas al auditor y conservar `mark_gpt`/prueba de autoría, `circuit_breaker.write_preflight`, selección y persistencia actuales. La extensión a otras rutas de salida se mantiene en #106, no se duplica aquí. La evaluación humana ciega y una prueba con Edge/móvil supervisada continúan pendientes. Los estados de CI se deben verificar siempre sobre el último HEAD, no sobre los SHA citados en rondas anteriores.
