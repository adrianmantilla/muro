"""Modo fantasma: el tablero, transparente, encima del visor de Maya.

Una ventana sin marco y sin fondo muestra las referencias con poca opacidad
encima del visor y deja pasar los clics a Maya. Una pastilla pequeña permite
cambiar la opacidad, «Ajustar» (mover y acercar las referencias con el ratón;
mientras tanto los clics no llegan a Maya) y salir.
"""

from muro import iconos
from muro.i18n import t
from muro.qt import QtCore, QtGui, QtWidgets

Qt = QtCore.Qt


def _banderas(pasa_clics):
    banderas = Qt.Tool | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint | Qt.WindowDoesNotAcceptFocus
    if pasa_clics:
        banderas |= Qt.WindowTransparentForInput
    return banderas


class CapaFantasma(QtWidgets.QGraphicsView):
    def __init__(self, lienzo, padre=None):
        super(CapaFantasma, self).__init__(lienzo.escena, padre)
        self.lienzo = lienzo
        self.setWindowFlags(_banderas(True))
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setStyleSheet("QGraphicsView{background:transparent;border:0}")
        self.viewport().setAutoFillBackground(False)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.NoAnchor)
        self.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.SmoothPixmapTransform)
        self.setInteractive(False)
        self._pan = None

    def drawBackground(self, p, rect):
        pass

    def zoom(self):
        return self.transform().m11()

    def mousePressEvent(self, evento):
        self._pan = evento.position().toPoint() if hasattr(evento, "position") else evento.pos()

    def mouseMoveEvent(self, evento):
        if self._pan is None:
            return
        pos = evento.position().toPoint() if hasattr(evento, "position") else evento.pos()
        z = self.zoom()
        self.translate((pos.x() - self._pan.x()) / z, (pos.y() - self._pan.y()) / z)
        self._pan = pos

    def mouseReleaseEvent(self, _evento):
        self._pan = None

    def wheelEvent(self, evento):
        pos = evento.position().toPoint() if hasattr(evento, "position") else evento.pos()
        pixeles = evento.pixelDelta()
        if not pixeles.isNull() and not (evento.modifiers() & (Qt.ControlModifier | Qt.MetaModifier)):
            z = self.zoom()
            self.translate(pixeles.x() / z, pixeles.y() / z)
            return
        pasos = evento.angleDelta().y() / 120.0 or pixeles.y() / 60.0
        antes = self.mapToScene(pos)
        factor = 1.15 ** pasos
        self.scale(factor, factor)
        despues = self.mapToScene(pos)
        d = despues - antes
        self.translate(d.x(), d.y())


class ControlFantasma(QtWidgets.QWidget):
    """Pastilla con salir, opacidad y ajustar."""
    salir = QtCore.Signal()
    opacidad = QtCore.Signal(float)
    ajustar = QtCore.Signal(bool)

    def __init__(self, opacidad_inicial, padre=None):
        super(ControlFantasma, self).__init__(padre, Qt.Tool | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        fila = QtWidgets.QHBoxLayout(self)
        fila.setContentsMargins(6, 4, 12, 4)
        fila.setSpacing(6)
        self.boton_salir = _boton("fantasma", t("fantasma_salir"))
        self.boton_salir.setChecked(True)
        self.boton_salir.clicked.connect(self.salir.emit)
        fila.addWidget(self.boton_salir)
        etiqueta = QtWidgets.QLabel(t("fantasma_opacidad"))
        etiqueta.setStyleSheet("color:#cfd3d7;font-size:11px;background:transparent")
        fila.addWidget(etiqueta)
        self.deslizador = QtWidgets.QSlider(Qt.Horizontal)
        self.deslizador.setRange(10, 95)
        self.deslizador.setValue(int(round(opacidad_inicial * 100)))
        self.deslizador.setFixedWidth(110)
        self.deslizador.valueChanged.connect(lambda v: self.opacidad.emit(v / 100.0))
        fila.addWidget(self.deslizador)
        self.boton_ajustar = _boton("ajustar", t("fantasma_ajustar"))
        self.boton_ajustar.toggled.connect(self.ajustar.emit)
        fila.addWidget(self.boton_ajustar)
        self.adjustSize()

    def paintEvent(self, _evento):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        r = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 40), 1))
        p.setBrush(QtGui.QColor(16, 17, 19, 205))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        p.end()


