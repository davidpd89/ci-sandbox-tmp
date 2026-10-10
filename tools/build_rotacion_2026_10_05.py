"""Construye la rotación multirred del 05/10 al 11/10 de 2026."""
from __future__ import annotations

import csv
import shutil
from pathlib import Path

import build_rotacion_2026_09_28 as previous
from build_publicaciones_gpt_assets import info_card, pinterest_card


ROOT = Path(__file__).resolve().parents[1]


POSTS = [
    # X recibe tres bases que la semana anterior estuvieron en Pinterest.
    dict(net="X", id="XGPT-P006", base="BASE-026", date="2026-10-05", time="18:45", title="Una cifra no sabe si una repetición funciona", theme="variedad léxica", objective="clics y conversación", url="https://davidportodiaz.com/herramientas/variedad-lexica/", tags="#Escritura #Autores", source="publicaciones Pinterest GPT/2026-09-28/analizar-variedad-lexica-texto.png", image="variedad-lexica-x.png", alt="Herramienta para comparar la variedad léxica de distintas zonas de un texto.", text="""Un texto puede repetir una palabra por torpeza, ritmo, voz o pura necesidad. La cifra no conoce la diferencia.

Esta herramienta señala cambios de variedad para que vuelvas al párrafo, no para que obedezcas al gráfico.

https://davidportodiaz.com/herramientas/variedad-lexica/

#Escritura #Autores"""),
    dict(net="X", id="XGPT-P007", base="BASE-019", date="2026-10-10", time="12:15", title="El personaje que desapareció del manuscrito", theme="distribución de POV", objective="uso de herramienta y respuestas", url="https://davidportodiaz.com/herramientas/distribucion-pov/", tags="#EscrituraCreativa #Novela", source="publicaciones Pinterest GPT/2026-10-03/revisar-puntos-vista-novela.png", image="huecos-punto-vista-x.png", alt="Herramienta para visualizar la distribución de puntos de vista en una novela.", text="""A veces un personaje no pierde importancia: simplemente desaparece durante seis capítulos y nadie lo nota hasta releer.

El mapa de POV deja esos huecos a la vista. Luego toca decidir si son pausa o problema.

https://davidportodiaz.com/herramientas/distribucion-pov/

#EscrituraCreativa #Novela"""),
    dict(net="X", id="XGPT-P008", base="BASE-013", date="2026-10-11", time="11:30", title="Cuando dos nombres empiezan a mezclarse", theme="nombres de personajes", objective="clics y conversación", url="https://davidportodiaz.com/herramientas/nombres-personajes/", tags="#Personajes #Escritura", source="publicaciones Pinterest GPT/2026-10-04/detectar-nombres-personajes-parecidos.png", image="nombres-parecidos-x.png", alt="Comprobador de nombres de personajes con parecido visual o sonoro.", text="""Mara y Maia pueden ser personas muy distintas y aun así fundirse en la cabeza del lector.

Este comprobador señala parecidos visuales y sonoros. No renombra a nadie: te devuelve la decisión.

https://davidportodiaz.com/herramientas/nombres-personajes/

#Personajes #Escritura"""),

    # Threads recibe las tres bases anteriores de X y abre conversación con tema nativo.
    dict(net="Threads", id="THGPT-P006", base="BASE-017", date="2026-10-05", time="20:15", title="El material de prensa que nadie debería adivinar", theme="kit de prensa", objective="conversación y visitas", url="https://davidportodiaz.com/herramientas/kit-prensa-escritores/", topic="Writing", source="publicaciones X GPT/2026-09-28/kit-prensa-local-escritores.png", image="kit-prensa-threads.png", alt="Generador local de un kit de prensa con biografías, ficha del libro, permisos y manifiesto.", text="""Cuando un medio pide una bio corta, una larga, la ficha del libro y una foto utilizable, el problema no es escribirlo una vez. Es saber cuál era la versión correcta.

El generador reúne las versiones correctas en un ZIP, sin obligarte a rebuscar en cinco carpetas.

¿Qué archivo te tocó improvisar la última vez que te pidieron material?

https://davidportodiaz.com/herramientas/kit-prensa-escritores/"""),
    dict(net="Threads", id="THGPT-P007", base="BASE-011", date="2026-10-08", time="20:00", title="La lectura que recomendarías hoy", theme="tarjeta estoy leyendo", objective="respuestas y uso de herramienta", url="https://davidportodiaz.com/herramientas/tarjeta-estoy-leyendo/", topic="Book Threads", source="publicaciones X GPT/2026-10-01/tarjeta-estoy-leyendo-abierta.png", image="estoy-leyendo-threads.png", alt="Generador de una tarjeta abierta para compartir el libro que estás leyendo.", text="""Hay libros que recomendarías al terminar y otros que ya estás recomendando por la página 40.

La tarjeta «Estoy leyendo» captura justo ese momento. No pide cuenta ni nota.

¿Qué libro tienes abierto ahora mismo y qué te está haciendo continuar?

https://davidportodiaz.com/herramientas/tarjeta-estoy-leyendo/"""),
    dict(net="Threads", id="THGPT-P008", base="BASE-016", date="2026-10-11", time="18:45", title="No todas las puertas prometen regreso", theme="portal fantasy en español", objective="recomendaciones y conversación", url="https://davidportodiaz.com/recomendaciones/portal-fantasy-espanol/", topic="Fantasy Books", source="publicaciones X GPT/2026-10-04/portal-fantasy-juvenil-x.png", image="portal-fantasy-threads.png", alt="Selección comentada de diez libros de portal fantasy juvenil disponibles en español.", text="""En el portal fantasy, cruzar suele ser lo sencillo. Lo difícil es descubrir qué has dejado atrás, quién controla la vuelta o si todavía quieres regresar.

En la lista hay diez libros disponibles en español y ninguna puerta funciona igual.

¿Qué cruce entre mundos se te quedó grabado?

https://davidportodiaz.com/recomendaciones/portal-fantasy-espanol/"""),

    # Instagram recibe tres bases de Threads y las convierte en carruseles.
    dict(net="Instagram", id="IGGPT-P006", base="BASE-018", date="2026-10-05", time="19:30", title="Una página bonita no siempre ayuda a elegir", theme="auditoría de página de libro", objective="guardados y visitas", url="https://davidportodiaz.com/herramientas/auditor-pagina-libro/", profile_label="Auditor de página", tags="#Autores #MarketingEditorial #Libros #Escritura", source="publicaciones Threads GPT/2026-09-28/auditor-pagina-libro-threads.png", image="auditor-pagina-libro-instagram.png", alt="Auditor que revisa si una página de libro ayuda a una persona a decidir.", text="""Una página de libro puede ser preciosa y dejarte con tres dudas: qué clase de historia es, si está escrita para ti y dónde puedes probarla o comprarla.

Este auditor no puntúa el diseño. Revisa si la página responde esas preguntas y si cada afirmación importante puede comprobarse.

Guarda la lista para la próxima revisión. Al descubrir un libro, ¿qué dato buscas primero?

En el perfil: «Auditor de página».

#Autores #MarketingEditorial #Libros #Escritura"""),
    dict(net="Instagram", id="IGGPT-P007", base="BASE-007", date="2026-10-08", time="11:30", title="Lo que sabemos y lo que la familia recuerda", theme="historia de un objeto heredado", objective="guardados y conversación", url="https://davidportodiaz.com/recursos/ficha-historia-objeto-heredado/", profile_label="Objeto heredado", tags="#MemoriaFamiliar #HistoriasDeFamilia #Escritura #ObjetosConHistoria", source="publicaciones Threads GPT/2026-10-01/objeto-heredado-threads.png", image="objeto-heredado-instagram.png", alt="Ficha para documentar la procedencia y los recuerdos ligados a un objeto heredado.", text="""En casi todas las familias hay un objeto cuya historia cambia un poco según quién la cuente.

La ficha separa lo comprobado, lo recordado y lo que todavía es una hipótesis. No para quitarle misterio, sino para que cada voz conserve su lugar.

En la última lámina dejo las preguntas para empezar. ¿Qué objeto de tu familia merecería esa conversación?

En el perfil: «Objeto heredado».

#MemoriaFamiliar #HistoriasDeFamilia #Escritura #ObjetosConHistoria"""),
    dict(net="Instagram", id="IGGPT-P008", base="BASE-009", date="2026-10-09", time="18:30", title="La diferencia está en dónde empieza el viaje", theme="portal fantasy frente a fantasía épica", objective="comentarios y lectura", url="https://davidportodiaz.com/cuaderno/portal-fantasy-vs-fantasia-epica/", profile_label="Portal o épica", tags="#PortalFantasy #FantasíaÉpica #BookstagramEspaña #LibrosDeFantasía", source="publicaciones TikTok GPT/2026-09-25/portal-fantasy-vs-fantasia-epica-01.png", image="portal-vs-epica-instagram-01.png", alt="Portada de una comparación entre portal fantasy y fantasía épica.", text="""Dos historias pueden tener magia, mapas y criaturas imposibles, y pedirle al lector cosas completamente distintas.

En una, el protagonista cruza desde un mundo conocido. En la otra, ya pertenece al mundo fantástico y nosotros aprendemos a habitarlo con él.

Primera decisión: ¿cruzar la puerta o despertar ya al otro lado?

En el perfil: «Portal o épica».

#PortalFantasy #FantasíaÉpica #BookstagramEspaña #LibrosDeFantasía"""),

    # Facebook recibe las piezas anteriores de Instagram con más contexto.
    dict(net="Facebook", id="FBGPT-P006", base="BASE-021", date="2026-10-06", time="12:30", title="Qué significa documentar un reconocimiento", theme="premios documentados", objective="confianza y conversación", url="https://davidportodiaz.com/premios.html", tags="#PremiosLiterarios #Escritores", source="publicaciones Instagram GPT/2026-09-29/premios-david-porto-2026.png", image="premios-documentados-facebook.png", alt="Página de premios de David Porto Díaz con resultado, entidad, fecha y fuente.", text="""Un reconocimiento cabe en una línea, pero esa línea debería decir exactamente qué ocurrió.

En la página de premios he reunido el resultado, la entidad, la fecha y la fuente de cada mención de 2026. También separo los premios del autor de los premios de sus libros, porque no significan lo mismo.

https://davidportodiaz.com/premios.html

Cuando lees una trayectoria, ¿qué dato te ayuda a confiar en ella?

#PremiosLiterarios #Escritores"""),
    dict(net="Facebook", id="FBGPT-P007", base="BASE-003", date="2026-10-09", time="19:00", title="Por qué sigues leyendo cuando podrías cerrar el libro", theme="test de tipo de lector", objective="comentarios y visitas", url="https://davidportodiaz.com/herramientas/que-tipo-de-lector-eres/", tags="#Lectores #Libros", source="publicaciones Instagram GPT/2026-10-02/que-te-hace-seguir-leyendo.png", image="tipo-lector-facebook.png", alt="Test breve sobre los motivos que hacen que una persona continúe leyendo.", text="""En el último libro que te robó horas de sueño, ¿qué tiraba más de ti: el personaje, el misterio o el mundo?

El test pone esas tres razones sobre la mesa. El resultado no es una etiqueta; seguramente cambie con la siguiente lectura.

https://davidportodiaz.com/herramientas/que-tipo-de-lector-eres/

¿Qué pesó más en el último libro que no pudiste soltar?

#Lectores #Libros"""),
    dict(net="Facebook", id="FBGPT-P008", base="BASE-008", date="2026-10-10", time="12:00", title="Leer el capítulo antes de decidir", theme="capítulo gratuito de Samuel", objective="lectura y descubrimiento", url="https://davidportodiaz.com/fragmento/", tags="#FantasíaJuvenil #LecturaEnEspañol", source="publicaciones Instagram GPT/2026-10-03/samuel-capitulo-antes-sinopsis.png", image="capitulo-samuel-facebook.png", alt="Cabecera del primer capítulo gratuito de Samuel entre mundos.", text="""Una sinopsis puede contarte la promesa de una novela. El primer capítulo te enseña su voz, su ritmo y cuánto tardas en querer saber algo más.

El de *Samuel entre mundos* empieza con una familia obsesionada con parecer normal y un chico que aún no conoce el secreto que explica por qué nunca ha encajado.

Puedes leerlo completo, gratis y sin registro:
https://davidportodiaz.com/fragmento/

¿Qué necesitas encontrar en un primer capítulo para continuar?

#FantasíaJuvenil #LecturaEnEspañol"""),

    # TikTok recibe las tres bases de Facebook como carruseles fotográficos.
    dict(net="TikTok", id="TTGPT-P006", base="BASE-022", date="2026-10-06", time="19:30", title="Lo que no se ve en una foto de feria", theme="Feria del Libro de Madrid", objective="comentarios y comunidad", url="https://davidportodiaz.com/cuaderno/feria-libro-madrid-2026-samuel-entre-mundos/", tags="#FeriaDelLibro #Autores #Libros #BookTokEspaña #SamuelEntreMundos", source="publicaciones Facebook GPT/2026-09-29/samuel-feria-libro-madrid-2026.png", image="feria-libro-tiktok-01.png", alt="Crónica de la firma de Samuel entre mundos en la Feria del Libro de Madrid 2026.", text="""Una foto de feria enseña la mesa. No enseña la espera, las conversaciones ni el momento en que alguien abre tu libro delante de ti.

En las siguientes imágenes está lo que no salió en la foto de la firma de *Samuel entre mundos* en Madrid.

¿Qué recuerdas más de una feria: un libro, una charla o una casualidad?

La crónica está en davidportodiaz.com.

#FeriaDelLibro #Autores #Libros #BookTokEspaña #SamuelEntreMundos"""),
    dict(net="TikTok", id="TTGPT-P007", base="BASE-001", date="2026-10-08", time="12:00", title="Tres formas de entrar en la misma novela", theme="Las manecillas del recuerdo", objective="descubrimiento y comentarios", url="https://davidportodiaz.com/las-manecillas-del-recuerdo/", tags="#NovelaCoral #Libros #LecturaEnEspañol #BookTokEspaña #FicciónEspeculativa", source="publicaciones Facebook GPT/2026-10-01/manecillas-tres-vidas-facebook.png", image="manecillas-tres-puertas-tiktok-01.png", alt="Página de Las manecillas del recuerdo con memoria, valor y futuro como puertas de entrada.", text="""La misma novela puede empezar en tres sitios distintos.

Por lo que una familia recuerda a medias. Por el valor que damos a un objeto. O por lo extraño que resulta conservar algo antiguo en un mundo digital.

Tres imágenes, tres entradas: memoria, valor o futuro. ¿Por cuál empiezas?

La novela está en davidportodiaz.com.

#NovelaCoral #Libros #LecturaEnEspañol #BookTokEspaña #FicciónEspeculativa"""),
    dict(net="TikTok", id="TTGPT-P008", base="BASE-014", date="2026-10-11", time="20:00", title="La relación que cambió sin que la apuntaras", theme="relaciones entre personajes", objective="guardados y uso de herramienta", url="https://davidportodiaz.com/herramientas/personajes/", tags="#EscrituraCreativa #Personajes #Novela #BookTokEspaña #HerramientasParaEscritores", source="publicaciones Facebook GPT/2026-10-04/mapa-relaciones-personajes-facebook.png", image="relaciones-personajes-tiktok-01.png", alt="Mapa local para registrar relaciones y cambios entre personajes.", text="""En el capítulo dos se soportan. En el ocho se protegen. En el doce actúan como si siempre hubieran confiado el uno en el otro.

El problema no es el cambio: es perder la escena que lo hizo posible.

Pasa a la siguiente. ¿Qué relación te cuesta más seguir: familia, amistad o rivalidad?

La herramienta está en davidportodiaz.com.

#EscrituraCreativa #Personajes #Novela #BookTokEspaña #HerramientasParaEscritores"""),

    # Bluesky recibe tres bases de TikTok en formato breve.
    dict(net="Bluesky", id="BSGPT-P006", base="BASE-023", date="2026-10-07", time="09:30", title="Leer antes de comprar", theme="muestra de Las manecillas", objective="clics y lectura", url="https://davidportodiaz.com/las-manecillas-del-recuerdo/kindle/", tags="#BookSky #Lectura", source="publicaciones TikTok GPT/2026-09-30/muestra-manecillas-kindle-01.png", image="muestra-manecillas-bluesky.png", alt="Página para descargar gratis una muestra de Las manecillas del recuerdo en EPUB o TXT.", text="""Antes de comprar un libro, prefiero que puedas escuchar su voz. El capítulo 1.1 de *Las manecillas del recuerdo* se descarga gratis en EPUB o TXT y también puede enviarse a Kindle.

https://davidportodiaz.com/las-manecillas-del-recuerdo/kindle/

#BookSky #Lectura"""),
    dict(net="Bluesky", id="BSGPT-P007", base="BASE-005", date="2026-10-08", time="18:00", title="Tres voces, una novela", theme="fragmentos de Las manecillas", objective="elección y lectura", url="https://davidportodiaz.com/las-manecillas-del-recuerdo/fragmentos/", tags="#BookSky #NovelaCoral", source="publicaciones TikTok GPT/2026-10-01/tres-fragmentos-tiktok-01.png", image="tres-fragmentos-bluesky.png", alt="Tres fragmentos de Las manecillas del recuerdo con registros íntimo, de humor negro y futuro cercano.", text="""Tres entradas a la misma novela: un desayuno donde nadie toca el chocolate, una casa de empeños que infla una historia y un futuro sin tic-tac.

¿Con cuál empezarías: 1, 2 o 3?
https://davidportodiaz.com/las-manecillas-del-recuerdo/fragmentos/

#BookSky #NovelaCoral"""),
    dict(net="Bluesky", id="BSGPT-P008", base="BASE-012", date="2026-10-10", time="09:45", title="Cinco minutos no siempre son cinco minutos", theme="lectura en voz alta", objective="uso de herramienta y conversación", url="https://davidportodiaz.com/herramientas/tiempo-lectura-voz-alta/", tags="#Escritura #Autores", source="publicaciones TikTok GPT/2026-10-03/tiempo-lectura-cinco-minutos-01.png", image="tiempo-lectura-bluesky.png", alt="Estimador local de tiempo para leer un texto en voz alta.", text="""Una lectura de cinco minutos cambia con los diálogos, las pausas, los nombres difíciles y los nervios. Este estimador da un rango; el ensayo sigue mandando.

https://davidportodiaz.com/herramientas/tiempo-lectura-voz-alta/

¿Qué te hace frenar al leer en público?

#Escritura #Autores"""),

    # Mastodon recibe tres bases de Bluesky con contexto y conversación.
    dict(net="Mastodon", id="MAGPT-P006", base="BASE-024", date="2026-10-05", time="08:45", title="Una pregunta de club no es un examen", theme="club de lectura de Samuel", objective="conversación y visitas", url="https://davidportodiaz.com/clubes-de-lectura/samuel-entre-mundos/", tags="#ClubDeLectura #Libros #Bookstodon", source="publicaciones Bluesky GPT/2026-09-28/club-lectura-samuel-bluesky.png", image="club-samuel-mastodon.png", alt="Guía de Samuel entre mundos con preguntas abiertas y recursos para clubes de lectura.", text="""Una pregunta de club funciona cuando dos personas pueden defender respuestas distintas con escenas del libro. Si solo comprueba quién recordó un dato, se parece demasiado a un examen.

La guía de *Samuel entre mundos* propone hablar de identidad, pertenencia y coste del poder sin spoilers innecesarios.

https://davidportodiaz.com/clubes-de-lectura/samuel-entre-mundos/

¿Qué pregunta os ha abierto una conversación inesperada?

#ClubDeLectura #Libros #Bookstodon"""),
    dict(net="Mastodon", id="MAGPT-P007", base="BASE-002", date="2026-10-10", time="17:45", title="La repetición que debe quedarse", theme="repeticiones deliberadas", objective="conversación y uso de herramienta", url="https://davidportodiaz.com/herramientas/repeticiones/", tags="#Escritura #Edición #Autores", source="publicaciones Bluesky GPT/2026-10-03/ecos-repeticiones-bluesky.png", image="repeticiones-mastodon.png", alt="Detector local de ecos, palabras próximas y arranques repetidos.", text="""No toda repetición pide tijera. Algunas sostienen una voz, fijan una imagen o hacen que una frase vuelva con otro significado.

El detector localiza palabras próximas y arranques parecidos; la decisión sigue siendo narrativa y el texto no sale del navegador.

https://davidportodiaz.com/herramientas/repeticiones/

¿Qué repetición deliberada recuerdas haber defendido?

#Escritura #Edición #Autores"""),
    dict(net="Mastodon", id="MAGPT-P008", base="BASE-010", date="2026-10-11", time="08:45", title="Una ciudad necesita una razón para estar ahí", theme="worldbuilding de Noveris", objective="lectura y conversación", url="https://davidportodiaz.com/cuaderno/worldbuilding-noveris-ciudad-magica/", tags="#Worldbuilding #Fantasía #Escritura", source="publicaciones Bluesky GPT/2026-10-04/noveris-no-es-decorado-bluesky.png", image="noveris-mastodon.png", alt="Artículo sobre cómo la ubicación de Noveris condiciona su economía, arquitectura y conflictos.", text="""Mover una ciudad fantástica diez kilómetros debería cambiar algo. Si no cambia rutas, recursos, arquitectura ni conflictos, quizá todavía sea un decorado con nombre.

Noveris empezó a volverse concreta cuando me pregunté por qué existía exactamente allí.

https://davidportodiaz.com/cuaderno/worldbuilding-noveris-ciudad-magica/

¿Qué detalle hace habitable una ciudad ficticia para ti?

#Worldbuilding #Fantasía #Escritura"""),

    # Pinterest recibe tres bases de Mastodon y nuevas portadas 2:3.
    dict(net="Pinterest", id="PINGPT-P006", base="BASE-025", date="2026-10-05", time="10:30", title="Cómo comprobar datos de una editorial", theme="metodología editorial", objective="guardados y visitas", url="https://davidportodiaz.com/metodologia-editorial/", board="Recursos para escritores", image="comprobar-datos-editorial.png", alt="Guía visual para comprobar fuente, fecha y estado de los datos de una editorial.", description="Método para investigar editoriales sin copiar listados desactualizados: localizar la fuente oficial, registrar la fecha de revisión, distinguir datos confirmados de inferencias y marcar convocatorias o vías de envío cerradas."),
    dict(net="Pinterest", id="PINGPT-P007", base="BASE-015", date="2026-10-09", time="10:30", title="Fantasía juvenil española publicada en 2025 y 2026", theme="fantasía juvenil española", objective="guardados y clics", url="https://davidportodiaz.com/cuaderno/libros-fantasia-juvenil-espanola-2025-2026/", board="Lecturas y fantasía", image="fantasia-juvenil-espanola-pinterest.png", alt="Portada de una selección comentada de fantasía juvenil española de 2025 y 2026.", description="Selección de fantasía juvenil española reciente con el rasgo que distingue cada libro y una orientación sobre el tipo de lector al que puede interesar. Incluye obras publicadas en 2025 y 2026, no una clasificación automática."),
    dict(net="Pinterest", id="PINGPT-P008", base="BASE-004", date="2026-10-11", time="10:30", title="6 libros de fantasía donde la magia tiene un coste", theme="magia con coste", objective="guardados y clics", url="https://davidportodiaz.com/recomendaciones/magia-con-coste/", board="Lecturas y fantasía", image="libros-magia-con-coste-pinterest.png", alt="Portada de una selección de seis libros donde la magia exige recursos, intercambios o consecuencias.", description="Seis libros de fantasía donde la magia tiene un precio que afecta a las decisiones: recursos limitados, intercambio, consecuencias físicas o costes colectivos. La selección explica también por qué hard magic y magia con coste no son exactamente lo mismo."),

    # Reddit mantiene cadencia semanal. Son tres reservas nuevas, sin enlaces ni imágenes.
    dict(net="Reddit", id="RDGPT-P005", base="BASE-028", date="2026-10-20", time="18:00", title="¿Os sirve conocer el porcentaje de diálogo de un capítulo?", theme="porcentaje de diálogo", objective="conversación de oficio", subreddit="r/escribir", flair="Duda sobre estilo/ritmo", text="""No sé si se lee menos o si ahora se lee de otra forma. ¿Cómo lo veis?""", state="reserva_regla_semanal"),
    dict(net="Reddit", id="RDGPT-P006", base="BASE-029", date="2026-10-27", time="18:00", title="¿Cuándo corregís las convenciones de diálogo?", theme="convenciones de diálogo", objective="conversación de oficio", subreddit="r/escribir", flair="Duda sobre estilo/ritmo", text="""A mí todavía me cuesta dejar uno a medias, aunque cada vez tengo menos paciencia. ¿Qué hacéis vosotros?""", state="reserva_regla_semanal"),
    dict(net="Reddit", id="RDGPT-P007", base="BASE-030", date="2026-11-03", time="18:00", title="¿Comparáis la estructura de los capítulos entre sí?", theme="comparación de capítulos", objective="conversación de oficio", subreddit="r/escribir", flair="Duda sobre estilo/ritmo", text="""El típico libro que os gustaría descubrir de nuevo desde cero.""", state="reserva_regla_semanal"),
]


