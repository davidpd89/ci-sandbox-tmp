# Colas, idempotencia y recuperacion

Investigar implementaciones publicas de durable queues, outbox/inbox, intent
logs, leases, locks, retries con jitter, dead letters y reconciliacion.

Comparar con action ledger, reply/content/round queues y CSV actuales. Adoptar
una tecnica pequena que sobreviva a crash, doble proceso y confirmacion incierta
en Windows y Linux. Probar fault injection y replay sin depender de servicios
externos ni introducir infraestructura desproporcionada.
