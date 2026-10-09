# Test y fix: cursor v2 e idempotencia del collector taste de Bluesky

## Encargo para GPT

La segunda revisión adversarial de [PR #11](https://github.com/davidpd89/ci-sandbox-tmp/pull/11)
ha descubierto que el collector de gustos `tools/bluesky_taste_collect.py` usa
`js._normalize_frame` sobre Jetstream v2 pero **no** hereda su protección de
high-water. Guarda `taste_last_seq`, lo ignora al inicializar `last_seq = None`,
mueve `cursor` antes de aplicar, confirma la fila `taste_likes` antes que el
checkpoint y acepta errores de transporte permanentes con salida 0.

Es una ruta **distinta** del collector de posts que corrige #11. No tocar
el ledger de acciones ni reproducir un patrón de writes social.

## Fuente y contexto

- Repo privado: `davidpd89/rrss-davidporto-CODE`,
  rama `integracion/crecimiento-2026-10`,
  `tools/bluesky_taste_collect.py` (leído 09-10-2026).
- Mirror público: comprobar que el archivo y tests replican la misma
  versión antes de portar; documentar el SHA real. No copiar secretos.
- `bluesky_growth_flow.py --deep` ejecuta Jetstream posts y taste en serie,
  pero los dos usan la misma SQLite con claves de estado diferentes.
- Jetstream v2 (cursor seq inclusivo):
  https://github.com/bluesky-social/jetstream/blob/f42df08ba0ca9e4287020139aefbcfe24506d1ef/docs/README.md
- Contratos de #11: replay idempotente, transacción atómica, aislamiento de
  instancia, salida no-cero en error no recuperado, logs sin cuerpos.

## Implementación exigida

1. Reproducir con frames sintéticos un like create(seq=10), update/delete
   (seq=12), replay retrasado create(seq=11). La caché no debe resucitar
   un subject ya borrado. El high-water debe recuperar su valor desde
   `taste_last_seq` tras reinicio.
2. Confirmar filas y estado de `taste_*` **en la misma transacción**
   para cada checkpoint; no confundir el cursor global de posts
   (`last_seq`) con el de taste (`taste_last_seq`).
3. Conservar fingerprint DID/endpoint y migración reversible cuando cambia
   el conjunto de objetivos. No retroceder un cursor seq con marca time_us.
4. Rechazar frames corruptos, cursores inválidos y `CursorTooOld` sin
   ocultar lagunas; backoff en errores recuperables, pero error final no
   recuperado debe propagarse al `--deep`.
5. Probar idle, reconexión, fallo de socket, restart SQLite, rollback,
   cursor de otro endpoint, dos readers y handles Windows.
6. Comparar licencias/mantenimiento de Jetstream oficial Go, cliente TS y
   SDK Python con la continuidad local. Emplear abstracciones comunes solo
   si el coste/contrato y los tests justifican compartirlas; no copiar
   librerías grandes para resolver un script pequeño.
7. Python 3.11, Ubuntu/Windows, tests offline, fixtures sintéticos y
   ningún like/follow/publicación reales. Documento `docs/research/`,
   procedencia, medición antes/después, rollback y revisión adversarial.
8. Coordinar con #11 (collector posts), #26 (SQLite), #41 (drift/parser)
   y #70 (discovery desde likes, diferente al estado del collector).
   No ampliar esos cambios sin acuerdo de Claude.

## Criterios de aceptación

Dos colectores sobre la misma SQLite no se pisan el checkpoint, un evento
antiguo no resucita un like borrado, ninguna escritura queda confirmada
sin su cursor, y los fallos persistentes no son éxitos falsos.
Pruebas del mirror y cross-check con HEAD privado oficial. Si falta
prueba con Windows real o movilidad, dejar bloqueo verificable.
No merge automático. Dejar código, tests y segundo code review DENTRO de
la PR; no convertirla en solo estudio.

## Independencia

#11 arregla el collector general de posts. Esta PR corrige el collector
`taste_likes`, cuya semántica y checkpoint son propios. Se puede
integrar después de #11 sin reabrir el alcance de esa PR.
