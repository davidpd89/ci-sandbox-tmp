# Encargo — evaluación off-policy con propensiones verificadas

## Encargo para GPT

**Objetivo autónomo:** construir un evaluador estrictamente offline de políticas de ranking de acciones, sin elegir ni ejecutar acciones sociales. Es distinto de [PR #116](https://github.com/davidpd89/ci-sandbox-tmp/pull/116), que solo implementa scoring LinUCB con feedback observado, y de #80/#107/#111, que instrumentan experimentos, normalizan resultados y separan colas; NO copiar esos módulos.

1. Leer el repositorio oficial `davidpd89/rrss-davidporto-CODE` (`integracion/crecimiento-2026-10`) y comparar #116, #80, #107, #111, #66, #71, #103 y #134. No dar por disponibles los registros de probabilidad: detectar qué falta. Verificar otros encargos/PR antes de duplicar.
2. Investigar implementaciones públicas y documentación académica para evaluación off-policy (IPS, self-normalized IPS/SNIPS, doubly robust) con licencias, commits inmutables, actividad y compatibilidad Windows/Python 3.11. Considerar [banditml/offline-policy-evaluation](https://github.com/banditml/offline-policy-evaluation), pero verificar licencia independiente antes de cualquier copia. Preferir dependencia/implementación madura sin vendoring innecesario.
3. Implementar un **contrato común de logging de propensiones/alternativas efectivamente elegibles** para nueve redes y sus colas WEB/API/MOBILE. Probabilidad ausente, cero, mayor que uno, elección determinista sin soporte o grupos sin solapamiento implican **no evaluable**, jamás estimación 0. No inferir probabilidades desde scores LinUCB. Validar ID de episodio, identidad, muestras únicas, observación madura D+7 y calidad de evidencia.
4. Ejecutar un backtest secuencial solo con datos sintéticos y un estimador IPS/SNIPS con tamaño efectivo de muestra, intervalos de incertidumbre, tamaño mínimo y diagnóstico de soporte/varianza. DR solo si hay nuisance model validado fuera de muestra para no inventar causalidad. Respetar cohortes, redes y colas: ninguna mezcla automática ni fuga temporal.
5. Tests de reproducibilidad, pesos extremos, censura D+1/D+3, fechas, duplicados, ruido/adversarial inputs y nueve redes. CI Ubuntu/Windows Python 3.11, documentación breve con resultados y rollback.
6. No tocar redes, credenciales, sesiones, seguidores reales ni modificar planes. No habilitar ranking automático por un único backtest. No hacer merge; Claude revisará integración con #116 y las otras PR dependientes.

**Valor independiente:** #116 aprende sobre los resultados de acciones efectivamente elegidas, pero no permite comparar políticas alternativas con garantía de soporte. Este encargo aporta medición de si una política candidata mejora frente a los datos registrados o si, por falta de propensiones/suficiente cobertura, debe declararse no evaluable.

**Rama:** `research/bandit-offpolicy-propensity-replay`. **Base:** `research/public-reuse-parent`.
