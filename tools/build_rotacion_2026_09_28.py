"""Construye la rotacion multirred del 28/09 al 04/10 de 2026."""
from __future__ import annotations

import csv
import shutil
from pathlib import Path

from build_publicaciones_gpt_assets import info_card, pinterest_card


ROOT = Path(__file__).resolve().parents[1]
BANK = ROOT / "publicaciones GPT/banco imagenes web"


POSTS = [
    # X
    dict(net="X", id="XGPT-P003", base="BASE-017", date="2026-09-28", time="18:45", title="Un kit de prensa que se queda en tu navegador", theme="kit de prensa local", objective="clics y conversación profesional", url="https://davidportodiaz.com/herramientas/kit-prensa-escritores/", tags="#Escritores #PrensaCultural", source="publicaciones LinkedIn GPT/2026-09-24/kit-prensa-para-escritores.png", image="kit-prensa-local-escritores.png", alt="Herramienta local para ordenar biografía, fotografías y fichas de un libro y descargar un kit de prensa.", text="""Un kit de prensa no debería obligarte a subir fotos y biografía a una web ajena. Esta herramienta ordena los archivos en tu navegador y descarga un ZIP.

¿Qué material echas siempre en falta?

https://davidportodiaz.com/herramientas/kit-prensa-escritores/

#Escritores #PrensaCultural"""),
    dict(net="X", id="XGPT-P004", base="BASE-011", date="2026-10-01", time="12:15", title="Qué estás leyendo, sin otra plataforma", theme="tarjeta abierta de lectura", objective="respuestas y clics", url="https://davidportodiaz.com/herramientas/tarjeta-estoy-leyendo/", tags="#Lectura #BookTwitter", source="publicaciones Bluesky GPT/2026-09-24/tarjeta-estoy-leyendo.png", image="tarjeta-estoy-leyendo-abierta.png", alt="Generador de una tarjeta Estoy leyendo en HTML o Markdown, sin rastreadores.", text="""Hay lecturas que no necesitan puntuación ni reseña: basta con contar qué libro te acompaña hoy.

Esta tarjeta genera HTML o Markdown y no rastrea a quien la abre. ¿Qué estás leyendo?

https://davidportodiaz.com/herramientas/tarjeta-estoy-leyendo/

#Lectura #BookTwitter"""),
    dict(net="X", id="XGPT-P005", base="BASE-016", date="2026-10-04", time="11:30", title="Diez puertas a otros mundos", theme="recomendaciones portal fantasy", objective="recomendaciones, clics y conversación", url="https://davidportodiaz.com/recomendaciones/portal-fantasy-espanol/", tags="#FantasíaJuvenil #Libros", source="publicaciones Pinterest GPT/2026-09-27/libros-portal-fantasy-espanol.png", image="portal-fantasy-juvenil-x.png", alt="Selección de diez libros de portal fantasy juvenil disponibles en español.", text="""Cruzar a otro mundo es solo el principio: la puerta puede ser una huida, una trampa o un viaje sin regreso.

Hay 10 libros disponibles en español en la lista. ¿Cuál falta seguro?

https://davidportodiaz.com/recomendaciones/portal-fantasy-espanol/

#FantasíaJuvenil #Libros"""),

    # Threads
    dict(net="Threads", id="THGPT-P003", base="BASE-018", date="2026-09-28", time="20:15", title="Una página de libro debe ayudar a decidir", theme="auditoría de página de libro", objective="conversación y clics cualificados", url="https://davidportodiaz.com/herramientas/auditor-pagina-libro/", topic="Writing", source="publicaciones LinkedIn GPT/2026-09-25/auditor-pagina-libro.png", image="auditor-pagina-libro-threads.png", alt="Auditor que revisa si una página explica qué es un libro, para quién es y cuál es el siguiente paso.", text="""Una página de libro puede ser bonita y seguir sin responder lo básico: qué es, para quién puede encajar y qué debería hacer después quien llega.

Preparé una revisión guiada para detectar esos huecos sin puntuar el diseño.

¿Qué dato buscas primero cuando descubres un libro?

https://davidportodiaz.com/herramientas/auditor-pagina-libro/"""),
    dict(net="Threads", id="THGPT-P004", base="BASE-007", date="2026-10-01", time="20:00", title="Cuando una familia conserva tres historias del mismo objeto", theme="historia de objetos heredados", objective="respuestas con recuerdos concretos", url="https://davidportodiaz.com/recursos/ficha-historia-objeto-heredado/", topic="Book Threads", source="publicaciones Facebook GPT/2026-09-24/ficha-objeto-heredado.png", image="objeto-heredado-threads.png", alt="Ficha para separar hechos comprobables, recuerdos e hipótesis sobre un objeto heredado.", text="""«Ese reloj era de tu bisabuelo». «No, lo compró tu abuelo». «No, apareció después de la mudanza».

Los objetos heredados suelen guardar varias historias a la vez. Hice una ficha para separar hechos, recuerdos e hipótesis sin borrar ninguna capa.

¿Qué objeto provocaría más versiones en tu familia?

https://davidportodiaz.com/recursos/ficha-historia-objeto-heredado/"""),
    dict(net="Threads", id="THGPT-P005", base="BASE-009", date="2026-10-02", time="18:45", title="El protagonista ya vivía allí o tuvo que cruzar", theme="portal fantasy frente a fantasía épica", objective="debate lector", url="https://davidportodiaz.com/cuaderno/portal-fantasy-vs-fantasia-epica/", topic="Book Threads", source="publicaciones TikTok GPT/2026-09-25/portal-fantasy-vs-fantasia-epica-01.png", image="portal-fantasy-o-epica-threads.png", alt="Cabecera de una comparación entre portal fantasy y fantasía épica.", text="""Dos novelas pueden tener magia, criaturas y un mapa enorme, pero pedir cosas muy distintas al lector.

Para mí la diferencia útil empieza aquí: ¿el protagonista ya pertenece al mundo fantástico o tiene que cruzar hasta él?

¿Qué entrada te engancha más y con qué libro?

https://davidportodiaz.com/cuaderno/portal-fantasy-vs-fantasia-epica/"""),

    # Instagram
    dict(net="Instagram", id="IGGPT-P003", base="BASE-021", date="2026-09-29", time="19:30", title="Tres reconocimientos, tres fuentes", theme="premios documentados", objective="trayectoria y conversación", url="https://davidportodiaz.com/premios.html", profile_label="Premios", tags="#Microrrelato #Escritores #PremiosLiterarios #LiteraturaEspañola", source="publicaciones GPT/banco imagenes web/359/captura.png", image="premios-david-porto-2026.png", alt="Página de premios de David Porto Díaz con tres reconocimientos documentados de 2026.", text="""Un premio ocupa una línea. El texto que llegó hasta allí suele haber pasado por bastantes más.

Los he reunido con el resultado exacto, la entidad, la fecha y la fuente. Prefiero que una trayectoria se pueda comprobar, no solo resumir.

Desliza para verlos. ¿Qué te interesa más conocer cuando un autor menciona un premio: el texto, el jurado o la historia que hubo antes?

En el perfil: «Premios».

#Microrrelato #Escritores #PremiosLiterarios #LiteraturaEspañola"""),
    dict(net="Instagram", id="IGGPT-P004", base="BASE-003", date="2026-10-02", time="11:30", title="Qué hace que sigas leyendo", theme="test de tipo de lector", objective="comentarios y visitas a herramienta", url="https://davidportodiaz.com/herramientas/que-tipo-de-lector-eres/", profile_label="Test lector", tags="#Lectores #BookstagramEspaña #HábitosDeLectura #Libros", source="publicaciones Threads GPT/2026-09-25/test-que-tipo-de-lector-david-porto.png", image="que-te-hace-seguir-leyendo.png", alt="Test breve que propone distintos motivos por los que una persona continúa leyendo.", text="""Hay quien sigue por una pista. Quien necesita encariñarse con alguien. Y quien solo quiere descubrir cómo funciona ese mundo.

Preparé un test breve para jugar con esa diferencia. Si el resultado no te representa, mejor: ahí empieza la conversación.

Desliza, elige y cuéntame qué pesa más en tu caso: personaje, misterio o mundo.

En el perfil: «Test lector».

#Lectores #BookstagramEspaña #HábitosDeLectura #Libros"""),
    dict(net="Instagram", id="IGGPT-P005", base="BASE-008", date="2026-10-03", time="18:30", title="El capítulo antes de la sinopsis", theme="primer capítulo de Samuel entre mundos", objective="lectura y descubrimiento", url="https://davidportodiaz.com/fragmento/", profile_label="Capítulo de Samuel", tags="#FantasíaJuvenil #PortalFantasy #BookstagramEspaña #LecturaEnEspañol", source="publicaciones Facebook GPT/2026-09-26/samuel-entre-mundos-capitulo-gratis.png", image="samuel-capitulo-antes-sinopsis.png", alt="Cabecera del capítulo uno gratuito de Samuel entre mundos.", text="""A veces una sinopsis te cuenta qué promete un libro. Un capítulo te enseña si quieres quedarte.

El primero de *Samuel entre mundos* empieza con una familia empeñada en parecer normal y un chico que todavía no sabe por qué no encaja.

En las dos láminas siguientes están las preguntas que abre el comienzo. Para seguir, ¿necesitas antes entender el mundo o confiar en el protagonista?

En el perfil: «Capítulo de Samuel».

#FantasíaJuvenil #PortalFantasy #BookstagramEspaña #LecturaEnEspañol"""),

    # Facebook
    dict(net="Facebook", id="FBGPT-P003", base="BASE-022", date="2026-09-29", time="12:30", title="Samuel en la Feria del Libro de Madrid", theme="crónica de feria", objective="comunidad y lectura de crónica", url="https://davidportodiaz.com/cuaderno/feria-libro-madrid-2026-samuel-entre-mundos/", tags="#FeriaDelLibroDeMadrid #Autores", source="publicaciones GPT/banco imagenes web/100/captura.png", image="samuel-feria-libro-madrid-2026.png", alt="Crónica de la firma de Samuel entre mundos en la caseta 337 de la Feria del Libro de Madrid 2026.", text="""El 10 de junio firmé ejemplares de *Samuel entre mundos* en la caseta 337 de la Feria del Libro de Madrid.

Había imaginado muchas veces lo que sería publicar una novela. Verla sobre una mesa mientras alguien se acercaba a preguntar de qué iba resultó bastante más concreto y más raro.

He dejado una crónica breve de aquella tarde, con fotografías reales:
https://davidportodiaz.com/cuaderno/feria-libro-madrid-2026-samuel-entre-mundos/

¿Qué recuerdas mejor de una feria: el libro que encontraste, la conversación o el paseo entre casetas?

#FeriaDelLibroDeMadrid #Autores"""),
    dict(net="Facebook", id="FBGPT-P004", base="BASE-001", date="2026-10-01", time="19:00", title="Lo que cambia cuando cambia el dueño", theme="memoria valor y futuro", objective="comentarios y lectura de la novela", url="https://davidportodiaz.com/las-manecillas-del-recuerdo/", tags="#NovelaCoral #MemoriaFamiliar", source="publicaciones X GPT/2026-09-24/las-manecillas-memoria-valor-futuro-david-porto.png", image="manecillas-tres-vidas-facebook.png", alt="Página de Las manecillas del recuerdo sobre memoria, valor y futuro alrededor de un reloj.", text="""Un mismo reloj puede ser recuerdo para una familia, mercancía para otra persona y una rareza antigua unos años después.

Ese cambio de significado es una de las ideas que recorre *Las manecillas del recuerdo*: el objeto sigue ahí, pero cada dueño cree tener una historia distinta entre las manos.

Puedes conocer la novela aquí:
https://davidportodiaz.com/las-manecillas-del-recuerdo/

¿Conservas algo cuyo valor solo entiende bien tu familia?

#NovelaCoral #MemoriaFamiliar"""),
    dict(net="Facebook", id="FBGPT-P005", base="BASE-014", date="2026-10-04", time="12:00", title="Las relaciones también tienen versiones", theme="mapa de relaciones de personajes", objective="utilidad y conversación de oficio", url="https://davidportodiaz.com/herramientas/personajes/", tags="#EscrituraCreativa #Personajes", source="publicaciones Mastodon GPT/2026-09-27/mapa-relaciones-personajes.png", image="mapa-relaciones-personajes-facebook.png", alt="Herramienta local para registrar relaciones entre personajes y cómo cambian durante una novela.", text="""Dos personajes no tienen una sola relación durante toda una novela. Pueden empezar como aliados, ocultarse algo y acabar queriendo cosas incompatibles.

Este mapa permite registrar esas relaciones y sus cambios sin subir el proyecto. No interpreta a los personajes: ayuda a ver contradicciones entre lo que declaraste y lo que termina ocurriendo.

https://davidportodiaz.com/herramientas/personajes/

¿Qué relación te cuesta más controlar mientras escribes: familia, amistad o rivalidad?

#EscrituraCreativa #Personajes"""),

    # TikTok
    dict(net="TikTok", id="TTGPT-P003", base="BASE-023", date="2026-09-30", time="19:30", title="Prueba el capítulo antes de comprar", theme="muestra Kindle de Las manecillas", objective="guardados y lectura de muestra", url="https://davidportodiaz.com/las-manecillas-del-recuerdo/kindle/", tags="#KindleEspaña #LecturaEnEspañol #Libros #BookTokEspaña #MuestraGratis", source="publicaciones GPT/banco imagenes web/315/captura.png", image="muestra-manecillas-kindle-01.png", alt="Página para descargar gratis el capítulo 1.1 de Las manecillas del recuerdo en EPUB o TXT.", text="""Antes de comprar un libro prefiero que puedas leer cómo empieza.

El capítulo 1.1 de *Las manecillas del recuerdo* se descarga gratis en EPUB o TXT. También puedes enviarlo a Kindle.

Desliza para elegir formato. ¿Dónde lees las muestras: móvil, lector electrónico u ordenador?

La muestra está en davidportodiaz.com.

#KindleEspaña #LecturaEnEspañol #Libros #BookTokEspaña #MuestraGratis"""),
    dict(net="TikTok", id="TTGPT-P004", base="BASE-005", date="2026-10-01", time="12:00", title="Tres voces de una misma novela", theme="tres fragmentos y registros", objective="comentarios y lectura", url="https://davidportodiaz.com/las-manecillas-del-recuerdo/fragmentos/", tags="#NovelaCoral #BookTokEspaña #LecturaEnEspañol #Fragmentos #Libros", source="publicaciones Instagram GPT/2026-09-24/tres-fragmentos-tres-registros.png", image="tres-fragmentos-tiktok-01.png", alt="Portada de tres fragmentos de Las manecillas del recuerdo con registros íntimo, de humor negro y futuro cercano.", text="""Una novela, tres registros que casi parecen de libros distintos.

1. Un desayuno donde nadie toca el chocolate.
2. Una casa de empeños que infla una historia.
3. Un futuro donde las horas ya no suenan.

Desliza y elige: ¿1, 2 o 3?

Los tres fragmentos están en davidportodiaz.com.

#NovelaCoral #BookTokEspaña #LecturaEnEspañol #Fragmentos #Libros"""),
    dict(net="TikTok", id="TTGPT-P005", base="BASE-012", date="2026-10-03", time="20:00", title="¿Cabe de verdad en cinco minutos?", theme="tiempo de lectura en voz alta", objective="guardados y uso de herramienta", url="https://davidportodiaz.com/herramientas/tiempo-lectura-voz-alta/", tags="#EscrituraCreativa #LecturaEnVozAlta #Autores #BookTokEspaña #HerramientasParaEscritores", source="publicaciones Bluesky GPT/2026-09-26/tiempo-lectura-fragmento.png", image="tiempo-lectura-cinco-minutos-01.png", alt="Estimador local del tiempo necesario para leer un fragmento en voz alta.", text="""«Es corto» no sirve demasiado cuando una lectura tiene cinco minutos exactos.

Este estimador convierte las palabras en un rango y permite ajustar el ritmo. No es un cronómetro y no guarda el texto.

En las siguientes imágenes hay tres usos concretos. ¿Para qué medirías tú una lectura?

La herramienta está en davidportodiaz.com.

#EscrituraCreativa #LecturaEnVozAlta #Autores #BookTokEspaña #HerramientasParaEscritores"""),

    # Bluesky
    dict(net="Bluesky", id="BSGPT-P003", base="BASE-024", date="2026-09-28", time="09:30", title="Preguntas que abren un club de lectura", theme="guía de club de lectura", objective="conversación y visitas", url="https://davidportodiaz.com/clubes-de-lectura/samuel-entre-mundos/", tags="#BookSky #ClubDeLectura", source="publicaciones GPT/banco imagenes web/067/captura.png", image="club-lectura-samuel-bluesky.png", alt="Guía de Samuel entre mundos con preguntas de debate y recursos para clubes de lectura.", text="""Un club mejora cuando las preguntas no buscan comprobar quién entendió «bien» el libro. Esta guía de Samuel propone debatir identidad, pertenencia y coste del poder.

¿Qué pregunta os ha dado más juego?
https://davidportodiaz.com/clubes-de-lectura/samuel-entre-mundos/

#BookSky #ClubDeLectura"""),
    dict(net="Bluesky", id="BSGPT-P004", base="BASE-002", date="2026-10-03", time="09:45", title="Los ecos que ya no ves", theme="repeticiones en un texto", objective="respuestas y uso de herramienta", url="https://davidportodiaz.com/herramientas/repeticiones/", tags="#Escritura #Autores", source="publicaciones X GPT/2026-09-26/detector-repeticiones-escritores-david-porto.png", image="ecos-repeticiones-bluesky.png", alt="Detector local de palabras próximas, arranques repetidos y frases que vuelven en un texto.", text="""Una repetición puede sostener el ritmo o colarse sin que la veamos. El detector marca los ecos próximos; después toca volver a la frase.

¿Cuál se te escapa más: palabras, arranques o muletillas?
https://davidportodiaz.com/herramientas/repeticiones/

#Escritura #Autores"""),
    dict(net="Bluesky", id="BSGPT-P005", base="BASE-010", date="2026-10-04", time="18:00", title="La ciudad que no podría estar en otro sitio", theme="worldbuilding de Noveris", objective="conversación y lectura", url="https://davidportodiaz.com/cuaderno/worldbuilding-noveris-ciudad-magica/", tags="#Worldbuilding #Fantasía", source="publicaciones TikTok GPT/2026-09-27/worldbuilding-noveris-01.png", image="noveris-no-es-decorado-bluesky.png", alt="Artículo sobre cómo la ubicación de Noveris afecta a su arquitectura, economía y conflictos.", text="""Una ciudad fantástica deja de ser decorado cuando su ubicación cambia el mercado, la arquitectura y los conflictos. Noveris empezó con una pregunta: ¿por qué existe justo ahí?

https://davidportodiaz.com/cuaderno/worldbuilding-noveris-ciudad-magica/

#Worldbuilding #Fantasía"""),

    # Mastodon
    dict(net="Mastodon", id="MAGPT-P003", base="BASE-025", date="2026-09-28", time="08:45", title="Cuando un dato editorial caduca", theme="metodología editorial", objective="confianza y conversación", url="https://davidportodiaz.com/metodologia-editorial/", tags="#Edición #Escritores #DatosAbiertos", source="publicaciones GPT/banco imagenes web/353/captura.png", image="metodologia-editorial-mastodon.png", alt="Página que explica fuentes, fechas de revisión y correcciones del directorio editorial.", text="""Una lista de editoriales deja de ser útil si no explica de dónde sale cada dato o cuándo se revisó.

Por eso el directorio separa la fuente oficial del resumen, marca estados cerrados y explica cómo corregir información. Cuando no hay vía de envío publicada, no la deduce.

https://davidportodiaz.com/metodologia-editorial/

¿Qué dato echáis más en falta al investigar una editorial?

#Edición #Escritores #DatosAbiertos"""),
    dict(net="Mastodon", id="MAGPT-P004", base="BASE-015", date="2026-10-02", time="08:45", title="Fantasía juvenil española reciente", theme="selección 2025-2026", objective="recomendaciones y clics", url="https://davidportodiaz.com/cuaderno/libros-fantasia-juvenil-espanola-2025-2026/", tags="#Fantasía #LiteraturaEspañola #Lecturas", source="publicaciones Pinterest GPT/2026-09-25/fantasia-juvenil-espanola-2025-2026.png", image="fantasia-juvenil-espanola-mastodon.png", alt="Selección comentada de fantasía juvenil española publicada en 2025 y 2026.", text="""Una lista de novedades sirve poco si solo apila cubiertas.

Esta selección de fantasía juvenil española de 2025 y 2026 explica qué distingue cada libro y para qué lector puede encajar, sin convertirlo en una clasificación automática.

https://davidportodiaz.com/cuaderno/libros-fantasia-juvenil-espanola-2025-2026/

¿Qué título reciente añadiríais y por qué?

#Fantasía #LiteraturaEspañola #Lecturas"""),
    dict(net="Mastodon", id="MAGPT-P005", base="BASE-004", date="2026-10-04", time="17:45", title="La magia cambia cuando obliga a renunciar", theme="fantasía con magia de coste", objective="recomendaciones y conversación", url="https://davidportodiaz.com/recomendaciones/magia-con-coste/", tags="#Fantasía #Libros #Bookstodon", source="publicaciones Threads GPT/2026-09-27/libros-fantasia-magia-con-coste-david-porto.png", image="magia-con-coste-mastodon.png", alt="Selección de seis libros de fantasía donde usar magia tiene un coste real.", text="""Un sistema de magia no necesita una tabla complicada para tener coste. Basta con que usarlo obligue a renunciar a algo que importa.

En los seis libros de la lista, el precio de la magia cambia decisiones; no está solo para decorar el mundo.

https://davidportodiaz.com/recomendaciones/magia-con-coste/

¿Qué coste mágico os ha parecido más difícil de esquivar?

#Fantasía #Libros #Bookstodon"""),

    # Pinterest
    dict(net="Pinterest", id="PINGPT-P003", base="BASE-026", date="2026-09-28", time="10:30", title="Cómo analizar la variedad léxica de un texto", theme="variedad léxica", objective="clics y guardados", url="https://davidportodiaz.com/herramientas/variedad-lexica/", board="Herramientas para escritores", image="analizar-variedad-lexica-texto.png", alt="Portada de una herramienta para comparar la variedad léxica dentro de un texto en español.", description="Herramienta gratuita para analizar la variedad léxica de un fragmento, capítulo o manuscrito mediante formas distintas, MATTR y MTLD. El texto se procesa en el navegador y el resultado no decide si la prosa es buena o mala: sirve para localizar cambios y revisarlos con contexto."),
    dict(net="Pinterest", id="PINGPT-P004", base="BASE-019", date="2026-10-03", time="10:30", title="Cómo revisar los puntos de vista de una novela", theme="distribución de POV", objective="clics y guardados", url="https://davidportodiaz.com/herramientas/distribucion-pov/", board="Herramientas para escritores", image="revisar-puntos-vista-novela.png", alt="Portada de una herramienta para visualizar cómo se reparten los puntos de vista de una novela.", description="Guía y herramienta para revisar cómo se distribuyen los puntos de vista a lo largo de una novela, detectar ausencias largas y contrastar la estructura sin convertir el gráfico en una regla automática de escritura."),
    dict(net="Pinterest", id="PINGPT-P005", base="BASE-013", date="2026-10-04", time="10:30", title="Cómo detectar nombres de personajes parecidos", theme="nombres de personajes", objective="clics y guardados", url="https://davidportodiaz.com/herramientas/nombres-personajes/", board="Herramientas para escritores", image="detectar-nombres-personajes-parecidos.png", alt="Portada de una herramienta para detectar nombres de personajes con parecido visual o sonoro.", description="Herramienta gratuita para comparar los nombres de un reparto y localizar similitudes visuales o sonoras que pueden confundir durante la lectura. El análisis se realiza en el navegador y funciona como aviso para revisar, no como una orden para renombrar personajes."),

    # Reddit: uno esta semana y dos reservas por la regla de un post propio semanal.
    dict(net="Reddit", id="RDGPT-P002", base="BASE-020", date="2026-09-29", time="18:00", title="¿Limpiáis el formato antes de revisar el fondo?", theme="limpieza de manuscritos", objective="conversación de oficio", subreddit="r/escribir", flair="Duda sobre estilo/ritmo", text="""Cuando un documento tiene espacios dobles, saltos extraños, guiones mezclados y párrafos partidos, cuesta saber qué problemas pertenecen al texto y cuáles al formato.

¿Preferís hacer primero una pasada puramente mecánica o vais corrigiendo forma y contenido a la vez? Me interesa especialmente qué errores limpiáis antes de entrar en ritmo, escenas o personajes.""", state="lista_manual"),
    dict(net="Reddit", id="RDGPT-P003", base="BASE-006", date="2026-10-06", time="18:00", title="¿Qué comentario de un lector beta os resulta realmente útil?", theme="feedback beta accionable", objective="conversación de oficio", subreddit="r/escribir", flair="Duda sobre estilo/ritmo", text="""Yo voy cambiando y nunca termino de quedarme con uno. ¿Cuál usáis más vosotros?""", state="reserva_regla_semanal"),
    dict(net="Reddit", id="RDGPT-P004", base="BASE-027", date="2026-10-13", time="18:00", title="¿Usáis índices de legibilidad o solo lectura en voz alta?", theme="densidad y legibilidad", objective="conversación de oficio", subreddit="r/escribir", flair="Duda sobre estilo/ritmo", text="""En digital subrayo sin pensarlo, pero en papel todavía me cuesta. ¿Los marcáis o los dejáis intactos?""", state="reserva_regla_semanal"),
]


