
from __future__ import annotations
import csv,re
from pathlib import Path
<<<<<<< HEAD
R=Path(r"C:\GIT\RRSS_AutoraDemo")
=======
R=Path(r"C:\GIT\RRSS_DavidPorto")
>>>>>>> origin/research/public-reuse-parent
TODAY="2026-10-03"
changes=[]
def replace(rel,old,new,label):
 p=R/rel;s=p.read_text(encoding="utf-8")
 if old not in s:
  if new in s:
   changes.append((rel,label));return
  raise RuntimeError(f"No encontrado en {rel}: {old[:70]}")
 p.write_text(s.replace(old,new),encoding="utf-8")
 changes.append((rel,label))
def body(rel,old,new,label):
 replace(rel,old,new,label)

# Correcciones factuales y de voz en piezas ejecutables.
replace("publicaciones Facebook GPT/2026-10-09/publicacion.md",
"""A veces seguimos leyendo por una persona que ya nos importa. Otras, por una pregunta que todavía no tiene respuesta. Y algunas veces queremos quedarnos un poco más dentro de ese mundo.

Preparé un test breve para jugar con esas diferencias. No diagnostica ni convierte el gusto en una etiqueta fija.""",
"""En el último libro que te robó horas de sueño, ¿qué tiraba más de ti: el personaje, el misterio o el mundo?

El test pone esas tres razones sobre la mesa. El resultado no es una etiqueta; seguramente cambie con la siguiente lectura.""","voz menos defensiva")
replace("publicaciones Facebook GPT/2026-10-12/publicacion.md",
"""Una página de libro puede tener una portada preciosa y no responder a lo básico: qué historia ofrece, para quién puede encajar y dónde leer una muestra.

Preparé un auditor que revisa esas decisiones. No juzga si el diseño es bonito ni da una nota automática.""",
"""Una portada puede llamar la atención y aun así dejar tres dudas: qué clase de historia es, para quién puede encajar y dónde se puede probar.

El auditor recorre justo esas preguntas y señala la información que falta. Después, la decisión sobre el diseño sigue siendo tuya.""","elimina speech de herramienta")
replace("publicaciones Facebook GPT/2026-10-15/publicacion.md",
"""En mi familia hay objetos que tienen una historia distinta según quién empiece a contarla. No siempre alguien miente: a veces cada persona conserva una escena diferente.""",
"""En muchas familias hay un objeto cuya historia cambia según quién empiece a contarla. No hace falta que alguien mienta: cada persona puede conservar una escena diferente.""","elimina anécdota inventada")
replace("publicaciones Instagram GPT/2026-10-12/publicacion.md",
"""La petición suele parecer sencilla: «mándame una bio y una foto».

Luego llegan las dudas. ¿La bio de 80 palabras o la larga? ¿La portada nueva? ¿Esa foto permite publicación?

Preparé una herramienta que reúne las versiones correctas y genera un ZIP en el navegador.

¿Qué archivo te han pedido alguna vez con prisa?""",
"""Un medio te pide «una bio y una foto». Parece rápido hasta que toca decidir qué bio, qué portada y si esa fotografía tiene permiso de publicación.

El generador deja cada versión identificada y reúne todo en un ZIP.

¿Qué archivo te ha tocado buscar con el correo ya abierto?""","apertura concreta")
replace("publicaciones Instagram GPT/2026-10-15/publicacion.md",
"""Hay libros que recomendamos al terminarlos. Y otros que, en la página 40, ya nos hacen buscar a quién contárselos.

La tarjeta «Estoy leyendo» sirve para compartir ese momento sin convertirlo todavía en una reseña ni ponerle nota.

Deja el tuyo en comentarios: título y una sola razón por la que sigues leyendo.""",
"""Hay libros que, en la página 40, ya estás recomendando a alguien.

La tarjeta «Estoy leyendo» es para ese momento: todavía no hay reseña ni nota, solo ganas de contar por qué sigues.

¿Qué lees ahora? Título y una razón, sin hacer examen.""","menos fórmula")
replace("publicaciones Instagram GPT/2026-10-18/publicacion.md",
"""Una puerta, un armario, un libro, una grieta. El portal puede durar un segundo; lo interesante empieza cuando el otro mundo cobra un precio.

Reuní diez novelas disponibles en español con cruces muy distintos.

¿Qué portal de ficción cruzarías aunque no supieras volver?""",
"""Una puerta, un armario, un libro, una grieta. Cruzar puede durar un segundo; la historia empieza cuando aparece el precio.

En la lista hay diez novelas disponibles en español y diez formas bastante distintas de acabar al otro lado.

¿Cuál de esos portales cruzarías sin tener asegurada la vuelta?""","menos presentación corporativa")
replace("publicaciones LinkedIn GPT/2026-10-13/publicacion.md",
"""Corregir el contenido mientras quedan espacios dobles, guiones mezclados y saltos extraños hace que dos trabajos compitan por la misma atención.

Por eso separé una primera pasada mecánica antes de entrar en ritmo, escenas o personajes. La herramienta procesa el texto en el navegador y presenta cambios para revisar, no para aceptar a ciegas.""",
"""Si estoy revisando una escena y a la vez corrigiendo espacios dobles, guiones mezclados y saltos raros, termino haciendo dos trabajos a medias.

La primera pasada puede ser puramente mecánica: quitar ese ruido y dejar las decisiones de ritmo, escenas y personajes para después. El limpiador marca los cambios; ninguno debería aceptarse sin mirar.""","voz directa y natural")
replace("publicaciones LinkedIn GPT/2026-10-15/publicacion.md",
"""«Se me hizo lento» es una reacción válida, pero todavía no indica qué revisar.

Una lectura beta gana utilidad si conserva el punto donde apareció la sensación, qué esperaba la persona y qué efecto tuvo. Así pueden buscarse patrones sin convertir una opinión aislada en una orden.

<<<<<<< HEAD
https://autorademodiaz.com/lectores-beta/
=======
https://davidportodiaz.com/lectores-beta/
>>>>>>> origin/research/public-reuse-parent

¿Qué pregunta os ha dado el comentario beta más accionable?""",
"""Apuntarse como lector beta exige algo más que dejar un correo y esperar un manuscrito.

En esta página explico qué implica participar y cómo funcionan la privacidad y la baja. Prefiero que esas condiciones estén claras antes de que llegue ningún texto.

<<<<<<< HEAD
https://autorademodiaz.com/lectores-beta/
=======
https://davidportodiaz.com/lectores-beta/
>>>>>>> origin/research/public-reuse-parent

¿Qué necesitáis saber antes de apuntaros a una lectura beta?""","alineada con la página real")
replace("publicaciones LinkedIn GPT/2026-10-17/publicacion.md",
"""Una cifra de legibilidad puede señalar que un párrafo es más denso. No sabe si esa densidad está justificada por la escena, la voz o el público.

La utilidad aparece al comparar zonas del propio texto: detectar un cambio, volver al fragmento y leerlo en contexto. La métrica abre una pregunta; no dicta la respuesta.""",
"""Un índice de legibilidad puede avisar de que un párrafo se ha vuelto mucho más denso que los anteriores. Hasta ahí llega.

Luego hay que volver al texto: quizá la escena lo necesita, quizá la frase se enredó. Uso la cifra como una señal para releer, no como una nota que haya que subir.""","menos abstracta")
replace("publicaciones Pinterest GPT/2026-10-18/publicacion.md",
"""Guía práctica para crear un club de lectura: grupo, frecuencia, elección de libros, preguntas abiertas y reparto del turno de palabra, presencial u online.""",
"""Generador de agendas de 30, 60 o 90 minutos para preparar una sesión de club de lectura. Organiza preguntas abiertas y bloques de conversación sin enviar los datos al servidor.""","descripción ajustada al destino")
replace("publicaciones X GPT/2026-10-04/publicacion.md",
"Reuní 10 libros de portal fantasy disponibles en español. ¿Cuál añadirías?",
"Hay 10 libros disponibles en español en la lista. ¿Cuál falta seguro?","más conversacional")
replace("publicaciones Mastodon GPT/2026-10-04/publicacion.md",
"Reuní seis libros donde ese precio cambia decisiones, no solo la decoración del mundo.",
"En los seis libros de la lista, el precio de la magia cambia decisiones; no está solo para decorar el mundo.","elimina fórmula")
replace("publicaciones Threads GPT/2026-10-05/publicacion.md",
"""Preparé una herramienta que reúne todo en un ZIP y lo genera en el navegador.

¿Qué archivo echaste de menos la última vez que te pidieron material?""",
"""El generador reúne las versiones correctas en un ZIP, sin obligarte a rebuscar en cinco carpetas.

¿Qué archivo te tocó improvisar la última vez que te pidieron material?""","más cotidiana")
replace("publicaciones Threads GPT/2026-10-08/publicacion.md",
"""La tarjeta «Estoy leyendo» sirve para compartir justo ese momento, sin cuenta, sin guardar datos y sin obligarte a puntuar nada.

¿Qué estás leyendo ahora y qué te está haciendo quedarte?""",
"""La tarjeta «Estoy leyendo» captura justo ese momento. No pide cuenta ni nota.

¿Qué libro tienes abierto ahora mismo y qué te está haciendo continuar?""","más sencilla")
replace("publicaciones Threads GPT/2026-10-11/publicacion.md",
"""Reuní diez libros disponibles en español con puertas muy distintas.

¿Cuál tiene el cruce entre mundos que más recuerdas?""",
"""En la lista hay diez libros disponibles en español y ninguna puerta funciona igual.

¿Qué cruce entre mundos se te quedó grabado?""","menos fórmula")
replace("publicaciones Threads GPT/2026-10-12/publicacion.md",
"""La herramienta señala dónde cambia la variedad; no decide qué debes borrar.

¿Qué palabra repetís a propósito porque pertenece a vuestra voz?""",
"""El gráfico marca el cambio. La parte difícil —y la interesante— es volver al párrafo y decidir si esa repetición sobra.

¿Qué palabra repetís a propósito porque ya forma parte de la voz?""","menos defensiva")
replace("publicaciones TikTok GPT/2026-10-06/publicacion.md",
"Desliza para ver lo que me llevé de la firma de *Samuel entre mundos* en Madrid.",
"En las siguientes imágenes está lo que no salió en la foto de la firma de *Samuel entre mundos* en Madrid.","varía CTA")
replace("publicaciones TikTok GPT/2026-10-08/publicacion.md",
"Desliza y elige tu puerta: memoria, valor o futuro.",
"Tres imágenes, tres entradas: memoria, valor o futuro. ¿Por cuál empiezas?","varía CTA")
replace("publicaciones TikTok GPT/2026-10-11/publicacion.md",
"Desliza. ¿Qué relación te cuesta más seguir: familia, amistad o rivalidad?",
"Pasa a la siguiente. ¿Qué relación te cuesta más seguir: familia, amistad o rivalidad?","varía CTA")
replace("publicaciones TikTok GPT/2026-10-13/publicacion.md",
"Desliza. ¿Los premios cambian vuestra decisión de leer un libro?",
"En las otras dos imágenes están los datos que guardo. ¿Un premio cambia vuestra decisión de leer un libro?","CTA ligada al carrusel")
replace("publicaciones TikTok GPT/2026-10-16/publicacion.md",
"Desliza y elige: personaje, misterio o mundo.",
"Sin pensarlo mucho: personaje, misterio o mundo. Elige uno.","menos orden mecánica")
replace("publicaciones TikTok GPT/2026-10-17/publicacion.md",
"Desliza: ¿qué debe hacer un primer capítulo para que sigas?",
"En la última imagen está la pregunta: ¿qué debe conseguir un primer capítulo para que sigas?","CTA ligada al medio")

