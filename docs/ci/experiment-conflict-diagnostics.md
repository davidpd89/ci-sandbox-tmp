# Diagnóstico de colisiones de ensayos v2 (sin cambio de política)

Dependencia: [PR #91](https://github.com/davidpd89/ci-sandbox-tmp/pull/91), rama base `ci/experiment-evidence-lineage`.

## Problema verificable

`duplicate_evidence` cuenta propuestas positivas bloqueadas, pero agrupa tanto
replay del mismo ensayo como ensayos independientes con igual origen, táctica,
red de destino y cola. También oculta réplicas negativas y no auditadas; todas
mantienen el mismo veto conservador. Este agregado no permite diagnosticar qué
evidencia hace falta contrastar antes de mejorar el aprendizaje entre redes.

## Contrato añadido

Solo para `schema=2` el informe agrega `collision_diagnostics` con contadores
sin identificadores ni datos de cuentas:

- `same_trial_replay`: evidencia repetida de idéntica tupla
  (ID, SHA de diseño, SHA de asignaciones).
- `distinct_trials`: colisión entre identidades de ensayo diferentes.
- `includes_non_positive`: al menos una de las réplicas del grupo no
  supera el umbral Wilson positivo.
- `includes_unreviewed`: al menos una réplica del grupo carece de
  aprobación en el `TrustedRegistry` para ese destino y cola.
- `includes_unknown_queue`: una fila sin cola reconocida contamina la
  colisión de una cola concreta o la propia cola indeterminada.

**Los contadores son por propuesta positiva vetada**, no por grupo. Las
categorías se solapan: una colisión de identidades distintas puede incluir
una réplica negativa y no auditada. Las pruebas recorren 8 redes × 7 destinos
× 3 colas = 168 combinaciones, más replay, réplica negativa y cola desconocida.

El estado `proponer_ensayo_manual`, `suppressed`, `duplicate_evidence`,
`writes: false`, el TTL, el registro externo, las verificaciones
`schema=1` y el bloqueo de colisiones **no cambian**. `schema=1`
conserva su estructura de informe sin este campo nuevo.

## Validación y alcance

```powershell
py -3.11 -m compileall -q tools tests
py -3.11 -m pytest -q -p no:cacheprovider tests/test_cross_network_learning.py tests/test_experiment_evidence_lineage.py
py -3.11 -m pytest -q -p no:cacheprovider tests
```

Pruebas offline de lectura, Windows y Ubuntu; sin credenciales, cuentas ni
acciones reales. Exigir checks en el HEAD de esta nueva PR. Al trasladar al
oficial, conciliar antes la PR #91 y el gate de #3, y conservar la política
conservadora hasta diseñar una resolución de contradicciones con procedencia
auditada. No interpretar `includes_unreviewed` como fraude: solo indica que
no existe una aprobación en el registro recibido.