NEW_BASES = [
    ("BASE-021", "Tres reconocimientos de 2026 con resultado y fuente", "premios y trayectoria", "https://davidportodiaz.com/premios.html", "359"),
    ("BASE-022", "Crónica de Samuel entre mundos en la Feria del Libro de Madrid 2026", "eventos y comunidad", "https://davidportodiaz.com/cuaderno/feria-libro-madrid-2026-samuel-entre-mundos/", "100"),
    ("BASE-023", "Muestra gratuita en EPUB o TXT de Las manecillas del recuerdo", "Las manecillas del recuerdo", "https://davidportodiaz.com/las-manecillas-del-recuerdo/kindle/", "315"),
    ("BASE-024", "Preguntas y recursos para un club de lectura de Samuel entre mundos", "clubes de lectura", "https://davidportodiaz.com/clubes-de-lectura/samuel-entre-mundos/", "067"),
    ("BASE-025", "Cómo se verifican y caducan los datos del directorio editorial", "metodología editorial", "https://davidportodiaz.com/metodologia-editorial/", "353"),
    ("BASE-026", "Analizar variedad léxica sin convertir una cifra en juicio", "herramientas para escritores", "https://davidportodiaz.com/herramientas/variedad-lexica/", "293"),
    ("BASE-027", "Usar legibilidad como aviso y no como norma automática", "oficio de escritura", "https://davidportodiaz.com/herramientas/legibilidad/", "249"),
]


