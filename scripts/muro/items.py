"""Elementos dibujables del tablero (imágenes, notas, marcos, flechas y trazos).

Cada elemento gráfico guarda una referencia al diccionario del modelo
(``self.e``) y se dibuja a partir de él. Mover un elemento con el ratón cambia
solo su posición en Qt; el lienzo pasa las posiciones al modelo al soltar.
"""

import math
import os
from collections import OrderedDict

from muro import archivo, modelo
from muro.qt import QtCore, QtGui, QtWidgets

Qt = QtCore.Qt
QRectF = QtCore.QRectF
QPointF = QtCore.QPointF

FONDO_NOTA = QtGui.QColor(38, 41, 45)
BORDE = QtGui.QColor(255, 255, 255, 42)
BLANCO = QtGui.QColor(244, 244, 244)
TEXTO = QtGui.QColor(233, 233, 233)
TEXTO_TENUE = QtGui.QColor(169, 174, 179)
FONDO_TABLERO = QtGui.QColor(26, 27, 29)
TIRADOR = 9.0
MINIATURA_MAX = 2048


def fuente(pixeles, peso=QtGui.QFont.Normal, familia=None):
    f = QtGui.QFont(familia) if familia else QtGui.QFont()
    f.setPixelSize(int(pixeles))
    f.setWeight(peso)
    return f


def pluma_fina(color, ancho=1.0):
    p = QtGui.QPen(color, ancho)
    p.setCosmetic(True)
    return p


# --- Caché de imágenes ---------------------------------------------------------------

class CacheImagenes(object):
    """Pixmaps de las referencias: miniatura para el día a día y original solo si hace falta."""

    def __init__(self):
        self.carpeta = None
        self._miniaturas = {}
        self._grises = {}
        self._originales = OrderedDict()

    def usar_carpeta(self, carpeta):
        if carpeta != self.carpeta:
            self.carpeta = carpeta
            self._miniaturas.clear()
            self._grises.clear()
            self._originales.clear()

    def ruta(self, relativa):
        return archivo.ruta_absoluta(self.carpeta, relativa) if self.carpeta else relativa

    def _marcador_roto(self):
        mapa = QtGui.QPixmap(64, 64)
        mapa.fill(QtGui.QColor(60, 62, 66))
        p = QtGui.QPainter(mapa)
        p.setPen(QtGui.QColor(180, 180, 180))
        p.drawText(mapa.rect(), Qt.AlignCenter, "?")
        p.end()
        return mapa

    def miniatura(self, relativa):
        if relativa in self._miniaturas:
            return self._miniaturas[relativa]
        mapa = None
        if self.carpeta:
            ruta_mini = archivo.ruta_miniatura(self.carpeta, relativa)
            if os.path.isfile(ruta_mini):
                mapa = QtGui.QPixmap(ruta_mini)
                if mapa.isNull():
                    mapa = None
        if mapa is None:
            lector = QtGui.QImageReader(self.ruta(relativa))
            lector.setAutoTransform(True)
            tamano = lector.size()
            grande = tamano.isValid() and max(tamano.width(), tamano.height()) > MINIATURA_MAX
            if grande:
                lector.setScaledSize(tamano.scaled(MINIATURA_MAX, MINIATURA_MAX, Qt.KeepAspectRatio))
            imagen = lector.read()
            if imagen.isNull():
                mapa = self._marcador_roto()
            else:
                mapa = QtGui.QPixmap.fromImage(imagen)
                if grande and self.carpeta:
                    ruta_mini = archivo.ruta_miniatura(self.carpeta, relativa)
                    try:
                        os.makedirs(os.path.dirname(ruta_mini), exist_ok=True)
                        imagen.save(ruta_mini, "PNG")
                    except OSError:
                        pass
        self._miniaturas[relativa] = mapa
        return mapa

    def original(self, relativa):
        """QImage a tamaño completo (se guardan las cuatro últimas)."""
        if relativa in self._originales:
            self._originales.move_to_end(relativa)
            return self._originales[relativa]
        lector = QtGui.QImageReader(self.ruta(relativa))
        lector.setAutoTransform(True)
        imagen = lector.read()
        if imagen.isNull():
            imagen = self.miniatura(relativa).toImage()
        self._originales[relativa] = imagen
        while len(self._originales) > 4:
            self._originales.popitem(last=False)
        return imagen

    def pixmap(self, relativa, gris=False, pixeles_pantalla=0):
        """El pixmap adecuado para dibujar ``pixeles_pantalla`` de ancho."""
        mini = self.miniatura(relativa)
        usar_original = pixeles_pantalla > mini.width() * 1.2 and mini.width() >= MINIATURA_MAX - 1
        if usar_original:
            clave = ("o", relativa, gris)
            if clave not in self._grises:
                imagen = self.original(relativa)
                if gris:
                    imagen = imagen.convertToFormat(QtGui.QImage.Format_Grayscale8)
                self._grises = {k: v for k, v in self._grises.items() if k[0] != "o"}
                self._grises[clave] = QtGui.QPixmap.fromImage(imagen)
            return self._grises[clave]
        if not gris:
            return mini
        clave = ("m", relativa, True)
        if clave not in self._grises:
            self._grises[clave] = QtGui.QPixmap.fromImage(
                mini.toImage().convertToFormat(QtGui.QImage.Format_Grayscale8))
        return self._grises[clave]

    def tamano(self, relativa):
        lector = QtGui.QImageReader(self.ruta(relativa))
        lector.setAutoTransform(True)
        tamano = lector.size()
        if tamano.isValid():
            return tamano.width(), tamano.height()
        mini = self.miniatura(relativa)
        return mini.width(), mini.height()


