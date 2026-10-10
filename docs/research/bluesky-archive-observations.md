# Puente externo JSONL a observaciones Bluesky (#115-hija)

## Propósito y origen

Adaptar **offline** registros ya archivados por [ruggsea/bluesky-firehose-py@5c279172c40b7f5ceab0b8ae97f1e0a83b07be69](https://github.com/ruggsea/bluesky-firehose-py/tree/5c279172c40b7f5ceab0b8ae97f1e0a83b07be69), licencia **MIT**, último commit 03/02/2025. Se reutiliza su **contrato JSONL documentado** (dos formatos: posts-only y all-records). No se copia código de la librería ni se exige instalar sus dependencias antiguas. La atribución es al formato de salida, no a funciones copiadas.

El repositorio oficial ya recolecta Jetstream; #11 mejora su colector y #94 trata recuperación de brechas archive/live. Esta herramienta NO abre otra conexión, no gestiona cursores ni pretende recuperar pérdidas: permite convertir un archivo externo entregado voluntariamente en observaciones con forma compatible con `hashtag_expansion.build_snapshot` de #63.

## Contrato

`from bluesky_archive_observations import normalize_archive_events`, pasar una **lista** de registros JSON decodificados de JSONL; devolver `{"observations": ..., "diagnostics": ...}`. Se exige DID+RKEY, fecha con zona, idioma español declarado, texto no vacío. `delete` vence incluso si su evento llega antes en el lote, y los datos contradictorios del mismo ID se excluyen. Los registros dan **evidencia archivada**, no garantizan estado actual ni tienen permiso de acción.

## Pruebas

`python -m unittest discover -s tests -p 'test_bluesky_archive_observations.py' -v`: **7/7 OK**, Python 3.13.5 en Linux. Datos sintéticos, sin red, sin datos de cuentas. Validación Windows/Python 3.11 y suite privada **pendiente de Claude**. No merge. Sugerido: integrar sólo como adaptador opcional de ficheros existentes; no activar un segundo colector.
