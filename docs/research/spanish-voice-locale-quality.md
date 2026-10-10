# PR #79 — calidad lingüística y voz (10/10/2026)

## Problema

Rama: research/69-spanish-voice-locale-quality. Se leyó el encargo, PROTOCOL.md y el código del espejo; el contexto adicional de `davidpd89/rrss-davidporto-CODE` en `integracion/crecimiento-2026-10` incluye `tools/reply_quality_metrics.py`, `reply_blind_review.py`, `reply_research_eval.py` y `reply_context_trial.py`. No se copió código privado. En el espejo ya están `spellcheck_es.py`, `check_language_variety.py`, `reply_corpus_lint.py` y `reply_writer.py`. El primero detecta algunas tildes faltantes; los otros miden repetición/cadencia. Falta un diagnóstico **común y no destructivo** de apertura de interrogación/exclamación, calcos, variantes es-ES, codificación y preservación de spans ajenos.

**Implementación:** `tools/spanish_voice_quality.py`: `audit(text, network, queue, locale)`, nueve redes (X, Threads, Facebook, Pinterest, Reddit, Bluesky, Mastodon, TikTok, Instagram), colas WEB/API/MOBILE, offsets por puntos de código, lista de códigos y niveles, `changed=false`. No es corrector general ni filtro de naturalidad. Solo revisa reglas acotadas y reutiliza el corrector de tildes ya presente si la dependencia está instalada; devuelve `accent_check=unavailable_or_disabled` cuando no lo está. Acepta `es` sin imponer localismos peninsulares. Citas entre comillas, títulos, enlaces Markdown, URLs, correos, hashtags, menciones y código inline se enmascaran sin mover índices. Ninguna sugerencia reescribe nombres, citas ni formatos.

`tools/reply_writer.py`: invoca el auditor solo después de superar la validación preexistente. Emite **códigos de aviso, nunca el contenido auditado**, sin bloquear respuesta, alterar candidatos ni actuar en redes. `reddit_micro` reutiliza el adaptador de Reddit. Las nueve redes pueden llamar a `audit` desde los demás productores. Integración activa ya verificada por código compartido de `reply_queue`: los productores que usan `rw.write_replies`; no se afirma que todos los publicadores o caminos manuales estén conectados. No se modifica la cola WEB/API/MOBILE ni los preflights de seguridad.

`tools/spanish_voice_blind.py`: revisión A/B emparejada con semilla, orden estable y fichero de clave aparte. Cada caso incluye el mismo contexto y dos textos; las preferencias quedan vacías hasta que un revisor humano puntúe `left/right/tie/both_bad`. `score` no acepta opiniones ausentes. `tools/spanish_voice_eval.py` mide avisos en antes/después sintéticos y genera los dos ficheros ciegos opcionalmente. No confunde menos avisos con ser más humano.

## Alternativas

Se contrastaron herramientas públicas actuales con la continuidad de los módulos internos ya instalados.

## Licencias y procedencia

Fuente primaria: https://github.com/barrust/pyspellchecker
Fecha de consulta: 2026-10-10
Licencia SPDX: MIT
Referencia inmutable: https://github.com/barrust/pyspellchecker/commit/f72172c4ddb3d1c3464cf500cc2420a4831a2b55

### Comparativa aplicada

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
python tools/spanish_voice_eval.py tests/fixtures/spanish_voice_pairs.json --blind-prefix revision79 --seed revisor1
```

Fixture propia sintética: **9 pares / 9 redes**. Auditor sin diccionario (reglas deterministas): **10 avisos antes / 0 después**. Es un caso de regresión construido para comprobar las reglas, no una ganancia real de 100 % ni un benchmark de publicaciones. Tests: 11 casos unitarios sintéticos (paridad 9×3, citas, offsets, UTF-8, calcos, tildes inyectadas, preguntas, comparación A/B, fallos de esquema); CI Windows/Ubuntu Python 3.11 en `.github/workflows/spanish-voice-quality.yml`. Pruebas locales también ejecutadas con Python 3.13 stdlib. **Preferencia humana antes/después: pendiente** de al menos dos revisores independientes con clave oculta, sin mostrar el nombre de variante, sin inferir consenso de un scoring de reglas.

## Segunda revisión adversarial

1. **Falso positivo por dialecto:** checar/carrito/carros pueden ser legítimos en una cita o texto dirigido a América. Corregido: máscara de cita y severidad `hint` en `es-ES`, jamás autocorrección ni bloqueo.
2. **Fuentes y formato alterados:** normalizar Unicode en el texto o sustituir tildes en nombres altera offsets/portadas. Corregido: solo reportar NFC, conservar índices, proteger URLs, hashtags, menciones, títulos y enlaces Markdown. El formato nativo sigue intacto.
3. **Confundir heurística con verdad:** pyspellchecker puede generar falsos positivos en formas verbales y nombres. Corregido: usar módulo ya existente, incluir la disponibilidad en salida, señales como hipótesis editoriales y no contar tildes en el benchmark determinista.
4. **Sesgo A/B:** comparaciones sin mismos posts, elección inventada o clave visible contaminan el resultado. Corregido: pares con contexto común, IDs únicos, clave aparte, decisión vacía por defecto y excepción si falta un voto. Revisión humana aún no realizada.
5. **Interferencia con crecimiento:** nuevo preflight impediría comentarios sanos. Corregido: diagnóstico posterior a `valid_reply`, informativo, excepción del auditor aislada; ninguna operación de escritura remota ni modificación de colas.
6. **Alcance parcial:** el autor de respuestas común conecta varios caminos, pero las fichas de publicación y cualquier edición manual no pasan necesariamente por él. No afirmar cobertura operativa total por tener nueve adaptadores; auditar cada punto de salida o abrir integración separada cuando no duplique otros frentes.

## Retirada y pendientes para Claude

Revertir el commit de integración en `reply_writer.py` para volver exactamente a la lógica anterior (los módulos nuevos no tienen efectos por importación). Los tests y reportes se pueden retirar independientemente. No hay esquema, DB, fichero operativo ni credenciales modificados. Ejecutar la suite global del mirror y de la rama privada tras integrar; verificar en Windows vivo con tildes, consolidador de logs, Edge real y móvil en **canario supervisado**, no en prueba simulada; repetir evaluación ciega con corpus propio/autorizado y seguimiento de preferencia humana. Ninguna acción real de redes fue realizada por esta PR.

**Límites conocidos:** no valida semántica, contexto conversacional, concordancia general, contenido multimedia ni naturalidad; los regex se restringen deliberadamente a señales de alta precisión. El detector de tildes no es infalible. Las pruebas de esta PR son offline y sintéticas.
