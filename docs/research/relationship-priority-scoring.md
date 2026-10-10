# Priorización diaria de relaciones: implementación y revisión

**Estado:** código offline en la PR #71; no merge, no publicaciones, no llamadas a redes, no datos reales.
**Fecha de investigación:** 10/10/2026. **Python:** >=3.11, biblioteca estándar (solo pytest en CI).
**Rama/base:** `research/61-relationship-priority-scoring` / `research/public-reuse-parent`.

## Hueco real y comparación con el sistema existente

La implementación base ya registra interacciones entrantes en
`tools/relationship_policy.py` (`inbound_interacciones.csv`),
las agrega de forma sencilla en `tools/loyalty.py::loyal_handles`
y calcula señales de followback en `tools/reciprocity.py`.
`tools/conversation_followups.py` filtra conversaciones por contexto.
Faltaba **una vista diaria común**, explicable, estable y con presupuestos
independientes WEB/API/MOBILE para elegir cuentas con prioridad, sin
ejecutar automáticamente nada. Ningún algoritmo debe sustituir las
políticas de elegibilidad antes de redactar/ejecutar.

El repositorio oficial privado
`davidpd89/rrss-davidporto-CODE@integracion/crecimiento-2026-10`
se consultó mediante el conector GitHub; por ejemplo
`tools/loyalty.py` blob `c60cd8c70fed57fc840bb620ae7c8f5877e98381`,
`tools/growth_core.py` blob `f3a4ff43a75a2efe4cd7de6a4b7e79f4f2092dcd`
y `tools/relationship_policy.py` (contrato de comentarios, follows
y bloqueos). El mirror tiene una versión ligeramente distinta de loyalty.
No se publicó contenido privado ni se modificó ese repositorio.

### Software público comparado (commits fijos)