ALT_EXTRA = {
    "IGGPT-P006": [
        "Tres preguntas para una página de libro: qué es, para quién puede encajar y cuál es el siguiente paso.",
        "Lista de comprobación sobre muestra, compra y afirmaciones verificables en una página de libro.",
    ],
    "IGGPT-P007": [
        "Tres capas para documentar un objeto heredado: hechos comprobados, recuerdos e hipótesis.",
        "Preguntas sobre propietarios, fechas, fuentes y versiones familiares de la historia de un objeto.",
    ],
    "IGGPT-P008": [
        "Comparación: en portal fantasy el protagonista cruza desde un mundo conocido; en fantasía épica ya pertenece al mundo fantástico.",
        "Dos formas de entrar en una historia fantástica: cruzar una puerta o despertar ya dentro de ese mundo.",
    ],
    "TTGPT-P006": [
        "Tres cosas que no caben en una foto de feria: espera, conversaciones y lectores abriendo el libro.",
        "Invitación a recordar un libro, una charla o una casualidad vivida en una feria.",
    ],
    "TTGPT-P007": [
        "Tres puertas de entrada a Las manecillas del recuerdo: memoria, valor y futuro.",
        "Pregunta visual para elegir entre memoria familiar, valor de los objetos y futuro digital.",
    ],
    "TTGPT-P008": [
        "Evolución de una relación ficticia desde la desconfianza hasta la protección.",
        "Recordatorio de localizar la escena que hace creíble un cambio entre personajes.",
    ],
}