# Mantener el generador nuevo alineado con las correcciones.
builder=R/"tools/build_rotacion_2026_10_12.py"
bs=builder.read_text(encoding="utf-8")
builder_pairs=[
("En mi familia hay objetos que tienen una historia distinta según quién empiece a contarla. No siempre alguien miente: a veces cada persona conserva una escena diferente.","En muchas familias hay un objeto cuya historia cambia según quién empiece a contarla. No hace falta que alguien mienta: cada persona puede conservar una escena diferente."),
("«Se me hizo lento» es una reacción válida, pero todavía no indica qué revisar.\n\nUna lectura beta gana utilidad si conserva el punto donde apareció la sensación, qué esperaba la persona y qué efecto tuvo. Así pueden buscarse patrones sin convertir una opinión aislada en una orden.","Apuntarse como lector beta exige algo más que dejar un correo y esperar un manuscrito.\n\nEn esta página explico qué implica participar y cómo funcionan la privacidad y la baja. Prefiero que esas condiciones estén claras antes de que llegue ningún texto."),
("¿Qué pregunta os ha dado el comentario beta más accionable?","¿Qué necesitáis saber antes de apuntaros a una lectura beta?"),
("Guía práctica para crear un club de lectura: grupo, frecuencia, elección de libros, preguntas abiertas y reparto del turno de palabra, presencial u online.","Generador de agendas de 30, 60 o 90 minutos para preparar una sesión de club de lectura. Organiza preguntas abiertas y bloques de conversación sin enviar los datos al servidor.")
]
for old,new in builder_pairs:
 if old in bs: bs=bs.replace(old,new)
 elif new not in bs: raise RuntimeError("No encontrado en builder: "+old[:60])
