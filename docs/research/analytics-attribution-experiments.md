# PR #23 — Analítica, atribución y experimentos (10-10-2026)

## Problema

El espejo disponía de atribución parcial sin informe reproducible de ausencia, controles y madurez.

## Alternativas

Se compararon GrowthBook, statsmodels, SciPy, Matomo y continuidad del cálculo existente (detalle y SHAs más abajo).

## Licencias y procedencia

Fuente primaria: https://github.com/statsmodels/statsmodels
Fecha de consulta: 2026-10-10
Licencia SPDX: NOASSERTION
Referencia inmutable: https://github.com/davidpd89/rrss-davidporto-CODE/blob/d3bc39a12ec3bf87d3998979be70da8dce9fbaa8/tools/experiment_uplift.py

La etiqueta NOASSERTION se refiere exclusivamente al módulo propio extraído del repositorio privado del usuario; la tabla inferior identifica las licencias SPDX de cada alternativa externa, sin incorporar código de terceros.

## Decisión

Implementación mínima offline sobre la biblioteca estándar, módulo estadístico propio y Wilson ya disponible.

## Pruebas

Pruebas deterministas de evidencia, control, deduplicación, ventanas, métricas y compatibilidad de nueve redes/tres colas. La CI verifica el contrato en Ubuntu/Windows y la suite de pruebas debe ejecutarse expresamente en Python 3.11.

## Retirada

Revertir el commit de esta PR. No hay nuevas dependencias, secretos, credenciales ni migraciones persistentes.

## Decisión y alcance

Se integra un **informe offline, descriptivo, por evidencia confirmada**, separado de los ejecutores y de la asignación experimental. No se añade servicio, credencial, conexión de red, nueva dependencia ni acción social. El objetivo real no es maximizar contadores, sino distinguir **observado / desconocido / inmaduro / duplicado** sin fabricar tráfico, ventas, lecturas o causalidad.

