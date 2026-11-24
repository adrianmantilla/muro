"""Menú de clic derecho: seis puntos alrededor del cursor, como Radial (estilo Puntos).

Los puntos son discretos; al pasar por encima crecen, se vuelven blancos con
el icono en oscuro y el nombre de la acción aparece en el centro.
"""

import math

from muro import iconos
from muro.qt import QtCore, QtGui, QtWidgets, posicion_local

Qt = QtCore.Qt

RADIO = 58
PUNTO = 9
ABIERTO = 18
LADO = 2 * (RADIO + ABIERTO + 6)


class MenuRadial(QtWidgets.QWidget):
    """``acciones`` es una lista de hasta seis ``(icono, nombre, funcion)``."""

    def __init__(self, acciones, padre=None):
        super(MenuRadial, self).__init__(padre, Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setMouseTracking(True)
        self.setFixedSize(LADO, LADO)
        self.acciones = list(acciones)[:6]
        self.sobre = -1
        self.elegida = None

    def centros(self):
        c = QtCore.QPointF(LADO / 2.0, LADO / 2.0)
        puntos = []
        for i in range(len(self.acciones)):
            angulo = -math.pi / 2 + i * 2 * math.pi / 6
            puntos.append(c + QtCore.QPointF(math.cos(angulo) * RADIO, math.sin(angulo) * RADIO))
        return puntos

    def abrir(self, posicion_global):
        self.move(posicion_global - QtCore.QPoint(LADO // 2, LADO // 2))
        self.show()
        self.setFocus()

    def boton_en(self, punto):
        for i, c in enumerate(self.centros()):
            if (QtCore.QPointF(punto) - c).manhattanLength() < ABIERTO * 1.6:
                return i
        return -1

    def mouseMoveEvent(self, evento):
        i = self.boton_en(posicion_local(evento))
        if i != self.sobre:
            self.sobre = i
            self.update()

    def mouseReleaseEvent(self, evento):
        i = self.boton_en(posicion_local(evento))
        if evento.button() == Qt.LeftButton and i >= 0:
            self.ejecutar(i)
        elif not self.rect().contains(posicion_local(evento)):
            self.close()

    def mousePressEvent(self, evento):
        if not self.rect().contains(posicion_local(evento)):
            self.close()

    def keyPressEvent(self, evento):
        tecla = evento.key()
        if tecla == Qt.Key_Escape:
            self.close()
        elif tecla in (Qt.Key_Right, Qt.Key_Down, Qt.Key_Tab):
            self.sobre = (self.sobre + 1) % len(self.acciones)
            self.update()
        elif tecla in (Qt.Key_Left, Qt.Key_Up, Qt.Key_Backtab):
            self.sobre = (self.sobre - 1) % len(self.acciones)
            self.update()
        elif tecla in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space) and self.sobre >= 0:
            self.ejecutar(self.sobre)
        elif Qt.Key_1 <= tecla <= Qt.Key_6 and tecla - Qt.Key_1 < len(self.acciones):
            self.ejecutar(tecla - Qt.Key_1)

    def ejecutar(self, i):
        self.elegida = i
        funcion = self.acciones[i][2]
        self.close()
        QtCore.QTimer.singleShot(0, funcion)

    def paintEvent(self, _evento):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        c = QtCore.QPointF(LADO / 2.0, LADO / 2.0)
        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 40), 1))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(c, RADIO, RADIO)
        p.setPen(Qt.NoPen)
        p.setBrush(QtGui.QColor(16, 17, 19, 178))
        p.drawEllipse(c, 32, 32)
        for i, centro in enumerate(self.centros()):
            icono, nombre, _ = self.acciones[i]
            if i == self.sobre:
                p.setPen(Qt.NoPen)
                p.setBrush(QtGui.QColor(0, 0, 0, 90))
                p.drawEllipse(centro + QtCore.QPointF(0, 1.5), ABIERTO + 1, ABIERTO + 1)
                p.setBrush(QtGui.QColor(244, 244, 244))
                p.drawEllipse(centro, ABIERTO, ABIERTO)
                lado = 20
                iconos.dibujar(p, icono, QtCore.QRectF(centro.x() - lado / 2, centro.y() - lado / 2, lado, lado),
                               "#141414")
            else:
                p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 80), 1))
                p.setBrush(QtGui.QColor(16, 17, 19, 190))
                p.drawEllipse(centro, PUNTO, PUNTO)
        if self.sobre >= 0:
            p.setPen(QtGui.QColor(242, 242, 242))
            fuente = p.font()
            fuente.setPointSizeF(max(7.0, fuente.pointSizeF() * 0.85))
            p.setFont(fuente)
            p.drawText(QtCore.QRectF(c.x() - 30, c.y() - 22, 60, 44), Qt.AlignCenter | Qt.TextWordWrap,
                       self.acciones[self.sobre][1])
        p.end()
