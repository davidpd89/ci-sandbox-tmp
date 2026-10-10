# Adaptadores de observaciones agregadas para expansión de hashtags

## Encargo para GPT

Implementar **código real, pruebas offline y documentación** para conectar
colectores de lectura de X, Threads, Facebook, Pinterest, Reddit, Bluesky,
Mastodon, TikTok e Instagram con el contrato offline de la PR #63
(https://github.com/davidpd89/ci-sandbox-tmp/pull/63). Esta PR es un puente de
datos, NO reimplementa el ranking ni el motor de hashtags de #63. No cerrar
ni fusionar; Claude integrará después de validar #63.

### Problema verificable

#63 implementa el ranking, la deduplicación, la procedencia y la caché, pero
solo acepta observaciones JSON suministradas: **ningún colector real genera
todavía estas entradas comúnmente ni su feedback de resultados**. El
espejo sanitizado contiene principalmente los escáneres de Bluesky y
Mastodon; leer el repositorio privado para el resto, sin extraer secretos.
No duplicar #21 (ranking general), #23 (atribución general) o #70
(descubrimiento desde interacciones).

### Alcance separado

1. Norma común y adaptadores read-only por red; representación sintética
   network/source/post_id/author_id/created_at/text/tags, y métricas agregadas
   eligible/engaged/replies/followers. IDs estables solo en memoria de trabajo;
   exportación final exclusivamente de agregados si es posible. Si se necesita
   un archivo de observaciones, mantenerlo fuera del árbol público.
2. Tres canales WEB, API, MOBILE independientes; por cada red verificar
   de dónde se obtienen etiquetas, texto, autor y fecha; ausencia de campos
   se trata como dato insuficiente, nunca se inventa. No confundir autores
   entre redes ni asignar una etiqueta a una plataforma sin evidencia local.
3. Garantizar que los colectores no disparan ninguna acción social, guardan
   la política de no-necroposting de los destinos y no modifican métricas
   de atribución históricas. Deduplicación idempotente y backfill limitado.
4. Comparar repositorios públicos de conectores y modelos de datos actuales,
   licencias SPDX, commits inmutables y compatibilidad Windows/Python 3.11.
   Continuidad del código actual permitida si obtiene mejores resultados.
5. Suite sintética Ubuntu/Windows, medición de cobertura por red, segunda
   revisión adversarial y plan de retirada. Si aún no está integrada #63,
   probar la salida contra un esquema reproducido en fixtures sin copiar
   código privado o datos reales.

### Límites

Sin cuentas, credenciales, tokens ni llamadas reales a redes; ningún
follow, like, comentario, post o borrado. Pruebas totalmente sintéticas.
Canario Windows/Edge/Android/servicios vivos **pendiente para Claude**.
Abrir commits exclusivamente en esta rama; no merge.

### Criterios de aceptación

Contrato para las nueve redes y las tres colas, fixtures sanos/malformados,
IDs repetidos entre fuentes, posts antiguos, autor desconocido, timestamp
sin zona, salidas vacías, Windows Unicode, feedback sin denominador y
rollback; documentación con tabla de cobertura y evidencia de CI.
