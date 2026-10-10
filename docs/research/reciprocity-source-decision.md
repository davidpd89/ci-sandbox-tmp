# Evidencia mínima verificable — PR #65

## Problema
La regex existente detectaba followback en negaciones y no distinguía comentarios, cadenas ni apoyo mutuo. El análisis extenso, dataset, notas adversariales y limitaciones figuran en [el informe principal](reciprocity-explicit-signals.md).

## Alternativas
RapidFuzz para fuzzy matching; pyahocorasick y FlashText para matching exacto; o aprovechar re, unicodedata y el núcleo reciprocity ya instalado. Las alternativas no proporcionan intención declarada ni contexto de rechazo por sí mismas.

## Licencias y procedencia
Fuente primaria: https://github.com/rapidfuzz/RapidFuzz
Fecha de consulta: 2026-10-10
Licencia SPDX: MIT
Referencia inmutable: https://github.com/rapidfuzz/RapidFuzz/commit/db6e504539a9c895180b266a06b36a32cb6029ee

Otros candidatos: pyahocorasick BSD-3-Clause (https://github.com/WojciechMula/pyahocorasick/commit/4e28d29898f1019d9706485b2a06026466814d9d); FlashText MIT (https://github.com/vi3k6i5/flashtext/commit/f49274459bc9879789c6e6bb64bf05af755de0b3). Fuente del núcleo: tools/reciprocity.py y tools/discovery_terms.py del propio espejo. Ningún código de esas dependencias externas fue copiado o instalado.

## Decisión
Conservar re y normalización Unicode de la biblioteca estándar, ampliar la semántica en un módulo aislado y reutilizar los dos puntos de integración existentes. No requiere ruedas nativas ni variables de entorno. Sin cambios en el código privado.

## Pruebas
python -m unittest discover -s tests -p test_reciprocity_signals.py -v

16 pruebas y 108 casos por nueve redes; workflow Windows/Ubuntu Python 3.11. Datos exclusivamente sintéticos; las métricas de producción y los canarios Edge/Android requieren comprobación posterior.

## Retirada
Revertir la integración de reciprocity.py y discovery_terms.py y retirar el nuevo módulo, tests, fixture y workflow. Sin migración de estado. No se han realizado acciones sociales.

Revisión adversarial final: se impidió que una negación en una cláusula suprimiese otra oferta distinta; se conservaron los patrones heredados «sigo de regreso» y «síguenos y te seguimos». Regresiones específicas añadidas. El detector sigue siendo heurístico y no sustituye comprobaciones de plataforma.
