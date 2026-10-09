# Chaos testing y fault injection

Investigar librerias publicas para inyectar timeouts, errores HTTP, disco lleno,
JSON truncado, procesos terminados, reloj alterado y fallos de reemplazo atomico.

Crear un harness offline que recorra una operacion completa y pruebe recuperacion,
diagnostico e idempotencia en puntos intermedios. Usar los fallos encontrados
para mejorar transacciones, retries, cuarentenas y mensajes operativos.