NEW_BASES = [
    ("BASE-028", "Usar el porcentaje de diálogo como señal, no como objetivo", "oficio de escritura", "https://davidportodiaz.com/herramientas/dialogo/", "229"),
    ("BASE-029", "Elegir cuándo revisar las convenciones de diálogo", "oficio de escritura", "https://davidportodiaz.com/herramientas/dialogo-convenciones/", "228"),
    ("BASE-030", "Comparar capítulos para encontrar diferencias estructurales", "oficio de escritura", "https://davidportodiaz.com/herramientas/manuscrito/", "260"),
]


ORIGIN = {
    "BASE-026": ("Pinterest", "2026-09-28"), "BASE-019": ("Pinterest", "2026-10-03"), "BASE-013": ("Pinterest", "2026-10-04"),
    "BASE-017": ("X", "2026-09-28"), "BASE-011": ("X", "2026-10-01"), "BASE-016": ("X", "2026-10-04"),
    "BASE-018": ("Threads", "2026-09-28"), "BASE-007": ("Threads", "2026-10-01"), "BASE-009": ("Threads", "2026-10-02"),
    "BASE-021": ("Instagram", "2026-09-29"), "BASE-003": ("Instagram", "2026-10-02"), "BASE-008": ("Instagram", "2026-10-03"),
    "BASE-022": ("Facebook", "2026-09-29"), "BASE-001": ("Facebook", "2026-10-01"), "BASE-014": ("Facebook", "2026-10-04"),
    "BASE-023": ("TikTok", "2026-09-30"), "BASE-005": ("TikTok", "2026-10-01"), "BASE-012": ("TikTok", "2026-10-03"),
    "BASE-024": ("Bluesky", "2026-09-28"), "BASE-002": ("Bluesky", "2026-10-03"), "BASE-010": ("Bluesky", "2026-10-04"),
    "BASE-025": ("Mastodon", "2026-09-28"), "BASE-015": ("Mastodon", "2026-10-02"), "BASE-004": ("Mastodon", "2026-10-04"),
    "BASE-028": ("nueva", ""), "BASE-029": ("nueva", ""), "BASE-030": ("nueva", ""),
}


