"""Publicacion propia por la API oficial de Meta: Pagina de Facebook e Instagram (06/10/2026, David: «tendras que hacerlo, tienes acceso a todas»).

  * Facebook: `/{page}/feed` (solo texto), `/{page}/photos` (una imagen, con texto alternativo) o fotos sin publicar + `attached_media` (varias). Token de Pagina con `pages_manage_posts`.
  * Instagram: contenedor (`/media`) + `/media_publish`; la API exige una URL PUBLICA de la imagen (JPEG). Sin alojar nada fuera: la imagen se sube a la Pagina de Facebook SIN publicar
    (`published=false`), de ahi sale una URL publica de su CDN y se usa como `image_url`. Carrusel: un contenedor hijo por imagen + uno padre.
Las fichas ya vienen aprobadas (David autorizo la publicacion automatica el 06/10): aqui se publica con `approved=True`, nunca desde una ficha que no pase `content_publisher.eligible`.
"""
import io
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(__file__))
import meta_common as mc

FB_BASE = "https://graph.facebook.com/v26.0/"
IG_BASE = "https://graph.instagram.com/v26.0/"
FB_TEXT_MAX, IG_CAPTION_MAX = 63000, 2200


def _json(response):
    try:
        data = response.json()
    except ValueError:
        data = {}
    if not response.ok or "error" in data:
        message = (data.get("error") or {}).get("message") or response.text[:200]
        raise RuntimeError(f"API {response.status_code}: {message[:200]}")
    return data


def _fb_photo(token, page_id, path, caption="", alt="", published=True):
    with open(path, "rb") as stream:
        data = {"access_token": token, "published": "true" if published else "false"}
        if caption:
            data["message"] = caption
        if alt:
            data["alt_text_custom"] = alt[:1000]
        return _json(requests.post(f"{FB_BASE}{page_id}/photos", data=data, files={"source": (os.path.basename(path), stream)}, timeout=120))


def publish_facebook(token, page_id, text, images=(), alts=()):
    """Publica en la Pagina. `images`: rutas locales. Devuelve el id del post."""
    text = mc.check_text(text, FB_TEXT_MAX)
    if not images:
        return mc.graph_post(FB_BASE, f"{page_id}/feed", token, message=text)["id"]
    if len(images) == 1:
        result = _fb_photo(token, page_id, images[0], text, alts[0] if alts else "")
        return result.get("post_id") or result["id"]
    attached = {}
    for index, path in enumerate(images):
        photo = _fb_photo(token, page_id, path, "", alts[index] if index < len(alts) else "", published=False)
        attached[f"attached_media[{index}]"] = '{"media_fbid":"%s"}' % photo["id"]
    return mc.graph_post(FB_BASE, f"{page_id}/feed", token, message=text, **attached)["id"]


def facebook_permalink(token, post_id):
    try:
        return mc.graph_get(FB_BASE, post_id, token, fields="permalink_url").get("permalink_url") or post_id
    except RuntimeError:
        return post_id


def facebook_recent_texts(token, page_id, limit=50):
    data = mc.graph_get(FB_BASE, f"{page_id}/posts", token, fields="message", limit=limit)
    return [row.get("message") or "" for row in data.get("data", [])]


def _jpeg_bytes(path):
    """La API de Instagram solo acepta JPEG: se convierte (fondo blanco si hay transparencia)."""
    from PIL import Image
    image = Image.open(path)
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[-1])
        image = background
    else:
        image = image.convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=93, optimize=True)
    return buffer.getvalue()


def public_image_url(fb_token, page_id, path):
    """Sube la imagen (como JPEG) a la Pagina SIN publicarla y devuelve la URL publica de su CDN."""
    files = {"source": (os.path.splitext(os.path.basename(path))[0] + ".jpg", _jpeg_bytes(path), "image/jpeg")}
    photo = _json(requests.post(f"{FB_BASE}{page_id}/photos", data={"access_token": fb_token, "published": "false"}, files=files, timeout=120))
    info = mc.graph_get(FB_BASE, photo["id"], fb_token, fields="images")
    images = sorted(info.get("images") or [], key=lambda i: i.get("width", 0), reverse=True)
    if not images:
        raise RuntimeError("Facebook no devolvio la URL publica de la imagen")
    return images[0]["source"]


def _wait_container(token, container_id, tries=30, sleep=time.sleep):
    for _ in range(tries):
        status = mc.graph_get(IG_BASE, container_id, token, fields="status_code").get("status_code")
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"contenedor de Instagram en estado {status}")
        sleep(4)
    raise RuntimeError("el contenedor de Instagram no termino de procesarse a tiempo")


def publish_instagram(ig_token, user_id, caption, image_urls, alts=()):
    """Publica una imagen o un carrusel (URLs publicas JPEG). Devuelve el id del medio."""
    caption = mc.check_text(caption, IG_CAPTION_MAX)
    if not image_urls:
        raise ValueError("Instagram exige al menos una imagen")
    if len(image_urls) == 1:
        params = {"image_url": image_urls[0], "caption": caption}
        if alts and alts[0]:
            params["alt_text"] = alts[0][:1000]
        container = mc.graph_post(IG_BASE, f"{user_id}/media", ig_token, **params)["id"]
    else:
        children = []
        for index, url in enumerate(image_urls):
            params = {"image_url": url, "is_carousel_item": "true"}
            if index < len(alts) and alts[index]:
                params["alt_text"] = alts[index][:1000]
            child = mc.graph_post(IG_BASE, f"{user_id}/media", ig_token, **params)["id"]
            _wait_container(ig_token, child)
            children.append(child)
        container = mc.graph_post(IG_BASE, f"{user_id}/media", ig_token, media_type="CAROUSEL", children=",".join(children), caption=caption)["id"]
    _wait_container(ig_token, container)
    return mc.graph_post(IG_BASE, f"{user_id}/media_publish", ig_token, creation_id=container)["id"]


def instagram_permalink(ig_token, media_id):
    try:
        return mc.graph_get(IG_BASE, media_id, ig_token, fields="permalink").get("permalink") or media_id
    except RuntimeError:
        return media_id


def instagram_recent_texts(ig_token, user_id, limit=50):
    data = mc.graph_get(IG_BASE, f"{user_id}/media", ig_token, fields="caption", limit=limit)
    return [row.get("caption") or "" for row in data.get("data", [])]
