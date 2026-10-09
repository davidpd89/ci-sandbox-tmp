"""Politica de crecimiento COMUN a todas las redes (06/10/2026): umbrales que antes estaban repetidos (y a veces con nombre distinto) en cada scan, pool y ejecutor.

Antes: el tope de seguidores para seguir (20.000) vivia en `bluesky_pool.HUGE_ACCOUNT`, `mastodon_pool.HUGE_ACCOUNT`, `threads_execute.FOLLOW_MAX_FOLLOWERS` y en el JSON de Bluesky; las
edades maximas de un post para darle like se llamaban `like_max_age_*` en Bluesky y `favourite_max_age_*` en Mastodon; el reenvio de una cuenta a la reserva (3 dias) estaba escrito en dos pools.
Aqui hay un unico sitio. Cada red puede cambiar un valor en el JSON de su scan (`shortlist`), que manda sobre el comun, pero el valor por defecto es el mismo para todas.

    import growth_policy as gp
    gp.follow_max_followers(config)         # 20000
    gp.max_post_age_days(config, "acquisition")   # 21
"""

FOLLOW_MAX_FOLLOWERS = 20_000       # una cuenta mayor casi nunca devuelve el follow: se puede dar like, no se sigue
OFFER_AGAIN_DAYS = 3                # una cuenta ofrecida por la reserva no vuelve a ofrecerse antes
MAX_INACTIVE_DAYS = 45              # una cuenta sin publicar desde hace mas no entra en la reserva
MAX_POST_AGE_DAYS = {"acquisition": 21, "community": 45}   # a un lector NUEVO solo se le da like a lo reciente; a la comunidad conocida, algo mas
FOLLOW_SHARE_OF_DAILY = 0.15        # tope de follows del dia sobre el objetivo diario (volume_shape.FOLLOW_DAILY_SHARE)
NONRECIPROCAL_DAYS = 7              # 07/10 (David): antes 30. A quien seguimos desde el sistema y no nos devuelve el follow en este plazo se le deja de seguir (unfollow_cleanup.py); ver relationship_policy.py
SHARE_TTL_DAYS = 1                  # un repost/boost/retuit nuestro se retira solo a las 24 h (07/10, David: max 3 al dia, solo curados; antes 7 dias): el perfil queda con nuestras publicaciones
MIN_BIO_HITS_FOR_BIO_ONLY_LIKE = 2  # like por «bio afin» (sin post del nicho) exige al menos dos terminos del nicho

_AGE_KEYS = {"acquisition": ("like_max_age_acquisition_days", "favourite_max_age_acquisition_days"),
             "community": ("like_max_age_days", "favourite_max_age_days")}


def _section(config):
    return (config or {}).get("shortlist") or {}


def max_post_age_days(config, lane):
    """Edad maxima (dias) de un post para darle like/favorito. Acepta los dos nombres historicos de la clave (`like_*` de Bluesky, `favourite_*` de Mastodon)."""
    section = _section(config)
    for key in _AGE_KEYS["acquisition" if lane == "acquisition" else "community"]:
        if section.get(key) is not None:
            return int(section[key])
    return MAX_POST_AGE_DAYS["acquisition" if lane == "acquisition" else "community"]


def follow_max_followers(config=None):
    value = _section(config).get("follow_max_followers")
    return int(value) if value is not None else FOLLOW_MAX_FOLLOWERS
