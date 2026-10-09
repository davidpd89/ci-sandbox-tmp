# TikTok: inspección estructural Android sin datos personales

Investigación e implementación **09/10/2026** · PR hija [#19](https://github.com/davidpd89/ci-sandbox-tmp/pull/19). Base `research/public-reuse-parent`. No ejecuta acciones en cuentas.

## Problema: hueco real verificado

Se inspeccionaron en **`davidpd89/rrss-davidporto-CODE`**, rama `integracion/crecimiento-2026-10` (repo privado, no copiar datos operativos), `tools/mobile_client.py`, `mobile_runtime.py`, `tiktok_mobile_nav.py`, `tiktok_mobile_interact.py`, `tiktok_mobile_execute.py`, `tiktok_safety.py`, `tiktok_source_evidence.py` y `tests/test_pr152_tiktok_intent_reconciliation.py`. El mirror contiene ya `mobilecli`, árbol UI y navegación de TikTok. Las intenciones write-ahead, los locks y pausas de TikTok **ya están implementados**; [PR #7](https://github.com/davidpd89/ci-sandbox-tmp/pull/7) los examina por separado. Duplicarlos introduciría divergencia.

La navegación existente confía en selectores semánticos de UI española, pero carecía de una huella **estructural, comparable y minimizada** para distinguir cambios de disposición de fallos de dispositivo/estado. Almacenar capturas o dumps textuales expondría identificadores. El problema concreto elegido es **observar la deriva de UI sin guardar contenido de usuarios**, no ejecutar más acciones ni reintentar acciones inciertas.

## Alternativas: candidatos comprobados

| Candidato | Procedencia y mantenimiento observado | Licencia | Encaje Windows/Python 3.11 | Decisión |
| --- | --- | --- | --- | --- |
| `mobile-next/mobilecli` | [tag 1.0.17 (01/10/2026)](https://github.com/mobile-next/mobilecli/releases/tag/1.0.17), [1.0.18 (04/10/2026)](https://github.com/mobile-next/mobilecli/releases/tag/1.0.18), [contrato OpenRPC 1.0.17](https://github.com/mobile-next/mobilecli/blob/1.0.17/docs/openrpc.json) | [FSL 1.1, futura Apache 2.0](https://github.com/mobile-next/mobilecli/blob/1.0.17/LICENSE); **no es MIT** | Binario y servidor disponibles en entorno actual, no debe instalarse en CI | **Conservar 1.0.17**, ya fijado en `mobile_runtime.py`; no copiar upstream ni actualizar sin ensayo supervisado. |
| `openatx/uiautomator2` | [v3.7.0, 26/06/2026](https://github.com/openatx/uiautomator2/releases/tag/3.7.0), [fuente del release](https://github.com/openatx/uiautomator2/tree/39742b7b63f9bc33f875ccca6db125299a183af2) | [MIT](https://github.com/openatx/uiautomator2/blob/39742b7b63f9bc33f875ccca6db125299a183af2/LICENSE) | Python >=3.8, cliente en Windows; requiere jar/servicio Android propio | Útil si migra el transporte, pero duplicaría el servidor activo solo para comparar árboles. |
| `openatx/adbutils` | [v2.12.0, 12/11/2025](https://github.com/openatx/adbutils/releases/tag/2.12.0), [código del tag](https://github.com/openatx/adbutils/tree/2.12.0) | [MIT](https://github.com/openatx/adbutils/blob/2.12.0/LICENSE) | Python >=3.8 y Windows, requiere ADB | Complementa dispositivos/transferencias, no aporta un detector de deriva semántica; no copiar. |
| TikTok Display / Posting / Research APIs | [Display](https://developers.tiktok.com/docs/en/display-api-overview), [Posting](https://developers.tiktok.com/products/content-posting-api), [Research](https://developers.tiktok.com/docs/en/research-api-get-started) | API remota (no librería libre candidata) | Implica autenticación y redes; CI offline incompatible | Útiles para vídeos propios/publicación/estudios, **no** reemplazan la inspección de botones Android ni verifican un estado de la app. |

## Licencias y procedencia

Fuente primaria: https://github.com/mobile-next/mobilecli/tree/1.0.17
Fecha de consulta: 2026-10-09
Licencia SPDX: NOASSERTION
Referencia inmutable: N/A (sin codigo incorporado)

`NOASSERTION` describe **el código nuevo de este mirror, que no incorpora código externo**; no reclasifica las licencias upstream: `uiautomator2` y `adbutils` son MIT, mientras que `mobilecli` tiene FSL 1.1 con licencia futura Apache-2.0. Los tags/commits exactos de cada candidato figuran en la tabla. Se reutiliza únicamente la interfaz de lectura ya presente.

Las bibliotecas externas no aportan más a este hueco que la lectura ya disponible. Se **reutiliza el contrato existente** de `TikTokNavigator.tree()`; implementación nueva mínima solo de reducción, comparación y validación. No se copia código de terceros ni hay cambios de dependencias, pagos, permisos o credenciales.

## Decisión y entrega

- `tools/mobile_ui_diagnostics.py`: función pura `diagnose(tree)` sobre jerarquías JSON sintéticas, cota de 3000 nodos y 32 niveles; roles enumerados, cuatro zonas verticales relativas, palabras de navegación en una lista cerrada. No registra texto arbitrario, coordenadas crudas, IDs, identificadores Android, paquetes, vídeos ni capturas. Descarta nodos con rectángulos no válidos.
- `compare(reference, current)`: contrato schema=1 y comprobación de integridad SHA-256 de las *características permitidas*; similitud Jaccard ponderada con recuentos, entradas/salidas observadas. El SHA **no autentica al productor ni demuestra UI real**; solo detecta ediciones accidentales del resumen.
- `TikTokNavigator.diagnose_current_ui(reference=...)`: un `tree()` de solo lectura, sin taps, sin `--apply`, sin estado persistente. Únicamente bajo invocación explícita; no afecta al ejecutor ni aumenta volumen.
- CLI reproducible: `python -B tools/mobile_ui_diagnostics.py /ruta/arbol-sintetico.json --reference /ruta/arbol-base-sintetico.json`. Entrada local <=1 MB. La salida puede guardarse como baseline **siempre que se valide la procedencia de la muestra**; no almacenar árboles reales en el repositorio.

## Pruebas y medición

Comandos offline, sin móvil, red ni cuentas:

```console
python -B -m unittest discover -s tests -p test_mobile_ui_diagnostics.py -v
python -B -m pytest tests/test_mobile_ui_diagnostics.py -q -p no:cacheprovider
```

Regresiones previstas: sustitución de texto privado con idéntica huella (sin fuga), cambio de `Seguir` a `Siguiendo` distinguible, equivalencia árbol plano/anidado, rechazo de límites, geometría NaN, edición de digest, inyección de claves y schema booleano, ejecución CLI sintética, método de navegación estrictamente de lectura. Los CI preexistentes `validate-social-tools.yml` y `validate-public-campaign.yml` prueban Ubuntu/Windows Python 3.11 en cada push. Registrar sus resultados **sobre el HEAD definitivo**, no sobre commits anteriores.

Comparación antes/después (criterio funcional, datos sintéticos): antes no existía `diagnose_current_ui` ni comparación; después se puede comparar huella permitida sin retener dumps. No hay evidencia de aumento de interacciones, detección fiable de todas las versiones de TikTok ni ganancia de tiempo en dispositivo; no se inventan benchmarks.

## Retirada, límites, despliegue y reversión

Un selector textual de otra lengua, una pantalla distinta con las mismas clases y distribuciones o un texto dinámico idéntico a una etiqueta permitida producen falsos positivos/negativos. Cambios benignos de distribución causan alarma; un árbol alterado para conservar características queda invisible. La comparación **no valida identidad de cuenta, edad de posts, integridad criptográfica externa ni éxito de acciones**. Mantener tales verificaciones en sus módulos existentes. Sin baseline real permitido, esto es **solo prueba simulada**, no canario supervisado.

Para Claude: contrastar un conjunto pequeño de pantallas sintéticas y, si se decide, inspeccionar canarios supervisados en Windows/Xiaomi con privacidad, locales ES y EN, versiones de TikTok y autorización de cuenta verificadas; medir matrices de confusión y coste de `dump_ui` con el hardware propio **antes** de usar el resultado como señal operativa. El método es observacional: una deriva jamás debe provocar pulsación, reintento de acciones inciertas ni escalado automático de volumen.

Para retirar: revertir `tools/mobile_ui_diagnostics.py`, `tests/test_mobile_ui_diagnostics.py`, esta documentación y el método/import añadido a `tiktok_mobile_nav.py`. Sin esquema SQLite, migración, ficheros de estado, credenciales ni datos operativos. La integración puede eliminarse sin deshacer `mobilecli`.

## Revisión adversarial (segunda pasada)

Se contrastó el proyecto oficial con el mirror y PR #7: **no** se tocó el journal, límites ni registro de acciones. Ataques cubiertos: texto con identificador, clave de característica inyectada, esquema impostor `true`, árbol anidado profundo, tamaño excesivo, geometría `NaN`, hash manipulado. Hallazgo pendiente para canario: la normalización vertical toma el borde máximo visible, por lo que barras del sistema o diálogos pueden alterar la huella aun sin cambio de versión; eso es información de contexto, no prueba de fallo. Otro pendiente: `mobilecli` 1.0.18 mejora Android, pero subirlo requiere pruebas de compatibilidad aparte; mantener el pin actual.

El alcance se mantiene aislado de PR #7, #8 (edad), #16 (Instagram) y del trabajo de KPI/cohortes de TikTok. Ninguna PR nueva merece abrirse de momento: las extensiones relevantes ya tienen contrato propio o carecen todavía de canario que las justifique.