# --- Base ----------------------------------------------------------------------------

class ItemBase(QtWidgets.QGraphicsItem):
    movible = True
    escalable = True
    girable = True

    def __init__(self, lienzo, elemento):
        super(ItemBase, self).__init__()
        self.lienzo = lienzo
        self.e = elemento
        self.modo = None
        self._inicio = None
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QtWidgets.QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.sincronizar()

    @property
    def id(self):
        return self.e["id"]

    def ancho(self):
        return self.e["ancho"]

    def alto(self):
        return self.e["alto"]

    def sincronizar(self):
        self.prepareGeometryChange()
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, self.movible and not self.e["bloqueado"])
        self.setPos(self.e["x"], self.e["y"])
        self.setTransformOriginPoint(self.ancho() / 2.0, self.alto() / 2.0)
        self.setRotation(self.e["rot"])
        self.update()

    def rect(self):
        return QRectF(0, 0, self.ancho(), self.alto())

    def boundingRect(self):
        margen = 3.0 + TIRADOR / max(self.escala_vista(), 0.01)
        r = self.rect().adjusted(-margen, -margen, margen, margen)
        if self.girable:
            r = r.united(QRectF(self.ancho() / 2 - margen, -30 / max(self.escala_vista(), 0.01) - margen,
                                2 * margen, 2 * margen))
        return r

    def escala_vista(self):
        return self.lienzo.zoom() if self.lienzo is not None else 1.0

    def con_tiradores(self):
        return (self.isSelected() and not self.e["bloqueado"] and self.lienzo is not None
                and self.lienzo.seleccion_unica() is self and not self.lienzo.exportando)

    def tirador_escala(self):
        lado = TIRADOR / self.escala_vista()
        return QRectF(self.ancho() - lado / 2, self.alto() - lado / 2, lado, lado)

    def tirador_giro(self):
        lado = TIRADOR / self.escala_vista()
        return QRectF(self.ancho() / 2 - lado / 2, -30 / self.escala_vista() - lado / 2, lado, lado)

    def dibujar_seleccion(self, p):
        if self.lienzo is not None and self.lienzo.exportando:
            return
        if self.isSelected():
            p.setPen(pluma_fina(BLANCO))
            p.setBrush(Qt.NoBrush)
            m = 2.0 / self.escala_vista()
            p.drawRect(self.rect().adjusted(-m, -m, m, m))
        if self.con_tiradores():
            p.setPen(pluma_fina(QtGui.QColor(20, 20, 20)))
            p.setBrush(BLANCO)
            if self.escalable:
                p.drawRect(self.tirador_escala())
            if self.girable:
                giro = self.tirador_giro()
                p.setPen(pluma_fina(BLANCO))
                p.drawLine(QPointF(self.ancho() / 2, 0), giro.center())
                p.setPen(pluma_fina(QtGui.QColor(20, 20, 20)))
                p.drawEllipse(giro)

    # --- ratón: escalar y girar desde los tiradores
    def mousePressEvent(self, evento):
        if evento.button() == Qt.LeftButton and self.con_tiradores():
            pos = evento.pos()
            holgura = 4 / self.escala_vista()
            if self.escalable and self.tirador_escala().adjusted(-holgura, -holgura, holgura, holgura).contains(pos):
                self.modo = "escala"
            elif self.girable and self.tirador_giro().adjusted(-holgura, -holgura, holgura, holgura).contains(pos):
                self.modo = "giro"
            if self.modo:
                self._inicio = (QPointF(pos), self.e["ancho"], self.e["alto"], self.e["rot"],
                                self.mapToScene(self.rect().center()))
                self.lienzo.empezar_cambio()
                evento.accept()
                return
        super(ItemBase, self).mousePressEvent(evento)

    def mouseMoveEvent(self, evento):
        if self.modo == "escala":
            self.escalar_a(evento.pos(), evento.modifiers())
            return
        if self.modo == "giro":
            centro = self._inicio[4]
            v = evento.scenePos() - centro
            angulo = math.degrees(math.atan2(v.y(), v.x())) + 90.0
            if evento.modifiers() & Qt.ShiftModifier:
                angulo = round(angulo / 15.0) * 15.0
            angulo = (angulo + 180.0) % 360.0 - 180.0
            if abs(angulo) < 2.0:
                angulo = 0.0
            self.e["rot"] = angulo
            self.sincronizar()
            self.lienzo.posicion_cambiada(self)
            return
        super(ItemBase, self).mouseMoveEvent(evento)

    def mouseReleaseEvent(self, evento):
        if self.modo:
            self.modo = None
            self.lienzo.terminar_cambio()
            evento.accept()
            return
        super(ItemBase, self).mouseReleaseEvent(evento)

    def escalar_a(self, pos, modificadores):
        _, ancho0, alto0, _, _ = self._inicio
        # Se escala dejando fija la esquina de arriba a la izquierda (en el tablero).
        esquina = self.mapToScene(QPointF(0, 0))
        nuevo_ancho = max(20.0, pos.x())
        self.prepareGeometryChange()
        self.redimensionar(nuevo_ancho, max(20.0, pos.y()), ancho0, alto0, modificadores)
        self.setTransformOriginPoint(self.ancho() / 2.0, self.alto() / 2.0)
        desfase = esquina - self.mapToScene(QPointF(0, 0))
        self.setPos(self.pos() + desfase)
        self.e["x"], self.e["y"] = self.pos().x(), self.pos().y()
        self.update()
        self.lienzo.posicion_cambiada(self)

    def redimensionar(self, ancho, alto, ancho0, alto0, modificadores):
        self.e["ancho"] = ancho
        self.e["alto"] = alto

    def itemChange(self, cambio, valor):
        if cambio == QtWidgets.QGraphicsItem.ItemPositionHasChanged and self.lienzo is not None:
            self.lienzo.posicion_cambiada(self)
        elif cambio == QtWidgets.QGraphicsItem.ItemSelectedHasChanged and self.lienzo is not None:
            self.lienzo.seleccion_tocada()
        return super(ItemBase, self).itemChange(cambio, valor)

    def hoverMoveEvent(self, evento):
        if self.con_tiradores():
            pos = evento.pos()
            if self.escalable and self.tirador_escala().contains(pos):
                self.setCursor(Qt.SizeFDiagCursor)
                return
            if self.girable and self.tirador_giro().contains(pos):
                self.setCursor(Qt.CrossCursor)
                return
        self.unsetCursor()