def media_for(post):
    extras = {
        "IGGPT-P006": ["pagina-libro-tres-preguntas.png", "pagina-libro-lista-comprobacion.png"],
        "IGGPT-P007": ["objeto-hechos-recuerdos-hipotesis.png", "objeto-preguntas-historia.png"],
        "IGGPT-P008": ["portal-vs-epica-instagram-02.png", "portal-vs-epica-instagram-03.png"],
        "TTGPT-P006": ["feria-libro-tiktok-02.png", "feria-libro-tiktok-03.png"],
        "TTGPT-P007": ["manecillas-tres-puertas-tiktok-02.png", "manecillas-tres-puertas-tiktok-03.png"],
        "TTGPT-P008": ["relaciones-personajes-tiktok-02.png", "relaciones-personajes-tiktok-03.png"],
    }
    return [post["image"], *extras.get(post["id"], [])] if post.get("image") else []


def copy_main_assets():
    for post in POSTS:
        if post.get("source"):
            destination = ROOT / f"publicaciones {post['net']} GPT" / post["date"] / post["image"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / post["source"], destination)


def make_supporting_assets():
    d = ROOT / "publicaciones Instagram GPT/2026-10-05"
    info_card(d / "pagina-libro-tres-preguntas.png", "Antes del diseño", "Tres preguntas que deben quedar claras", ["¿Qué clase de libro es?", "¿Para quién puede encajar?", "¿Cuál es el siguiente paso?"], "2/3", "Auditor de página de libro")
    info_card(d / "pagina-libro-lista-comprobacion.png", "Una página que ayuda", "Qué conviene comprobar", ["Muestra o fragmento accesible.", "Compra o siguiente paso inequívoco.", "Datos y afirmaciones verificables."], "3/3", "Auditor de página de libro")

    d = ROOT / "publicaciones Instagram GPT/2026-10-08"
    info_card(d / "objeto-hechos-recuerdos-hipotesis.png", "Una historia, varias capas", "No todo tiene el mismo grado de certeza", ["Hechos apoyados por una fuente.", "Recuerdos atribuidos a quien los cuenta.", "Hipótesis que todavía deben comprobarse."], "2/3", "Objeto heredado")
    info_card(d / "objeto-preguntas-historia.png", "Antes de que se pierda", "Preguntas para empezar", ["¿Quién lo tuvo antes?", "¿Qué fecha o lugar puede comprobarse?", "¿Qué versiones cambian según la persona?"], "3/3", "Objeto heredado")

    src = ROOT / "publicaciones TikTok GPT/2026-09-25"
    dst = ROOT / "publicaciones Instagram GPT/2026-10-09"
    for old, new in [("portal-fantasy-vs-fantasia-epica-02.png", "portal-vs-epica-instagram-02.png"), ("portal-fantasy-vs-fantasia-epica-03.png", "portal-vs-epica-instagram-03.png")]:
        shutil.copy2(src / old, dst / new)

    d = ROOT / "publicaciones TikTok GPT/2026-10-06"
    info_card(d / "feria-libro-tiktok-02.png", "Fuera de la foto", "Lo que también forma parte de una feria", ["La espera antes de la primera firma.", "Conversaciones que no estaban previstas.", "Ver a alguien abrir tu libro delante de ti."], "2/3", "Feria del Libro de Madrid")
    info_card(d / "feria-libro-tiktok-03.png", "Un recuerdo concreto", "¿Qué te llevas de una feria?", ["Un libro que no ibas buscando.", "Una charla con un autor o lector.", "Una casualidad que solo ocurre allí."], "3/3", "Feria del Libro de Madrid")

    d = ROOT / "publicaciones TikTok GPT/2026-10-08"
    info_card(d / "manecillas-tres-puertas-tiktok-02.png", "La misma novela", "Tres puertas de entrada", ["Memoria: lo que una familia recuerda a medias.", "Valor: lo que cuesta y significa un objeto.", "Futuro: lo antiguo dentro de un mundo digital."], "2/3", "Las manecillas del recuerdo")
    info_card(d / "manecillas-tres-puertas-tiktok-03.png", "Elige por dónde entrar", "¿Qué te despierta más curiosidad?", ["Una memoria incompleta.", "Un objeto que cambia de manos.", "Un futuro que ya no conserva el tic-tac."], "3/3", "Las manecillas del recuerdo")

    d = ROOT / "publicaciones TikTok GPT/2026-10-11"
    info_card(d / "relaciones-personajes-tiktok-02.png", "Capítulo 2 → capítulo 8", "Una relación también tiene arco", ["Primero se soportan.", "Después se protegen.", "Al final actúan como si siempre hubieran confiado."], "2/3", "Relaciones entre personajes")
    info_card(d / "relaciones-personajes-tiktok-03.png", "El cambio necesita una escena", "Busca el momento que lo sostiene", ["Una decisión compartida.", "Una confianza ganada o rota.", "Una consecuencia que afecta a ambos."], "3/3", "Relaciones entre personajes")

    for date, filename, eyebrow, title, subtitle, marker, body, footer in [
        ("2026-10-05", "comprobar-datos-editorial.png", "Investigación editorial", "Comprueba antes de guardar", "Fuente, fecha, estado y correcciones", "4", "Un método para distinguir datos vigentes de listados que solo se copian unos a otros.", "RECURSOS PARA ESCRITORES"),
        ("2026-10-09", "fantasia-juvenil-espanola-pinterest.png", "Lecturas 2025-2026", "Fantasía juvenil española reciente", "Qué distingue cada libro y para quién puede encajar", "YA", "Una selección comentada para descubrir obras recientes escritas y publicadas en español.", "LECTURAS Y FANTASÍA"),
        ("2026-10-11", "libros-magia-con-coste-pinterest.png", "Selección de fantasía", "6 libros donde la magia tiene un precio", "Recursos, intercambios y consecuencias", "6", "Historias donde usar el poder modifica decisiones y no se queda en decoración del mundo.", "LECTURAS Y FANTASÍA"),
    ]:
        d = ROOT / f"publicaciones Pinterest GPT/{date}"
        d.mkdir(parents=True, exist_ok=True)
        pinterest_card(d / filename, eyebrow, title, subtitle, marker, body, footer)