| Proyecto / revisión comprobada | Licencia | Actividad verificada | Reutilización / compatibilidad |
| --- | --- | --- | --- |
| [Olga-lab1/lead-scoring-engine@096c174](https://github.com/Olga-lab1/lead-scoring-engine/tree/096c174c7e35501ea0ff5ddd7474b0bc65ea7c66) | MIT | 07/07/2026 | Buen patrón de contribuciones explicables, entrenamiento y evaluación temporal. XGBoost, SHAP, FastAPI y un modelo entrenado para B2B exceden el problema; Python 3.11 plausible, stack mucho más pesado y sin observaciones reales de conversión. |
| [scikit-learn@46449a1](https://github.com/scikit-learn/scikit-learn/tree/46449a10defc79e0615391c15106fc966bbc8261) | BSD-3-Clause | 09/10/2026 | Modelos/calibración mantenidos; Windows + Python 3.11 soportables según distribución, pero primero hacen falta etiquetas maduras, volumen y evaluación temporal fiable. No se añade. |
| [AmenRa/ranx@7363db0](https://github.com/AmenRa/ranx/tree/7363db0c35e92e90d6fa6fe73907b760678f765e) | MIT | 07/08/2025 | Implementa NDCG/MAP, comparaciones de rankings; Numba/instalación más costosa que precision@k descriptivo en un cohort pequeño. Actividad menos reciente; no se añade. |
| Sistema original: `loyalty.py`, `relationship_policy.py`, `reciprocity.py` | código propio | octubre 2026 | Mantener como fuente de elegibilidad y señales, **no duplicar** políticas, decisiones de hilo o almacenamiento. |

**Decisión:** adaptar el patrón público de *puntuación explicable y validación
temporal* mediante una implementación original pequeña en stdlib. **No se
copió código tercero**; no hay nuevas licencias ni dependencias que
redistribuir. La continuidad de las reglas existentes gana frente a
reemplazarlas por un clasificador prematuro.

### Piezas y contrato

- `tools/relationship_priority.py`: `rank_daily(snapshot, today=...)` recibe
  `{"candidates":[...]}`, normaliza, valida, deduplica dentro de la red
  y elige **una recomendación** por cuenta. Cada fila requiere
  `network`, `lane` (WEB/API/MOBILE), `handle` y flags de elegibilidad
  autorizados por el adaptador que recogió el candidato.
- Señales opcionales: `actor_id` estable; `inbound` con contadores
  `comment/follow/repost/like` **ya deduplicados en origen**;
  `last_inbound_at`, `last_outbound_at`, `latest_post_at`,
  `reply_target_at` (YYYY-MM-DD, no timestamp naive);
  `affinity` y `reciprocity` en [0,1]; `outbound_30d`.
  No inferir afinidad/reciprocidad a partir del handle, no confundir
  cuenta seguida con cuenta recomendada.
- Elegibilidad explícita (bool por defecto falso):
  `reply_eligible`, `thread_verified`, `follow_eligible`,
  `already_following`, `reactivation_eligible`, `visit_eligible`,
  `blocked`, `self_account`. Una acción de respuesta necesita un
  hilo verificado y destino de hasta 7 días. La reactivación solo propone
  revisar un post reciente tras 14-90 días sin contacto. Un perfil sin
  publicación reciente puede visitarse, no comentar contenido antiguo.
  Nada habilita likes automáticos en X.
- Puntos auditables: hasta +12 nicho, +32 señales entrantes,
  +15 recencia (semivida 14 días), +8 tipos distintos, +8 reciprocidad
  si se conoce, +6 tiempo sin contacto, -15 fatiga y bono por acción
  (reply +16; follow +7; reactivate +5; visit +1).
  Las puntuaciones no pretenden ser probabilidades de conversión.
- Orden estable sin aleatoriedad: elección por `score`, desempates
  deterministas, y **diversidad blanda** por red (-3 puntos por elección
  previa de la misma red *en esa cola*). No hay cupos duros por red.
  Una cuenta solo aparece una vez, incluso si varios adaptadores
  informan de ella en colas distintas. WEB/API/MOBILE conservan cada
  una su límite propio, no consumen presupuesto de la otra.
- `notes`, `eligible_actions`, `features`, `score`, `selection_score`,
  `excluded` y `summary` hacen visible cada decisión. El campo
  `action` es **propuesta**; nunca un plan ejecutable.

Ejemplo sin credenciales, sobre un JSON **sintético y explícito**:

```powershell
python -m tools.relationship_priority --input fixtures_sinteticos.json --today 2026-10-10 --format markdown
python -m tools.relationship_priority --input fixtures_sinteticos.json --today 2026-10-10 --format json --evaluate-synthetic
python tools/relationship_priority_backtest.py
python -m pytest tests/test_relationship_priority.py -q
```

El CLI **solo lee** `--input` y emite stdout. No acepta rutas implícitas
del entorno operativo ni abre conexión, ejecutor, credenciales, Selenium,
Edge, Android, SQLite o CSV de estado. Para llevar el modelo al sistema
real hay que unir adaptadores de lectura de los nueve colectores;
recomprobando `comment_allowed`, bloqueos, estado de follow, fecha y
antigüedad **en preflight**, bajo la política compartida.

## Backtest sintético y criterio para medir después

`tools/relationship_priority_backtest.py` genera de forma determinista
216 cuentas ficticias (9 redes x 24), reparte 72 perfiles por cola
y compara **precision@10** del score frente a una selección ingenua por
número de likes. Simula un segundo día sin nuevas observaciones para
medir estabilidad por Jaccard y cobertura de redes por cola.
El campo ficticio `converted` **jamás se pasa a la función de scoring**,
solo a la evaluación posterior. Si faltan etiquetas, la precisión se
publica como `null`, no como 0 ni éxito supuesto.

Esto es una **prueba simulada**, no un backtest observado de seguidores,
respuestas o reciprocidad reales. Para un canario supervisado, exportar
solo snapshots validados, registrar cohortes y fecha de decisión,
esperar maduración del resultado, hacer un holdout temporal y contrastar
precision@k, diversidad y churn frente a la política anterior, por red
y por cola, **sin autorizar acciones por este motor**.

## Revisión adversarial y límites

- Entradas malformadas se aíslan por fila; no hay una caída global por un
  perfil defectuoso. NaN/infinito/valores fuera de rango, fechas futuras,
  fechas entrantes ausentes, tipos desconocidos y booleanos inválidos
  se excluyen con motivo reproducible. Se conserva una vista JSON de descartes.
- Casos cruzados: 9 redes, 3 colas, auto-cuentas, cuentas bloqueadas,
  actores con handles repetidos entre redes, duplicados entre colas,
  posts antiguos, reactivación, límites vacíos, miles de candidatos,
  estabilidad con entrada invertida, fatiga y filtrado por fecha.
- Revisión 1: el motor nunca autoriza acciones por inferir señales;
  eliminar la posibilidad de ejecutar un plan directamente desde la salida.
- Revisión 2: se detectó escape doble del regex de handles en el commit
  inicial; se corrigió en `tools/relationship_priority.py` y se incluyó
  una regresión de entrada válida con Unicode. Las etiquetas de backtest
  no modifican scores, y los duplicados cruzados no duplican presupuesto.
- **Límites:** las afinidades, pesos y semivida son heurísticos todavía
  no calibrados. Las observaciones pueden estar incompletas o agregadas
  con granularidad diaria; un CSV diario de inbound no distingue
  múltiples interacciones iguales. No se promueven acciones a partir
  de fechas/identidades no verificadas. Windows 3.11, Edge, ADB y APIs
  reales no equivalen a las simulaciones.

**Rollback:** se pueden retirar los tres archivos
`tools/relationship_priority*.py`, su test y su workflow sin migrar
datos ni cambiar planificadores: la herramienta no escribe estado.
**Relación con PR cercanas:** #69 crea señales inbound, #65 trata
reciprocidad, #66 ranking de posts/cuentas, #60 estados de relación,
#25 CRM. #71 toma esas señales ya validadas y selecciona la
**agenda relacional diaria**, no reemplaza esos módulos. La integración
productiva necesita revisión conjunta posterior de Claude.