# --- Imagen --------------------------------------------------------------------------

class ItemImagen(ItemBase):
    def redimensionar(self, ancho, alto, ancho0, alto0, modificadores):
        proporcion = alto0 / ancho0 if ancho0 else 1.0
        self.e["ancho"] = ancho
        self.e["alto"] = ancho * proporcion

    def paint(self, p, _opciones, _widget=None):
        e = self.e
        r = e["recorte"]
        lod = QtWidgets.QStyleOptionGraphicsItem.levelOfDetailFromTransform(p.worldTransform())
        pantalla = e["ancho"] * lod / max(r[2] - r[0], 0.01)
        mapa = self.lienzo.cache.pixmap(e["archivo"], e["gris"], pantalla)
        origen = QRectF(r[0] * mapa.width(), r[1] * mapa.height(), (r[2] - r[0]) * mapa.width(),
                        (r[3] - r[1]) * mapa.height())
        p.save()
        p.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
        p.setOpacity(e["opacidad"])
        if e["volteo"]:
            p.translate(e["ancho"], 0)
            p.scale(-1, 1)
        p.drawPixmap(self.rect(), mapa, origen)
        p.restore()
        self.dibujar_marcadores(p)
        self.dibujar_seleccion(p)

    def punto_marcador(self, m):
        return QPointF(modelo.visible_u(self.e, m["u"]) * self.e["ancho"],
                       modelo.visible_v(self.e, m["v"]) * self.e["alto"])

    def dibujar_marcadores(self, p):
        if not self.e["marcadores"]:
            return
        radio = 9.0
        p.save()
        p.setFont(fuente(10.5, QtGui.QFont.DemiBold))
        for m in self.e["marcadores"]:
            punto = self.punto_marcador(m)
            if not self.rect().adjusted(-1, -1, 1, 1).contains(punto):
                continue
            p.setPen(QtGui.QPen(QtGui.QColor(16, 17, 19, 140), 3))
            p.setBrush(BLANCO)
            p.drawEllipse(punto, radio, radio)
            p.setPen(QtGui.QColor(20, 20, 20))
            p.drawText(QRectF(punto.x() - radio, punto.y() - radio, 2 * radio, 2 * radio), Qt.AlignCenter,
                       str(m["n"]))
        p.restore()

    def uv_en(self, punto_local):
        """(u, v) sobre la imagen entera de un punto local, o None si cae fuera."""
        if not self.rect().contains(punto_local):
            return None
        fx = punto_local.x() / self.e["ancho"]
        fy = punto_local.y() / self.e["alto"]
        return modelo.imagen_u(self.e, fx), modelo.imagen_v(self.e, fy)