def append_new_bases():
    path = ROOT / "publicaciones GPT/REGISTRO_MAESTRO_MULTIRRED.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields, rows = reader.fieldnames, list(reader)
    by_base = {row["base_id"]: row for row in rows}
    for base, concept, family, url, bank in NEW_BASES:
        row = by_base.get(base)
        if row is None:
            row = {field: "" for field in fields}
            rows.append(row)
        row.update(base_id=base, concepto=concept, familia=family, fuente_url=url, captura_banco=bank,
                   asset_maestro=f"publicaciones GPT/banco imagenes web/{bank}/captura.png", estado_base="activo",
                   primera_adaptacion=f"{next(p['id'] for p in POSTS if p['base'] == base)}; reserva Reddit",
                   ultima_red="Reddit", ultima_fecha=next(p["date"] for p in POSTS if p["base"] == base),
                   proxima_red_sugerida="X", no_antes_de="tras publicación real + 7 días",
                   regla_reutilizacion="No copiar el debate; adaptar la idea a la cultura y formato de la red de destino",
                   notas="Base nueva creada como conversación autosuficiente para r/escribir; sin enlace propio.")
    by_post_base = {post["base"]: post for post in POSTS}
    for row in rows:
        post = by_post_base.get(row["base_id"])
        if not post:
            continue
        row["ultima_red"] = post["net"]
        row["ultima_fecha"] = post["date"]
        row["proxima_red_sugerida"] = {"X":"Threads", "Threads":"Instagram", "Instagram":"Facebook", "Facebook":"TikTok", "TikTok":"Bluesky", "Bluesky":"Mastodon", "Mastodon":"Pinterest", "Pinterest":"X", "Reddit":"X"}[post["net"]]
        row["no_antes_de"] = "tras publicación real + 7 días"
        marker = f"Rotación preparada: {post['id']} en {post['net']} para {post['date']}."
        clean_notes = row.get("notas", "").replace(marker, "").strip(" ;.")
        row["notas"] = f"{clean_notes}; {marker}" if clean_notes else marker
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, quoting=csv.QUOTE_ALL)
        writer.writeheader(); writer.writerows(rows)


