"""Iconos de línea (24 × 24) del tablero, a juego con los de Radial."""

from muro.qt import QtCore, QtGui, QtSvg

Qt = QtCore.Qt

TRAZOS = {
    "imagen": "M4 5h16v14H4z M4 16l5-5 4 4 3-3 4 4 M15.5 8a1.5 1.5 0 1 0 0.01 0",
    "nota": "M5 4h14v11l-5 5H5z M14 20v-5h5",
    "lista": "M10 6h10 M10 12h10 M10 18h10 M4 6l1.5 1.5L8 5 M4 12l1.5 1.5L8 11 M4 18h4",
    "marco": "M4 8h16v12H4z M4 5h7",
    "flecha": "M5 19L19 5 M10 5h9v9",
    "lapiz": "M4 20l1-4L16 5l3 3L8 19z M14 7l3 3",
    "captura": "M3 8V5h3 M18 5h3v3 M21 16v3h-3 M6 19H3v-3 M12 9a3 3 0 1 0 0.01 0",
    "gotas": "M14 4l6 6 M17 7l-9 9-3 1 1-3 9-9",
    "gris": "M12 4a8 8 0 1 0 0 16z M12 4a8 8 0 0 1 0 16",
    "voltear": "M12 3v18 M8 7l-5 5 5 5z M16 7l5 5-5 5z",
    "recortar": "M6 2v16h16 M2 6h16v16",
    "encuadrar": "M4 9V4h5 M15 4h5v5 M20 15v5h-5 M9 20H4v-5",
    "fantasma": "M6 20V10a6 6 0 0 1 12 0v10l-2-2-2 2-2-2-2 2-2-2z M10 11h.01 M14 11h.01",
    "menu": "M4 7h16 M4 12h16 M4 17h16",
    "marcador": "M12 21s-6-6-6-11a6 6 0 0 1 12 0c0 5-6 11-6 11z M12 10h.01",
    "plano": "M3 7h12v10H3z M15 10l6-3v10l-6-3",
    "borrar": "M5 7h14 M10 7V4h4v3 M7 7l1 13h8l1-13",
    "tono": "M12 4a8 8 0 1 0 0.01 0 M12 4v16",
    "duplicar": "M8.5 8.5h11v11h-11z M5 15.5V4.5h11",
    "frente": "M8 8h12v12H8z M4 16V4h12",
    "mas": "M6 12h.01 M12 12h.01 M18 12h.01",
    "pegar": "M9 4h6v3H9z M7 5H5v15h14V5h-2",
    "rejilla": "M4 4h7v7H4z M13 4h7v7h-7z M4 13h7v7H4z M13 13h7v7h-7z",
    "exportar": "M12 4v11 M7 10l5 5 5-5 M5 20h14",
    "renombrar": "M4 20h4L19 9l-4-4L4 16z M13 7l4 4",
    "desagrupar": "M4 8h16v12H4z M9 13h6",
    "enlace": "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1 M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
    "seleccionar": "M5 3l14 8-6 2-2 6z",
    "bloquear": "M6 11h12v9H6z M8 11V8a4 4 0 0 1 8 0v3",
    "ajustar": "M12 3v18 M3 12h18 M9 6l3-3 3 3 M9 18l3 3 3-3 M6 9l-3 3 3 3 M18 9l3 3-3 3",
    "cerrar": "M6 6l12 12 M18 6L6 18",
}

_cache = {}


def svg(nombre, color="#ececec", grosor=1.5):
    trazo = TRAZOS.get(nombre)
    if trazo is None:
        return None
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c}" '
            'stroke-width="{g}" stroke-linecap="round" stroke-linejoin="round"><path d="{d}"/></svg>'
            ).format(c=color, g=grosor, d=trazo).encode("utf-8")


def pixmap(nombre, lado=18, color="#ececec", escala=2.0):
    clave = (nombre, lado, color, escala)
    if clave in _cache:
        return _cache[clave]
    lado_px = max(1, int(round(lado * escala)))
    mapa = QtGui.QPixmap(lado_px, lado_px)
    mapa.fill(Qt.transparent)
    datos = svg(nombre, color)
    if datos is not None and QtSvg is not None:
        pintor = QtGui.QPainter(mapa)
        pintor.setRenderHint(QtGui.QPainter.Antialiasing)
        QtSvg.QSvgRenderer(QtCore.QByteArray(datos)).render(pintor)
        pintor.end()
    mapa.setDevicePixelRatio(escala)
    _cache[clave] = mapa
    return mapa


def icono(nombre, lado=18):
    """QIcon claro con versión oscura para cuando el botón está activo o bajo el ratón."""
    i = QtGui.QIcon()
    i.addPixmap(pixmap(nombre, lado, "#e6e6e6"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
    i.addPixmap(pixmap(nombre, lado, "#141414"), QtGui.QIcon.Active, QtGui.QIcon.Off)
    i.addPixmap(pixmap(nombre, lado, "#141414"), QtGui.QIcon.Normal, QtGui.QIcon.On)
    i.addPixmap(pixmap(nombre, lado, "#141414"), QtGui.QIcon.Active, QtGui.QIcon.On)
    return i


def dibujar(pintor, nombre, rect, color="#ececec", grosor=1.5):
    datos = svg(nombre, color, grosor)
    if datos is not None and QtSvg is not None:
        QtSvg.QSvgRenderer(QtCore.QByteArray(datos)).render(pintor, QtCore.QRectF(rect))