# --- Nota ----------------------------------------------------------------------------

class ItemNota(ItemBase):
    girable = False
    RELLENO = 10.0
    CABECERA = 20.0

    def __init__(self, lienzo, elemento, numero_marcador=None):
        self.numero_marcador = numero_marcador
        self._filas = []
        super(ItemNota, self).__init__(lienzo, elemento)

    def redimensionar(self, ancho, alto, ancho0, alto0, modificadores):
        self.e["ancho"] = max(80.0, ancho)
        self.calcular()

    def sincronizar(self):
        self.calcular()
        super(ItemNota, self).sincronizar()

    def cabecera_texto(self):
        from muro.i18n import t
        if self.e["objeto"]:
            return self.e["objeto"]["nombre"] or t("nota_objeto")
        if self.numero_marcador is not None:
            return t("nota_marcador", n=self.numero_marcador)
        return t("nota_lista") if self.e["subtipo"] == "lista" else t("nota_texto")

    def calcular(self):
        """Coloca el texto y ajusta la altura de la nota a lo que ocupa."""
        ancho_texto = self.e["ancho"] - 2 * self.RELLENO
        y = self.RELLENO + self.CABECERA
        self._filas = []
        f = fuente(13)
        metricas = QtGui.QFontMetricsF(f)
        if self.e["subtipo"] == "lista":
            for i, (hecho, texto) in enumerate(modelo.lineas_lista(self.e["texto"])):
                caja = metricas.boundingRect(QRectF(0, 0, ancho_texto - 18, 10000),
                                             Qt.TextWordWrap, texto or " ")
                alto = max(caja.height(), metricas.height())
                self._filas.append((QRectF(self.RELLENO, y, ancho_texto, alto), i, hecho, texto))
                y += alto + 4
            if not self._filas:
                y += metricas.height()
        else:
            documento = self.documento(ancho_texto)
            alto = max(documento.size().height(), metricas.height())
            self._filas.append((QRectF(self.RELLENO, y, ancho_texto, alto), -1, False, ""))
            y += alto
        self.e["alto"] = y + self.RELLENO

    def documento(self, ancho):
        doc = QtGui.QTextDocument()
        doc.setDefaultFont(fuente(13))
        doc.setDocumentMargin(0)
        doc.setDefaultStyleSheet("p,li{margin:0} ul{margin-left:14px}")
        texto = self.e["texto"]
        if hasattr(doc, "setMarkdown"):
            doc.setMarkdown(texto)
        else:  # pragma: no cover
            doc.setPlainText(texto)
        doc.setTextWidth(ancho)
        return doc

    def rect_cuerpo(self):
        return QRectF(self.RELLENO - 2, self.RELLENO + self.CABECERA - 2,
                      self.e["ancho"] - 2 * self.RELLENO + 4, self.e["alto"] - 2 * self.RELLENO - self.CABECERA + 4)

    def rect_enlace(self):
        """Zona de la cabecera que selecciona el objeto ligado en la escena."""
        return QRectF(self.RELLENO, self.RELLENO - 4, self.e["ancho"] - 2 * self.RELLENO, self.CABECERA)

    def paint(self, p, _opciones, _widget=None):
        e = self.e
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setPen(pluma_fina(BORDE))
        p.setBrush(FONDO_NOTA)
        p.drawRoundedRect(self.rect(), 6, 6)
        # cabecera
        tono = QtGui.QColor(modelo.TONOS[e["tono"]])
        p.setPen(Qt.NoPen)
        p.setBrush(tono)
        p.drawEllipse(QPointF(self.RELLENO + 4, self.RELLENO + 6), 4, 4)
        p.setFont(fuente(10.5, QtGui.QFont.Medium))
        p.setPen(TEXTO_TENUE)
        x_texto = self.RELLENO + 14
        if e["objeto"]:
            from muro import iconos
            iconos.dibujar(p, "enlace", QRectF(x_texto, self.RELLENO - 1, 13, 13), "#a9aeb3")
            x_texto += 17
        cab = QtGui.QFontMetricsF(p.font()).elidedText(self.cabecera_texto().upper(), Qt.ElideRight,
                                                        e["ancho"] - x_texto - self.RELLENO)
        p.drawText(QRectF(x_texto, self.RELLENO - 2, e["ancho"], 16), Qt.AlignLeft | Qt.AlignVCenter, cab)
        # cuerpo
        if self.lienzo is None or self.lienzo.editando_id != e["id"]:
            p.setFont(fuente(13))
            if e["subtipo"] == "lista":
                for rect, _i, hecho, texto in self._filas:
                    caja = QRectF(rect.x(), rect.y() + 3, 10, 10)
                    if hecho:
                        p.setPen(Qt.NoPen)
                        p.setBrush(BLANCO)
                        p.drawRoundedRect(caja, 2, 2)
                        p.setPen(QtGui.QPen(FONDO_NOTA, 1.6))
                        p.drawPolyline(QtGui.QPolygonF([QPointF(caja.x() + 2.2, caja.y() + 5.2),
                                                        QPointF(caja.x() + 4.2, caja.y() + 7.4),
                                                        QPointF(caja.x() + 8, caja.y() + 2.8)]))
                        p.setPen(QtGui.QColor(141, 146, 151))
                        f = fuente(13)
                        f.setStrikeOut(True)
                        p.setFont(f)
                    else:
                        p.setPen(pluma_fina(QtGui.QColor(185, 190, 195)))
                        p.setBrush(Qt.NoBrush)
                        p.drawRoundedRect(caja, 2, 2)
                        p.setPen(TEXTO)
                        p.setFont(fuente(13))
                    p.drawText(rect.adjusted(18, 0, 0, 0), Qt.TextWordWrap, texto)
                if not self._filas:
                    from muro.i18n import t
                    p.setPen(TEXTO_TENUE)
                    p.drawText(self.rect_cuerpo().adjusted(2, 2, 0, 0), Qt.AlignLeft, t("nota_vacia"))
            elif e["texto"].strip():
                rect = self._filas[0][0]
                doc = self.documento(rect.width())
                p.save()
                p.translate(rect.topLeft())
                contexto = QtGui.QAbstractTextDocumentLayout.PaintContext()
                contexto.palette.setColor(QtGui.QPalette.Text, TEXTO)
                doc.documentLayout().draw(p, contexto)
                p.restore()
            else:
                from muro.i18n import t
                p.setPen(TEXTO_TENUE)
                p.drawText(self.rect_cuerpo().adjusted(2, 2, 0, 0), Qt.AlignLeft, t("nota_vacia"))
        self.dibujar_seleccion(p)

    def fila_en(self, punto_local):
        if self.e["subtipo"] != "lista":
            return -1
        for rect, i, _hecho, _texto in self._filas:
            if rect.adjusted(-4, -2, 4, 2).contains(punto_local):
                return i
        return -1