ORIGIN = {
    "BASE-001": ("X", "2026-09-24"), "BASE-002": ("X", "2026-09-26"),
    "BASE-003": ("Threads", "2026-09-25"), "BASE-004": ("Threads", "2026-09-27"),
    "BASE-005": ("Instagram", "2026-09-24"), "BASE-006": ("Instagram", "2026-09-26"),
    "BASE-007": ("Facebook", "2026-09-24"), "BASE-008": ("Facebook", "2026-09-26"),
    "BASE-009": ("TikTok", "2026-09-25"), "BASE-010": ("TikTok", "2026-09-27"),
    "BASE-011": ("Bluesky", "2026-09-24"), "BASE-012": ("Bluesky", "2026-09-26"),
    "BASE-013": ("Mastodon", "2026-09-25"), "BASE-014": ("Mastodon", "2026-09-27"),
    "BASE-015": ("Pinterest", "2026-09-25"), "BASE-016": ("Pinterest", "2026-09-27"),
    "BASE-017": ("LinkedIn descartada", ""), "BASE-018": ("LinkedIn descartada", ""),
    "BASE-019": ("Reddit", "2026-09-26"), "BASE-020": ("Reddit", "2026-09-29"),
}

STANDARD_NETWORKS = ["X", "Threads", "Instagram", "Facebook", "TikTok", "Bluesky", "Mastodon", "Pinterest"]


