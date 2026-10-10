# PR #80 — motor offline de experimentos de contenido y comentarios

Fecha de verificación: 2026-10-10. **Implementación en espejo público**, sin credenciales,
acciones sobre redes ni estado productivo. Esta investigación produce
`tools/content_comment_experiments.py` y
`tests/test_content_comment_experiments.py`.

## Problema

### Hueco y sistema existente

El repositorio oficial privado `davidpd89/rrss-davidporto-CODE`,
rama `integracion/crecimiento-2026-10`, dispone de:
- `tools/experiment_uplift.py` (blob
  [d3bc39a](https://github.com/davidpd89/rrss-davidporto-CODE/blob/integracion/crecimiento-2026-10/tools/experiment_uplift.py)):
  analiza **dos cohortes preasignadas** con Newcombe–Wilson, detecta SRM,
  impone mínimo de **100 unidades por brazo**; no asigna ni registra
  exposiciones o resultados.
- `tools/growth_attribution.py` (blob
  [ff8f77a](https://github.com/davidpd89/rrss-davidporto-CODE/blob/integracion/crecimiento-2026-10/tools/growth_attribution.py)):
  atribución descriptiva a partir de interacciones/follow-back; las filas
  históricas no son un experimento controlado.
- `tools/cross_network_learning.py` (blob
  [673c74a](https://github.com/davidpd89/rrss-davidporto-CODE/blob/integracion/crecimiento-2026-10/tools/cross_network_learning.py)):
  genera propuestas de ensayo manual con evidencias auditadas; no asigna
  exposiciones ni valida permisos con un JSON autoafirmado.
- `tools/reply_quality_metrics.py` (blob
  [50cc4bd](https://github.com/davidpd89/rrss-davidporto-CODE/blob/integracion/crecimiento-2026-10/tools/reply_quality_metrics.py)):
  métricas de caché de respuestas, sin unión verificada
  respuesta-publicación-réplica.
- `tools/content_queue.py`, `tools/content_publisher.py` y el índice
  de publicaciones permiten calendarizar y registrar material; los
  campos legacy de hashtags, horarios e imágenes son covariables potenciales,
  **no** prueba de exposición ni de causalidad.

El espejo público carecía del pipeline común asignación → exposición
confirmada → resultado maduro por red. El nuevo módulo es independiente,
no replica módulos privados ni toca sus datos. La comparación sobre
`experiment_uplift` prueba que el nuevo resultado **NO** sustituye su
análisis confirmatorio con mínimo 100/SRM y flags de diseño.

## Alternativas

### Investigación pública (SHA y licencias comprobadas)

| Candidato | Revisión pública verificada | Licencia | Actividad y compatibilidad | Decisión |
|---|---|---|---|---|
| [Fidelity MABWiser](https://github.com/fidelity/mabwiser) | [b104071](https://github.com/fidelity/mabwiser/commit/b104071351d532aae977955d19b83872a9c1b1e3) (2024-08-30) | Apache-2.0, archivo LICENSE | Python >=3.8; NumPy / aprendizaje contextual, no se verificó matriz Windows 3.11 de este commit | No integrar dependencia pesada para dos brazos |
| [david-cortes/contextualbandits](https://github.com/david-cortes/contextualbandits) | [fc49364](https://github.com/david-cortes/contextualbandits/commit/fc49364bf7f98abb6171351521deeade7800f01e) (2026-06-28) | BSD-2-Clause, LICENSE | Activo; código Cython y compilador C/C++, flags de CPU a vigilar en Windows | No integrar: coste de compilación mayor que necesidad |
| [Spotify Confidence](https://github.com/spotify/confidence) | [0f12dd3](https://github.com/spotify/confidence/commit/0f12dd39afd15c48baf24e9d28fcbe72a905bb53) (2026-02-26) | Apache-2.0, LICENSE | Release 4.1.0 (2026-02-26); pandas/estadística secuencial orientada a ensayos con tamaños mayores | Conservar como referencia para análisis formal posterior |
| Módulo propio, estándar Python | PR #80 | Sin código externo copiado | `sqlite3`, `hashlib`, `random`, `datetime`; Python 3.11 Windows/Linux | Implementar contrato mínimo fijo; aprendizaje exploratorio |

Referencias conceptuales: Thompson Sampling / distribución Beta-Bernoulli
según MABWiser, y separación de asignación y análisis de confianza según
Spotify Confidence. **No se ha copiado código de esos repositorios**;
por ello no se redistribuyen sus fuentes ni sus avisos de licencia.
Las versiones y fechas anteriores son snapshots concretos, no garantía de
mantenimiento futuro. Seguridad de dependencias: sin nueva dependencia,
sin instaladores ni binarios nativos; subsiste el mantenimiento normal
de Python/SQLite.

## Licencias y procedencia

Fuente primaria: https://github.com/spotify/confidence
Fecha de consulta: 2026-10-10
Licencia SPDX: Apache-2.0
Referencia inmutable: https://github.com/spotify/confidence/commit/0f12dd39afd15c48baf24e9d28fcbe72a905bb53

Ninguna fuente externa fue copiada. La tabla anterior desglosa la
procedencia y licencia de las demás opciones; las herramientas privadas
solo se consultaron como contexto, sin copiar sus fuentes.

## Decisión

### Contrato de implementación

Las cuatro familias iniciales son hipótesis editoriales, nunca bancos
de frases:

| Experimento | Superficie | A / B | Resultado binario | Ventana |
|---|---|---|---|---|
| `apertura` | Post | detalle concreto / dilema narrativo | interaction | 7 días |
| `pregunta` | Post | pregunta abierta / reto específico | interaction | 7 días |
| `hashtag` | Post | sin hashtag / hashtag relevante verificado | interaction | 7 días |
| `contexto` | Comentario | detalle observable / cita verificada | reply_received | 14 días |

Para `contexto`, **ambos** brazos requieren contexto real: no se
ensayan comentarios genéricos sin evidencia. El generador de texto
permanece aguas abajo, responsable de validar contenido y evitar repeticiones.
La asignación solo devuelve el nombre del brazo; nunca escribe comentarios.

1. El llamador crea una base SQLite **aislada** y registra `name` con
   `seed` no secreto inmutable.
2. `assign(name, network, unit_id, queue)` devuelve variante estable
   SHA-256 por ensayo/red/unidad; registra exclusivamente el hash de unidad.
   `unit_id` debe ser un identificador **opaco y seudónimo**, jamás un
   usuario, post real, URL ni contenido literal.
3. Solo después de confirmar externamente la exposición se invoca
   `expose(event_id, ..., occurred_at=UTC)`. Sin confirmación, se conserva
   asignación sin exposición; no se cuenta como fracaso.
4. Una observación final de ventana completa (`converted: bool`)
   entra en `outcome` solo tras 7/14 días, con `source` explícito
   (`confirmed_snapshot` o `manual_review`). No se infiere un
   `False` desde una lectura ausente.
5. `report()` proporciona agregados separados por red y experimento:
   asignaciones, exposiciones, madurez, conversiones y Beta(1,1) con
   Monte Carlo **solo exploratorio**, reproducible y sin selección
   adaptativa. `markdown()` forma el panel acumulado. La CLI
   `--format json|markdown --db RUTA` es de consulta sin operaciones
   sociales.

Colas soportadas: `WEB`, `API`, `MOBILE`; redes:
X, Threads, Facebook, Pinterest, Reddit, Bluesky, Mastodon, TikTok e Instagram.
**La presencia de una red en el contrato no verifica que su productor
emita eventos**. Hay que integrar lectores de ACK y snapshots validados
por separado; ninguna cifra real se presume disponible. El seguimiento
de horarios, medios y etiquetas puede añadirse como **estratificación
predefinida** en una futura iteración, no confundirse con los brazos.

Los contadores de `mature` usan únicamente resultados completos,
no asignaciones, clics ni exposiciones pendientes. Una misma
`event_id` con datos iguales es un replay inofensivo; una distinta
carga para esa ID, doble exposición, doble resultado o cola cruzada falla
dentro de la transacción. El hash de unidad no anonimiza entradas
predecibles: el llamador debe generar IDs de alta entropía.

## Pruebas

### Reproducibilidad, antes/después y límites

Comando aislado:

```bash
python -m pytest tests/test_content_comment_experiments.py -q -p no:cacheprovider
python -m compileall -q tools/content_comment_experiments.py tests/test_content_comment_experiments.py
python tools/content_comment_experiments.py --db /ruta/a/experiments.db --format markdown
```

Baseline: el espejo no disponía de API de asignación/exposición/
resultados; el análisis privado solo calcula uplift en cohortes
ya formadas con n >= 100 por brazo. Después: contrato único para
**9 redes × 3 colas × 4 ensayos**, reintentos idempotentes,
ventanas verificadas, resumen sintético de n pequeño sin instalar
paquetes. Los tests ejercitan esas invariantes; no son pruebas de
retorno sobre cuentas ni de Windows/móvil/Edge reales.
El runner CI Linux/Windows Python 3.11 es la verificación reproducible.
No adjudicar porcentajes reales de uplift antes de enlazar exposiciones
con resultados confiables.

Limitaciones adversariales: resultados `confirmed_snapshot` son
declaraciones del llamador, no ACK remoto autenticado; no se verifica
la ausencia de interferencia entre autores, selección editorial ni
calidad subjetiva de texto. La aleatorización por SHA solo es válida
para IDs de alta entropía definidos antes de conocer el brazo; no
corrige experimentos seleccionados a posteriori. Repetidas consultas
a posteriores bayesianos **no** autorizan declarar ganadores; además
hay múltiples redes e hipótesis, dependencia entre interacciones y
falta de denominadores de impresiones. Un estudio confirmatorio
necesita diseño previo, potencia, análisis de asignación y SRM,
ventanas completas y revisión humana. No extrapolar el mismo efecto
de una red a otra.

Segunda revisión adversarial: se corrigió explícitamente el sesgo
de comparar **cuantiles ordenados** de dos posteriores; se permutan
las muestras del brazo B antes del Monte Carlo, de forma reproducible.
Además, el panel incluye un indicador de cobertura para no equiparar
ausencia de exposición a `False`. Pendientes para Claude: validar
el mecanismo de ACK por plataforma, Windows nativo, reloj real,
colisiones semánticas de identidad y canario supervisado con
resultados auténticos (no equipararlo a fixture sintético).

## Retirada

**Retirada / migración:** no hay migración de estados reales. Deshabilitar
productores que usen el motor, conservar/copiar el SQLite aislado,
eliminar módulo y tests. No existe escritura a colas, red ni ledger
operativo; ningún esquema previo queda modificado.

## Resumen de decisión

La continuidad de `experiment_uplift.py` gana para análisis
confirmatorio grande. La implementación nueva complementa ese módulo
con un ledger pequeño, independiente y reversible para experimentos
**offline** con observaciones etiquetadas. No añadir algoritmos
adaptativos que aprovechen ruido de muestras pequeñas ni un SDK
de experimentación con efectos secundarios.