class EditorTexto(QtWidgets.QGraphicsTextItem):
    """Editor dentro del tablero para notas y títulos de marco. Al perder el foco, guarda."""

    def __init__(self, texto, ancho, al_terminar, una_linea=False, padre=None):
        super(EditorTexto, self).__init__(padre)
        self.al_terminar = al_terminar
        self.una_linea = una_linea
        self.terminado = False
        self.setDefaultTextColor(TEXTO)
        self.setFont(fuente(14 if una_linea else 13))
        self.setPlainText(texto)
        if not una_linea:
            self.setTextWidth(ancho)
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.setZValue(1000)

    def empezar(self):
        self.setFocus(Qt.MouseFocusReason)
        cursor = self.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        self.setTextCursor(cursor)

    def terminar(self, guardar=True):
        if self.terminado:
            return
        self.terminado = True
        texto = self.toPlainText()
        QtCore.QTimer.singleShot(0, lambda: self.al_terminar(texto if guardar else None))

    def focusOutEvent(self, evento):
        super(EditorTexto, self).focusOutEvent(evento)
        self.terminar(True)

    def keyPressEvent(self, evento):
        if evento.key() == Qt.Key_Escape:
            self.terminar(True)
            return
        if evento.key() in (Qt.Key_Return, Qt.Key_Enter) and (
                self.una_linea or evento.modifiers() & (Qt.ControlModifier | Qt.MetaModifier)):
            self.terminar(True)
            return
        super(EditorTexto, self).keyPressEvent(evento)

    def paint(self, p, opciones, widget=None):
        p.setPen(Qt.NoPen)
        p.setBrush(QtGui.QColor(255, 255, 255, 12))
        p.drawRoundedRect(self.boundingRect(), 3, 3)
        super(EditorTexto, self).paint(p, opciones, widget)