def update_queue():
    path = ROOT / "publicaciones GPT/COLA_ROTACION_BASES.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle); fields, rows = reader.fieldnames, list(reader)
    by_base = {row["base_id"]: row for row in rows}
    for post in POSTS:
        row = by_base.get(post["base"])
        if row is None:
            row = {field: "" for field in fields}; row["base_id"] = post["base"]
            rows.append(row); by_base[post["base"]] = row
        nexts = {"X":["Threads","Instagram","Facebook"], "Threads":["Instagram","Facebook","TikTok"], "Instagram":["Facebook","TikTok","Bluesky"], "Facebook":["TikTok","Bluesky","Mastodon"], "TikTok":["Bluesky","Mastodon","Pinterest"], "Bluesky":["Mastodon","Pinterest","X"], "Mastodon":["Pinterest","X","Threads"], "Pinterest":["X","Threads","Instagram"], "Reddit":["X","Threads","Instagram"]}[post["net"]]
        row.update(adaptacion_actual=post["id"], red_actual=post["net"], fecha_actual=post["date"], siguiente_red_1=nexts[0], siguiente_red_2=nexts[1], siguiente_red_3=nexts[2], regla="adaptar texto, CTA, hashtags/topic, medio y fecha; nunca copiar el post terminado", estado="esperar_publicacion_y_metricas")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, quoting=csv.QUOTE_ALL)
        writer.writeheader(); writer.writerows(rows)


