# Plantilla de evidencia por PR hija (copiar a docs/research/<tema>.md)

## Problema

Síntoma reproducible en mirror y comprobación equivalente en original
privado; evidencia sintética, rutas de módulo y SHA de cada entorno.
Distinguir hallazgo reproducido de hipótesis.

## Alternativas

| Baseline | Candidato OSS | Adaptar patrón | Mantener baseline |
|---|---|---|---|
| Coste, fallos, tests | API, licencias, actividad | Complejidad propia | Riesgos/controles |

Incluir razones para adoptar o rechazar; no decidir por número de estrellas.

## Licencias y procedencia

Fuente primaria: https://docs.github.com/en/rest/pulls/pulls
Fecha de consulta: 2026-10-09
Licencia SPDX: NOASSERTION
Referencia inmutable: N/A (sin codigo incorporado)

**Sustituir los valores de ejemplo con referencias del caso real.**
`NOASSERTION` no autoriza copiar código. Si no se incorpora código
OSS, dejar explícito `N/A (sin codigo incorporado)`; si sí se incorpora,
aportar enlace permanente al tag/commit, licencia SPDX del componente,
autor, avisos, dependencias transitivas y condiciones de acceso.
No pegar ficheros privados ni tokens en el informe público.

## Decisión

A: componente mínimo / B: dependencia / C: patrón reimplementado /
D: conservar lo existente. Señalar flags, permisos y límites por red.

## Pruebas

Comando ejecutado, entorno, SHA, fixture sintético, antes/después con
la misma entrada, casos hostiles, resultado esperado/real. Tests nuevos
en `tests/`, sin acciones reales. No declarar ejecución que no ocurrió.

## Retirada

Feature flag default-off; pasos de rollback, compatibilidad de estados,
recuperación y verificación tras rollback. Identificar dueño del proceso
y autorización humana antes de integración en original privado.