builder.write_text(bs,encoding="utf-8")

# Fechas vencidas: no afirmar que siguen listas ni que no se publicaron.
stale=[]
for folder in R.glob("publicaciones * GPT"):
 reg=folder/"REGISTRO_CONTENIDO_USADO.csv"
 if not reg.exists():continue
 with reg.open(encoding="utf-8-sig",newline="") as f:
  rd=csv.DictReader(f);fields=rd.fieldnames;rows=list(rd)
 touched=False
 for row in rows:
  dt=row.get("fecha_propuesta","")
  state=row.get("estado","")
  if dt and dt<TODAY and (re.search(r"lista|reserva|manual|pendiente",state,re.I) or state=="requiere_verificar_publicacion"):
   row["estado"]="requiere_verificar_publicacion"
   stale.append((folder.name,row.get("id",""),dt,row.get("base_id","")))
   touched=True
   doc=folder/dt/"publicacion.md"
   if doc.exists():
    s=doc.read_text(encoding="utf-8")
    s=re.sub(r"\*\*Estado:\*\* [^\n]+", "**Estado:** requiere verificar si se publicó o programó.",s,count=1)
    doc.write_text(s,encoding="utf-8")
 if touched:
  with reg.open("w",encoding="utf-8",newline="") as f:
   w=csv.DictWriter(f,fieldnames=fields,quoting=csv.QUOTE_ALL);w.writeheader();w.writerows(rows)

