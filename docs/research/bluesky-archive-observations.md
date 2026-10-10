# Puente externo JSONL a observaciones Bluesky (#115-hija)

## Propósito y origen

Adaptar **offline** registros ya archivados por [ruggsea/bluesky-firehose-py@5c279172c40b7f5ceab0b8ae97f1e0a83b07be69](https://github.com/ruggsea/bluesky-firehose-py/tree/5c279172c40b7f5ceab0b8ae97f1e0a83b07be69), licencia **MIT**, último commit 03/02/2025. Se reutiliza su **contrato JSONL documentado** (dos formatos: posts-only y all-records). No se copia código de la librería ni se exige instalar sus dependencias antiguas. La atribución es al formato de salida, no a funciones copiadas.

El repositorio oficial ya recolecta Jetstream; #11 mejora su colector y #94 trata recuperación de brechas archive/live. Esta herramienta NO abre otra conexión, no gestiona cursores ni pretende recuperar pérdidas: permite convertir un archivo externo entregado voluntariamente en observaciones con forma compatible con `hashtag_expansion.build_snapshot` de #63.

## Contrato

`from bluesky_archive_observations import normalize_archive_events`, pasar una **lista** de registros JSON decodificados de JSONL; devolver `{"observations": ..., "diagnostics": ...}`. Se exige DID+RKEY, fecha con zona, idioma español declarado, texto no vacío. `delete` vence incluso si su evento llega antes en el lote, y los datos contradictorios del mismo ID se excluyen. Los registros dan **evidencia archivada**, no garantizan estado actual ni tienen permiso de acción.

## Pruebas

`python -m unittest discover -s tests -p 'test_bluesky_archive_observations.py' -v`: **7/7 OK**, Python 3.13.5 en Linux. Datos sintéticos, sin red, sin datos de cuentas. Validación Windows/Python 3.11 y suite privada **pendiente de Claude**. No merge. Sugerido: integrar sólo como adaptador opcional de ficheros existentes; no activar un segundo colector.


## Problema

Se dispone de un colector Jetstream propio y de trabajo independiente para recuperación de brechas (#11 y #94), pero falta una transformación pura para **registros de archivo externo ya existentes** al formato de observaciones de #63, sin abrir una segunda conexión.

## Alternativas

A. Instalar o copiar el archivador Python completo: dependencias antiguas y duplicación; descartado.
B. Reimplementar la recogida Jetstream: invade #11 y #94; descartado.
C. Reutilizar la estructura documentada del JSONL y adaptar solo el formato de entrada mediante función pura: **seleccionado**.

## Licencias y procedencia

Fuente primaria: https://github.com/ruggsea/bluesky-firehose-py/tree/5c279172c40b7f5ceab0b8ae97f1e0a83b07be69
Fecha de consulta: 2026-10-10
Licencia SPDX: MIT
Referencia inmutable: https://github.com/ruggsea/bluesky-firehose-py/tree/5c279172c40b7f5ceab0b8ae97f1e0a83b07be69

Autoría original: ruggsea/bluesky-firehose-py. Se adapta su **formato de salida documentado** (record/commit, rkey, did, record.text y langs); **no** se copia código ni se instalan dependencias. El formato y la atribución constan en este informe.

## Decisión

Adaptador offline opcional, compatibilidad con observaciones de expansión de hashtags; rejects de lengua no demostrada, timestamps sin zona y conflictos, y supresión por tombstones sin importar orden.

## Retirada

No se enlaza a un colector ni a una base de datos en esta rama. Retirar los tres archivos nuevos deshace íntegramente la mejora. No requiere migraciones, claves o limpieza de estado persistente.
