
from __future__ import annotations
import csv, shutil, sys
from pathlib import Path
<<<<<<< HEAD
R=Path(r"C:\GIT\RRSS_AutoraDemo")
=======
R=Path(r"C:\GIT\RRSS_DavidPorto")
>>>>>>> origin/research/public-reuse-parent
sys.path.insert(0,str(R/"tools"))
import build_rotacion_2026_09_28 as prev
from build_publicaciones_gpt_assets import pinterest_card
prev.VIA["LinkedIn"]=("si","Programador nativo de LinkedIn")
P=[]
def a(n,i,b,d,h,t,theme,obj,url,src,img,alt,text="",**k):
 P.append(dict(net=n,id=i,base=b,date=d,time=h,title=t,theme=theme,objective=obj,url=url,source=src,image=img,alt=alt,text=text,**k))
<<<<<<< HEAD
a("Instagram","IGGPT-P009","BASE-017","2026-10-12","19:30","El correo que llega cuando alguien pide material","kit de prensa","guardados y visitas","https://autorademodiaz.com/herramientas/kit-prensa-escritores/","publicaciones Threads GPT/2026-10-05/kit-prensa-threads.png","kit-prensa-escritores-instagram.png","Generador local de kit de prensa con biografías, ficha de libro y permisos.","""Un medio te pide «una bio y una foto». Parece rápido hasta que toca decidir qué bio, qué portada y si esa fotografía tiene permiso de publicación.
=======
a("Instagram","IGGPT-P009","BASE-017","2026-10-12","19:30","El correo que llega cuando alguien pide material","kit de prensa","guardados y visitas","https://davidportodiaz.com/herramientas/kit-prensa-escritores/","publicaciones Threads GPT/2026-10-05/kit-prensa-threads.png","kit-prensa-escritores-instagram.png","Generador local de kit de prensa con biografías, ficha de libro y permisos.","""Un medio te pide «una bio y una foto». Parece rápido hasta que toca decidir qué bio, qué portada y si esa fotografía tiene permiso de publicación.
>>>>>>> origin/research/public-reuse-parent

El generador deja cada versión identificada y reúne todo en un ZIP.

¿Qué archivo te ha tocado buscar con el correo ya abierto?

En el perfil: «Kit de prensa».

#Autores #MarketingEditorial #Escritores #PrensaCultural""",profile_label="Kit de prensa",tags="#Autores #MarketingEditorial #Escritores #PrensaCultural")
<<<<<<< HEAD
a("Instagram","IGGPT-P010","BASE-011","2026-10-15","20:00","El libro que ya recomiendas antes de acabarlo","lectura actual","comentarios y uso","https://autorademodiaz.com/herramientas/tarjeta-estoy-leyendo/","publicaciones Threads GPT/2026-10-08/estoy-leyendo-threads.png","estoy-leyendo-instagram.png","Tarjeta abierta para compartir el libro que se está leyendo.","""Hay libros que, en la página 40, ya estás recomendando a alguien.
=======
a("Instagram","IGGPT-P010","BASE-011","2026-10-15","20:00","El libro que ya recomiendas antes de acabarlo","lectura actual","comentarios y uso","https://davidportodiaz.com/herramientas/tarjeta-estoy-leyendo/","publicaciones Threads GPT/2026-10-08/estoy-leyendo-threads.png","estoy-leyendo-instagram.png","Tarjeta abierta para compartir el libro que se está leyendo.","""Hay libros que, en la página 40, ya estás recomendando a alguien.
>>>>>>> origin/research/public-reuse-parent

La tarjeta «Estoy leyendo» es para ese momento: todavía no hay reseña ni nota, solo ganas de contar por qué sigues.

¿Qué lees ahora? Título y una razón, sin hacer examen.

En el perfil: «Estoy leyendo».

#EstoyLeyendo #Lectores #BookstagramEspaña #RecomendacionesDeLibros""",profile_label="Estoy leyendo",tags="#EstoyLeyendo #Lectores #BookstagramEspaña #RecomendacionesDeLibros")
<<<<<<< HEAD
a("Instagram","IGGPT-P011","BASE-016","2026-10-18","18:45","Cruzar es fácil. Volver ya es otra historia","portal fantasy","comentarios y visitas","https://autorademodiaz.com/recomendaciones/portal-fantasy-espanol/","publicaciones Threads GPT/2026-10-11/portal-fantasy-threads.png","portal-fantasy-instagram.png","Selección de portal fantasy juvenil disponible en español.","""Una puerta, un armario, un libro, una grieta. Cruzar puede durar un segundo; la historia empieza cuando aparece el precio.
=======
a("Instagram","IGGPT-P011","BASE-016","2026-10-18","18:45","Cruzar es fácil. Volver ya es otra historia","portal fantasy","comentarios y visitas","https://davidportodiaz.com/recomendaciones/portal-fantasy-espanol/","publicaciones Threads GPT/2026-10-11/portal-fantasy-threads.png","portal-fantasy-instagram.png","Selección de portal fantasy juvenil disponible en español.","""Una puerta, un armario, un libro, una grieta. Cruzar puede durar un segundo; la historia empieza cuando aparece el precio.
>>>>>>> origin/research/public-reuse-parent

En la lista hay diez novelas disponibles en español y diez formas bastante distintas de acabar al otro lado.

¿Cuál de esos portales cruzarías sin tener asegurada la vuelta?

En el perfil: «Portal fantasy».

#PortalFantasy #FantasíaJuvenil #BookstagramEspaña #LibrosDeFantasía""",profile_label="Portal fantasy",tags="#PortalFantasy #FantasíaJuvenil #BookstagramEspaña #LibrosDeFantasía")
<<<<<<< HEAD
a("Facebook","FBGPT-P009","BASE-018","2026-10-12","12:30","Una página de libro debe ayudar a decidir","página de libro","clics y conversación","https://autorademodiaz.com/herramientas/auditor-pagina-libro/","publicaciones Instagram GPT/2026-10-05/auditor-pagina-libro-instagram.png","auditor-pagina-libro-facebook.png","Auditor centrado en la información que necesita un lector.","""Una portada puede llamar la atención y aun así dejar tres dudas: qué clase de historia es, para quién puede encajar y dónde se puede probar.

El auditor recorre justo esas preguntas y señala la información que falta. Después, la decisión sobre el diseño sigue siendo tuya.

https://autorademodiaz.com/herramientas/auditor-pagina-libro/
=======
a("Facebook","FBGPT-P009","BASE-018","2026-10-12","12:30","Una página de libro debe ayudar a decidir","página de libro","clics y conversación","https://davidportodiaz.com/herramientas/auditor-pagina-libro/","publicaciones Instagram GPT/2026-10-05/auditor-pagina-libro-instagram.png","auditor-pagina-libro-facebook.png","Auditor centrado en la información que necesita un lector.","""Una portada puede llamar la atención y aun así dejar tres dudas: qué clase de historia es, para quién puede encajar y dónde se puede probar.

El auditor recorre justo esas preguntas y señala la información que falta. Después, la decisión sobre el diseño sigue siendo tuya.

https://davidportodiaz.com/herramientas/auditor-pagina-libro/
>>>>>>> origin/research/public-reuse-parent

Cuando descubrís un libro, ¿qué dato buscáis primero?

#Autores #MarketingEditorial""",tags="#Autores #MarketingEditorial")
<<<<<<< HEAD
a("Facebook","FBGPT-P010","BASE-007","2026-10-15","19:00","El objeto cuya historia cambia según quién la cuenta","memoria familiar","comentarios y guardados","https://autorademodiaz.com/recursos/ficha-historia-objeto-heredado/","publicaciones Instagram GPT/2026-10-08/objeto-heredado-instagram.png","objeto-heredado-facebook.png","Ficha para separar hechos, recuerdos e hipótesis de un objeto heredado.","""En muchas familias hay un objeto cuya historia cambia según quién empiece a contarla. No hace falta que alguien mienta: cada persona puede conservar una escena diferente.

Esta ficha separa lo comprobado, lo recordado y lo que todavía es una hipótesis.

https://autorademodiaz.com/recursos/ficha-historia-objeto-heredado/
=======
a("Facebook","FBGPT-P010","BASE-007","2026-10-15","19:00","El objeto cuya historia cambia según quién la cuenta","memoria familiar","comentarios y guardados","https://davidportodiaz.com/recursos/ficha-historia-objeto-heredado/","publicaciones Instagram GPT/2026-10-08/objeto-heredado-instagram.png","objeto-heredado-facebook.png","Ficha para separar hechos, recuerdos e hipótesis de un objeto heredado.","""En muchas familias hay un objeto cuya historia cambia según quién empiece a contarla. No hace falta que alguien mienta: cada persona puede conservar una escena diferente.

Esta ficha separa lo comprobado, lo recordado y lo que todavía es una hipótesis.

https://davidportodiaz.com/recursos/ficha-historia-objeto-heredado/
>>>>>>> origin/research/public-reuse-parent

¿Qué objeto de vuestra familia pediría una conversación antes de que se pierda su historia?

#MemoriaFamiliar #HistoriasDeFamilia""",tags="#MemoriaFamiliar #HistoriasDeFamilia")
<<<<<<< HEAD
a("Facebook","FBGPT-P011","BASE-009","2026-10-16","19:15","¿Cruzar al mundo fantástico o haber nacido en él?","portal fantasy frente a fantasía épica","comentarios y lectura","https://autorademodiaz.com/cuaderno/portal-fantasy-vs-fantasia-epica/","publicaciones Instagram GPT/2026-10-09/portal-vs-epica-instagram-01.png","portal-vs-epica-facebook.png","Comparación entre portal fantasy y fantasía épica.","""Dos novelas pueden tener magia, criaturas y mapas, pero no pedirnos la misma entrada.

En el portal fantasy acompañamos a alguien que cruza desde un mundo conocido. En la fantasía épica, el personaje ya pertenece al mundo fantástico.

https://autorademodiaz.com/cuaderno/portal-fantasy-vs-fantasia-epica/
=======
a("Facebook","FBGPT-P011","BASE-009","2026-10-16","19:15","¿Cruzar al mundo fantástico o haber nacido en él?","portal fantasy frente a fantasía épica","comentarios y lectura","https://davidportodiaz.com/cuaderno/portal-fantasy-vs-fantasia-epica/","publicaciones Instagram GPT/2026-10-09/portal-vs-epica-instagram-01.png","portal-vs-epica-facebook.png","Comparación entre portal fantasy y fantasía épica.","""Dos novelas pueden tener magia, criaturas y mapas, pero no pedirnos la misma entrada.

En el portal fantasy acompañamos a alguien que cruza desde un mundo conocido. En la fantasía épica, el personaje ya pertenece al mundo fantástico.

https://davidportodiaz.com/cuaderno/portal-fantasy-vs-fantasia-epica/
>>>>>>> origin/research/public-reuse-parent

¿Qué preferís: cruzar la puerta o despertar ya al otro lado?

#PortalFantasy #FantasíaÉpica""",tags="#PortalFantasy #FantasíaÉpica")
<<<<<<< HEAD
a("Bluesky","BSGPT-P009","BASE-022","2026-10-13","09:30","Lo que queda fuera de una foto de feria","Feria del Libro","conversación y visitas","https://autorademodiaz.com/cuaderno/feria-libro-madrid-2026-samuel-entre-mundos/","publicaciones TikTok GPT/2026-10-06/feria-libro-tiktok-01.png","feria-libro-bluesky.png","Crónica de la firma de Samuel entre mundos en Madrid.","""Una foto de feria enseña la mesa, pero no la espera ni las conversaciones imprevistas.

https://autorademodiaz.com/cuaderno/feria-libro-madrid-2026-samuel-entre-mundos/
=======
a("Bluesky","BSGPT-P009","BASE-022","2026-10-13","09:30","Lo que queda fuera de una foto de feria","Feria del Libro","conversación y visitas","https://davidportodiaz.com/cuaderno/feria-libro-madrid-2026-samuel-entre-mundos/","publicaciones TikTok GPT/2026-10-06/feria-libro-tiktok-01.png","feria-libro-bluesky.png","Crónica de la firma de Samuel entre mundos en Madrid.","""Una foto de feria enseña la mesa, pero no la espera ni las conversaciones imprevistas.

https://davidportodiaz.com/cuaderno/feria-libro-madrid-2026-samuel-entre-mundos/
>>>>>>> origin/research/public-reuse-parent

¿Qué recordáis más de una feria?

#BookSky #FeriaDelLibro""",tags="#BookSky #FeriaDelLibro")
<<<<<<< HEAD
a("Bluesky","BSGPT-P010","BASE-001","2026-10-15","18:00","Tres puertas para entrar en una novela","Las manecillas del recuerdo","conversación y visitas","https://autorademodiaz.com/las-manecillas-del-recuerdo/","publicaciones TikTok GPT/2026-10-08/manecillas-tres-puertas-tiktok-01.png","manecillas-tres-puertas-bluesky.png","La novela presentada desde memoria, valor y futuro.","""Una novela, tres puertas: lo que una familia recuerda a medias, el valor de un objeto y una pieza antigua en un mundo digital.

¿Por cuál entraríais: memoria, valor o futuro?

https://autorademodiaz.com/las-manecillas-del-recuerdo/

#BookSky #NovelaCoral""",tags="#BookSky #NovelaCoral")
a("Bluesky","BSGPT-P011","BASE-014","2026-10-18","11:00","La escena que faltaba entre dos personajes","relaciones entre personajes","respuestas y uso","https://autorademodiaz.com/herramientas/personajes/","publicaciones TikTok GPT/2026-10-11/relaciones-personajes-tiktok-01.png","relaciones-personajes-bluesky.png","Mapa para seguir relaciones entre personajes.","""En el capítulo 2 se soportan y en el 8 se protegen. El cambio puede funcionar; a veces falta la escena que lo vuelve creíble.

https://autorademodiaz.com/herramientas/personajes/

#Escritura #Personajes""",tags="#Escritura #Personajes")

a("TikTok","TTGPT-P009","BASE-021","2026-10-13","19:30","Un premio no debería necesitar letra pequeña","premios documentados","confianza y comentarios","https://autorademodiaz.com/premios.html","publicaciones Instagram GPT/2026-09-29/premios-david-porto-2026.png","premios-documentados-tiktok-01.png","Premios con resultado, entidad, fecha y fuente.","""«Premiado» puede significar demasiadas cosas.
=======
a("Bluesky","BSGPT-P010","BASE-001","2026-10-15","18:00","Tres puertas para entrar en una novela","Las manecillas del recuerdo","conversación y visitas","https://davidportodiaz.com/las-manecillas-del-recuerdo/","publicaciones TikTok GPT/2026-10-08/manecillas-tres-puertas-tiktok-01.png","manecillas-tres-puertas-bluesky.png","La novela presentada desde memoria, valor y futuro.","""Una novela, tres puertas: lo que una familia recuerda a medias, el valor de un objeto y una pieza antigua en un mundo digital.

¿Por cuál entraríais: memoria, valor o futuro?

https://davidportodiaz.com/las-manecillas-del-recuerdo/

#BookSky #NovelaCoral""",tags="#BookSky #NovelaCoral")
a("Bluesky","BSGPT-P011","BASE-014","2026-10-18","11:00","La escena que faltaba entre dos personajes","relaciones entre personajes","respuestas y uso","https://davidportodiaz.com/herramientas/personajes/","publicaciones TikTok GPT/2026-10-11/relaciones-personajes-tiktok-01.png","relaciones-personajes-bluesky.png","Mapa para seguir relaciones entre personajes.","""En el capítulo 2 se soportan y en el 8 se protegen. El cambio puede funcionar; a veces falta la escena que lo vuelve creíble.

https://davidportodiaz.com/herramientas/personajes/

#Escritura #Personajes""",tags="#Escritura #Personajes")

a("TikTok","TTGPT-P009","BASE-021","2026-10-13","19:30","Un premio no debería necesitar letra pequeña","premios documentados","confianza y comentarios","https://davidportodiaz.com/premios.html","publicaciones Instagram GPT/2026-09-29/premios-david-porto-2026.png","premios-documentados-tiktok-01.png","Premios con resultado, entidad, fecha y fuente.","""«Premiado» puede significar demasiadas cosas.
>>>>>>> origin/research/public-reuse-parent

Por eso prefiero guardar el resultado exacto, quién lo concedió, cuándo y dónde puede comprobarse.

En las otras dos imágenes están los datos que guardo. ¿Un premio cambia vuestra decisión de leer un libro?

<<<<<<< HEAD
Más información en autorademodiaz.com.

#PremiosLiterarios #Autores #Libros #BookTokEspaña #Escritores""",tags="#PremiosLiterarios #Autores #Libros #BookTokEspaña #Escritores",extras=[("publicaciones Instagram GPT/2026-09-29/premios-resultado-y-fuente.png","premios-documentados-tiktok-02.png"),("publicaciones Instagram GPT/2026-09-29/premios-que-se-documenta.png","premios-documentados-tiktok-03.png")])
a("TikTok","TTGPT-P010","BASE-003","2026-10-16","20:00","¿Qué te hace decir «un capítulo más»?","tipo de lector","comentarios y visitas","https://autorademodiaz.com/herramientas/que-tipo-de-lector-eres/","publicaciones Instagram GPT/2026-10-02/que-te-hace-seguir-leyendo.png","tipo-lector-tiktok-01.png","Test breve sobre motivos para seguir leyendo.","""A veces es un personaje. A veces, una pregunta. Y otras, no queremos salir de ese mundo.

Sin pensarlo mucho: personaje, misterio o mundo. Elige uno.

El test completo está en autorademodiaz.com.

#Lectores #Libros #BookTokEspaña #TestDeLectura #RecomendacionesDeLibros""",tags="#Lectores #Libros #BookTokEspaña #TestDeLectura #RecomendacionesDeLibros",extras=[("publicaciones Instagram GPT/2026-10-02/lector-personaje-misterio-mundo.png","tipo-lector-tiktok-02.png"),("publicaciones Instagram GPT/2026-10-02/test-para-discutir.png","tipo-lector-tiktok-03.png")])
a("TikTok","TTGPT-P011","BASE-008","2026-10-17","12:00","La sinopsis promete. El capítulo demuestra","capítulo gratuito de Samuel","lectura y descubrimiento","https://autorademodiaz.com/fragmento/","publicaciones Instagram GPT/2026-10-03/samuel-capitulo-antes-sinopsis.png","samuel-capitulo-tiktok-01.png","Primer capítulo gratuito de Samuel entre mundos.","""Una sinopsis puede gustarte. El primer capítulo demuestra si quieres quedarte con esa voz.
=======
Más información en davidportodiaz.com.

#PremiosLiterarios #Autores #Libros #BookTokEspaña #Escritores""",tags="#PremiosLiterarios #Autores #Libros #BookTokEspaña #Escritores",extras=[("publicaciones Instagram GPT/2026-09-29/premios-resultado-y-fuente.png","premios-documentados-tiktok-02.png"),("publicaciones Instagram GPT/2026-09-29/premios-que-se-documenta.png","premios-documentados-tiktok-03.png")])
a("TikTok","TTGPT-P010","BASE-003","2026-10-16","20:00","¿Qué te hace decir «un capítulo más»?","tipo de lector","comentarios y visitas","https://davidportodiaz.com/herramientas/que-tipo-de-lector-eres/","publicaciones Instagram GPT/2026-10-02/que-te-hace-seguir-leyendo.png","tipo-lector-tiktok-01.png","Test breve sobre motivos para seguir leyendo.","""A veces es un personaje. A veces, una pregunta. Y otras, no queremos salir de ese mundo.

Sin pensarlo mucho: personaje, misterio o mundo. Elige uno.

El test completo está en davidportodiaz.com.

#Lectores #Libros #BookTokEspaña #TestDeLectura #RecomendacionesDeLibros""",tags="#Lectores #Libros #BookTokEspaña #TestDeLectura #RecomendacionesDeLibros",extras=[("publicaciones Instagram GPT/2026-10-02/lector-personaje-misterio-mundo.png","tipo-lector-tiktok-02.png"),("publicaciones Instagram GPT/2026-10-02/test-para-discutir.png","tipo-lector-tiktok-03.png")])
a("TikTok","TTGPT-P011","BASE-008","2026-10-17","12:00","La sinopsis promete. El capítulo demuestra","capítulo gratuito de Samuel","lectura y descubrimiento","https://davidportodiaz.com/fragmento/","publicaciones Instagram GPT/2026-10-03/samuel-capitulo-antes-sinopsis.png","samuel-capitulo-tiktok-01.png","Primer capítulo gratuito de Samuel entre mundos.","""Una sinopsis puede gustarte. El primer capítulo demuestra si quieres quedarte con esa voz.
>>>>>>> origin/research/public-reuse-parent

*Samuel entre mundos* empieza con una familia empeñada en parecer normal y un chico que aún no sabe por qué nunca ha encajado.

En la última imagen está la pregunta: ¿qué debe conseguir un primer capítulo para que sigas?

<<<<<<< HEAD
Léelo gratis en autorademodiaz.com.

#SamuelEntreMundos #FantasíaJuvenil #BookTokEspaña #PrimerCapítulo #LecturaEnEspañol""",tags="#SamuelEntreMundos #FantasíaJuvenil #BookTokEspaña #PrimerCapítulo #LecturaEnEspañol",extras=[("publicaciones Instagram GPT/2026-10-03/samuel-familia-normal.png","samuel-capitulo-tiktok-02.png"),("publicaciones Instagram GPT/2026-10-03/samuel-mundo-o-personaje.png","samuel-capitulo-tiktok-03.png")])
a("Mastodon","MAGPT-P009","BASE-023","2026-10-14","08:45","Escuchar la voz antes de comprar","muestra gratuita","lectura y visitas","https://autorademodiaz.com/las-manecillas-del-recuerdo/kindle/","publicaciones Bluesky GPT/2026-10-07/muestra-manecillas-bluesky.png","muestra-manecillas-mastodon.png","Descarga de una muestra en EPUB y TXT.","""Antes de comprar una novela, viene bien escuchar su voz sin depender solo de la sinopsis.

El capítulo 1.1 de *Las manecillas del recuerdo* puede descargarse gratis en EPUB o TXT.

https://autorademodiaz.com/las-manecillas-del-recuerdo/kindle/
=======
Léelo gratis en davidportodiaz.com.

#SamuelEntreMundos #FantasíaJuvenil #BookTokEspaña #PrimerCapítulo #LecturaEnEspañol""",tags="#SamuelEntreMundos #FantasíaJuvenil #BookTokEspaña #PrimerCapítulo #LecturaEnEspañol",extras=[("publicaciones Instagram GPT/2026-10-03/samuel-familia-normal.png","samuel-capitulo-tiktok-02.png"),("publicaciones Instagram GPT/2026-10-03/samuel-mundo-o-personaje.png","samuel-capitulo-tiktok-03.png")])
a("Mastodon","MAGPT-P009","BASE-023","2026-10-14","08:45","Escuchar la voz antes de comprar","muestra gratuita","lectura y visitas","https://davidportodiaz.com/las-manecillas-del-recuerdo/kindle/","publicaciones Bluesky GPT/2026-10-07/muestra-manecillas-bluesky.png","muestra-manecillas-mastodon.png","Descarga de una muestra en EPUB y TXT.","""Antes de comprar una novela, viene bien escuchar su voz sin depender solo de la sinopsis.

El capítulo 1.1 de *Las manecillas del recuerdo* puede descargarse gratis en EPUB o TXT.

https://davidportodiaz.com/las-manecillas-del-recuerdo/kindle/
>>>>>>> origin/research/public-reuse-parent

¿Leéis muestras antes de decidir?

#Libros #Lectura #Bookstodon""",tags="#Libros #Lectura #Bookstodon")
<<<<<<< HEAD
a("Mastodon","MAGPT-P010","BASE-005","2026-10-15","17:45","Tres voces para decidir por dónde entrar","fragmentos de novela","lectura y conversación","https://autorademodiaz.com/las-manecillas-del-recuerdo/fragmentos/","publicaciones Bluesky GPT/2026-10-08/tres-fragmentos-bluesky.png","tres-fragmentos-mastodon.png","Tres fragmentos de la novela con tonos distintos.","""Un desayuno en el que nadie toca el chocolate. Una casa de empeños que infla una historia. Un futuro sin tic-tac.

Tres fragmentos de la misma novela, con voces y épocas distintas.

https://autorademodiaz.com/las-manecillas-del-recuerdo/fragmentos/
=======
a("Mastodon","MAGPT-P010","BASE-005","2026-10-15","17:45","Tres voces para decidir por dónde entrar","fragmentos de novela","lectura y conversación","https://davidportodiaz.com/las-manecillas-del-recuerdo/fragmentos/","publicaciones Bluesky GPT/2026-10-08/tres-fragmentos-bluesky.png","tres-fragmentos-mastodon.png","Tres fragmentos de la novela con tonos distintos.","""Un desayuno en el que nadie toca el chocolate. Una casa de empeños que infla una historia. Un futuro sin tic-tac.

Tres fragmentos de la misma novela, con voces y épocas distintas.

https://davidportodiaz.com/las-manecillas-del-recuerdo/fragmentos/
>>>>>>> origin/research/public-reuse-parent

¿Con cuál empezaríais: 1, 2 o 3?

#NovelaCoral #Lectura #Bookstodon""",tags="#NovelaCoral #Lectura #Bookstodon")
<<<<<<< HEAD
a("Mastodon","MAGPT-P011","BASE-012","2026-10-17","17:30","Cinco minutos no duran lo mismo en voz alta","tiempo de lectura","uso y conversación","https://autorademodiaz.com/herramientas/tiempo-lectura-voz-alta/","publicaciones Bluesky GPT/2026-10-10/tiempo-lectura-bluesky.png","tiempo-lectura-mastodon.png","Estimador local de lectura en voz alta.","""Cinco minutos cambian con los diálogos, las pausas, los nombres difíciles y los nervios.

El estimador da un rango ajustable. Después sigue mandando el ensayo real.

https://autorademodiaz.com/herramientas/tiempo-lectura-voz-alta/
=======
a("Mastodon","MAGPT-P011","BASE-012","2026-10-17","17:30","Cinco minutos no duran lo mismo en voz alta","tiempo de lectura","uso y conversación","https://davidportodiaz.com/herramientas/tiempo-lectura-voz-alta/","publicaciones Bluesky GPT/2026-10-10/tiempo-lectura-bluesky.png","tiempo-lectura-mastodon.png","Estimador local de lectura en voz alta.","""Cinco minutos cambian con los diálogos, las pausas, los nombres difíciles y los nervios.

El estimador da un rango ajustable. Después sigue mandando el ensayo real.

https://davidportodiaz.com/herramientas/tiempo-lectura-voz-alta/
>>>>>>> origin/research/public-reuse-parent

¿Qué os hace frenar más al leer en público?

#Escritura #LecturaEnVozAlta #Autores""",tags="#Escritura #LecturaEnVozAlta #Autores")
<<<<<<< HEAD
a("Pinterest","PINGPT-P009","BASE-024","2026-10-12","10:30","Preguntas para un club de lectura de fantasía juvenil","club de lectura","clics y guardados","https://autorademodiaz.com/clubes-de-lectura/samuel-entre-mundos/","","preguntas-club-lectura-fantasia.png","Pin vertical con preguntas para un club de lectura.","",board="Clubes de lectura",description="Guía para conversar sobre Samuel entre mundos: identidad, pertenencia, decisiones y coste del poder. Incluye preguntas abiertas y recursos sin convertir la sesión en un examen.")
a("Pinterest","PINGPT-P010","BASE-002","2026-10-17","10:30","Cómo detectar repeticiones sin borrar la voz del texto","repeticiones deliberadas","clics y guardados","https://autorademodiaz.com/herramientas/repeticiones/","","detectar-repeticiones-texto.png","Pin vertical sobre detección de repeticiones.","",board="Herramientas para escritores",description="Herramienta gratuita para localizar ecos, palabras próximas y arranques parecidos. Vuelve al párrafo y decide con contexto qué repetición sobra y cuál sostiene la voz.")
a("Pinterest","PINGPT-P011","BASE-010","2026-10-18","10:30","Cómo preparar una sesión de club de lectura","organizar club de lectura","clics y guardados","https://autorademodiaz.com/clubes-de-lectura/preparar-sesion/","","crear-club-lectura-paso-a-paso.png","Pin vertical con pasos para organizar un club.","",board="Clubes de lectura",description="Generador de agendas de 30, 60 o 90 minutos para preparar una sesión de club de lectura. Organiza preguntas abiertas y bloques de conversación sin enviar los datos al servidor.")

a("X","XGPT-P009","BASE-025","2026-10-12","18:45","Un dato editorial también caduca","metodología editorial","clics y confianza","https://autorademodiaz.com/metodologia-editorial/","publicaciones Pinterest GPT/2026-10-05/comprobar-datos-editorial.png","datos-editoriales-x.png","Método para comprobar y fechar datos editoriales.","""Una editorial puede cambiar de catálogo, cerrar envíos o modificar sus condiciones. Un directorio útil necesita fuente y fecha, no solo una lista larga.

https://autorademodiaz.com/metodologia-editorial/

#Editoriales #Autores""",tags="#Editoriales #Autores")
a("X","XGPT-P010","BASE-015","2026-10-16","18:30","La fantasía juvenil española no cabe en una etiqueta","fantasía juvenil española","recomendaciones y conversación","https://autorademodiaz.com/cuaderno/libros-fantasia-juvenil-espanola-2025-2026/","publicaciones Pinterest GPT/2026-10-09/fantasia-juvenil-espanola-pinterest.png","fantasia-juvenil-espanola-x.png","Selección de fantasía juvenil española.","""La fantasía juvenil española no es un único tono: hay portales, ciudades, mitologías, humor y mundos enteros.

Una selección para elegir por el viaje, no por un ranking:
https://autorademodiaz.com/cuaderno/libros-fantasia-juvenil-espanola-2025-2026/

#FantasíaJuvenil #Libros""",tags="#FantasíaJuvenil #Libros")
a("X","XGPT-P011","BASE-004","2026-10-18","11:30","La magia interesa más cuando obliga a elegir","magia con coste","recomendaciones y respuestas","https://autorademodiaz.com/recomendaciones/magia-con-coste/","publicaciones Pinterest GPT/2026-10-11/libros-magia-con-coste-pinterest.png","magia-con-coste-x.png","Libros donde usar magia tiene consecuencias.","""La magia cambia una historia cuando usarla obliga a renunciar a algo. Si el precio nunca llega, acaba pareciendo decoración.

Seis libros donde el coste cambia decisiones:
https://autorademodiaz.com/recomendaciones/magia-con-coste/

#Fantasía #Libros""",tags="#Fantasía #Libros")
a("Threads","THGPT-P009","BASE-026","2026-10-12","20:15","La palabra repetida que quizá sí debe quedarse","variedad léxica","conversación y uso","https://autorademodiaz.com/herramientas/variedad-lexica/","publicaciones X GPT/2026-10-05/variedad-lexica-x.png","variedad-lexica-threads.png","Comparador de variedad léxica.","""Una palabra puede repetirse por descuido. También por ritmo, por voz o porque cambiarla empeora la frase.
=======
a("Pinterest","PINGPT-P009","BASE-024","2026-10-12","10:30","Preguntas para un club de lectura de fantasía juvenil","club de lectura","clics y guardados","https://davidportodiaz.com/clubes-de-lectura/samuel-entre-mundos/","","preguntas-club-lectura-fantasia.png","Pin vertical con preguntas para un club de lectura.","",board="Clubes de lectura",description="Guía para conversar sobre Samuel entre mundos: identidad, pertenencia, decisiones y coste del poder. Incluye preguntas abiertas y recursos sin convertir la sesión en un examen.")
a("Pinterest","PINGPT-P010","BASE-002","2026-10-17","10:30","Cómo detectar repeticiones sin borrar la voz del texto","repeticiones deliberadas","clics y guardados","https://davidportodiaz.com/herramientas/repeticiones/","","detectar-repeticiones-texto.png","Pin vertical sobre detección de repeticiones.","",board="Herramientas para escritores",description="Herramienta gratuita para localizar ecos, palabras próximas y arranques parecidos. Vuelve al párrafo y decide con contexto qué repetición sobra y cuál sostiene la voz.")
a("Pinterest","PINGPT-P011","BASE-010","2026-10-18","10:30","Cómo preparar una sesión de club de lectura","organizar club de lectura","clics y guardados","https://davidportodiaz.com/clubes-de-lectura/preparar-sesion/","","crear-club-lectura-paso-a-paso.png","Pin vertical con pasos para organizar un club.","",board="Clubes de lectura",description="Generador de agendas de 30, 60 o 90 minutos para preparar una sesión de club de lectura. Organiza preguntas abiertas y bloques de conversación sin enviar los datos al servidor.")

a("X","XGPT-P009","BASE-025","2026-10-12","18:45","Un dato editorial también caduca","metodología editorial","clics y confianza","https://davidportodiaz.com/metodologia-editorial/","publicaciones Pinterest GPT/2026-10-05/comprobar-datos-editorial.png","datos-editoriales-x.png","Método para comprobar y fechar datos editoriales.","""Una editorial puede cambiar de catálogo, cerrar envíos o modificar sus condiciones. Un directorio útil necesita fuente y fecha, no solo una lista larga.

https://davidportodiaz.com/metodologia-editorial/

#Editoriales #Autores""",tags="#Editoriales #Autores")
a("X","XGPT-P010","BASE-015","2026-10-16","18:30","La fantasía juvenil española no cabe en una etiqueta","fantasía juvenil española","recomendaciones y conversación","https://davidportodiaz.com/cuaderno/libros-fantasia-juvenil-espanola-2025-2026/","publicaciones Pinterest GPT/2026-10-09/fantasia-juvenil-espanola-pinterest.png","fantasia-juvenil-espanola-x.png","Selección de fantasía juvenil española.","""La fantasía juvenil española no es un único tono: hay portales, ciudades, mitologías, humor y mundos enteros.

Una selección para elegir por el viaje, no por un ranking:
https://davidportodiaz.com/cuaderno/libros-fantasia-juvenil-espanola-2025-2026/

#FantasíaJuvenil #Libros""",tags="#FantasíaJuvenil #Libros")
a("X","XGPT-P011","BASE-004","2026-10-18","11:30","La magia interesa más cuando obliga a elegir","magia con coste","recomendaciones y respuestas","https://davidportodiaz.com/recomendaciones/magia-con-coste/","publicaciones Pinterest GPT/2026-10-11/libros-magia-con-coste-pinterest.png","magia-con-coste-x.png","Libros donde usar magia tiene consecuencias.","""La magia cambia una historia cuando usarla obliga a renunciar a algo. Si el precio nunca llega, acaba pareciendo decoración.

Seis libros donde el coste cambia decisiones:
https://davidportodiaz.com/recomendaciones/magia-con-coste/

#Fantasía #Libros""",tags="#Fantasía #Libros")
a("Threads","THGPT-P009","BASE-026","2026-10-12","20:15","La palabra repetida que quizá sí debe quedarse","variedad léxica","conversación y uso","https://davidportodiaz.com/herramientas/variedad-lexica/","publicaciones X GPT/2026-10-05/variedad-lexica-x.png","variedad-lexica-threads.png","Comparador de variedad léxica.","""Una palabra puede repetirse por descuido. También por ritmo, por voz o porque cambiarla empeora la frase.
>>>>>>> origin/research/public-reuse-parent

El gráfico marca el cambio. La parte difícil —y la interesante— es volver al párrafo y decidir si esa repetición sobra.

¿Qué palabra repetís a propósito porque ya forma parte de la voz?

<<<<<<< HEAD
https://autorademodiaz.com/herramientas/variedad-lexica/""",topic="Writing")
a("Threads","THGPT-P010","BASE-019","2026-10-17","20:00","El personaje que desaparece seis capítulos","distribución de puntos de vista","respuestas y uso","https://autorademodiaz.com/herramientas/distribucion-pov/","publicaciones X GPT/2026-10-10/huecos-punto-vista-x.png","puntos-vista-threads.png","Mapa de puntos de vista de una novela.","""A veces un personaje no pierde importancia: desaparece durante seis capítulos y no lo notas hasta releer.
=======
https://davidportodiaz.com/herramientas/variedad-lexica/""",topic="Writing")
a("Threads","THGPT-P010","BASE-019","2026-10-17","20:00","El personaje que desaparece seis capítulos","distribución de puntos de vista","respuestas y uso","https://davidportodiaz.com/herramientas/distribucion-pov/","publicaciones X GPT/2026-10-10/huecos-punto-vista-x.png","puntos-vista-threads.png","Mapa de puntos de vista de una novela.","""A veces un personaje no pierde importancia: desaparece durante seis capítulos y no lo notas hasta releer.
>>>>>>> origin/research/public-reuse-parent

El mapa de POV encuentra esos huecos. Después decides si son pausa o problema.

¿Cuál ha sido vuestro olvido estructural más difícil de ver?

<<<<<<< HEAD
https://autorademodiaz.com/herramientas/distribucion-pov/""",topic="Writing")
a("Threads","THGPT-P011","BASE-013","2026-10-18","18:45","Cuando Mara y Maia empiezan a ser la misma persona","nombres de personajes","conversación y uso","https://autorademodiaz.com/herramientas/nombres-personajes/","publicaciones X GPT/2026-10-11/nombres-parecidos-x.png","nombres-personajes-threads.png","Comprobador de nombres parecidos.","""Mara y Maia pueden tener vidas distintas y aun así mezclarse en la cabeza del lector.
=======
https://davidportodiaz.com/herramientas/distribucion-pov/""",topic="Writing")
a("Threads","THGPT-P011","BASE-013","2026-10-18","18:45","Cuando Mara y Maia empiezan a ser la misma persona","nombres de personajes","conversación y uso","https://davidportodiaz.com/herramientas/nombres-personajes/","publicaciones X GPT/2026-10-11/nombres-parecidos-x.png","nombres-personajes-threads.png","Comprobador de nombres parecidos.","""Mara y Maia pueden tener vidas distintas y aun así mezclarse en la cabeza del lector.
>>>>>>> origin/research/public-reuse-parent

El comprobador señala parecidos visuales y sonoros. No renombra a nadie.

¿Qué pareja de nombres os ha obligado a cambiar uno?

<<<<<<< HEAD
https://autorademodiaz.com/herramientas/nombres-personajes/""",topic="Writing")
a("LinkedIn","LIGPT-P003","BASE-020","2026-10-13","09:15","Separar la limpieza mecánica de la revisión","limpieza de manuscritos","utilidad y conversación","https://autorademodiaz.com/herramientas/limpiador-manuscritos/","publicaciones GPT/banco imagenes web/255/captura.png","limpiador-manuscritos-linkedin.png","Herramienta local para detectar ruido de formato.","""Si estoy revisando una escena y a la vez corrigiendo espacios dobles, guiones mezclados y saltos raros, termino haciendo dos trabajos a medias.

La primera pasada puede ser puramente mecánica: quitar ese ruido y dejar las decisiones de ritmo, escenas y personajes para después. El limpiador marca los cambios; ninguno debería aceptarse sin mirar.

https://autorademodiaz.com/herramientas/limpiador-manuscritos/
=======
https://davidportodiaz.com/herramientas/nombres-personajes/""",topic="Writing")
a("LinkedIn","LIGPT-P003","BASE-020","2026-10-13","09:15","Separar la limpieza mecánica de la revisión","limpieza de manuscritos","utilidad y conversación","https://davidportodiaz.com/herramientas/limpiador-manuscritos/","publicaciones GPT/banco imagenes web/255/captura.png","limpiador-manuscritos-linkedin.png","Herramienta local para detectar ruido de formato.","""Si estoy revisando una escena y a la vez corrigiendo espacios dobles, guiones mezclados y saltos raros, termino haciendo dos trabajos a medias.

La primera pasada puede ser puramente mecánica: quitar ese ruido y dejar las decisiones de ritmo, escenas y personajes para después. El limpiador marca los cambios; ninguno debería aceptarse sin mirar.

https://davidportodiaz.com/herramientas/limpiador-manuscritos/
>>>>>>> origin/research/public-reuse-parent

¿Qué limpiáis siempre antes de una revisión de fondo?

#Edición #Escritura #Productividad""",tags="#Edición #Escritura #Productividad")
<<<<<<< HEAD
a("LinkedIn","LIGPT-P004","BASE-006","2026-10-15","09:15","Convertir una impresión beta en una decisión útil","lectura beta","conversación profesional","https://autorademodiaz.com/lectores-beta/","publicaciones GPT/banco imagenes web/321/captura.png","lectura-beta-linkedin.png","Recurso para estructurar comentarios beta.","""Apuntarse como lector beta exige algo más que dejar un correo y esperar un manuscrito.

En esta página explico qué implica participar y cómo funcionan la privacidad y la baja. Prefiero que esas condiciones estén claras antes de que llegue ningún texto.

https://autorademodiaz.com/lectores-beta/
=======
a("LinkedIn","LIGPT-P004","BASE-006","2026-10-15","09:15","Convertir una impresión beta en una decisión útil","lectura beta","conversación profesional","https://davidportodiaz.com/lectores-beta/","publicaciones GPT/banco imagenes web/321/captura.png","lectura-beta-linkedin.png","Recurso para estructurar comentarios beta.","""Apuntarse como lector beta exige algo más que dejar un correo y esperar un manuscrito.

En esta página explico qué implica participar y cómo funcionan la privacidad y la baja. Prefiero que esas condiciones estén claras antes de que llegue ningún texto.

https://davidportodiaz.com/lectores-beta/
>>>>>>> origin/research/public-reuse-parent

¿Qué necesitáis saber antes de apuntaros a una lectura beta?

#LecturaBeta #Edición #Escritura""",tags="#LecturaBeta #Edición #Escritura")
<<<<<<< HEAD
a("LinkedIn","LIGPT-P005","BASE-027","2026-10-17","09:45","Una métrica de legibilidad no conoce la intención","legibilidad","utilidad y conversación","https://autorademodiaz.com/herramientas/legibilidad/","publicaciones GPT/banco imagenes web/249/captura.png","legibilidad-linkedin.png","Legibilidad usada como señal, no como nota.","""Un índice de legibilidad puede avisar de que un párrafo se ha vuelto mucho más denso que los anteriores. Hasta ahí llega.

Luego hay que volver al texto: quizá la escena lo necesita, quizá la frase se enredó. Uso la cifra como una señal para releer, no como una nota que haya que subir.

https://autorademodiaz.com/herramientas/legibilidad/
=======
a("LinkedIn","LIGPT-P005","BASE-027","2026-10-17","09:45","Una métrica de legibilidad no conoce la intención","legibilidad","utilidad y conversación","https://davidportodiaz.com/herramientas/legibilidad/","publicaciones GPT/banco imagenes web/249/captura.png","legibilidad-linkedin.png","Legibilidad usada como señal, no como nota.","""Un índice de legibilidad puede avisar de que un párrafo se ha vuelto mucho más denso que los anteriores. Hasta ahí llega.

Luego hay que volver al texto: quizá la escena lo necesita, quizá la frase se enredó. Uso la cifra como una señal para releer, no como una nota que haya que subir.

https://davidportodiaz.com/herramientas/legibilidad/
>>>>>>> origin/research/public-reuse-parent

¿Usáis alguna métrica como aviso, sin convertirla en objetivo?

#Edición #Legibilidad #Escritura""",tags="#Edición #Legibilidad #Escritura")

O={"BASE-017":("Threads","2026-10-05"),"BASE-011":("Threads","2026-10-08"),"BASE-016":("Threads","2026-10-11"),"BASE-018":("Instagram","2026-10-05"),"BASE-007":("Instagram","2026-10-08"),"BASE-009":("Instagram","2026-10-09"),"BASE-021":("Facebook","2026-10-06"),"BASE-003":("Facebook","2026-10-09"),"BASE-008":("Facebook","2026-10-10"),"BASE-022":("TikTok","2026-10-06"),"BASE-001":("TikTok","2026-10-08"),"BASE-014":("TikTok","2026-10-11"),"BASE-023":("Bluesky","2026-10-07"),"BASE-005":("Bluesky","2026-10-08"),"BASE-012":("Bluesky","2026-10-10"),"BASE-024":("Mastodon","2026-10-05"),"BASE-002":("Mastodon","2026-10-10"),"BASE-010":("Mastodon","2026-10-11"),"BASE-025":("Pinterest","2026-10-05"),"BASE-015":("Pinterest","2026-10-09"),"BASE-004":("Pinterest","2026-10-11"),"BASE-026":("X","2026-10-05"),"BASE-019":("X","2026-10-10"),"BASE-013":("X","2026-10-11"),"BASE-020":("Reddit","2026-09-29"),"BASE-006":("Instagram","2026-09-26"),"BASE-027":("Reddit cancelada","")}
def media(x):return [x["image"]]+[n for s,n in x.get("extras",[])] if x.get("image") else []
def render_li(x):
 d=R/"publicaciones LinkedIn GPT"/x["date"];d.mkdir(parents=True,exist_ok=True)
 (d/"publicacion.md").write_text(f"""# {x['id']} - {x['title']}

**Estado:** lista.

- **BASE:** `{x['base']}`.
- **Fecha y hora:** {x['date']}, {x['time']} (Europe/Madrid).
- **Programación:** sí; programador nativo de LinkedIn.
- **Objetivo:** {x['objective']}.

## Texto final

{x['text']}

## Medios y ALT

1. `{x['image']}`: {x['alt']}

## Ejecución y respuesta

Programar en LinkedIn, añadir ALT y revisar la vista previa. Responder con ejemplos o preguntas de seguimiento, sin llevar cada comentario al enlace.
""",encoding="utf-8")
def reg(x):
 path=R/f"publicaciones {x['net']} GPT"/"REGISTRO_CONTENIDO_USADO.csv"
 with path.open(encoding="utf-8-sig",newline="") as f:r=csv.DictReader(f);fs=r.fieldnames;rows=list(r)
 row=next((z for z in rows if z.get("id")==x["id"]),None)
 if row is None:row={k:"" for k in fs};rows.append(row)
 vals={"id":x["id"],"base_id":x["base"],"fecha_propuesta":x["date"],"hora_propuesta":x["time"],"estado":"lista","formato":"texto + imagen","tema":x["theme"],"familia":x["theme"],"angulo":x["title"],"objetivo":x["objective"],"hashtags":x.get("tags",""),"url_web":x["url"],"imagen":f"{x['date']}/{x['image']}","programacion":prev.VIA[x["net"]][0],"via_programacion":prev.VIA[x["net"]][1],"topic_nativo":x.get("topic",""),"comunidad":x.get("topic",""),"tablero":x.get("board",""),"titulo_pin":x["title"],"apertura":x.get("text","").splitlines()[0] if x.get("text") else ""}
 for k,v in vals.items():
  if k in row:row[k]=v
 with path.open("w",encoding="utf-8",newline="") as f:w=csv.DictWriter(f,fieldnames=fs,quoting=csv.QUOTE_ALL);w.writeheader();w.writerows(rows)
def assets():
 miss=[]
 for x in P:
  for src in [x.get("source"),*[s for s,n in x.get("extras",[])]]:
   if src and not (R/src).exists():miss.append(src)
 if miss:raise FileNotFoundError("\n".join(miss))
 for x in P:
  d=R/f"publicaciones {x['net']} GPT"/x["date"];d.mkdir(parents=True,exist_ok=True)
  if x.get("source"):shutil.copy2(R/x["source"],d/x["image"])
  for src,name in x.get("extras",[]):shutil.copy2(R/src,d/name)
 cards=[("2026-10-12","preguntas-club-lectura-fantasia.png","Club de lectura","Preguntas para conversar","Identidad, pertenencia y coste del poder","?","Preguntas abiertas sin convertir la sesión en un examen.","SAMUEL ENTRE MUNDOS"),("2026-10-17","detectar-repeticiones-texto.png","Revisión de estilo","Detecta repeticiones con contexto","Ecos, palabras próximas y arranques","ABC","Decide qué sobra y qué sostiene la voz.","HERRAMIENTAS PARA ESCRITORES"),("2026-10-18","crear-club-lectura-paso-a-paso.png","Guía práctica","Prepara una sesión de club","Grupo, frecuencia, libros y conversación","5","Pasos para encuentros presenciales u online.","CLUBES DE LECTURA")]
 for day,name,e,t,s,m,b,foot in cards:
  d=R/"publicaciones Pinterest GPT"/day;pinterest_card(d/name,e,t,s,m,b,foot)
def rotation():
 fs=["red","id","base_id","fecha","hora","estado","tema","objetivo","red_origen","fecha_origen_prevista","tipo_base","url_web","medio"]
 with (R/"publicaciones GPT/ROTACION_MULTIRRED_2026-10-12_10-18.csv").open("w",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=fs,quoting=csv.QUOTE_ALL);w.writeheader()
  for x in P:
   on,od=O[x["base"]];w.writerow(dict(red=x["net"],id=x["id"],base_id=x["base"],fecha=x["date"],hora=x["time"],estado="lista",tema=x["theme"],objetivo=x["objective"],red_origen=on,fecha_origen_prevista=od,tipo_base="rotada" if od else "rescatada",url_web=x["url"],medio=x["image"]))
 lines=["# Calendario de ejecución · 12-18 de octubre de 2026","","27 salidas: tres por cada una de las nueve redes. Reddit queda como conversación separada.","","## Calendario","","| Fecha | Hora | Red | ID | BASE | Vía |","|---|---:|---|---|---|---|"]
 for x in sorted(P,key=lambda z:(z["date"],z["time"],z["net"])):lines.append(f"| {x['date']} | {x['time']} | {x['net']} | `{x['id']}` | `{x['base']}` | {prev.VIA[x['net']][1]} |")
 lines+=["","## Reddit","","- 2026-10-13 · 18:00 · `RDQ-P002` · pregunta breve; revisión manual de reglas, flair y duplicados.","","## Preflight","","- Confirmar publicación real de la BASE de origen.","- Instagram: actualizar el enlace de perfil indicado.","- Threads: comprobar el tema nativo al programar.","- LinkedIn: revisar imagen, ALT y vista previa.","- Reddit: participar primero en hilos ajenos y no incluir enlaces.","","Registrar permalink y métricas a 24 horas y 7 días.",""]
 (R/"publicaciones GPT/CALENDARIO_EJECUCION_2026-10-12_10-18.md").write_text("\n".join(lines),encoding="utf-8")
def queue():
 path=R/"publicaciones GPT/COLA_ROTACION_BASES.csv"
 with path.open(encoding="utf-8-sig",newline="") as f:r=csv.DictReader(f);fs=r.fieldnames;rows=list(r)
 by={x["base_id"]:x for x in rows};nx={"Instagram":["Facebook","TikTok","Bluesky"],"Facebook":["TikTok","Bluesky","Mastodon"],"TikTok":["Bluesky","Mastodon","Pinterest"],"Bluesky":["Mastodon","Pinterest","X"],"Mastodon":["Pinterest","X","Threads"],"Pinterest":["X","Threads","Instagram"],"X":["Threads","Instagram","Facebook"],"Threads":["Instagram","Facebook","TikTok"],"LinkedIn":["X","Threads","Facebook"]}
 for x in P:
  n=nx[x["net"]];by[x["base"]].update(adaptacion_actual=x["id"],red_actual=x["net"],fecha_actual=x["date"],siguiente_red_1=n[0],siguiente_red_2=n[1],siguiente_red_3=n[2],estado="esperar_publicacion_y_metricas")
 for b in ("BASE-028","BASE-029","BASE-030"):
  if b in by:by[b]["estado"]="libre_reddit_cancelada"
 with path.open("w",encoding="utf-8",newline="") as f:w=csv.DictWriter(f,fieldnames=fs,quoting=csv.QUOTE_ALL);w.writeheader();w.writerows(rows)
Q=[("RDQ-P001","RQ-001","2026-10-06","¿Dónde leéis más: Kindle, Kobo, móvil o papel?","Yo voy cambiando y nunca termino de quedarme con uno. ¿Cuál usáis más vosotros?","lista_manual"),("RDQ-P002","RQ-002","2026-10-13","¿Subrayáis los libros o no podéis hacerlo?","En digital subrayo sin pensarlo, pero en papel todavía me cuesta. ¿Los marcáis o los dejáis intactos?","lista_manual"),("RDQ-P003","RQ-003","2026-10-20","¿Creéis que la gente joven lee más o menos que antes?","No sé si se lee menos o si ahora se lee de otra forma. ¿Cómo lo veis?","reserva"),("RDQ-P004","RQ-004","2026-10-27","¿Abandonáis un libro o lo termináis aunque no os guste?","A mí todavía me cuesta dejar uno a medias, aunque cada vez tengo menos paciencia. ¿Qué hacéis vosotros?","reserva"),("RDQ-P005","RQ-005","2026-11-03","¿Qué libro os gustaría poder leer otra vez sin recordar nada?","El típico libro que os gustaría descubrir de nuevo desde cero.","reserva")]
def reddit():
 folder=R/"publicaciones Reddit GPT";path=folder/"REGISTRO_CONTENIDO_USADO.csv"
 with path.open(encoding="utf-8-sig",newline="") as f:r=csv.DictReader(f);fs=r.fieldnames;rows=list(r)
 for z in rows:
  if z.get("id") in {"RDGPT-P003","RDGPT-P004","RDGPT-P005","RDGPT-P006","RDGPT-P007"}:
   z["estado"]="descartada_cambio_enfoque"
   if "aprendizaje" in z:z["aprendizaje"]="Sustituida antes de publicar por preguntas breves sin promoción."
 bank=[]
 for pid,qid,day,title,body,state in Q:
  z=next((x for x in rows if x.get("id")==pid),None)
  if z is None:z={k:"" for k in fs};rows.append(z)
  vals={"id":pid,"base_id":qid,"fecha_propuesta":day,"hora_propuesta":"18:00","estado":state,"subreddit":"r/libros","flair":"comprobar el día de publicación","titulo":title,"tema":"hábitos lectores","objetivo":"conversación","enlace_propio":"no","imagen":"ninguna","programacion":"manual","via_programacion":"Reddit web"}
  for k,v in vals.items():
   if k in z:z[k]=v
  d=folder/day;d.mkdir(parents=True,exist_ok=True)
  (d/"publicacion.md").write_text(f"""# {pid} - {title}

**Estado:** {state}.

- **Pregunta:** `{qid}`.
- **Fecha:** {day}, 18:00.
- **Subreddit candidato:** `r/libros`.
- **Flair:** comprobar ese día.
- **Enlace e imagen:** ninguno.

## Título

{title}

## Texto

{body}

## Ejecución

Participar primero en conversaciones ajenas. Releer reglas, buscar una pregunta equivalente y confirmar el flair. No mencionar la web ni libros propios. Responder de forma breve y específica.
""",encoding="utf-8")
  bank.append([qid,day,"r/libros",title,body,state,"obligatoria ese día","sin enlace, imagen ni hashtags"])
 with path.open("w",encoding="utf-8",newline="") as f:w=csv.DictWriter(f,fieldnames=fs,quoting=csv.QUOTE_ALL);w.writeheader();w.writerows(rows)
 bank.append(["RQ-006","","r/libros","Si solo pudierais recomendar tres poetas, ¿cuáles serían?","Quiero leer más poesía. Solo tres nombres.","aplazada","hilos recientes en octubre de 2026","esperar y buscar de nuevo"])
 bfs=["pregunta_id","fecha_propuesta","subreddit","titulo","texto","estado","comprobacion_duplicado","notas"]
 with (folder/"BANCO_PREGUNTAS_SENCILLAS.csv").open("w",encoding="utf-8",newline="") as f:w=csv.writer(f,quoting=csv.QUOTE_ALL);w.writerow(bfs);w.writerows(bank)
 (folder/"00_ENFOQUE_PREGUNTAS_SENCILLAS.md").write_text("""# Enfoque Reddit: preguntas sencillas

Reddit queda fuera de la rotación promocional. El objetivo es participar y conversar.

- Una pregunta clara y una o dos frases de contexto.
- Sin enlaces propios, imágenes, hashtags ni llamadas al perfil.
- Buscar duplicados recientes; comentar en el hilo existente o aplazar.
- Participar primero en hilos ajenos.
- Máximo una publicación propia por semana.
- Responder a lo que diga cada persona, sin respuestas gemelas.
- Elegir el flair real el día de publicación.

La pregunta de tres poetas queda aplazada porque ya hay hilos recientes de recomendaciones de poesía.
""",encoding="utf-8")
 cal=R/"publicaciones GPT/CALENDARIO_EJECUCION_2026-10-05_10-11.md"
 if cal.exists():cal.write_text(cal.read_text(encoding="utf-8").replace("`RDGPT-P003`","`RDQ-P001`").replace("`BASE-006`","`RQ-001`"),encoding="utf-8")
def main():
 assets();prev.media_for=media;prev.ALT_EXTRA={"TTGPT-P009":["Lámina con los resultados exactos de los reconocimientos.","Lámina con entidad, fecha y fuente de cada reconocimiento."],"TTGPT-P010":["Tres motivos para seguir leyendo: personaje, misterio o mundo.","Pregunta para elegir qué motivo pesó más en la última lectura."],"TTGPT-P011":["La familia de Samuel se esfuerza por parecer normal.","Pregunta sobre lo que debe conseguir un primer capítulo."]}
 for x in P:
  if x["net"]=="LinkedIn":render_li(x)
  else:prev.render_doc(x)
  reg(x)
 rotation();queue();reddit()
 readme=R/"publicaciones LinkedIn GPT/README.md";s=readme.read_text(encoding="utf-8") if readme.exists() else "# Publicaciones LinkedIn GPT\n"
 if "## Reactivación octubre de 2026" not in s:readme.write_text(s.rstrip()+"\n\n## Reactivación octubre de 2026\n\nLinkedIn vuelve a la rotación con tres publicaciones semanales de proceso, edición y utilidad profesional. Se usa su programador nativo.\n",encoding="utf-8")
 print(f"Creadas {len(P)} publicaciones y {len(Q)} preguntas Reddit.")
if __name__=="__main__":main()