VIA = {
    "X": ("si", "Programador nativo de X"),
    "Threads": ("si o manual", "Threads web nativo"),
    "Instagram": ("si", "Instagram app nativa / Meta Business Suite"),
    "Facebook": ("si", "Meta Business Suite"),
    "TikTok": ("manual", "TikTok app"),
    "Bluesky": ("manual", "Bluesky app/web"),
    "Mastodon": ("manual", "Web Mastodon autenticada"),
    "Pinterest": ("si", "Pinterest Business nativo"),
    "Reddit": ("manual", "Web Reddit autenticada"),
}


ALT_EXTRA = {
    "IGGPT-P003": [
        "Lámina con los tres resultados documentados: ganador de Aullidos en papel, Primer Premio De amor y Top 10 Juan Andrés Teno.",
        "Lámina que explica que cada reconocimiento conserva resultado, entidad, fecha y fuente.",
    ],
    "IGGPT-P004": [
        "Tres motivos para seguir leyendo: personaje, misterio o mundo.",
        "Lámina que aclara que el test no diagnostica, permite discutir el resultado y puede cambiar según el libro.",
    ],
    "IGGPT-P005": [
        "Lámina sobre la familia de Samuel, empeñada en parecer normal, y el secreto que él todavía desconoce.",
        "Tres posibles motivos para continuar un primer capítulo: mundo, protagonista o pregunta abierta.",
    ],
    "TTGPT-P003": [
        "Formatos de la muestra gratuita: EPUB para lectores y aplicaciones, y TXT para cualquier editor.",
        "Tres formas de leer la muestra: Kindle, EPUB en móvil u ordenador, o archivo TXT.",
    ],
    "TTGPT-P004": [
        "Cita de El ritual del domingo sobre un chocolate que nadie ha tocado.",
        "Diálogo de El precio de una historia en una casa de empeños.",
        "Diálogo de Las horas silenciosas sobre una generación que ya no conoce el tic-tac.",
    ],
    "TTGPT-P005": [
        "Lámina que presenta el tiempo de lectura como un rango ajustable, no como un cronómetro.",
        "Usos del estimador: presentaciones, clubes de lectura y fragmentos con tiempo limitado.",
    ],
}