El espejo de partida ya contenía \`tools/growth_attribution.py\`, con tasas de follow-back y Wilson, pero el CLI operativo obtenía seguidores de Bluesky/Mastodon y no ofrecía un contrato de embudo web/ventas ni informe sin red. Se consultó **solo en lectura** la rama \`integracion/crecimiento-2026-10\` del repo privado \`davidpd89/rrss-davidporto-CODE\`: allí existe \`tools/experiment_uplift.py\` (blob \`d3bc39a12ec3bf87d3998979be70da8dce9fbaa8\`), que se incorpora **íntegro y sin datos de producción** para no reconstruir el cálculo Newcombe-Wilson/SRM ya realizado por el propio proyecto. También se revisó \`tools/growth_attribution.py\` privado (blob \`ff8f77a0326c5c1f3a3daefd321856d2fd2f7f76\`) con correcciones posteriores de holdout. **No se retroporta el CLI online privado** ni se toca el código de producción.

Se añade \`tools/analytics_evidence.py\`: una norma para **nueve redes** (X, Threads, Facebook, Pinterest, Reddit, Bluesky, Mastodon, TikTok, Instagram) y **tres colas** (WEB, API, MOBILE), sin bifurcaciones de calidad por red. Su entrada son evidencias normalizadas y seudónimas que otros productores pueden suministrar; esta PR no afirma que ya existan productores completos. Se respetan alcances: #80 asignación/motor A/B; #91 identidad; #107 adaptadores de observación; #111 estratificación del motor por cola; #86 embudo operativo. No se duplican.

## Reutilización pública investigada el 10-10-2026

| Candidato, procedencia inmutable | Licencia | Mantenimiento comprobado | Compatibilidad y coste | Decisión |
|---|---|---|---|---|
| [GrowthBook Python SDK](https://github.com/growthbook/growthbook-python/tree/5366593b6c7624c0b7e4c4b4db1ee240f127bbd2), \`5366593\` | MIT | commit 05-10-2026, repositorio activo | Python, Windows y Linux; añade cliente de flags/asignación y piezas operativas no requeridas | No adoptar: #80 ya cubre asignación; usar principios de exposición explícita |
| [statsmodels](https://github.com/statsmodels/statsmodels/tree/9bf43a292c6e906754744fef3b1a77c5e549410f), \`9bf43a2\` | BSD-3-Clause | commit 08-10-2026 | Soporta Python 3.11/Windows en versiones publicadas; stack NumPy/Pandas/SciPy costoso para informe pequeño | No introducir solo para una proporción |
| [SciPy](https://github.com/scipy/scipy/tree/ecee36d388004b86bdf56bf3fd7498006cddda96), \`ecee36d\` | BSD-3-Clause | commit 09-10-2026 | Wheels Windows/Python 3.11 en releases compatibles; rama main puede exigir Python más reciente, y añade stack científico | No introducir: análisis existente ya aplica Wilson y SRM |
| [Matomo MarketingCampaignsReporting](https://github.com/matomo-org/plugin-MarketingCampaignsReporting/tree/94bd2c542b6b4ef2103596d549c41a6503afef50), \`94bd2c5\` | GPL-3.0 | commit 09-10-2026 | PHP/Matomo, no módulo Python/Windows independiente | No copiar código GPL a motor MIT/propio; solo usar idea de separación UTM/venta verificada |

Repositorio y metadatos consultados a través de GitHub; las fechas documentan actividad, **no** demuestran por sí solas salud de dependencias o ausencia de vulnerabilidades. Ningún archivo público se copia. El único módulo copiado es código propio del repositorio privado autorizado. Dependencias añadidas: **cero**. Esta elección preserva compatibilidad Python 3.11 y Windows al utilizar la biblioteca estándar.

## Contrato de datos

Entrada JSON v1 (UTF-8) con \`schema_version=1\`, \`as_of\` UTC ISO con \`Z\`, \`window_days\` (1..365), \`exposures\` y \`observations\`. Límite de CLI: 2 MB. Se rechazan claves JSON duplicadas, NaN/Infinity, fechas futuras, IDs que no sean seudónimos alfanuméricos, redes/colas desconocidas y registros malformados. El tiempo es una ventana de observación, **no** el máximo de antigüedad para actuar sobre un post.

Cada exposición declara \`id, network, queue, campaign, subject, action, cohort, status, source, source_ref, occurred_at\`. Tratamiento exige estado \`confirmed\` y ACK de \`action_ledger/confirmed_api/confirmed_web/confirmed_mobile\` (los estados \`failed/uncertain\` se contabilizan únicamente en calidad y no entran en denominador). Control exige \`status=holdout\`, \`source=holdout_ledger\`, nunca tracking/UTM. Si una misma persona se asigna a tratamiento y control en una campaña/red: **error**, nunca se omite silenciosamente. Se toma la primera exposición elegible por persona/red/campaña para evitar contar varios follows como adquisiciones distintas. \`tracking_id\` no puede reutilizarse entre personas/campañas/redes.

La evidencia de resultado declara \`id, exposure_id, outcome, positive, complete, observed_at, source, source_ref, basis\`. \`outcome\`: \`followback\` (snapshot API y enlace por identidad), \`web_visit\` (analítica de primera parte), \`sale\` (sistema de pedidos), \`reading\` (sistema de lecturas). Para los tres resultados web/compra/lectura es obligatorio el \`tracking_id\` exacto; para visita también UTM exacta. Se rechaza un recibo positivo utilizado por exposiciones distintas. **Nunca se deriva venta de visita, lectura de venta ni seguimiento de un simple like.**

### Semántica de madurez y ausencia

- **Inmaduro**: antes de \`occurred_at + window_days\`, no se publica tasa.
- **Desconocido**: cohorte madura sin prueba suficiente, o negativo provisional/incompleto: no es cero.
- **Negativo**: solo \`positive=false\` con \`complete=true\` y sello de captura al final de la ventana; el productor debe avalar que el snapshot está completo.
- **Positivo**: fuente específica verificada dentro de la ventana; se admite aunque el seguimiento no haya acabado, pero la tasa permanece ausente mientras haya inmaduros/desconocidos.
- **Conflicto** entre positivo y negativo definitivo: error explícito.

Desglose de salida: \`network × queue × campaign × cohort × outcome\`, contadores \`eligible/immature/positive/negative/unknown\`, \`readiness\`, tasa e intervalo de Wilson 90 % **solo si todas las unidades del grupo están maduras y tienen resultado conocido**. También se informa sobre duplicados, acciones sin confirmar, repetición de sujetos, observaciones fuera de ventana y redes sin exposición. El informe se califica **\`descriptive_only_not_causal\`**: ninguna diferencia entre brazo de tratamiento y holdout prueba incrementalidad. Los intervalos son descriptivos, no corrigen selección, interferencia, muestreo, tests secuenciales ni comparaciones múltiples.

\`tools/experiment_uplift.py\` ofrece **aparte** dos cohortes preasignadas, umbral mínimo 100 por brazo, SRM, Newcombe-Wilson, banderas auditables de diseño, rechazo de redes mezcladas y \`causal_claim_approved=False\` siempre. Las banderas proporcionadas externamente no sustituyen la auditoría.

## Ejecución reproducible y regresiones

\`\`\`bash
python tools/analytics_evidence.py tests/fixtures/analytics_evidence.synthetic.json
python -m unittest discover -s tests -p "test_analytics_evidence.py" -v
# En CI, ejecutar el test sobre Windows y Ubuntu con Python 3.11.
\`\`\`

Fixture 100 % sintético: tratamiento Bluesky/API maduro con follow-back y visita verificadas, control Bluesky/API maduro con negativo completo de follow-back, tratamiento TikTok/MOBILE inmaduro y sin resultado. Ningún secreto ni handle real. Ejecución no abre navegador, no lee registro de producción y no llama a API. Pruebas de regresión incluyen 9 × 3, identidad de experimentos, ausencia ≠ cero, control, ventana negativa tardía, contradictorios, tracking/UTM, doble recibo, deduplicación, CLI y rechazo de JSON. La versión local previa del analizador superó 22 pruebas con Python 3.13.5; para **este HEAD** es obligatoria validación CI sobre el código realmente cometido y Windows/Python 3.11 antes de integrar.

Comparación de cobertura frente al espejo original: antes, \`growth_attribution\` calcula solo las tasas de follow-back por API Bluesky/Mastodon; después, el informe **puede representar** nueve redes, tres colas y cuatro métricas con metadatos de pruebas sintéticas. No es aumento demostrado de acciones, tráfico ni ventas: faltan productores vivos de evidencia.

## Segunda auditoría adversarial y límites

Primera revisión: detectados y corregidos fixture JSON incompleto y una aserción de test demasiado permisiva durante el prototipado. Segunda revisión: 1) un negativo anterior a horizonte no cierra ventana; 2) no se acredita un recibo para dos campañas/personas; 3) si coexisten positivo y negativo final se rechaza; 4) se rechazan mezclas de brazos; 5) todos los datos sintéticos y no se consulta red; 6) el analizador experimental externo nunca autoriza automáticamente causalidad. Seguimiento aún requerido: productores de #107 deben aportar prueba de snapshot completo y ACK nativo; mantener condición de identidad estable ante renombres; ejecutar smoke en Windows vivo y canario supervisado solo con aprobación específica. Prueba sintética no es canario.

## Retirada / rollback

Revertir el commit que incorpora \`tools/analytics_evidence.py\`, \`tools/experiment_uplift.py\`, pruebas y fixture. No hay migración de SQLite, cambio de estados, secretos, dependencia, tarea programada ni acción en redes. El módulo original \`growth_attribution.py\` del espejo permanece intacto. No hay configuración persistente que deshacer.
