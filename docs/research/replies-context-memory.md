# PR #22 — memoria editorial contextual para respuestas humanas

Fecha de verificación: **10/10/2026**. Rama: `research/12-replies-context-memory`.
Base: `research/public-reuse-parent`. Trabajo **offline**, sin cuentas, sin publicaciones,
sin cambios de estado real y sin merge.

## Problema — necesidad real y punto de integración

En el mirror se ha comprobado el flujo `tools/reply_writer.py`:
`build_prompt()` inyectaba **los últimos diez ejemplos buenos y ocho malos**
de `00_OPERATIVO/respuestas_memoria.json`, sin relación temática con el
destino. La memoria negativa incluía **la respuesta errónea** en el prompt,
dándole al modelo una frase para reproducir. Un lote con posts sobre dragones
podía recibir recuerdos sobre huertos. La redacción de respuestas, el registro,
la caducidad, la aprobación de textos GPT y el envío **ya existen** y no se
reescriben en esta PR.

Lectura **solo en el conector** del repo oficial privado
`davidpd89/rrss-davidporto-CODE`, HEAD
[`5449513d9b545d0a6a72abf066ab6a779bfdad71`](https://github.com/davidpd89/rrss-davidporto-CODE/commit/5449513d9b545d0a6a72abf066ab6a779bfdad71).
Revisados `tools/reply_writer.py`, `reply_research_eval.py`,
`reply_blind_review.py`, `reply_context_trial.py`, `reply_quality_metrics.py`
y `reply_provenance.py`. **No se transfieren registros privados ni credenciales.**
El repositorio oficial dispone ya de evaluación ciega A/B, métricas de variedad
y provenance de los destinos. Esos componentes no se duplican. Las PR públicas
[#74](https://github.com/davidpd89/ci-sandbox-tmp/pull/74)
(evidencia contextual), [#72](https://github.com/davidpd89/ci-sandbox-tmp/pull/72)
(benchmark), [#79](https://github.com/davidpd89/ci-sandbox-tmp/pull/79)
(calidad de voz), [#77](https://github.com/davidpd89/ci-sandbox-tmp/pull/77)
(conversación) y [#104](https://github.com/davidpd89/ci-sandbox-tmp/pull/104)
(adaptadores de evidencia) tienen alcance vecino: no copiar esos motores aquí.

## Alternativas — comparativa de reutilización pública

Revisiones inmutables inspeccionadas mediante GitHub, no simplemente URLs de portada:

| Candidato | Revisión y licencia verificada | Dependencias / compatibilidad | Decisión |
| --- | --- | --- | --- |
| [RapidFuzz](https://github.com/rapidfuzz/RapidFuzz/commit/db6e504539a9c895180b266a06b36a32cb6029ee) | `db6e5045`, **MIT** | Python >=3.11; ruedas Windows/Linux; redistribuible VC++ en Windows; proyecto activo (release 3.14.6, agosto 2026) | **No instalar** para pocos registros: similitud de cadenas cortas no acredita relevancia semántica; coste operativo extra |
| [LangMem](https://github.com/langchain-ai/langmem/commit/48e3c11f5bb527282c7d5339c6a87a0b35abccfc) | `48e3c11f`, **MIT** | Python >=3.10; LangChain, LangGraph, integraciones de modelos; actividad reciente | Patrón de separar *selección* y *generación* útil; dependencia desproporcionada sin necesidad de almacenar recuerdos generados |
| [Mem0](https://github.com/mem0ai/mem0/commit/b7ad69afda6b6ed030347c66d48a13e4de9dec08) | `b7ad69af`, **Apache-2.0** | Python >=3.10; qdrant-client, OpenAI, HTTPX, SQLAlchemy, telemetría; Windows no validado localmente | No añadir LLM ni almacén vectorial para ejemplos curatoriales en JSON; son mecanismos distintos de la necesidad actual |
| Código vigente de RRSS | HEAD `5449513d` del repo oficial (no OSS) | stdlib Python 3.11, escritor, filtros, cola, memoria JSON ya instalados | **Continuidad preferida**: conservar contratos, introducir un selector específico y aislado |

Los tres proyectos son públicos y con actividad consultable a fecha de revisión.
Sus licencias **permitirían** una integración conforme a sus condiciones.
No se ha copiado su implementación: el código nuevo se diseñó a partir del
contrato local. La idea arquitectónica de aislar extracción de recuerdos y
consumo se contrastó con LangMem; no constituye reutilización literal de código.

## Licencias y procedencia

Fuente primaria: https://github.com/rapidfuzz/RapidFuzz
Fecha de consulta: 2026-10-10
Licencia SPDX: MIT
Referencia inmutable: https://github.com/rapidfuzz/RapidFuzz/commit/db6e504539a9c895180b266a06b36a32cb6029ee

La referencia primaria es una alternativa contrastada, **no código incorporado**.
Las otras fuentes con su revisión y licencia figuran en la tabla anterior
(LangMem: MIT; Mem0: Apache-2.0). No hay código de terceros copiado.

## Decisión — implementación

- `tools/reply_context_memory.py`: selector de ejemplos **aprobados** y de
  **errores** sobre coincidencia léxica relevante. Normaliza acentos y ñ
  para *buscar*, no para escribir. Descarta términos demasiado genéricos
  (p. ej., «libros», «fantasía»). Exige al menos **dos términos informativos
  comunes** con el post. Ordena por cantidad de coincidencias, similitud
  de conjuntos y recencia del registro en caso de empate. Devuelve como máximo
  una aprobación y un error por destino; la frase errónea jamás se incluye.
- La memoria se etiqueta con el **ID del post** en JSON; si el ejemplo tiene
  `network`, solo sirve para esa red. Hay soporte de nombre de red heredado
  y de `reddit_micro`. No deduce quién es una persona ni que hayamos leído
  un libro por el contenido de un ejemplo.
- `reply_writer.memoria_texto(..., items=..., network=...)` conserva para los
  lotes la lista de textos recientes publicada como **control de repetición**,
  pero sustituye la memoria indiferenciada por ejemplos relevantes.
  `build_prompt` utiliza el selector en el punto ya compartido por los
  consumidores del escritor. La firma legada de `memoria_texto(recent, path)`
  sigue disponible; para desinstalar el selector, revertir el cambio del
  escritor y borrar el módulo nuevo.
- Los textos de referencia son **datos**, no órdenes. Un ejemplo no se trata
  como evidencia de multimedia, conversación completa, identidad ni resultado.
  Los JSON no contienen credenciales ni se vuelcan a logs. La memoria se lee;
  **no se escribe** durante el render.

**Alcance efectivo:** el motor de memoria admite las **nueve redes** y
`reddit_micro`; WEB/API/MOBILE comparten la pieza si invocan
`reply_writer.build_prompt`. Esto **no** demuestra que cada ejecutor use
ya esa ruta. Instagram no figura en el `MAX_CHARS` del escritor del espejo:
esta PR no amplía el publicador ni atribuye paridad operativa inexistente.
La extracción de evidencia nativa corresponde a #104, no aquí.

## Comparación reproducible con corpus sintético

El test `test_retrieval_vs_legacy_recency_on_synthetic_relevance` coloca
una referencia sobre «saga del dragón rojo» antes de 15 entradas sobre huertos
y consulta un post sintético de dragones con mapas.

| Medida | Baseline: últimos 10 ejemplos | Selector PR #22 |
| --- | --- | --- |
| Ejemplos pertinentes recuperados, caso sintético | **0** | **1** |
| Ejemplos de huertos presentados como memoria útil | 10 | 0 |
| Coste de servicios externos | 0 | 0 |

Es **una prueba de recuperación**, no un ensayo de calidad lingüística ni una
estimación de mejora de seguidores. Para demostrar respuestas más naturales
hace falta comparar textos realmente producidos con los mismos posts/contextos,
aleatorizar A/B, usar la revisión ciega de `reply_blind_review.py` del repo
oficial y separar pertinencia, naturalidad, invenciones y abstenciones. No se
puede deducir el resultado del número de coincidencias léxicas.

## Pruebas y auditoría adversarial

Pruebas sintéticas reproducibles:

```bash
python -m compileall -q tools/reply_context_memory.py tools/reply_writer.py
python -m pytest -q tests/test_reply_context_memory.py -p no:cacheprovider
```

`.github/workflows/research22-reply-context-memory.yml` ejecuta Python 3.11
en Ubuntu/Windows y activa `tests/offline_guard` durante las pruebas. El
workflow general de RRSS se ejecuta también en los commits del mirror.

**Segunda revisión adversarial:** se localizaron y corrigieron (a) una memoria
JSON válida de tipo lista que derribaba `estilo_red_texto`, (b) `network`
inesperado de tipo no hashable, (c) IDs sin delimitación razonable y (d) errores
de serialización de saltos de línea inicialmente detectados por `compileall`
de CI en ambos SO. La verificación debe leerse **por SHA del último HEAD**:
las ejecuciones antiguas fallidas o canceladas no prueban el código corregido.
Se cubren memoria inexistente/malformada, ausencia pertinente, mezcla de lotes,
español con tildes, preferencias por red, no mutación del JSON, fallback legada,
recuperación determinista y límite de longitud.

## Retirada — limitaciones y reversión

La similitud por tokens ignora sinónimos, morfología compleja, ironía, intención
y calidad estilística: puede no recuperar ejemplos útiles o recuperar otros
solo superficialmente relacionados. El criterio de dos términos evita parte
del ruido, pero no equivale a evaluación semántica humana. Los textos aprobados
siguen siendo material potencialmente no fiable para el LLM; su marcado como
datos y la política superior reducen confusión, **no garantizan 100 %** de
resistencia a instrucciones incrustadas. La memoria heredada no tiene
procedencia de aprobación firmada: el lector usa lo que ya conste en el JSON,
sin elevarlo a prueba factual.

**Rollback:** un revert de la modificación en `reply_writer.py` restablece
la memoria legada; eliminar `reply_context_memory.py`, tests y workflow deja
el resto de colas intacto. No hay migración de datos ni nuevos estados.
**Canario supervisado, pendiente de Claude:** validar render en Windows real,
revisar un lote de cada cola y evaluar a ciegas con posts autorizados,
sin confundirlo con estas pruebas offline. No publicar automáticamente durante
la evaluación.
