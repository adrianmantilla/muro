"""Bajar una imagen arrastrada desde el navegador cuando solo llega su dirección web."""

import os

try:
    from urllib.parse import unquote, urlparse
    from urllib.request import Request, urlopen
except ImportError:  # pragma: no cover
    from urllib import unquote
    from urllib2 import Request, urlopen
    from urlparse import urlparse

LIMITE = 60 * 1024 * 1024
TIPOS = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/webp": ".webp",
         "image/bmp": ".bmp", "image/tiff": ".tif"}
FIRMAS = ((b"\x89PNG", ".png"), (b"\xff\xd8", ".jpg"), (b"GIF8", ".gif"), (b"RIFF", ".webp"), (b"BM", ".bmp"),
          (b"II*\x00", ".tif"), (b"MM\x00*", ".tif"))


def extension_por_contenido(datos):
    for firma, extension in FIRMAS:
        if datos.startswith(firma):
            return extension
    return None


def nombre_de_url(url):
    ruta = unquote(urlparse(url).path)
    return os.path.basename(ruta) or "web"


def bajar_imagen(url, tiempo=10):
    """(bytes, extensión) de la imagen, o None si no es una imagen o no se pudo bajar."""
    if not url.lower().startswith(("http://", "https://")):
        return None
    try:
        peticion = Request(url, headers={"User-Agent": "Mozilla/5.0 (Muro para Maya)"})
        respuesta = urlopen(peticion, timeout=tiempo)
        tipo = (respuesta.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        datos = respuesta.read(LIMITE + 1)
    except Exception:
        return None
    if len(datos) > LIMITE or not datos:
        return None
    extension = extension_por_contenido(datos) or TIPOS.get(tipo)
    if extension is None:
        return None
    return datos, extension
