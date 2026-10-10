# Auditoria de relaciones entre PR abiertas

Fuente primaria: https://github.com/davidpd89/ci-sandbox-tmp/pulls
Fecha de consulta: 2026-10-10
Licencia SPDX: CC0-1.0
Referencia inmutable: https://github.com/davidpd89/ci-sandbox-tmp/commit/ba38c0fdbf690550f3142c2daa7d7dc8003e465e

## Problema

Las PR se crearon desde agentes y encargos independientes. Los titulos no
distinguen de forma fiable una implementacion apilada, una validacion vacia, un
contrato comun o una adaptacion por red. Esto favorece revisiones repetidas y
ordenes de integracion contradictorios.

## Alternativas

Se compararon tres formas de coordinacion: editar todos los cuerpos, publicar
comentarios cruzados o mantener un mapa versionado. Los cuerpos son propiedad
del flujo de cada agente. Los comentarios aportan visibilidad local y el mapa
versionado permite revisar relaciones, probar enlaces y evolucionar el grafo.

La solucion combina mapa central y comentarios con un marcador estable. Las
relaciones se obtuvieron de titulo, base/head, lista de archivos, commits y
cuerpo de las 106 PR abiertas observadas.

## Licencias y procedencia

El mapa contiene metadatos y conclusiones producidos para este repositorio. No
incorpora codigo de terceros. Los enlaces apuntan a las PR originales y la
procedencia detallada permanece en sus commits y documentos de investigacion.

## Decisión

Mantener `docs/open-source-scouting/PR_RELATIONSHIPS_2026-10-10.md` como foto
auditable. Las PR apiladas con trabajo real se consolidan en una fuente
canonica; las hijas sin delta quedan identificadas; las adaptaciones por red se
agrupan bajo contratos globales #114-#117.

## Pruebas

`tests/test_pr_relationship_map.py` valida formato de enlaces, cadenas de
consolidacion, contratos globales y cobertura de cada familia por red. Es una
prueba offline y determinista compatible con Windows y Ubuntu.

## Retirada

Al sustituir esta foto por un registro generado, retirar conjuntamente el mapa,
su prueba y los comentarios marcados `pr-relationship-audit-2026-10-10`. El
historial de Git conserva la auditoria y su razonamiento.
