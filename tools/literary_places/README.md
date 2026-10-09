# IG-13 — Lugares de libros con una historia rara

Pipeline determinista: fuente institucional para el hecho + foto exacta de Wikimedia Commons con licencia validada.

## Dependencias

```bash
python -m pip install pillow
```

El kit exige una sans legible, no una familia concreta. El renderer usa un orden cerrado: DejaVu Sans y, si no está disponible, Arial. Si no encuentra ninguna, aborta con `IG13_RENDER_BLOCKED`; no cae a la fuente bitmap por defecto de Pillow.

## Descarga

```bash
python tools/literary_places/download_commons.py
```

Debe devolver 4 líneas `COMMONS_OK`. El script bloquea si no coincide licencia o autor esperado.

## Gate

```bash
python tools/literary_places/render_carousel.py --item ig13_01
python tools/literary_places/render_carousel.py --item ig13_03
```

Abrir las 8 slides. El gate falla si:
- el carrusel parece guía turística genérica;
- el hecho necesita letra pequeña;
- la foto se deforma o se recolorea;
- falta fuente/crédito/licencia en slide 4;
- IG-13-03 no muestra `Adaptación distribuida bajo CC BY-SA 4.0`;
- se añade precio, horario, `debes visitar`, CTA o dato no incluido en `manifest.json`;
- el renderer ha usado una fuente distinta de las dos familias autorizadas por el pipeline.

Si pasa:

```bash
python tools/literary_places/render_carousel.py --all
```

## Integridad

- No sustituir una foto por otra parecida.
- No descargar desde Google Images.
- No eliminar atribuciones.
- No generar arquitectura/personas con IA.
- Caption, ALT y calendario salen de `manifest.json`.
- No programar sin aprobación humana.
