# Research y Solución: Desambiguación DST en Fichas y Ejecutores de Publicación

## 1. Misión y Necesidad Detectada

En la auditoría de la PR #20 y la cola de publicaciones automáticas de redes sociales, se detectó una vulnerabilidad en el cálculo de horas locales cuando coinciden con transiciones de cambio de hora (Daylight Saving Time / DST):

1. **Horas Inexistentes (Spring-Forward Gap):**
   - En el cambio de hora de primavera (por ejemplo, el 29/03/2026 en `Europe/Madrid`), el reloj salta de las 02:00 a las 03:00.
   - Una ficha con la hora propuesta `2026-03-29 02:30` representa un instante local imposible que no existe en el mundo real.
2. **Horas Ambiguas (Fall-Back Overlap / Solapamiento de Otoño):**
   - En el cambio de hora de otoño (por ejemplo, el 25/10/2026 en `Europe/Madrid`), el reloj retrocede de las 03:00 a las 02:00.
   - Una ficha con la hora propuesta `2026-10-25 02:30` ocurre dos veces:
     - Primero con offset UTC +02:00 (CEST / horario de verano, `fold=0`, 00:30 UTC).
     - Segundo con offset UTC +01:00 (CET / horario estándar, `fold=1`, 01:30 UTC).
3. **Consumo Naive vs. Instante UTC Inequívoco:**
   - Previamente, el parser de fichas (`content_queue.py`) y sus ejecutores (`content_publisher.py`, `content_queue_alert.py`) trataban `datetime` local como naive.
   - Esto provocaba que los ejecutores pudieran comparar incorrectamente la hora naive con la hora del sistema Windows/Linux, provocando que publicaciones salgan con 1 hora de adelanto o retraso, o se cataloguen de forma inconsistente entre sistemas.

---

## 2. Estudio Comparativo de Alternativas y Repositorios Públicos

Se evalúan las principales alternativas y librerías públicas mantenidas:

| Candidato | Tipo / Licencia | Ventajas | Inconvenientes / Riesgos | Decisión |
| --- | --- | --- | --- | --- |
| **Standard Library `zoneinfo` + PEP 495 (`fold`)** | Python stdlib (PSF License) | Nativo desde Python 3.9, cero dependencias de terceros, integrado con `tzdata` (actualizado vía `requirements-ci.txt`). Compatible con Windows/Linux. | Requiere manejo explícito de `fold` y detección de gaps en la conversión a UTC. | **ELEGIDO**: Ligero, robusto, determinista y portable. |
| **`python-dateutil`** | BSD 3-Clause / Apache 2.0 | Muy difundido, soporte para parsing laxo e intervalos de zona. | Añade dependencia externa adicional, parsing demasiado flexible puede ocultar fichas mal formateadas o ambiguas sin advertir al usuario. | Reutilizado solo si fuera necesario para parsing, pero `zoneinfo` nativo resuelve 100% de la lógica temporal sin acoplamiento. |
| **`APScheduler` / `celery` / schedulers pesados** | MIT / BSD | Schedulers completos con persistencia en BD y cron expressions. | Excesivamente pesado para fichas basadas en Markdown/ficheros, rompe el modelo offline/sin estado continuo y la simplicidad de la cola actual. | **DESCARTADO**: Viola el principio de acoplamiento mínimo y simplicidad operativa. |

---

## 3. Arquitectura y Contrato Global de Desambiguación DST

Se define una norma global en `content_queue.py` con adaptadores y preflights por red en `content_publisher.py`:

### A. Formato y Metadatos de Fichas (Compatibilidad Hacia Atrás y Migración)
Las fichas mantienen su campo `Fecha y hora:` o `Fecha:` / `Hora:`. Para desambiguación explícita, se admiten las siguientes claves opcionales en el bloque de metadatos (`- **Clave:** valor`):
- `- **Offset:** +02:00` (o `- **Offset UTC:** +02:00`)
- `- **Fold:** 0` (o `1`)
- `- **Instante UTC:** 2026-10-25T00:30:00Z` (o `- **UTC:** ...`)

### B. Reglas de Clasificación DST
1. **Unambiguous (Hora normal inequívoca):** Se calcula el instante UTC exacto. `fecha_hora_utc` se adjunta al diccionario de la ficha.
2. **Non-existent (Gap / Salto de primavera):** Se marca la ficha con issue en `pending_parse_issues`: `"fecha/hora imposible (salto DST / spring-forward gap)"`. La ficha NO es catalogada como `due` ni `future`.
3. **Ambiguous (Overlap / Solapamiento de otoño):**
   - Si la ficha declara `Offset`, `Fold` o `Instante UTC` explícito, se resuelve inequívocamente al instante UTC correspondiente.
   - Si la ficha NO declara desambiguación explícita, se marca con issue en `pending_parse_issues`: `"fecha/hora ambigua en cambio de hora (fall-back overlap); se requiere offset o fold explícito"`.

### C. Comparación Inequívoca en Preflights y Ejecutores
- En `due_items`, `future_items` y `eligible`, la comparación de vencimiento se realiza comparando instantes UTC (`now_utc = now.astimezone(ZoneInfo("UTC"))` contra `item["fecha_hora_utc"]`).
- No se depende de la zona del reloj local del sistema operativo (Windows / Ubuntu) para tomar decisiones de orden o vencimiento.
