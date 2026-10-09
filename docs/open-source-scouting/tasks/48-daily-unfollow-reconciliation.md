# Reconciliacion diaria de unfollow

Revisar los jobs diarios que detectan follows pendientes de reciprocidad y
ejecutan la accion correspondiente en cada red. Comprobar paginacion, ventanas
temporales, reintentos, confirmacion remota, cursores y ejecuciones parciales.

Preparar fixtures para miles de relaciones y fallos intermedios. Implementar
reconciliacion idempotente, resumen por red y pruebas repetibles que demuestren
que dos rondas producen el mismo estado confirmado.