# --- Marco ---------------------------------------------------------------------------

class ItemMarco(ItemBase):
    girable = False
    BANDA = 10.0

    def fuente_titulo(self):
        return fuente(15, QtGui.QFont.DemiBold)

    def rect_titulo(self):
        metricas = QtGui.QFontMetricsF(self.fuente_titulo())
        from muro.i18n import t
        texto = self.e["titulo"] or t("marco_sin_titulo")
        return QRectF(10, -metricas.height() / 2 - 1, metricas.horizontalAdvance(texto) + 16, metricas.height() + 2)

    def boundingRect(self):
        return super(ItemMarco, self).boundingRect().united(self.rect_titulo().adjusted(-2, -2, 2, 2))

    def shape(self):
        camino = QtGui.QPainterPath()
        camino.addRect(self.rect_titulo())
        exterior = QtGui.QPainterPath()
        exterior.addRect(self.rect().adjusted(-self.BANDA / 2, -self.BANDA / 2, self.BANDA / 2, self.BANDA / 2))
        interior = QtGui.QPainterPath()
        interior.addRect(self.rect().adjusted(self.BANDA / 2, self.BANDA / 2, -self.BANDA / 2, -self.BANDA / 2))
        camino.addPath(exterior.subtracted(interior))
        if self.con_tiradores():
            camino.addRect(self.tirador_escala().adjusted(-4, -4, 4, 4))
        return camino

    def paint(self, p, _opciones, _widget=None):
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setBrush(QtGui.QColor(255, 255, 255, 5))
        pluma = pluma_fina(QtGui.QColor(255, 255, 255, 70 if self.isSelected() else 56))
        pluma.setStyle(Qt.DashLine)
        p.setPen(pluma)
        p.drawRoundedRect(self.rect(), 8, 8)
        if self.lienzo is None or self.lienzo.editando_id != self.e["id"]:
            titulo = self.rect_titulo()
            p.setPen(Qt.NoPen)
            p.setBrush(FONDO_TABLERO)
            p.drawRect(titulo)
            p.setPen(QtGui.QColor(207, 211, 215))
            p.setFont(self.fuente_titulo())
            from muro.i18n import t
            p.drawText(titulo, Qt.AlignCenter, self.e["titulo"] or t("marco_sin_titulo"))
        if self.con_tiradores():
            p.setPen(pluma_fina(QtGui.QColor(20, 20, 20)))
            p.setBrush(BLANCO)
            p.drawRect(self.tirador_escala())


