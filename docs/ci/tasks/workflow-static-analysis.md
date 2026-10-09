# CI: análisis estático real del workflow (complemento al contrato #2)

## Gap

Las aserciones de `tests/test_mirror_windows_ci_contract.py` comprueban cadenas
seleccionadas del YAML. No son un parser de GitHub Actions; si otro workflow
se modifica o aparecen expresiones/eventos incompatibles, el contrato no
detecta necesariamente el fallo, y un YAML inválido puede impedir ejecutar
la propia CI.

## Encargo para GPT (implementación)

- Audita todos los workflows activos del mirror y los correspondientes del
  repo oficial privado `davidpd89/rrss-davidporto-CODE`
  (`integracion/crecimiento-2026-10`); sanitiza antes de trasladar algo.
- Compara `rhysd/actionlint` (MIT, Go; release v1.7.12 comprobada
  2026-10-09) frente a `zizmorcore/zizmor` (MIT, Rust;
  `--offline`, actividad 2026-10-08) y alternativas existentes.
- Elige una cobertura base de sintaxis/esquema/expresiones. Valora una segunda
  capa de hallazgos accionables sin falsos positivos que bloqueen mejoras.
- Integra el ejecutable mantenido con versión inmutable, SHA256 o
  verificación de integridad y atribución; sin descargar binarios `latest`
  ni copiar el parser a Python.
- Prueba sintética: evento mal declarado, job con expresión inválida, action
  no fijada, campo desconocido, y YAML correcto. Test de ausencia de secretos,
  inyección de salida y modificaciones de datos operativos.
- Ejecuta sin acceso a cuentas sociales en Ubuntu y Windows; no requiere
  autenticación GitHub para verificar workflows locales.
- Mantiene la suite y el contrato de la #2, no introduce bloqueos de volumen
  de las colas WEB/API/MOBILE ni acciones reales en redes.
- Documenta coste, runtime, licencia, versionado, rollback y límites,
  con segunda revisión adversarial.

Origen: auditoría adicional de PR #2; no duplicar #31, que es una investigación
transversal de seguridad y cadena de suministro. Este encargo produce un
**linter operativo de workflows**, no una investigación genérica.
