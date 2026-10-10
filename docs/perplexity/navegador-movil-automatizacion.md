# Automatización fiable de navegador y móvil

Fuente: informe de Perplexity (https://www.perplexity.ai/search/f7e7822e-ac49-4ed5-b83b-350cfcc3b6df), generado 10/10/2026.

Informe: automatización estable con Playwright/CDP y Android
Resumen

La base recomendada es Playwright para web/CDP y uiautomator2 para Android, con una capa propia común de selectores, esperas, reintentos y capturas de evidencia. Playwright aporta localizadores con auto-waiting y aserciones con reintento; uiautomator2 ofrece un wrapper Python maduro para Android con espera integrada en acciones.
playwright
+2

Para regresión visual, empieza con toHaveScreenshot() de Playwright: genera baselines, compara capturas y produce diferencias revisables; para Android, usa capturas estandarizadas por pantalla y un comparador propio o Argos como plataforma visual.
playwright
+1

Hallazgos
Repositorio / fuente	Licencia	Qué reutilizar	Integración en nuestro sistema	Riesgos técnicos	Tests propuestos
microsoft/playwright — 97.403 estrellas, activo hoy	Apache-2.0 
playwright
	Locators, auto-waiting, retries, tracing, toHaveScreenshot, soporte Chromium/Firefox/WebKit	Núcleo del adaptador web/CDP para X, Threads, Facebook, Pinterest, Reddit, Bluesky, Mastodon, TikTok e Instagram web	Las interfaces cambian con frecuencia; los selectores CSS/XPath frágiles siguen siendo el principal punto de rotura	Unit tests de resolución de locator; smoke por red; test de login/sesión; captura visual de feed y perfil

openatx/uiautomator2
 — 8.416 estrellas, último push 2026-10-05	MIT 
playwright
	Cliente Python para Android, d(...) selectors, wait, timeout por acción, dump de jerarquía UI	Adaptador Android para TikTok/Instagram cuando la web no cubra un flujo; driver común AndroidDriver	Requiere dispositivo/emulador estable, ADB y versiones de Android; la jerarquía de apps puede cambiar	Test de conexión ADB; localización de elementos; reintento ante UiObjectNotFoundError; captura XML + PNG en fallo
appium/appium-uiautomator2-driver — 884 estrellas, activo hoy	Apache-2.0 
playwright
	Driver UiAutomator2, Settings API y timeouts de búsqueda	Alternativa si se quiere orquestación multiplataforma con Appium; no imprescindible si ya trabajamos en Python con uiautomator2	Añade servidor Appium y complejidad operativa	Compatibilidad de capacidades; sesión en emulador y dispositivo físico; timeout de búsqueda
argos-ci/argos — 637 estrellas, push hoy	MIT 
playwright
	Plataforma visual de comparación, revisión de diffs y integración Playwright	Opcional para revisar diffs de capturas en PR; útil cuando las baselines locales generan demasiado ruido	Dependencia de servicio externo o despliegue propio	PR con captura nueva, diff esperado y aprobación de baseline

Playwright: Best practices
	Documentación oficial	Priorizar getByRole, getByLabel, getByText; evitar XPath/CSS salvo necesidad	Definir la jerarquía de selectores en selectors.py / locators.ts	Ninguno directo; exige disciplina de mantenimiento	Lint que prohíba XPath absoluto y selectores generados sin contrato

Playwright: Auto-waiting
	Documentación oficial	Espera por visibilidad, habilitación, estabilidad y recepción de eventos antes de actuar	Sustituir sleep() por esperas de condición y aserciones auto-retry	Timeouts mal calibrados pueden ocultar fallos reales	Test de UI lenta simulada; verificar que no hay sleep en código de producción

Playwright: Retries
	Documentación oficial	Reintentos de tests fallidos y separación de artefactos entre intentos	Reintentos solo para fallos transitorios: red, render, ANR puntual; no para selectores rotos	Reintentar puede enmascarar bugs de selectores	Clasificar fallos por categoría: selector, network, device, assertion

UI Automator oficial
	Documentación Android	Selectores By.res, By.text, By.desc, By.clazz y esperas explícitas	Traducir a una tabla de selectores por red y plataforma	Texto localizado y A/B tests rompen selectores de texto	Matriz de dispositivos/Android; test de selector tras actualización de app

Playwright: Visual comparisons
	Documentación oficial	toHaveScreenshot, maxDiffPixels, maxDiffPixelRatio, threshold, masks y --update-snapshots	Baselines por red, vista, viewport y tema claro/oscuro	Contenido dinámico, avatares, timestamps y anuncios generan falsos positivos	Mask de zonas dinámicas; baseline por plataforma; diff obligatorio en PR
Buenas prácticas transversales
Selectores resistentes

Usa una jerarquía única en todas las redes:

data-testid, aria-label, role o atributos semánticos estables.

En Android: resource-id y content-desc; son más estables que el texto visible.
getautonoma
+1

Texto visible solo como fallback, con coincidencia flexible y normalizada.

XPath/CSS profundos únicamente como último recurso y siempre versionados.

Playwright recomienda explícitamente atributos orientados al usuario y contratos estables frente a XPath/CSS; sus localizadores integran auto-waiting y reintentos. En Android, resource-id sobrevive a cambios de copia y localización, mientras que el texto se rompe con traducciones, A/B tests o cambios de diseño.
playwright
+2

Ejemplo de contrato común:

python
SELECTORS = {
  "comment_box": [
    {"web": "role=textbox[name~='Comentar|Comment']"},
    {"android": {"resource-id": "com.instagram.android:id/layout_comment_thread_edittext"}},
    {"android_fallback": {"description_contains": "Añadir un comentario"}},
  ]
}
Reintentos y esperas

Prohibir time.sleep() y Thread.sleep() en el código de acciones.

Esperar siempre por estado: elemento visible, habilitado, texto esperado, red quieta o pantalla estable.

Reintentar acciones idempotentes —abrir perfil, scroll, captura—, no acciones potencialmente duplicadas —publicar, enviar comentario— sin idempotencia.

Clasificar el error antes de reintentar: SelectorNotFound, Timeout, NetworkError, DeviceError, RateLimit.

Guardar en cada fallo: URL/pantalla, selector intentado, HTML o dump UI, captura PNG, vídeo/trace y logs.

Playwright espera automáticamente las condiciones de accionabilidad y falla con TimeoutError si no se cumplen; sus aserciones también reintentan hasta que la condición se cumple. uiautomator2 aplica un tiempo de espera por defecto de 20 segundos a acciones como click, get_text y set_text.
playwright
+1

Detección de cambios de interfaz

Implementa tres niveles:

Canario de selectores: cada noche, resolver todos los selectores críticos sin interactuar.

Contrato de pantalla: comprobar que existen los elementos mínimos de una vista —caja de comentario, botón de seguir, feed, perfil—.

Regresión visual: comparar capturas acotadas a componentes, no pantallas completas llenas de contenido cambiante.

Para web, toHaveScreenshot() crea la baseline en la primera ejecución y compara las siguientes; admite umbrales, máscaras y actualización controlada de snapshots. Para Android, captura PNG y XML de jerarquía en cada ejecución canaria; si el XML cambia pero el selector sigue resolviendo, marca el cambio como informativo; si deja de resolver, marca el adaptador como roto.
playwright
+1

Regresión visual práctica

Captura componentes, no feeds completos: tarjeta de perfil, botón, modal, formulario.

Enmascara avatares, nombres, contadores, timestamps, anuncios y áreas de contenido infinito.

Fija viewport, tema, idioma, escala y estado de sesión.

Usa maxDiffPixelRatio bajo —por ejemplo, 0,01— y threshold moderado para tolerar antialiasing sin aceptar cambios de layout.
qapractices
+1

Actualiza baselines solo mediante PR, nunca automáticamente en CI.

Recomendación

Adopta una arquitectura de adaptadores por red sobre un núcleo común:

text
core/
  selector_resolver.py
  wait_policy.py
  retry.py
  evidence.py
  visual_diff.py
adapters/
  x_web.py
  threads_web.py
  facebook_web.py
  pinterest_web.py
  reddit_web.py
  bluesky_web.py
  mastodon_web.py
  tiktok_web.py / tiktok_android.py
  instagram_web.py / instagram_android.py

Playwright como motor principal para las nueve redes mediante sus versiones web.

uiautomator2 solo para flujos Android de alto valor donde la web no alcance: TikTok e Instagram.

Baselines visuales versionadas por red, vista, viewport y tema.

Argos como mejora posterior, no como requisito inicial; el repositorio es MIT, está activo y está diseñado para revisión visual de Playwright.
playwright

Plan de implementación en PR pequeñas
PR 1 — Contrato de selectores

Crear core/selector_resolver.py con prioridad: testid/aria > resource-id/content-desc > texto > CSS/XPath.

Añadir esquema YAML/JSON de selectores por red.

Tests: resolución única, fallo controlado y registro del selector ganador.

PR 2 — Política de espera y reintento

Crear wait_policy.py y retry.py.

Sustituir todos los sleep() por esperas condicionales.

Reintentos: 2 para red/render, 0 por defecto para acciones publicadoras.

Tests: timeout, recuperación transitoria y no duplicación de acción.

PR 3 — Evidencia de fallo

Guardar PNG, HTML o dump UI, trace, metadatos de dispositivo y selector fallido.

Añadir identificador de ejecución y red.

Tests: simular fallo y verificar artefactos completos.

PR 4 — Canario de UI

Job diario que resuelve selectores críticos en las nueve redes.

Emitir informe: ok, degradado, roto.

Tests: selector presente, selector ambiguo y selector ausente.

PR 5 — Regresión visual web

Añadir toHaveScreenshot() para componentes estables.

Configurar viewport, tema, máscaras y umbrales.

Tests: primera baseline, cambio visual detectado y actualización manual de baseline.

PR 6 — Regresión visual Android

Captura PNG + XML por pantalla con uiautomator2.

Comparador de componentes con máscara de zonas dinámicas.

Tests: resolución de resource-id, detección de layout alterado y fallo con evidencia.

PR 7 — Dashboard de salud

Métricas: tasa de éxito por red, fallos por tipo, selectores rotos, duración y falsos positivos visuales.

Alerta cuando una red supere un umbral de fallos recurrentes.

Tests: agregación de resultados y cálculo de ranking de fiabilidad.

Aplicación a las redes
Red	Motor inicial	Selectores prioritarios	Puntos críticos
X	Playwright/CDP	data-testid, roles, texto estable	Timeline infinita, modales y cambios frecuentes
Threads	Playwright/CDP	Roles, aria-labels, texto	Feed dinámico y estados de sesión
Facebook	Playwright/CDP	Aria-labels y contenedores estables	Menús, overlays y variantes de idioma
Pinterest	Playwright/CDP	data-testid, alt de imágenes, roles	Masonry y carga diferida
Reddit	Playwright/CDP	Roles, data-testid, texto	Old/New UI y comunidades con temas propios
Bluesky	Playwright/CDP	Roles y atributos semánticos	Interfaz más predecible; buena red piloto
Mastodon	Playwright/CDP	Roles, enlaces, texto	Instancias con temas y versiones distintas
TikTok	Playwright web + uiautomator2	resource-id, content-desc, texto	Vídeo, gestos y cambios frecuentes de app
Instagram	Playwright web + uiautomator2	resource-id, content-desc, aria	Feed, stories y modales muy dinámicos
Fuentes

Playwright — mejores prácticas: 
https://playwright.dev/docs/best-practices
playwright

Playwright — auto-waiting: 
https://playwright.dev/docs/actionability
playwright

Playwright — reintentos: 
https://playwright.dev/docs/test-retries
playwright

Playwright — comparaciones visuales: 
https://playwright.dev/docs/test-snapshots
playwright

uiautomator2 — repositorio y espera por acción: 
https://github.com/openatx/uiautomator2
playwright
+1

Appium UiAutomator2 Driver: https://github.com/appium/appium-uiautomator2-driver
playwright
+1

Android UI Automator oficial: 
https://developer.android.com/training/testing/other-components/ui-automator
developer.android

Guía de selectores Android y esperas explícitas: 
https://getautonoma.com/blog/android-ui-automator-testing-guide
getautonoma

Estrategias de localización móvil: 
https://www.testmuai.com/blog/locators-in-appium/
testmuai

Argos — plataforma visual MIT: https://github.com/argos-ci/argos
playwright
