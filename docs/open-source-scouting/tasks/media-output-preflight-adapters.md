# Implementación: conectar preflight de media en puntos nativos de salida

**Origen:** [PR #28](https://github.com/davidpd89/ci-sandbox-tmp/pull/28).
**Dependencia de integración:** revisar y fusionar #28 antes de este trabajo.
**Base:** research/public-reuse-parent. No fusionar automáticamente.

## Encargo para GPT

Implementación obligatoria (código, tests, documentación, segunda revisión
adversarial), no solo informe de investigación. Leer #28, su contrato
`tools/media_preflight.py`, `docs/research/content-media-assets.md`,
`docs/open-source-scouting/PROTOCOL.md` y consultar en solo lectura el
repositorio oficial `davidpd89/rrss-davidporto-CODE`, rama
`integracion/crecimiento-2026-10`, en los módulos ausentes del mirror.

### Hueco probado

#28 bloquea media corrupta en `tools/content_publisher.blockers_of`, pero
varios caminos de salida no atraviesan esa función: banco X, módulos
`meta_publish` y `pinterest_publish`, colas manuales y preparación
`nuevas ideas rrss/02 — Instagram/00_PLANIFICACION_METRICOOL/preparar_media_publica_metricool.py`
en el privado, y eventuales consumidores directos de imágenes/video de
Threads, TikTok, Bluesky, Mastodon y Reddit. Esa es una brecha de paridad,
**no** un motivo para duplicar el motor de #28 o reescribir #20/#106.

### Implementar

1. Hacer inventario exhaustivo con búsqueda de llamadas reales de salida
   de medios para nueve redes, indicando cola WEB/API/MOBILE, si pasan
   o no por #28, soporte imagen/video/ALT/múltiples, y gate justo antes
   del primer side effect. Documentar estados realmente no conectados.
2. Crear adaptadores mínimos que llamen al **mismo**
   `media_preflight.inspect_asset/inspect_item` para media local. No clonar
   reglas en cada red; mapear datos de cada formato al contrato común.
3. Garantizar que una ficha con imagen/codec/ALT incompatible **no** provoca
   ninguna llamada externa ni escritura de estado. Para flujos sin medio
   no introducir dependencias o bloqueos. Para vídeos sin ffprobe, marcar
   estado explícito no verificado; para servidores con límites variantes,
   inyectar `max_bytes` desde configuración probada, sin inventar límites.
4. En exportadores de Metricool, comprobar **antes** de copiar/escribir
   `metricool_payload.json` o subir al repositorio público; usar una
   carpeta de staging y reversibilidad, nunca tocar activos reales en tests.
5. Matriz sintética de nueve redes × tres colas, incluidos salidas no
   disponibles explicitadas; testear bytes válidos y corruptos, symlinks,
   vídeo simulado, carrusel con ALT individual, duplicados sin borrado y
   que el publicador no se invoca ante error. No acceder a red ni cuentas.
6. Comparar Pillow, ImageHash, imageio-ffmpeg y alternativa mantenida
   con licencia SPDX, último commit y compatibilidad Windows/Python 3.11
   a fecha de ejecución; reutilizar #28 y priorizar migración mínima.

### Entregables y aceptación

- Código real por adaptador y tests herméticos en Windows/Ubuntu 3.11.
- `docs/research/media-output-preflight-adapters.md`: matriz antes/después,
  licencias, URLs con SHAs, pasos de rollback y canario **supervisado**
  claramente diferenciado de simulaciones.
- Auditoría adversarial tras CI: rutas paralelas, fail-open, alternancia de
  ejecuciones, JPEG con extensión engañosa, vídeo no comprobado.
- Coordinación: #20 gestiona publicación/programación; #106 QA de voz;
  #28 preflight genérico. Aquí solo la **conexión de medios a entradas
  nativas antes de efectos externos**.
- **Sin merge, sin acciones sociales reales, sin secretos, sin estados
  reales y sin llamadas a red durante los tests.**