def copy_asset(post, output_name=None):
    source = post.get("source")
    if not source:
        return
    dest = ROOT / f"publicaciones {post['net']} GPT" / post["date"] / (output_name or post["image"])
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / source, dest)


def make_supporting_assets():
    # Copias simples para redes de una sola imagen y portadas de carrusel.
    for post in POSTS:
        if post["net"] != "Reddit" and post.get("source"):
            copy_asset(post)

    # Instagram: dos laminas de apoyo por carrusel.
    d = ROOT / "publicaciones Instagram GPT/2026-09-29"
    info_card(d / "premios-resultado-y-fuente.png", "2026", "Tres resultados documentados", [
        "Ganador: I Concurso Aullidos en papel.",
        "Primer Premio: XII Certamen de Microrrelatos De amor.",
        "Top 10 finalista: I Premio Juan Andrés Teno.",
    ], "2/3", "Premios y reconocimientos")
    info_card(d / "premios-que-se-documenta.png", "Sin mezclar obra y resultado", "Qué conserva cada registro", [
        "El resultado exacto.", "La entidad que lo concede.", "La fecha y la fuente comprobable."
    ], "3/3", "Premios y reconocimientos")

    d = ROOT / "publicaciones Instagram GPT/2026-10-02"
    info_card(d / "lector-personaje-misterio-mundo.png", "No hay una respuesta correcta", "¿Qué te hace seguir?", [
        "Un personaje al que quieres acompañar.", "Una pregunta que necesitas resolver.", "Un mundo cuyas reglas quieres entender."
    ], "2/3", "Qué tipo de lector eres")
    info_card(d / "test-para-discutir.png", "Un juego breve", "El resultado no te encierra", [
        "No diagnostica ni puntúa.", "Puedes discutir el resultado.", "Tus motivos cambian de un libro a otro."
    ], "3/3", "Qué tipo de lector eres")

    d = ROOT / "publicaciones Instagram GPT/2026-10-03"
    info_card(d / "samuel-familia-normal.png", "Capítulo 1", "Una familia empeñada en parecer normal", [
        "Samuel no encaja en esa normalidad.", "Todavía no sabe por qué.", "El secreto aparece antes que las respuestas."
    ], "2/3", "Samuel entre mundos")
    info_card(d / "samuel-mundo-o-personaje.png", "Antes de la sinopsis", "¿Qué necesitas para quedarte?", [
        "Entender cómo funciona el mundo.", "Confiar en el protagonista.", "Encontrar una pregunta que no puedas soltar."
    ], "3/3", "Capítulo gratuito")

    # TikTok: secuencias verticales. BASE-005 reutiliza las tres citas de Instagram.
    src = ROOT / "publicaciones Instagram GPT/2026-09-24"
    dst = ROOT / "publicaciones TikTok GPT/2026-10-01"
    for old, new in [
        ("fragmento-ritual-domingo.png", "tres-fragmentos-tiktok-02.png"),
        ("fragmento-precio-historia.png", "tres-fragmentos-tiktok-03.png"),
        ("fragmento-horas-silenciosas.png", "tres-fragmentos-tiktok-04.png"),
    ]:
        shutil.copy2(src / old, dst / new)

    d = ROOT / "publicaciones TikTok GPT/2026-09-30"
    info_card(d / "muestra-manecillas-kindle-02.png", "Capítulo 1.1 completo", "Elige el formato", [
        "EPUB para lectores electrónicos y apps.", "TXT para abrirlo en cualquier editor.", "Descarga directa y gratuita."
    ], "2/3", "Las manecillas del recuerdo")
    info_card(d / "muestra-manecillas-kindle-03.png", "Tres formas de leer", "Sin comprar primero", [
        "Enviarlo a Kindle.", "Abrir el EPUB en móvil u ordenador.", "Leer el TXT donde prefieras."
    ], "3/3", "Muestra gratuita")

    d = ROOT / "publicaciones TikTok GPT/2026-10-03"
    info_card(d / "tiempo-lectura-cinco-minutos-02.png", "Una estimación", "No es un cronómetro", [
        "Convierte palabras en un rango.", "Permite ajustar el ritmo de lectura.", "El texto no sale del navegador."
    ], "2/3", "Lectura en voz alta")
    info_card(d / "tiempo-lectura-cinco-minutos-03.png", "Cuándo puede servir", "Antes de ponerse a leer", [
        "Presentaciones y eventos.", "Muestras para clubes de lectura.", "Fragmentos con tiempo limitado."
    ], "3/3", "Lectura en voz alta")

    # Pinterest: portadas 2:3 nuevas.
    d = ROOT / "publicaciones Pinterest GPT/2026-09-28"
    d.mkdir(parents=True, exist_ok=True)
    pinterest_card(d / "analizar-variedad-lexica-texto.png", "Herramienta gratuita", "Variedad léxica en español", "MATTR, MTLD y cambios dentro del texto", "3", "Compara zonas del texto sin convertir una cifra en un juicio sobre la prosa.", "HERRAMIENTAS DE DAVID PORTO DÍAZ")
    d = ROOT / "publicaciones Pinterest GPT/2026-10-03"
    d.mkdir(parents=True, exist_ok=True)
    pinterest_card(d / "revisar-puntos-vista-novela.png", "Estructura de novela", "Revisa la distribución de POV", "Localiza huecos entre puntos de vista", "POV", "Visualiza el reparto de voces y contrasta la estructura sin imponer una regla automática.", "HERRAMIENTAS DE DAVID PORTO DÍAZ")
    d = ROOT / "publicaciones Pinterest GPT/2026-10-04"
    d.mkdir(parents=True, exist_ok=True)
    pinterest_card(d / "detectar-nombres-personajes-parecidos.png", "Revisión de personajes", "Detecta nombres demasiado parecidos", "Compara semejanza visual y sonora", "ABC", "Localiza posibles confusiones en el reparto y decide con el contexto de tu novela.", "HERRAMIENTAS DE DAVID PORTO DÍAZ")


