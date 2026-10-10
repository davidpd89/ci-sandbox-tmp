# Port mínimo de lectura de conversaciones en Threads (10/10/2026)

Origen: PR #14; destino: base sincronizada `research/public-reuse-parent` (commit 737fc01 inspeccionado). **No se porta el publicador ni el ejecutor** del mirror anterior: la base ya contiene `reply_provenance`, `action_ledger`, `conversation_turn_policy` y el contrato POST→ACK→TTL.

## Problema

El cliente oficial sincronizado leía solo una página de `me/threads` y de replies: las preguntas antiguas, hijas de otras respuestas y las ya contestadas podían interpretarse mal.

## Alternativas

1. SDK de Threads externo: añade dependencias y cambia el contrato del publicador protegido.
2. Reemplazo integral con la PR #14: **descartado** porque elimina los certificados y ledger del repo operativo.
3. Port selectivo y sin dependencias de lectura por cursor y reconstrucción de ancestros: **elegido**.

## Licencias y procedencia

Fuente primaria: https://www.postman.com/meta/threads/documentation/dht3nzz/threads-api
Fecha de consulta: 2026-10-10
Licencia SPDX: NOASSERTION
Referencia inmutable: N/A (sin codigo incorporado)

El ejemplo público de https://github.com/fbsamples/threads_api (JavaScript/Node) es complementario; no se copia código ni se añaden paquetes. Implementación propia extraída de la rama interna de revisión #14 y adaptada a la base protegida.

## Decisión

## Cambio

- `paginated` consume únicamente el endpoint fijo original con cursor `after`, nunca una URL de `paging.next`; deduplica ID y aborta ante errores, cursores cíclicos o presupuesto de páginas excedido. Un lote incompleto no genera candidatos silenciosamente.
- `followups` reconcilia `me/replies` y `/{id}/conversation`, reconstruye el camino comprobable raíz→destino y solo admite preguntas directamente dirigidas a un mensaje propio. Si la cadena o el padre no son verificables, detiene el barrido.
- El constructor conserva fecha `target_created_at` e historial `thread_turns`, **sin fabricar certificados**: mantiene `reply_provenance.carry_decision_proof` original. Sin GET ni POST reales en tests.
- No se cambia el algoritmo global de selección, ranking, edad ni los adaptadores de otras redes; esta es una implementación nativa del contrato transversal de contexto comprobado. Para Meta en Facebook/Instagram, centralizar cursores solo tras comparar su código y las PR #15/#16/#41.

## Contraste externo

Fuente principal: colección oficial Meta, https://www.postman.com/meta/threads/documentation/dht3nzz/threads-api (ejemplos `paging.cursors.after`, `me/replies`, `/{thread_id}/conversation`). Ejemplo oficial https://github.com/fbsamples/threads_api usa Node.js, no ofrece una sustitución Python 3.11 más conveniente. No se añade una dependencia; licencia y código de esta portabilidad son propios del repositorio.

## Pruebas

Comprobaciones reproducibles y fixtures sintéticos; verificar logs de Actions del nuevo HEAD antes de considerar verde.

## Comprobaciones

```powershell
python -m pip install --disable-pip-version-check -r requirements-ci.txt
python -m compileall -q tools tests
python -m pytest tests/test_threads_conversation_read_port_2026.py tests/test_threads_api.py tests/test_threads_execute_api.py -q -p no:cacheprovider
python -m pytest tests -q -p no:cacheprovider
```

En integración privada, comprobar con un **GET supervisado y autorizado** `me/replies`, `/{id}/conversation` y paginación (con y sin `paging.next`), sin publicar; probar en Windows Python 3.11. Repetir suites de ledger, certificados, política de antigüedad y ejecutores por red; prohibido el port del `publish_reply` de #14. Paginación limitada a cinco páginas por recurso: ante una cuenta de mucho volumen aborta en lugar de presentar falsamente una bandeja completa. Extensión incremental y observabilidad en contrato común: coordinar con #41, no duplicar mecanismo ahora.

## Retirada

Rollback: revertir este único cambio de lectura, sin migración ni datos operativos.