def write_rotation():
    fields = ["red","id","base_id","fecha","hora","estado","tema","objetivo","red_origen","fecha_origen_prevista","tipo_base","url_web","medio"]
    path = ROOT / "publicaciones GPT/ROTACION_MULTIRRED_2026-10-05_10-11.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, quoting=csv.QUOTE_ALL); writer.writeheader()
        for post in POSTS:
            origin_net, origin_date = ORIGIN[post["base"]]
            writer.writerow(dict(red=post["net"], id=post["id"], base_id=post["base"], fecha=post["date"], hora=post["time"], estado=post.get("state","lista"), tema=post["theme"], objetivo=post["objective"], red_origen=origin_net, fecha_origen_prevista=origin_date, tipo_base="nueva" if origin_net == "nueva" else "rotada", url_web=post.get("url",""), medio=post.get("image","ninguno")))


def write_calendar():
    path = ROOT / "publicaciones GPT/CALENDARIO_EJECUCION_2026-10-05_10-11.md"
    active = [post for post in POSTS if post.get("state") != "reserva_regla_semanal"]
    active.append(dict(net="Reddit", id="RDGPT-P003", base="BASE-006", date="2026-10-06", time="18:00"))
    lines = ["# Calendario de ejecución · 5-11 de octubre de 2026", "", "Segunda rotación: 24 salidas nuevas en ocho redes y la salida de Reddit `RDGPT-P003`, ya preparada para el 6 de octubre. Las tres piezas Reddit de esta tanda quedan escalonadas como reservas semanales.", "", "## Calendario", "", "| Fecha | Hora | Red | ID | BASE | Vía |", "|---|---:|---|---|---|---|"]
    for post in sorted(active, key=lambda p: (p["date"], p["time"], p["net"])):
        lines.append(f"| {post['date']} | {post['time']} | {post['net']} | `{post['id']}` | `{post['base']}` | {previous.VIA[post['net']][1]} |")
    lines += ["", "## Reservas Reddit", "", "- 2026-10-13 · `RDGPT-P004` · `BASE-027` · reserva anterior ya terminada."]
    for post in POSTS:
        if post.get("state") == "reserva_regla_semanal":
            lines.append(f"- {post['date']} · `{post['id']}` · `{post['base']}` · {post['title']}")
    lines += ["", "## Preflight", "", "- Confirmar publicación real de la BASE de origen antes de ejecutar cada rotación.", "- Sustituir en Instagram los enlaces de perfil ya vencidos por `Auditor de página`, `Objeto heredado` y `Portal o épica` después de las salidas anteriores.", "- Confirmar tema nativo en Threads y conservarlo en la cola programada.", "- TikTok continúa manual para estos carruseles fotográficos.", "- Reddit exige revisión de reglas, duplicados y flair el mismo día.", "", "Registrar permalink y métricas a 24 horas y 7 días.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    previous.ALT_EXTRA = ALT_EXTRA
    previous.media_for = media_for
    copy_main_assets(); make_supporting_assets()
    for post in POSTS:
        previous.render_doc(post); previous.append_registry(post)
    append_new_bases(); update_queue(); write_rotation(); write_calendar()
    print(f"Construidas {len(POSTS)} adaptaciones: 24 de la semana y 3 reservas Reddit.")


if __name__ == "__main__":
    main()