def media_for(post):
    if post["net"] == "Instagram":
        extras = {
            "IGGPT-P003": ["premios-resultado-y-fuente.png", "premios-que-se-documenta.png"],
            "IGGPT-P004": ["lector-personaje-misterio-mundo.png", "test-para-discutir.png"],
            "IGGPT-P005": ["samuel-familia-normal.png", "samuel-mundo-o-personaje.png"],
        }
        return [post["image"], *extras[post["id"]]]
    if post["net"] == "TikTok":
        extras = {
            "TTGPT-P003": ["muestra-manecillas-kindle-02.png", "muestra-manecillas-kindle-03.png"],
            "TTGPT-P004": ["tres-fragmentos-tiktok-02.png", "tres-fragmentos-tiktok-03.png", "tres-fragmentos-tiktok-04.png"],
            "TTGPT-P005": ["tiempo-lectura-cinco-minutos-02.png", "tiempo-lectura-cinco-minutos-03.png"],
        }
        return [post["image"], *extras[post["id"]]]
    return [post["image"]] if post.get("image") else []


def render_doc(post):
    net = post["net"]
    folder = ROOT / f"publicaciones {net} GPT" / post["date"]
    folder.mkdir(parents=True, exist_ok=True)
    prog, via = VIA[net]
    state = post.get("state", "lista")
    lines = [f"# {post['id']} - {post['title']}", "", f"**Estado:** {state}.", "", f"- **BASE:** `{post['base']}`.", f"- **Fecha y hora:** {post['date']}, {post['time']} (Europe/Madrid).", f"- **Programación:** {prog}; {via}.", f"- **Objetivo:** {post['objective']}."]
    if net == "Threads":
        lines += [f"- **Tema nativo candidato:** `{post['topic']}`."]
    if net in {"Instagram", "TikTok"}:
        lines += [f"- **Destino web:** {post['url']}."]
    if net == "Instagram":
        lines += [f"- **Etiqueta del enlace de perfil:** `{post['profile_label']}`."]
    if net == "Pinterest":
        lines += [f"- **Tablero:** `{post['board']}`.", f"- **Imagen:** `{post['image']}`.", "", "## Título", "", post["title"], "", "## Descripción", "", post["description"], "", "## Destino y ALT", "", f"- **Enlace:** {post['url']}", f"- **ALT:** {post['alt']}", "", "## Ejecución", "", "Crear el Pin desde Pinterest Business, comprobar tablero, destino, ALT y vista previa 2:3, y elegir Publicar más adelante. Guardar la URL del Pin en el registro."]
    elif net == "Reddit":
        lines += [f"- **Subreddit:** `{post['subreddit']}`.", f"- **Flair candidato:** `{post['flair']}`.", "- **Enlace propio:** ninguno.", "- **Imagen:** ninguna.", "", "## Título", "", post["title"], "", "## Texto", "", post["text"], "", "## Ejecución", "", "Releer reglas y fijados, comprobar que no haya una pregunta equivalente reciente y elegir un flair real. No añadir enlaces propios en el post ni en respuestas. Responder desde lo que diga cada persona, sin llevar la conversación a una herramienta."]
    else:
        heading = "Caption final" if net in {"Instagram", "TikTok"} else "Texto final propuesto" if net in {"X", "Threads"} else "Texto final"
        lines += ["", f"## {heading}", "", post["text"], "", "## Medios y ALT", ""]
        files = media_for(post)
        for i, name in enumerate(files, 1):
            alt = post["alt"] if i == 1 else ALT_EXTRA[post["id"]][i - 2]
            lines.append(f"{i}. `{name}`: {alt}")
        lines += ["", "## Ejecución y respuesta", ""]
        if net == "X":
            lines.append("Programar en X con su compositor nativo, añadir ALT y comprobar el recuento ponderado. Responder a ejemplos concretos; no contestar con una plantilla de agradecimiento.")
        elif net == "Threads":
            lines.append("Añadir imagen, ALT y el tema nativo desde Threads web. Confirmar que el tema candidato existe y que la programación lo conserva; si no, publicar manualmente. Usar las respuestas para abrir segundos turnos, no para repetir el enlace.")
        elif net == "Instagram":
            lines.append(f"Cargar el carrusel en el orden indicado, añadir un ALT por imagen y revisar el recorte móvil. Antes de programar, añadir o verificar en el perfil el enlace `{post['profile_label']}` con el destino web de esta ficha. Responder sobre la elección o experiencia concreta del comentario.")
        elif net == "Facebook":
            lines.append("Programar desde Meta Business Suite como la página correcta. Revisar previsualización y enlace. Conversar primero; no convertir cada comentario en una venta.")
        elif net == "TikTok":
            lines.append("Publicar manualmente como carrusel fotográfico y revisar portada, orden, descripción y comentarios habilitados. El dominio escrito orienta al destino de esta ficha sin depender de cambiar el enlace del perfil.")
        elif net == "Bluesky":
            lines.append("Publicar manualmente con idioma español, imagen y ALT. Confirmar menos de 300 caracteres y guardar la URI. Responder con curiosidad real, sin repetir la pregunta inicial.")
        elif net == "Mastodon":
            lines.append("Publicar manualmente con visibilidad pública, imagen y ALT. Confirmar menos de 500 caracteres. Favorecer respuestas desarrolladas y no usar el enlace como cierre automático.")
    (folder / "publicacion.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def append_registry(post):
    path = ROOT / f"publicaciones {post['net']} GPT/REGISTRO_CONTENIDO_USADO.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        rows = list(reader)
    row = next((item for item in rows if item.get("id") == post["id"]), None)
    if row is None:
        row = {field: "" for field in fields}
        rows.append(row)
    common = {
        "id": post["id"], "base_id": post["base"], "fecha_propuesta": post["date"], "hora_propuesta": post["time"],
        "estado": post.get("state", "lista"), "formato": "texto + imagen", "tema": post["theme"], "objetivo": post["objective"],
        "hashtags": post.get("tags", ""), "url_web": post.get("url", ""), "imagen": f"{post['date']}/{post.get('image','')}" if post.get("image") else "ninguna",
        "programacion": VIA[post["net"]][0], "via_programacion": VIA[post["net"]][1],
    }
    for key, value in common.items():
        if key in row:
            row[key] = value
    if "familia" in row:
        row["familia"] = post["theme"]
    if "angulo" in row:
        row["angulo"] = post["title"]
    if "apertura" in row and post.get("text"):
        row["apertura"] = post["text"].splitlines()[0]
    if "topic_nativo" in row:
        row["topic_nativo"] = post.get("topic", "")
    if "comunidad" in row:
        row["comunidad"] = post.get("topic", "")
    if "tablero" in row:
        row["tablero"] = post.get("board", "")
    if "titulo_pin" in row:
        row["titulo_pin"] = post["title"]
    if "subreddit" in row:
        row["subreddit"] = post.get("subreddit", "")
    if "flair" in row:
        row["flair"] = post.get("flair", "")
    if "titulo" in row:
        row["titulo"] = post["title"]
    if "enlace_propio" in row:
        row["enlace_propio"] = "no"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)