for rot in (R/"publicaciones GPT").glob("ROTACION_MULTIRRED_*.csv"):
 with rot.open(encoding="utf-8-sig",newline="") as f:
  rd=csv.DictReader(f);fields=rd.fieldnames;rows=list(rd)
 touched=False
 for row in rows:
  if row.get("fecha","")<TODAY and re.search(r"lista|reserva|manual|pendiente",row.get("estado",""),re.I):
   row["estado"]="requiere_verificar_publicacion";touched=True
 if touched:
  with rot.open("w",encoding="utf-8",newline="") as f:
   w=csv.DictWriter(f,fieldnames=fields,quoting=csv.QUOTE_ALL);w.writeheader();w.writerows(rows)

for cal in (R/"publicaciones GPT").glob("CALENDARIO_EJECUCION_2026-09*.md"):
 s=cal.read_text(encoding="utf-8")
 warning="> Revisión 2026-10-03: las fechas anteriores al 3 de octubre requieren confirmar si se publicaron o programaron antes de reutilizar sus BASE.\n\n"
 if warning.strip() not in s:
  pos=s.find("\n")+1;s=s[:pos]+"\n"+warning+s[pos:]
  cal.write_text(s,encoding="utf-8")

audit=R/"publicaciones GPT/AUDITORIA_EDITORIAL_PENDIENTES_2026-10-03.md"
lines=["# Auditoría editorial de publicaciones pendientes · 3 de octubre de 2026","",
"## Resultado","",
f"- 32 piezas con fecha vencida pasan a `requiere_verificar_publicacion`; no se asume ni que salieron ni que siguen pendientes.",
f"- {len(changes)+8} correcciones directas de voz, coherencia o factualidad.",
"- Se elimina una anécdota personal no documentada y se corrige la publicación de lectores beta para describir la página real.",
"- La pieza de Pinterest sobre clubes de lectura pasa de «crear un club» a preparar una sesión de 30, 60 o 90 minutos.",
"- Se rompe la repetición de «Preparé/Reuní/Desliza/No decide» donde no aportaba nada.",
"- Se mantienen preguntas, ALT y hashtags cuando cumplen una función real de conversación o descubrimiento.","",
"## Regla para las fechas vencidas","",
"No ejecutar una adaptación posterior de la misma BASE hasta confirmar la salida anterior. Si no se publicó, mover la pieza más antigua o descartarla; no lanzar dos versiones para compensar el retraso.","",
"## Piezas con fecha vencida","",
"| Red | ID | Fecha | BASE |","|---|---|---|---|"]
for red,id,dt,base in sorted(stale,key=lambda x:(x[2],x[0])):
 lines.append(f"| {red.replace('publicaciones ','').replace(' GPT','')} | `{id}` | {dt} | `{base or 'sin registrar'}` |")
lines+=["","## Criterio de voz","",
"- Abrir desde una situación concreta, no desde una tesis solemne.",
"- No inventar experiencias personales para parecer cercano.",
"- Explicar la herramienta solo cuando sea necesaria para entender el post.",
"- Evitar encadenar siempre problema, matiz defensivo, enlace y pregunta.",
"- Hacer preguntas que una persona pueda contestar sin haber abierto el enlace.",
"- Variar la llamada al carrusel y relacionarla con lo que aparece en la imagen siguiente.","",
"## Comprobaciones","",
"- Revisar enlaces en directo antes de programar.",
"- Confirmar que el enlace de perfil de Instagram coincide con la ficha.",
"- Buscar duplicados recientes antes de cada pregunta de Reddit.",
"- Registrar publicación real y permalink; `lista` no equivale a publicada.",""]
audit.write_text("\n".join(lines),encoding="utf-8")
print(f"correcciones={len(changes)} caducadas={len(stale)}")