def _boton(icono, ayuda):
    boton = QtWidgets.QToolButton()
    boton.setIcon(iconos.icono(icono))
    boton.setIconSize(QtCore.QSize(17, 17))
    boton.setCheckable(True)
    boton.setAutoRaise(True)
    boton.setToolTip(ayuda)
    boton.setFixedSize(30, 30)
    boton.setStyleSheet(ESTILO_BOTON)
    return boton


ESTILO_BOTON = ("QToolButton{border:0;border-radius:15px;background:transparent}"
                "QToolButton:hover,QToolButton:checked{background:#f4f4f4}")


class Fantasma(QtCore.QObject):
    terminado = QtCore.Signal()

    def __init__(self, lienzo, servicios, opacidad=0.5, padre_ventanas=None):
        super(Fantasma, self).__init__()
        self.lienzo = lienzo
        self.servicios = servicios
        self.opacidad = opacidad
        self.capa = CapaFantasma(lienzo, padre_ventanas)
        self.control = ControlFantasma(opacidad, padre_ventanas)
        self.control.salir.connect(self.salir)
        self.control.opacidad.connect(self.fijar_opacidad)
        self.control.ajustar.connect(self.fijar_ajuste)
        self.reloj = QtCore.QTimer(self)
        self.reloj.setInterval(400)
        self.reloj.timeout.connect(self.seguir_visor)
        self.activo = False
        self._ultimo = None

    def rect_destino(self):
        rect = self.servicios.geometria_visor()
        if rect is None or rect.isEmpty():
            ventana = self.lienzo.window()
            arriba = self.lienzo.mapToGlobal(QtCore.QPoint(0, 0))
            rect = QtCore.QRect(arriba, self.lienzo.size()) if ventana else QtCore.QRect(100, 100, 800, 600)
        return rect

    def iniciar(self):
        self.lienzo.escena.clearSelection()
        rect = self.rect_destino()
        centro = self.lienzo.centro_escena()
        self.capa.setGeometry(rect)
        self.capa.setTransform(QtGui.QTransform.fromScale(self.lienzo.zoom(), self.lienzo.zoom()))
        self.capa.centerOn(centro)
        self.capa.setWindowOpacity(self.opacidad)
        self.capa.show()
        self.colocar_control(rect)
        self.control.show()
        self.control.raise_()
        self.activo = True
        self._ultimo = rect
        self.reloj.start()

    def colocar_control(self, rect):
        self.control.adjustSize()
        self.control.move(rect.left() + 12, rect.top() + 12)

    def seguir_visor(self):
        if not self.activo or self.control.boton_ajustar.isChecked():
            return
        rect = self.rect_destino()
        if rect != self._ultimo:
            centro = self.capa.mapToScene(self.capa.viewport().rect().center())
            self.capa.setGeometry(rect)
            self.capa.centerOn(centro)
            self.colocar_control(rect)
            self._ultimo = rect

    def fijar_opacidad(self, valor):
        self.opacidad = valor
        self.capa.setWindowOpacity(valor)

    def fijar_ajuste(self, ajustando):
        geometria = self.capa.geometry()
        visible = self.capa.isVisible()
        self.capa.setWindowFlags(_banderas(not ajustando))
        self.capa.setGeometry(geometria)
        self.capa.setWindowOpacity(self.opacidad)
        self.capa.setCursor(Qt.OpenHandCursor if ajustando else Qt.ArrowCursor)
        if visible:
            self.capa.show()
        self.control.raise_()

    def salir(self):
        if not self.activo:
            return
        self.activo = False
        self.reloj.stop()
        self.capa.hide()
        self.control.hide()
        self.terminado.emit()

    def destruir(self):
        self.salir()
        for widget in (self.capa, self.control):
            widget.setParent(None)
            widget.deleteLater()