def append_master():
    path = ROOT / "publicaciones GPT/REGISTRO_MAESTRO_MULTIRRED.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        rows = list(reader)
    known = {row["base_id"] for row in rows}
    for base, concept, family, url, capture in NEW_BASES:
        if base in known:
            continue
        rows.append({
            "base_id": base, "concepto": concept, "familia": family, "fuente_url": url, "captura_banco": capture,
            "asset_maestro": f"publicaciones GPT/banco imagenes web/{capture}/captura.png", "estado_base": "activo",
            "primera_adaptacion": next(post["id"] for post in POSTS if post["base"] == base), "fecha_primera_publicacion": "",
            "ultima_red": "", "ultima_fecha": "", "proxima_red_sugerida": "", "no_antes_de": "",
            "regla_reutilizacion": "No usar en dos redes la misma semana; esperar al menos 7 días desde la publicación real y reescribir para la red de destino",
            "notas": "Creada para la rotación 28/09-04/10; pendiente de publicación real",
        })
    planned = {post["base"]: post for post in POSTS}
    for row in rows:
        row["notas"] = row.get("notas", "").replace("Bloqueada hasta sanear cola Pinterest; ", "")
        post = planned.get(row["base_id"])
        if not post:
            continue
        row["proxima_red_sugerida"] = post["net"]
        row["no_antes_de"] = post["date"]
        marker = f"Rotación preparada: {post['id']} en {post['net']} para {post['date']}"
        notes = [part for part in row.get("notas", "").split("; ") if not part.startswith("Rotación preparada:")]
        row["notas"] = "; ".join([*notes, marker])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)


