"""Cuentas para llevar una referencia a Maya: plano de imagen a escala y colores.

Sin Qt ni Maya, para poder probarlas solas.
"""

CAMARAS = ("front", "side", "top")

# Cuántos centímetros tiene cada unidad lineal de Maya.
CM_POR_UNIDAD = {"mm": 0.1, "cm": 1.0, "m": 100.0, "km": 100000.0,
                 "in": 2.54, "ft": 30.48, "yd": 91.44, "mi": 160934.4}


def convertir(valor, de_unidad, a_unidad):
    return valor * CM_POR_UNIDAD[de_unidad] / CM_POR_UNIDAD[a_unidad]


def plano_de_imagen(px_ancho, px_alto, punto_a, punto_b, altura, camara="front", profundidad=None):
    """Tamaño y centro de un plano de imagen para que la distancia entre dos puntos mida ``altura``.

    ``punto_a`` y ``punto_b`` están en píxeles de la imagen (x a la derecha,
    y hacia abajo); en «front» y «side» ``punto_b`` es el de abajo (los pies)
    y queda sobre el suelo (y = 0). Todo sale en las unidades de ``altura``.
    Devuelve ``{"ancho", "alto", "centro": (x, y, z), "unidades_por_px"}``.
    """
    ax, ay = punto_a
    bx, by = punto_b
    distancia = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
    if distancia < 1e-6:
        raise ValueError("Los dos puntos están en el mismo sitio.")
    if altura <= 0:
        raise ValueError("La altura tiene que ser mayor que cero.")
    por_px = float(altura) / distancia
    ancho = px_ancho * por_px
    alto = px_alto * por_px
    if profundidad is None:
        profundidad = max(ancho, alto)
    medio_x = (ax + bx) / 2.0
    # Desplazamiento del centro de la imagen respecto al punto de referencia, en el plano de la imagen
    derecha = (px_ancho / 2.0 - medio_x) * por_px
    if camara == "top":
        medio_y = (ay + by) / 2.0
        abajo = (px_alto / 2.0 - medio_y) * por_px
        centro = (derecha, -profundidad, abajo)
    else:
        suelo = by if by >= ay else ay
        arriba = (suelo - px_alto / 2.0) * por_px
        if camara == "side":
            centro = (-profundidad, arriba, -derecha)
        else:
            centro = (derecha, arriba, -profundidad)
    return {"ancho": ancho, "alto": alto, "centro": centro, "unidades_por_px": por_px}


# --- Colores -------------------------------------------------------------------

def hex_a_rgb(texto):
    texto = texto.lstrip("#")
    return tuple(int(texto[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def rgb_a_hex(r, g, b):
    return "#" + "".join("{:02x}".format(int(round(max(0.0, min(1.0, c)) * 255))) for c in (r, g, b))


def srgb_a_lineal(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def gris(r, g, b):
    y = 0.299 * r + 0.587 * g + 0.114 * b
    return y, y, y


# Atributo de color base de cada tipo de material, por orden de preferencia.
ATRIBUTO_COLOR = {
    "aiStandardSurface": "baseColor",
    "standardSurface": "baseColor",
    "openPBRSurface": "baseColor",
    "aiFlat": "color",
    "aiLambert": "Kd_color",
    "lambert": "color",
    "blinn": "color",
    "phong": "color",
    "phongE": "color",
    "usdPreviewSurface": "diffuseColor",
}