# --- Flecha --------------------------------------------------------------------------

class ItemFlecha(QtWidgets.QGraphicsItem):
    def __init__(self, lienzo, elemento):
        super(ItemFlecha, self).__init__()
        self.lienzo = lienzo
        self.e = elemento
        self.a = QPointF(*elemento["p0"])
        self.b = QPointF(*elemento["p1"])
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, True)

    @property
    def id(self):
        return self.e["id"]

    def fijar(self, a, b):
        self.prepareGeometryChange()
        self.a, self.b = a, b
        self.update()

    def boundingRect(self):
        return QRectF(self.a, self.b).normalized().adjusted(-14, -14, 14, 14)

    def shape(self):
        camino = QtGui.QPainterPath(self.a)
        camino.lineTo(self.b)
        trazador = QtGui.QPainterPathStroker()
        trazador.setWidth(10 / max(self.lienzo.zoom(), 0.05))
        return trazador.createStroke(camino)

    def paint(self, p, _opciones, _widget=None):
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        color = QtGui.QColor(modelo.TONOS_TRAZO[self.e["tono"]])
        if self.isSelected() and not self.lienzo.exportando:
            p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 60), 6, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(self.a, self.b)
        p.setPen(QtGui.QPen(color, 2, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(self.a, self.b)
        v = self.b - self.a
        largo = math.hypot(v.x(), v.y())
        if largo > 1:
            ux, uy = v.x() / largo, v.y() / largo
            punta = 12.0
            izq = QPointF(self.b.x() - punta * ux + punta * 0.45 * uy, self.b.y() - punta * uy - punta * 0.45 * ux)
            der = QPointF(self.b.x() - punta * ux - punta * 0.45 * uy, self.b.y() - punta * uy + punta * 0.45 * ux)
            p.setPen(Qt.NoPen)
            p.setBrush(color)
            p.drawPolygon(QtGui.QPolygonF([self.b, izq, der]))


def borde_hacia(item, desde):
    """Punto del borde de ``item`` en la línea entre su centro y ``desde`` (en el tablero)."""
    forma = item.mapToScene(item.rect()) if hasattr(item, "rect") else item.mapToScene(item.boundingRect())
    caja = forma.boundingRect()
    centro = caja.center()
    linea = QtCore.QLineF(centro, desde)
    mejor = None
    for i in range(forma.count()):
        lado = QtCore.QLineF(forma[i], forma[(i + 1) % forma.count()])
        tipo, punto = linea.intersects(lado) if hasattr(linea, "intersects") else linea.intersect(lado)
        if tipo == QtCore.QLineF.BoundedIntersection:
            if mejor is None or QtCore.QLineF(punto, desde).length() < QtCore.QLineF(mejor, desde).length():
                mejor = punto
    return QPointF(mejor) if mejor is not None else centro


# --- Trazo de lápiz -------------------------------------------------------------------

class ItemTrazo(QtWidgets.QGraphicsPathItem):
    def __init__(self, lienzo, elemento, padre=None):
        super(ItemTrazo, self).__init__(padre)
        self.lienzo = lienzo
        self.e = elemento
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QtWidgets.QGraphicsItem.ItemSendsGeometryChanges, True)
        if padre is None:
            self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, not elemento["bloqueado"])
        pluma = QtGui.QPen(QtGui.QColor(modelo.TONOS_TRAZO[elemento["tono"]]), elemento["grosor"],
                           Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        self.setPen(pluma)
        self.setPath(camino_suave(elemento["puntos"]))

    @property
    def id(self):
        return self.e["id"]

    def shape(self):
        trazador = QtGui.QPainterPathStroker()
        trazador.setWidth(max(self.e["grosor"], 10 / max(self.lienzo.zoom(), 0.05)))
        return trazador.createStroke(self.path())

    def paint(self, p, opciones, widget=None):
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        if self.isSelected() and not self.lienzo.exportando:
            p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 70), self.e["grosor"] + 6, Qt.SolidLine, Qt.RoundCap,
                                Qt.RoundJoin))
            p.drawPath(self.path())
        p.setPen(self.pen())
        p.drawPath(self.path())

    def itemChange(self, cambio, valor):
        if cambio == QtWidgets.QGraphicsItem.ItemSelectedHasChanged and self.lienzo is not None:
            self.lienzo.seleccion_tocada()
        return super(ItemTrazo, self).itemChange(cambio, valor)


