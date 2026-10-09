# Instagram — control de publicaciones ambiguas

Fecha: 09-10-2026. Diagnóstico: el flujo del mirror puede volver a enviar una ficha cuando `media_publish` pierde la respuesta y la verificación remota no permite confirmar el resultado. Esta nota identifica el problema; las pruebas y la solución deben incorporarse antes del merge.

El journal SQLite debe bloquear reintentos inciertos.
