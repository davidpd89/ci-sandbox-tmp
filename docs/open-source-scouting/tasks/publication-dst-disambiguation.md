# Implementación: horas locales ambiguas en la cola editorial

Origen: auditoría y 23 regresiones sintéticas de la PR #20. El calendario
nuevo detecta que una ficha con 29/03/2026 02:30 Europe/Madrid es imposible
y una con 25/10/2026 02:30 tiene dos instantes UTC. Sin embargo, el lector
de fichas existente y sus ejecutores siguen usando datetime local naive.
El informe no impide por sí mismo que otro ejecutor trate la ficha como
vencida, futura o candidata a programación.

## Encargo para GPT

Implementar y probar en código real una política transversal de calendario
para lectores y ejecutores de fichas, sin modificar el comportamiento
normal de fechas inequívocas. Reutilizar content_queue, adaptadores existentes
y el análisis de PR #20; no duplicar el parser ni abrir un scheduler nuevo.

1. Añadir un campo editorial inequívoco opcional (offset o instante UTC)
   para fechas DST ambiguas, con migración de formato documentada y
   compatibilidad hacia atrás; horas inexistentes siempre invalidan.
2. Propagar el instante resuelto a la comprobación de due/future y al
   preflight de publicación. No confundir offset editorial con hora del
   sistema Windows; comparar instantes UTC.
3. Tests sintéticos de spring-forward, fall-back, dos folds, medianoche,
   redes WEB/API/MOBILE, hora normal e idempotencia de reanudación.
4. Los cambios no deben publicar ni programar nada durante pruebas.
   Ningún dato real ni credencial en fixtures, commits o logs.
5. Comparar dependencias públicas actuales (zoneinfo, dateutil,
   APScheduler) con licencias/commits fijos; reutilizar lo compatible,
   evitar plataformas completas.
6. Añadir workflow Windows y Ubuntu Python 3.11, documentación, rollback
   y segunda revisión adversarial. Contrastar con el oficial privado sin
   volcar código ajeno. No hacer merge: revisión de Claude.

Criterio de aceptación: ninguna ruta de ejecución cataloga como lista
una ficha de hora imposible o ambigua sin desambiguación explícita.
Pruebas offline primero; canario supervisado por Claude separado.

Dependencia: PR #20 puede fusionarse independientemente; coordinar con
Claude los cambios comunes al integrar la nueva política.
