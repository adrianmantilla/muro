"""Diálogo «Plano de imagen»: marcar dos puntos, decir cuánto miden y elegir cámara."""

from muro import escala, estilo
from muro.i18n import t
from muro.qt import QtCore, QtGui, QtWidgets, posicion_local

Qt = QtCore.Qt

UNIDADES = ("m", "cm", "mm", "ft", "in")


class VistaPuntos(QtWidgets.QWidget):
    """La referencia con los dos puntos que dan la escala (A arriba, B abajo)."""
    cambiado = QtCore.Signal()

    def __init__(self, imagen, padre=None):
        super(VistaPuntos, self).__init__(padre)
        self.imagen = imagen
        self.pixmap = QtGui.QPixmap.fromImage(imagen)
        self.puntos = [QtCore.QPointF(imagen.width() / 2.0, 0.0),
                       QtCore.QPointF(imagen.width() / 2.0, float(imagen.height()))]
        self.siguiente = 0
        self.setMinimumSize(320, 320)
        self.setCursor(Qt.CrossCursor)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

    def zona(self):
        """Rectángulo del widget donde se dibuja la imagen, manteniendo proporción."""
        w, h = self.imagen.width(), self.imagen.height()
        escala_v = min(self.width() / float(w), self.height() / float(h))
        ancho, alto = w * escala_v, h * escala_v
        return QtCore.QRectF((self.width() - ancho) / 2, (self.height() - alto) / 2, ancho, alto), escala_v

    def a_widget(self, punto):
        zona, e = self.zona()
        return QtCore.QPointF(zona.x() + punto.x() * e, zona.y() + punto.y() * e)

    def a_imagen(self, punto):
        zona, e = self.zona()
        x = min(max((punto.x() - zona.x()) / e, 0.0), float(self.imagen.width()))
        y = min(max((punto.y() - zona.y()) / e, 0.0), float(self.imagen.height()))
        return QtCore.QPointF(x, y)

    def mousePressEvent(self, evento):
        pos = QtCore.QPointF(posicion_local(evento))
        # Si se pulsa cerca de un punto, se arrastra ese; si no, se coloca el siguiente.
        for i, punto in enumerate(self.puntos):
            if (self.a_widget(punto) - pos).manhattanLength() < 14:
                self.siguiente = i
                break
        self.puntos[self.siguiente] = self.a_imagen(pos)
        self._arrastrando = self.siguiente
        self.update()
        self.cambiado.emit()

    def mouseMoveEvent(self, evento):
        if getattr(self, "_arrastrando", None) is not None:
            self.puntos[self._arrastrando] = self.a_imagen(QtCore.QPointF(posicion_local(evento)))
            self.update()
            self.cambiado.emit()

    def mouseReleaseEvent(self, _evento):
        if getattr(self, "_arrastrando", None) is not None:
            self.siguiente = 1 - self._arrastrando
        self._arrastrando = None

    def paintEvent(self, _evento):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), QtGui.QColor(26, 27, 29))
        zona, _ = self.zona()
        p.drawPixmap(zona, self.pixmap, QtCore.QRectF(self.pixmap.rect()))
        a, b = self.a_widget(self.puntos[0]), self.a_widget(self.puntos[1])
        p.setPen(QtGui.QPen(QtGui.QColor(255, 90, 79), 1.5, Qt.DashLine))
        p.drawLine(a, b)
        for punto, letra in ((a, "A"), (b, "B")):
            p.setPen(QtGui.QPen(QtGui.QColor(16, 17, 19, 160), 3))
            p.setBrush(QtGui.QColor(244, 244, 244))
            p.drawEllipse(punto, 9, 9)
            p.setPen(QtGui.QColor(20, 20, 20))
            p.drawText(QtCore.QRectF(punto.x() - 9, punto.y() - 9, 18, 18), Qt.AlignCenter, letra)
        p.end()


