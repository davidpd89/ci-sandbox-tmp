# Pinterest — elegibilidad independiente por acción

Fuente primaria: https://github.com/pinterest/api-description
Fecha de consulta: 2026-10-10
Licencia SPDX: MIT
Referencia inmutable: N/A (sin codigo incorporado)

## Problema

`build_plan` en la rama base construía una sola lista de Pines `ok` **y no reaccionados** para las tres acciones `react`, `save` y `comment`. Como consecuencia, un Pin ya reaccionado no podía volver a considerarse para guardar o comentar aunque no constasen esas acciones. Es un defecto verificable leyendo la comprensión de `tools/pinterest_growth.py`, no una hipótesis sobre el algoritmo de Pinterest.

## Alternativas

A: mantener el filtro global y ampliar rondas, que nunca recuperaría los pines ya reaccionados. B: filtrar `done_react` exclusivamente en el bucle de reacción y mantener `done_save` y `done_comments` para sus acciones. Elegida B por ser cambio de comportamiento mínimo y probado.

## Licencias y procedencia

No hay código externo copiado. El cambio modifica código existente del proyecto; se consultó el esquema OpenAPI MIT para confirmar el nombre de Pinterest, pero no se integra dependencia nueva. No usar scraping ni guardar tokens.

## Decisión

Un Pin `ok` entra al conjunto de candidatos; cada acción evalúa **su** estado de confirmación por separado. Los topes, la selección de tableros, la deduplicación de URL y el trabajo de red no cambian. Las mismas reglas de independencia de estados deberían revisarse por los adaptadores de las otras ocho redes, dentro de la PR general de paridad (#117), sin reescribirlas aquí.

## Pruebas

Se añaden seis regresiones puras en `tests/test_pinterest_action_eligibility.py`. Ejecutar `python -m pytest tests/test_pinterest_action_eligibility.py tests/test_pinterest_growth.py -q`. La matriz automática Linux/Windows Python 3.11 del mirror servirá de evidencia de ejecución cuando termine. Ninguna prueba abre Pinterest ni Edge.

## Retirada

Revertir el pequeño cambio en `tools/pinterest_growth.py` y eliminar el test. No tocar SQLite, CSV ni registros históricos; no se han ejecutado acciones reales.
