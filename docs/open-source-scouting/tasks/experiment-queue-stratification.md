# Ensayos multired: análisis separado por cola WEB/API/MOBILE

Origen: revisión adversarial de [PR #80](https://github.com/davidpd89/ci-sandbox-tmp/pull/80) el 2026-10-10.
Estado: encargo de implementación **pendiente**; esta PR nace en borrador.
Dependencias funcionales: #80 (ledger), #91 (identidad de ensayos), #107 (fuentes/ACK).

## Hallazgo reproducible

En `tools/content_comment_experiments.py::report` de #80,
la consulta agrupa por `name, network, arm` (sin `queue`) aunque la
asignación se fija en `WEB`, `API` o `MOBILE`. El JSON expone una
probabilidad Beta exploratoria por red; no permite comprobar qué cola
contribuye a exposiciones, resultados maduros y conversiones de cada
brazo. La prueba existente recorre las nueve redes, pero utiliza solo
una de las tres colas por red: no cubre simultáneamente las 27 parejas.

Esto es relevante para todas las redes: una cola con tasas de ACK,
audiencia y captura diferentes puede cambiar el agregado sin reflejar
el efecto editorial. No mezclar heterogeneidad operativa con aprendizaje
del contenido. La solución debe ser genérica, sin ramas particulares
por proveedor.

## Encargo para GPT

1. Leer PR #80 **en su HEAD actual** y `docs/open-source-scouting/PROTOCOL.md`.
   Revisar #91/#107 y el módulo privado `experiment_uplift.py` **solo en
   lectura** para evitar contratos duplicados.
2. Implementar desglose `network × queue × arm` de asignados,
   expuestos, resultados finales y éxitos. Conservar totales por red,
   comprobar que sus sumas coinciden y distinguir `unknown` de `False`.
3. Publicar métricas de cobertura por cola (proporción expuesta,
   observación final y resultados ausentes/vencidos). No atribuir una
   conversión ausente a fracaso ni llamar `pending maturity` a una
   observación ya vencida sin explicitarlo.
4. Mantener compatibilidad o introducir migración versionada explícita
   con pruebas del esquema JSON de #80. Cualquier estimación por red
   combinada ha de marcarse descriptiva/no comparable cuando se mezclen
   colas; si se calcula un estimador estratificado, documentar supuestos,
   denominadores y relación con #23 / `experiment_uplift.py`.
5. Construir fixtures deterministas de las **9 redes × 3 colas × 2
   brazos**, con estratos desequilibrados, replays idempotentes,
   exposiciones sin snapshot final y una cola sin observabilidad. Incluir
   una regresión que capture la diferencia entre agregado ingenuo
   y lectura estratificada; nunca proponer acciones desde posterior.
6. Investigar alternativas públicas vigentes con SHA/tag y licencia,
   documentar por qué reutilizar stdlib/los módulos existentes o
   incorporar un componente mejora el resultado. Comparar dependencias,
   mantenimiento y compatibilidad Ubuntu/Windows Python 3.11.
7. Implementación real + tests + informe `docs/research` + segunda
   revisión adversarial y CI offline en Windows y Ubuntu.
   Sin llamadas sociales, credenciales, secretos ni datos de cuentas.
   **No hacer merge**.

## Fuera de alcance

Esta PR no fabrica observaciones de las redes (#107), no valida
identidades independientes de ensayo (#91), no genera comentarios ni
decide rankings. Puede utilizar APIs del ledger de #80, sin duplicarlas.

## Criterios de aceptación

- Para una misma red, observar simultáneamente las tres colas sin
  pérdida ni duplicación; sumas por cola = totales por red.
- Resultado no disponible no equivale a negativo, tanto en JSON
  como en Markdown.
- La estimación no es causal ni comparable sin cobertura suficiente,
  incluso cuando un agregado global dé una probabilidad extrema.
- Test de compatibilidad con base SQLite histórica de #80 y regresión
  de nombres/métricas de la definición persistente.
- CI verde en HEAD final; integración real y canario quedan a Claude.