class DialogoPlano(QtWidgets.QDialog):
    def __init__(self, imagen, nombre, ajustes=None, gris_inicial=False, unidad_escena="cm", padre=None):
        super(DialogoPlano, self).__init__(padre)
        self.setWindowTitle(t("plano_titulo", nombre=nombre))
        self.ajustes = ajustes
        self.unidad_escena = unidad_escena
        estilo.aplicar(self, "MuroDialogoPlano")
        self.vista = VistaPuntos(imagen)
        disposicion = QtWidgets.QVBoxLayout(self)
        ayuda = QtWidgets.QLabel(t("plano_ayuda"))
        ayuda.setWordWrap(True)
        disposicion.addWidget(ayuda)
        disposicion.addWidget(self.vista, 1)

        formulario = estilo.formulario()
        fila_altura = QtWidgets.QHBoxLayout()
        self.altura = QtWidgets.QDoubleSpinBox()
        self.altura.setDecimals(3)
        self.altura.setRange(0.001, 100000.0)
        self.unidad = QtWidgets.QComboBox()
        self.unidad.addItems(UNIDADES)
        altura = ajustes["altura_plano"] if ajustes else 1.8
        unidad = ajustes["unidad_altura"] if ajustes else "m"
        self.altura.setValue(float(altura))
        self.unidad.setCurrentText(unidad if unidad in UNIDADES else "m")
        fila_altura.addWidget(self.altura, 1)
        fila_altura.addWidget(self.unidad)
        formulario.addRow(t("plano_altura"), fila_altura)

        self.camaras = QtWidgets.QButtonGroup(self)
        fila_camara = QtWidgets.QHBoxLayout()
        for i, nombre_camara in enumerate(escala.CAMARAS):
            boton = QtWidgets.QRadioButton(nombre_camara)
            boton.setChecked(i == 0)
            self.camaras.addButton(boton, i)
            fila_camara.addWidget(boton)
        fila_camara.addStretch(1)
        formulario.addRow(t("plano_camara"), fila_camara)

        self.opacidad = QtWidgets.QDoubleSpinBox()
        self.opacidad.setRange(0.05, 1.0)
        self.opacidad.setSingleStep(0.05)
        self.opacidad.setValue(0.5)
        formulario.addRow(t("plano_opacidad"), self.opacidad)
        self.gris = QtWidgets.QCheckBox(t("plano_gris"))
        self.gris.setChecked(gris_inicial)
        formulario.addRow("", self.gris)
        self.capa = QtWidgets.QCheckBox(t("plano_capa"))
        self.capa.setChecked(True)
        formulario.addRow("", self.capa)
        disposicion.addLayout(formulario)

        self.resumen = QtWidgets.QLabel()
        estilo.rol(self.resumen, "tenue")
        disposicion.addWidget(self.resumen)
        botones = QtWidgets.QDialogButtonBox()
        estilo.primario(botones.addButton(t("boton_crear"), QtWidgets.QDialogButtonBox.AcceptRole))
        botones.addButton(t("boton_cancelar"), QtWidgets.QDialogButtonBox.RejectRole)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        disposicion.addWidget(botones)
        for senal in (self.vista.cambiado, self.altura.valueChanged, self.unidad.currentTextChanged):
            senal.connect(self.actualizar)
        self.camaras.buttonClicked.connect(lambda *_: self.actualizar())
        self.resize(560, 680)
        self.actualizar()

    def parametros(self):
        a, b = self.vista.puntos
        camara = escala.CAMARAS[max(0, self.camaras.checkedId())]
        altura = escala.convertir(self.altura.value(), self.unidad.currentText(), self.unidad_escena)
        return {"punto_a": (a.x(), a.y()), "punto_b": (b.x(), b.y()), "altura": altura,
                "camara": camara, "opacidad": self.opacidad.value(), "gris": self.gris.isChecked(),
                "capa": self.capa.isChecked(), "px": (self.vista.imagen.width(), self.vista.imagen.height())}

    def actualizar(self, *_):
        p = self.parametros()
        try:
            datos = escala.plano_de_imagen(p["px"][0], p["px"][1], p["punto_a"], p["punto_b"], p["altura"],
                                           p["camara"])
            self.resumen.setText(t("plano_resumen", ancho=datos["ancho"], alto=datos["alto"],
                                   unidad=self.unidad_escena))
        except ValueError as error:
            self.resumen.setText(str(error))

    def accept(self):
        if self.ajustes is not None:
            self.ajustes["altura_plano"] = self.altura.value()
            self.ajustes["unidad_altura"] = self.unidad.currentText()
        super(DialogoPlano, self).accept()