def camino_suave(puntos):
    camino = QtGui.QPainterPath()
    if not puntos:
        return camino
    camino.moveTo(QPointF(*puntos[0]))
    if len(puntos) == 1:
        camino.lineTo(QPointF(puntos[0][0] + 0.1, puntos[0][1]))
        return camino
    for i in range(1, len(puntos) - 1):
        medio = QPointF((puntos[i][0] + puntos[i + 1][0]) / 2.0, (puntos[i][1] + puntos[i + 1][1]) / 2.0)
        camino.quadTo(QPointF(*puntos[i]), medio)
    camino.lineTo(QPointF(*puntos[-1]))
    return camino


# --- Líneas de los marcadores a sus notas ----------------------------------------------

class ItemConexiones(QtWidgets.QGraphicsItem):
    def __init__(self, lienzo):
        super(ItemConexiones, self).__init__()
        self.lienzo = lienzo
        self.lineas = []
        self.setAcceptedMouseButtons(Qt.NoButton)

    def fijar(self, lineas):
        self.prepareGeometryChange()
        self.lineas = lineas
        self.update()

    def boundingRect(self):
        if not self.lineas:
            return QRectF()
        xs = [p.x() for l in self.lineas for p in l]
        ys = [p.y() for l in self.lineas for p in l]
        return QRectF(min(xs) - 4, min(ys) - 4, max(xs) - min(xs) + 8, max(ys) - min(ys) + 8)

    def paint(self, p, _opciones, _widget=None):
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        for a, b in self.lineas:
            p.setPen(pluma_fina(QtGui.QColor(244, 244, 244, 140)))
            p.drawLine(a, b)
            p.setPen(Qt.NoPen)
            p.setBrush(BLANCO)
            r = 2.5 / max(self.lienzo.zoom(), 0.05)
            p.drawEllipse(b, r, r)
