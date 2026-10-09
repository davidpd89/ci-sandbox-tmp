# ci-sandbox-tmp

Repositorio **temporal** y anonimizado cuyo único fin es ejecutar GitHub Actions (gratis en repos públicos) sobre una copia reducida del código de otro proyecto privado.

- Contiene solo `tools/`, `tests/`, `requirements-ci.txt`, un workflow y unos pocos ficheros de configuración que los tests leen. No hay datos operativos, historial ni credenciales.
- Cada snapshot es **un commit generado por script** desde una referencia concreta del repo privado y anonimizado (nombres, handles, emails y rutas sustituidos de forma coherente). No editar a mano: se sobrescribe en cada sincronización.
- El workflow (`.github/workflows/validate-social-tools.yml`) corre en `push`, en Ubuntu y Windows, y excluye 8 tests que leen datos reales que aquí no existen (lista en el propio workflow).
- Se borrará cuando termine la mejora en curso.

Cómo se actualiza (en la máquina del mantenedor, fuera de este repo): `sh C:\GIT\rrss-ci-sync.sh <ref> <rama>`, luego commit con identidad neutra y `git push --force` de la rama. Documentación completa en el repo privado: `00_OPERATIVO/CI_ESPEJO_Y_FLUJO_DE_MERGE.md`.