def write_rotation_registry():
    path = ROOT / "publicaciones GPT/ROTACION_MULTIRRED_2026-09-28_10-04.csv"
    fields = ["fecha", "hora", "red", "id", "base_id", "tipo_base", "red_origen", "fecha_origen_prevista", "separacion_dias_prevista", "confirmar_publicacion_origen", "estado", "via", "tema"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for post in POSTS:
            base_num = int(post["base"].split("-")[1])
            if base_num <= 16 or base_num == 19:
                kind = "rotada"
            elif base_num in {17, 18}:
                kind = "rescatada_de_red_descartada"
            elif base_num == 20:
                kind = "continuidad_original_reddit"
            else:
                kind = "nueva_para_completar_pool"
            origin_net, origin_date = ORIGIN.get(post["base"], ("nueva", ""))
            if origin_date:
                from datetime import date
                separation = (date.fromisoformat(post["date"]) - date.fromisoformat(origin_date)).days
            else:
                separation = ""
            writer.writerow({
                "fecha": post["date"], "hora": post["time"], "red": post["net"], "id": post["id"], "base_id": post["base"],
                "tipo_base": kind, "red_origen": origin_net, "fecha_origen_prevista": origin_date,
                "separacion_dias_prevista": separation, "confirmar_publicacion_origen": "si" if kind == "rotada" else "no",
                "estado": post.get("state", "lista"), "via": VIA[post["net"]][1], "tema": post["theme"],
            })


def write_future_queue():
    path = ROOT / "publicaciones GPT/COLA_ROTACION_BASES.csv"
    fields = ["base_id", "adaptacion_actual", "red_actual", "fecha_actual", "siguiente_red_1", "siguiente_red_2", "siguiente_red_3", "regla", "estado"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for post in POSTS:
            current = post["net"]
            if current in STANDARD_NETWORKS:
                index = STANDARD_NETWORKS.index(current)
                next_networks = [STANDARD_NETWORKS[(index + step) % len(STANDARD_NETWORKS)] for step in (1, 2, 3)]
            else:
                next_networks = ["X", "Threads", "Instagram"]
            writer.writerow({
                "base_id": post["base"], "adaptacion_actual": post["id"], "red_actual": current, "fecha_actual": post["date"],
                "siguiente_red_1": next_networks[0], "siguiente_red_2": next_networks[1], "siguiente_red_3": next_networks[2],
                "regla": "adaptar texto, CTA, hashtags/topic, medio y fecha; nunca copiar el post terminado",
                "estado": "esperar_publicacion_y_metricas",
            })


def write_calendar():
    path = ROOT / "publicaciones GPT/CALENDARIO_EJECUCION_2026-09-28_10-04.md"
    active = [post for post in POSTS if post.get("state", "lista") != "reserva_regla_semanal"]
    lines = [
        "# Calendario de ejecución · 28 de septiembre-4 de octubre de 2026", "",
        "Rotación de 27 bases distintas: 25 salidas de la semana y 2 reservas de Reddit. Ninguna base se repite entre redes durante la misma semana.", "",
        "## Calendario", "", "| Fecha | Hora | Red | ID | BASE | Vía |", "|---|---:|---|---|---|---|",
    ]
    for post in sorted(active, key=lambda p: (p["date"], p["time"], p["net"])):
        lines.append(f"| {post['date']} | {post['time']} | {post['net']} | `{post['id']}` | `{post['base']}` | {VIA[post['net']][1]} |")
    lines += ["", "## Reservas Reddit", "", "Reddit mantiene un máximo de un post propio por semana. Los otros dos textos quedan terminados, pero no se publican en la misma semana:", ""]
    for post in POSTS:
        if post.get("state") == "reserva_regla_semanal":
            lines.append(f"- {post['date']} · `{post['id']}` · `{post['base']}` · {post['title']}")
    lines += [
        "", "## Preflight de plataforma", "",
        "- Instagram: comprobar que las etiquetas de enlace de perfil indicadas en las fichas existen y llevan al destino correcto.",
        "- Threads: confirmar el tema nativo en el selector y revisar que siga presente después de programar.",
        "- TikTok: estas piezas son carruseles fotográficos manuales hasta validar su programación sin pérdida de formato.",
        "- Reddit: releer reglas, buscar duplicados y elegir un flair real antes de cada salida.",
        "", "## Regla de rotación", "",
        "El plazo de siete días se calcula desde la publicación real. Si una pieza de la semana anterior no llegó a publicarse, revisar su BASE antes de ejecutar la adaptación y moverla si produciría simultaneidad.",
        "", "Cada ficha contiene texto, medios, ALT, vía y pauta de respuesta. Guardar el permalink tras publicar y medir a 24 horas y 7 días.", "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    make_supporting_assets()
    for post in POSTS:
        # RDGPT-P002 ya existía: se reescribe para unificar la ficha, sin duplicar CSV.
        render_doc(post)
        append_registry(post)
    append_master()
    write_rotation_registry()
    write_future_queue()
    write_calendar()
    print(f"Construidas {len(POSTS)} adaptaciones ({sum(p.get('state') != 'reserva_regla_semanal' for p in POSTS)} activas y 2 reservas Reddit).")


if __name__ == "__main__":
    main()
