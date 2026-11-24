"""Lienzo infinito del tablero: navegación, herramientas, deshacer y operaciones.

No depende de Maya. Lo que necesita de Maya (capturar el visor, aplicar un
color al material...) lo pide a ``self.servicios``, que fuera de Maya no hace
nada.
"""

import os
import time

from muro import archivo, items, modelo
from muro.i18n import t
from muro.qt import QtCore, QtGui, QtWidgets

Qt = QtCore.Qt
QPointF = QtCore.QPointF
QRectF = QtCore.QRectF

ZOOM_MIN = 0.03
ZOOM_MAX = 40.0
HERRAMIENTAS = ("seleccion", "flecha", "lapiz", "recortar", "cuentagotas")


class Servicios(object):
    """Lo que el tablero pide fuera de sí mismo. Fuera de Maya no hace nada."""
    en_maya = False

    def capturar_visor(self, carpeta):
        return None

    def aplicar_color(self, color_hex):
        return None

    def objeto_seleccionado(self):
        return None

    def seleccionar_objeto(self, objeto):
        return False

    def plano_de_imagen(self, ruta_png, parametros):
        return None

    def geometria_visor(self):
        return None

    def unidad_escena(self):
        return "cm"

    def ligar_escena(self, carpeta):
        return False


class Lienzo(QtWidgets.QGraphicsView):
    cambiado = QtCore.Signal()
    aviso = QtCore.Signal(str)
    seleccion = QtCore.Signal()
    herramienta_cambiada = QtCore.Signal(str)
    vista_cambiada = QtCore.Signal()
    color_tomado = QtCore.Signal(str)
    pide_menu = QtCore.Signal(object, object)  # (item o None, posición global)
    pide_plano = QtCore.Signal(object)  # elemento imagen

    def __init__(self, padre=None):
        super(Lienzo, self).__init__(padre)
        self.escena = QtWidgets.QGraphicsScene(self)
        self.escena.setSceneRect(-1e6, -1e6, 2e6, 2e6)
        self.escena.setItemIndexMethod(QtWidgets.QGraphicsScene.NoIndex)
        self.setScene(self.escena)
        self.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.SmoothPixmapTransform
                            | QtGui.QPainter.TextAntialiasing)
        self.setViewportUpdateMode(QtWidgets.QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.NoAnchor)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorViewCenter)
        self.setDragMode(QtWidgets.QGraphicsView.RubberBandDrag)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setStyleSheet("QGraphicsView{background:#1a1b1d;border:0}")
        self.escena.selectionChanged.connect(self.seleccion_tocada)

        self.servicios = Servicios()
        self.cache = items.CacheImagenes()
        self.historial = modelo.Historial()
        self.carpeta = None
        self.tablero = modelo.nuevo_tablero()
        self.items = {}
        self.conexiones = None
        self.exportando = False
        self.editando_id = None
        self.editor = None
        self.herramienta = "seleccion"
        self.tono_lapiz = 1
        self.grosor_lapiz = 3.0
        self._foto = None
        self._arrastre = None
        self._espacio = False
        self._hijos_marco = {}
        self._reconstruyendo = False
        self._provisional = None

    # --- Abrir ---------------------------------------------------------------------
    def abrir(self, carpeta):
        tablero = archivo.leer(carpeta)
        self.carpeta = carpeta
        self.cache.usar_carpeta(carpeta)
        self.tablero = tablero
        self.historial.vaciar()
        self.reconstruir()
        self.aplicar_vista(tablero["vista"])
        if not tablero["elementos"]:
            self.centrar_en(QPointF(0, 0))

    def guardar(self):
        if self.carpeta is None:
            return False
        self.tablero["vista"] = self.vista_actual()
        archivo.guardar(self.carpeta, self.tablero)
        return True

    # --- Vista ---------------------------------------------------------------------
    def zoom(self):
        return self.transform().m11()

    def vista_actual(self):
        centro = self.mapToScene(self.viewport().rect().center())
        return {"x": centro.x(), "y": centro.y(), "zoom": self.zoom()}

    def aplicar_vista(self, vista):
        self.setTransform(QtGui.QTransform.fromScale(vista["zoom"], vista["zoom"]))
        self.centrar_en(QPointF(vista["x"], vista["y"]))

    def centrar_en(self, punto):
        self.centerOn(punto)
        self.vista_cambiada.emit()

    def zoom_en(self, factor, punto_vista=None):
        actual = self.zoom()
        nuevo = max(ZOOM_MIN, min(ZOOM_MAX, actual * factor))
        factor = nuevo / actual
        if abs(factor - 1.0) < 1e-6:
            return
        if punto_vista is None:
            punto_vista = self.viewport().rect().center()
        antes = self.mapToScene(punto_vista)
        self.scale(factor, factor)
        despues = self.mapToScene(punto_vista)
        self.desplazar_escena(despues - antes)
        self.vista_cambiada.emit()

    def desplazar_escena(self, delta):
        """Mueve la vista para que el contenido se desplace ``-delta`` (en unidades del tablero)."""
        self.translate(delta.x(), delta.y())

    def desplazar_pixeles(self, dx, dy):
        z = self.zoom()
        self.translate(dx / z, dy / z)
        self.vista_cambiada.emit()

    def encuadrar(self, elementos=None):
        if elementos is None:
            elementos = self.seleccionados() or self.tablero["elementos"]
        caja = self.caja_items([self.items[e["id"]] for e in elementos if e["id"] in self.items])
        if caja is None or caja.isEmpty():
            return
        margen = 40
        vista = self.viewport().rect().adjusted(margen, margen, -margen, -margen)
        z = min(vista.width() / max(caja.width(), 1), vista.height() / max(caja.height(), 1))
        z = max(ZOOM_MIN, min(ZOOM_MAX, z))
        self.setTransform(QtGui.QTransform.fromScale(z, z))
        self.centerOn(caja.center())
        self.vista_cambiada.emit()

    def caja_items(self, lista):
        caja = None
        for item in lista:
            r = item.mapToScene(item.rect()).boundingRect() if hasattr(item, "rect") else item.sceneBoundingRect()
            if isinstance(item, items.ItemMarco):
                r = r.united(item.mapToScene(item.rect_titulo()).boundingRect())
            caja = r if caja is None else caja.united(r)
        return caja

    def drawBackground(self, p, rect):
        p.fillRect(rect, items.FONDO_TABLERO)
        z = self.zoom()
        paso = 24.0
        while paso * z < 14:
            paso *= 4
        if paso * z > 200:
            return
        p.setPen(Qt.NoPen)
        alfa = int(min(1.0, (paso * z - 14) / 20.0) * 26) + 8
        p.setBrush(QtGui.QColor(255, 255, 255, alfa))
        x0 = int(rect.left() // paso) * paso
        y0 = int(rect.top() // paso) * paso
        r = 1.1 / z
        y = y0
        puntos = []
        while y < rect.bottom():
            x = x0
            while x < rect.right():
                puntos.append(QPointF(x, y))
                x += paso
            y += paso
        if len(puntos) < 20000:
            for punto in puntos:
                p.drawEllipse(punto, r, r)

    # --- Construir la escena a partir del modelo ---------------------------------------
    def reconstruir(self):
        self._reconstruyendo = True
        seleccion = {i.id for i in self.escena.selectedItems() if hasattr(i, "id")}
        if self.editor is not None:
            self.editor.terminado = True
            self.editor = None
            self.editando_id = None
        self.escena.clear()
        self.items = {}
        numeros = {}
        for e in self.tablero["elementos"]:
            if e["tipo"] == "imagen":
                for m in e["marcadores"]:
                    if m["nota"]:
                        numeros[m["nota"]] = m["n"]
        total = len(self.tablero["elementos"])
        for indice, e in enumerate(self.tablero["elementos"]):
            item = None
            if e["tipo"] == "imagen":
                item = items.ItemImagen(self, e)
            elif e["tipo"] == "nota":
                item = items.ItemNota(self, e, numeros.get(e["id"]))
            elif e["tipo"] == "marco":
                item = items.ItemMarco(self, e)
            elif e["tipo"] == "flecha":
                item = items.ItemFlecha(self, e)
            elif e["tipo"] == "trazo":
                continue
            item.setZValue(indice - (10 * total + 10) if e["tipo"] == "marco" else indice)
            self.escena.addItem(item)
            self.items[e["id"]] = item
        for indice, e in enumerate(self.tablero["elementos"]):
            if e["tipo"] != "trazo":
                continue
            padre = self.items.get(e["padre"]) if e["padre"] else None
            item = items.ItemTrazo(self, e, padre)
            if padre is None:
                self.escena.addItem(item)
                item.setZValue(indice)
            else:
                item.setZValue(1)
            self.items[e["id"]] = item
        self.conexiones = items.ItemConexiones(self)
        self.conexiones.setZValue(total + 5)
        self.escena.addItem(self.conexiones)
        for identificador in seleccion:
            if identificador in self.items:
                self.items[identificador].setSelected(True)
        self._reconstruyendo = False
        self.actualizar_conexiones()
        self.seleccion.emit()

    def actualizar_conexiones(self):
        if self.conexiones is None:
            return
        lineas = []
        for e in self.tablero["elementos"]:
            if e["tipo"] != "imagen" or e["id"] not in self.items:
                continue
            item = self.items[e["id"]]
            for m in e["marcadores"]:
                nota = self.items.get(m["nota"])
                if nota is None:
                    continue
                local = item.punto_marcador(m)
                if not item.rect().adjusted(-1, -1, 1, 1).contains(local):
                    continue
                a = item.mapToScene(local)
                caja = nota.mapToScene(nota.rect()).boundingRect()
                b = QPointF(min(max(a.x(), caja.left()), caja.right()), min(max(a.y(), caja.top()), caja.bottom()))
                if (a - b).manhattanLength() > 12:
                    lineas.append((a, b))
        self.conexiones.fijar(lineas)
        for e in self.tablero["elementos"]:
            if e["tipo"] == "flecha" and e["id"] in self.items:
                self.colocar_flecha(self.items[e["id"]])

    def colocar_flecha(self, item):
        e = item.e
        origen = self.items.get(e["desde"]) if e["desde"] else None
        destino = self.items.get(e["hasta"]) if e["hasta"] else None
        a = QPointF(*e["p0"])
        b = QPointF(*e["p1"])
        centro_a = origen.mapToScene(origen.rect().center()) if origen else a
        centro_b = destino.mapToScene(destino.rect().center()) if destino else b
        if origen is not None:
            a = items.borde_hacia(origen, centro_b)
        if destino is not None:
            b = items.borde_hacia(destino, centro_a)
        item.fijar(a, b)

    # --- Consultas -------------------------------------------------------------------
    def seleccionados(self):
        ids = [i.id for i in self.escena.selectedItems() if hasattr(i, "id")]
        return [e for e in self.tablero["elementos"] if e["id"] in ids]

    def seleccion_unica(self):
        elegidos = self.escena.selectedItems()
        return elegidos[0] if len(elegidos) == 1 else None

    def seleccionar(self, ids):
        self.escena.clearSelection()
        for identificador in ids:
            if identificador in self.items:
                self.items[identificador].setSelected(True)

    def seleccion_tocada(self):
        if self._reconstruyendo:
            return
        for item in self.escena.selectedItems():
            item.update()
        self.viewport().update()
        self.seleccion.emit()

    def item_en(self, pos_vista, tipos=None):
        for item in self.items_en(pos_vista):
            if tipos is None or (hasattr(item, "e") and item.e["tipo"] in tipos):
                return item
        return None

    def items_en(self, pos_vista):
        resultado = []
        for item in self.items_vista(pos_vista):
            while item is not None and not hasattr(item, "e"):
                item = item.parentItem()
            if item is not None and item is not self.editor and item not in resultado:
                resultado.append(item)
        return resultado

    def items_vista(self, pos_vista):
        return QtWidgets.QGraphicsView.items(self, pos_vista)

    def centro_escena(self):
        return self.mapToScene(self.viewport().rect().center())

    def posicion_raton(self):
        pos = self.viewport().mapFromGlobal(QtGui.QCursor.pos())
        if self.viewport().rect().contains(pos):
            return self.mapToScene(pos)
        return self.centro_escena()

    # --- Cambios con deshacer ---------------------------------------------------------
    def antes(self):
        self.historial.guardar(self.tablero)

    def despues(self, reconstruir=True):
        if reconstruir:
            self.reconstruir()
        self.cambiado.emit()

    def empezar_cambio(self):
        self._foto = modelo.a_json(self.tablero)

    def terminar_cambio(self):
        if self._foto is not None and self._foto != modelo.a_json(self.tablero):
            self.historial.guardar_foto(self._foto)
            self.cambiado.emit()
        self._foto = None
        self.actualizar_conexiones()

    def volcar_posiciones(self):
        """Pasa al modelo lo que el ratón ha movido en Qt. Devuelve True si algo cambió."""
        cambio = False
        for item in self.items.values():
            e = item.e
            if e["tipo"] in ("flecha",):
                continue
            if e["tipo"] == "trazo":
                if item.parentItem() is None and (item.pos().x() or item.pos().y()):
                    dx, dy = item.pos().x(), item.pos().y()
                    e["puntos"] = [[x + dx, y + dy] for x, y in e["puntos"]]
                    item.setPos(0, 0)
                    item.setPath(items.camino_suave(e["puntos"]))
                    cambio = True
                continue
            x, y = item.pos().x(), item.pos().y()
            if abs(x - e["x"]) > 1e-6 or abs(y - e["y"]) > 1e-6:
                e["x"], e["y"] = x, y
                cambio = True
        return cambio

    def deshacer(self):
        self.cancelar_edicion()
        anterior = self.historial.deshacer(self.tablero)
        if anterior is None:
            self.aviso.emit(t("nada_que_deshacer"))
            return
        self.tablero = modelo.normalizar(anterior)
        self.despues()

    def rehacer(self):
        self.cancelar_edicion()
        siguiente = self.historial.rehacer(self.tablero)
        if siguiente is None:
            return
        self.tablero = modelo.normalizar(siguiente)
        self.despues()

    def posicion_cambiada(self, item):
        if self._reconstruyendo:
            return
        hijos = self._hijos_marco.get(getattr(item, "id", None))
        if hijos:
            inicio, lista = hijos
            delta = item.pos() - inicio
            for hijo, pos in lista:
                hijo.setPos(pos + delta)
        self.actualizar_conexiones()

    # --- Ratón ---------------------------------------------------------------------------
    def mousePressEvent(self, evento):
        boton = evento.button()
        mods = evento.modifiers()
        pos = evento.position().toPoint() if hasattr(evento, "position") else evento.pos()
        if self.editor is not None and not self.editor.isUnderMouse():
            self.editor.terminar(True)
        if boton == Qt.MiddleButton or (boton == Qt.LeftButton and (mods & Qt.AltModifier or self._espacio)):
            self._arrastre = ("pan", pos)
            self.viewport().setCursor(Qt.ClosedHandCursor)
            evento.accept()
            return
        if boton == Qt.RightButton and mods & Qt.AltModifier:
            self._arrastre = ("zoom", pos, self.zoom(), self.mapToScene(pos), pos)
            evento.accept()
            return
        if boton == Qt.RightButton:
            item = self.item_en(pos)
            if item is not None and not item.isSelected():
                self.seleccionar([item.id])
            self._punto_menu = self.mapToScene(pos)
            self.pide_menu.emit(item, self.viewport().mapToGlobal(pos))
            evento.accept()
            return
        if boton == Qt.LeftButton and self.herramienta != "seleccion":
            self.empezar_herramienta(pos)
            evento.accept()
            return
        if boton == Qt.LeftButton:
            self.empezar_cambio()
            item = self.item_en(pos)
            super(Lienzo, self).mousePressEvent(evento)
            self._preparar_marcos()
            self._clic = (pos, item)
            return
        super(Lienzo, self).mousePressEvent(evento)

    def _preparar_marcos(self):
        """Al empezar a mover marcos, apunta lo que llevan dentro para moverlo con ellos."""
        self._hijos_marco = {}
        elegidos = set(i.id for i in self.escena.selectedItems() if hasattr(i, "id"))
        for item in self.escena.selectedItems():
            if isinstance(item, items.ItemMarco):
                dentro = []
                for e in modelo.dentro_de_marco(self.tablero, item.e):
                    hijo = self.items.get(e["id"])
                    if hijo is not None and e["id"] not in elegidos and (hijo.flags() & QtWidgets.QGraphicsItem.ItemIsMovable):
                        dentro.append((hijo, QPointF(hijo.pos())))
                self._hijos_marco[item.id] = (QPointF(item.pos()), dentro)

    def mouseMoveEvent(self, evento):
        pos = evento.position().toPoint() if hasattr(evento, "position") else evento.pos()
        if self._arrastre and self._arrastre[0] == "pan":
            anterior = self._arrastre[1]
            self.desplazar_pixeles(pos.x() - anterior.x(), pos.y() - anterior.y())
            self._arrastre = ("pan", pos)
            return
        if self._arrastre and self._arrastre[0] == "zoom":
            _, inicio, zoom0, ancla, ancla_vista = self._arrastre
            factor = 2 ** ((pos.x() - inicio.x() - (pos.y() - inicio.y())) / 150.0)
            self.zoom_en(zoom0 * factor / self.zoom(), ancla_vista)
            return
        if self.herramienta != "seleccion" and self._provisional is not None:
            self.mover_herramienta(pos)
            return
        super(Lienzo, self).mouseMoveEvent(evento)

    def mouseReleaseEvent(self, evento):
        pos = evento.position().toPoint() if hasattr(evento, "position") else evento.pos()
        if self._arrastre:
            self._arrastre = None
            self.viewport().unsetCursor()
            self.vista_cambiada.emit()
            return
        if self.herramienta != "seleccion" and self._provisional is not None:
            self.terminar_herramienta(pos)
            return
        super(Lienzo, self).mouseReleaseEvent(evento)
        if evento.button() == Qt.LeftButton:
            movido = self.volcar_posiciones()
            self._hijos_marco = {}
            clic = getattr(self, "_clic", None)
            self._clic = None
            if movido:
                self.terminar_cambio()
            else:
                self._foto = None
                if clic is not None and clic[1] is not None and (clic[0] - pos).manhattanLength() < 4:
                    self.clic_simple(clic[1], self.mapToScene(pos))

    def clic_simple(self, item, punto):
        """Un clic sin arrastrar: marcar líneas de lista o ir al objeto ligado."""
        if isinstance(item, items.ItemNota):
            local = item.mapFromScene(punto)
            fila = item.fila_en(local)
            if fila >= 0 and not item.e["bloqueado"]:
                self.antes()
                item.e["texto"] = modelo.alternar_linea(item.e["texto"], fila)
                item.sincronizar()
                self.despues(reconstruir=False)
                self.actualizar_conexiones()
                return
            if item.e["objeto"] and item.rect_enlace().contains(local):
                if not self.servicios.seleccionar_objeto(item.e["objeto"]):
                    self.aviso.emit(t("objeto_no_encontrado", nombre=item.e["objeto"]["nombre"]))

    def mouseDoubleClickEvent(self, evento):
        pos = evento.position().toPoint() if hasattr(evento, "position") else evento.pos()
        if evento.button() != Qt.LeftButton or self.herramienta != "seleccion":
            return
        item = self.item_en(pos)
        if isinstance(item, items.ItemNota):
            self.editar_nota(item.e)
        elif isinstance(item, items.ItemMarco):
            self.editar_titulo(item.e)
        elif isinstance(item, items.ItemImagen):
            self.encuadrar([item.e])
        elif item is None:
            self.nueva_nota(self.mapToScene(pos))

    def wheelEvent(self, evento):
        pixeles = evento.pixelDelta()
        angulo = evento.angleDelta()
        pos = evento.position().toPoint() if hasattr(evento, "position") else evento.pos()
        if not pixeles.isNull() and not (evento.modifiers() & (Qt.ControlModifier | Qt.MetaModifier)):
            # Trackpad: dos dedos desplazan, pellizcar (o Ctrl) acerca.
            self.desplazar_pixeles(pixeles.x(), pixeles.y())
            return
        pasos = angulo.y() / 120.0 if angulo.y() else angulo.x() / 120.0
        if not pasos and not pixeles.isNull():
            pasos = pixeles.y() / 60.0
        self.zoom_en(1.15 ** pasos, pos)

    def viewportEvent(self, evento):
        if evento.type() == QtCore.QEvent.NativeGesture:
            try:
                if evento.gestureType() == Qt.ZoomNativeGesture:
                    pos = self.viewport().mapFromGlobal(evento.globalPosition().toPoint())
                    self.zoom_en(1.0 + evento.value(), pos)
                    return True
            except AttributeError:
                pass
        return super(Lienzo, self).viewportEvent(evento)

    # --- Herramientas: flecha, lápiz, recortar y cuentagotas ------------------------------
    def usar_herramienta(self, nombre):
        if nombre not in HERRAMIENTAS:
            nombre = "seleccion"
        if nombre == self.herramienta and nombre != "seleccion":
            nombre = "seleccion"
        self.herramienta = nombre
        self.setDragMode(QtWidgets.QGraphicsView.RubberBandDrag if nombre == "seleccion"
                         else QtWidgets.QGraphicsView.NoDrag)
        cursores = {"seleccion": Qt.ArrowCursor, "flecha": Qt.CrossCursor, "lapiz": Qt.CrossCursor,
                    "recortar": Qt.CrossCursor, "cuentagotas": Qt.PointingHandCursor}
        self.viewport().setCursor(cursores[nombre])
        self.herramienta_cambiada.emit(nombre)
        if nombre != "seleccion":
            self.aviso.emit(t("ayuda_" + nombre))

    def empezar_herramienta(self, pos):
        punto = self.mapToScene(pos)
        if self.herramienta == "cuentagotas":
            item = self.item_en(pos, ("imagen",))
            if item is None:
                self.aviso.emit(t("cuentagotas_fuera"))
                return
            self.tomar_color(item, punto)
            return
        if self.herramienta == "recortar":
            item = self.item_en(pos, ("imagen",))
            if item is None or item.e["bloqueado"]:
                self.aviso.emit(t("recortar_fuera"))
                return
            local = item.mapFromScene(punto)
            marco = QtWidgets.QGraphicsRectItem(item)
            pluma = items.pluma_fina(items.BLANCO)
            pluma.setStyle(Qt.DashLine)
            marco.setPen(pluma)
            marco.setBrush(QtGui.QColor(255, 255, 255, 30))
            marco.setZValue(10)
            self._provisional = ("recortar", item, local, marco)
            return
        if self.herramienta == "lapiz":
            item = self.item_en(pos, ("imagen",))
            camino = QtWidgets.QGraphicsPathItem()
            camino.setPen(QtGui.QPen(QtGui.QColor(modelo.TONOS_TRAZO[self.tono_lapiz]), self.grosor_lapiz,
                                     Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            camino.setZValue(1e6)
            self.escena.addItem(camino)
            self._provisional = ("lapiz", item, [punto], camino)
            return
        if self.herramienta == "flecha":
            item = self.item_en(pos, ("imagen", "nota", "marco"))
            linea = QtWidgets.QGraphicsLineItem(QtCore.QLineF(punto, punto))
            linea.setPen(QtGui.QPen(QtGui.QColor(modelo.TONOS_TRAZO[self.tono_lapiz]), 2))
            linea.setZValue(1e6)
            self.escena.addItem(linea)
            self._provisional = ("flecha", item, punto, linea)

    def mover_herramienta(self, pos):
        punto = self.mapToScene(pos)
        tipo = self._provisional[0]
        if tipo == "recortar":
            _, item, inicio, marco = self._provisional
            fin = item.mapFromScene(punto)
            r = QRectF(inicio, fin).normalized().intersected(item.rect())
            marco.setRect(r)
        elif tipo == "lapiz":
            _, _, puntos, camino = self._provisional
            ultimo = puntos[-1]
            if (punto - ultimo).manhattanLength() * self.zoom() >= 2:
                puntos.append(punto)
                camino.setPath(items.camino_suave([[p.x(), p.y()] for p in puntos]))
        elif tipo == "flecha":
            _, _, inicio, linea = self._provisional
            linea.setLine(QtCore.QLineF(inicio, punto))

    def terminar_herramienta(self, pos):
        punto = self.mapToScene(pos)
        tipo = self._provisional[0]
        provisional = self._provisional
        self._provisional = None
        if tipo == "recortar":
            _, item, _inicio, marco = provisional
            r = marco.rect()
            self.escena.removeItem(marco)
            if r.width() * self.zoom() < 6 or r.height() * self.zoom() < 6:
                return
            e = item.e
            u0, v0 = modelo.imagen_u(e, r.left() / e["ancho"]), modelo.imagen_v(e, r.top() / e["alto"])
            u1, v1 = modelo.imagen_u(e, r.right() / e["ancho"]), modelo.imagen_v(e, r.bottom() / e["alto"])
            self.antes()
            modelo.recortar(e, [min(u0, u1), v0, max(u0, u1), v1])
            self.despues()
            self.usar_herramienta("seleccion")
            return
        if tipo == "lapiz":
            _, item, puntos, camino = provisional
            self.escena.removeItem(camino)
            if item is not None:
                lista = [[q.x(), q.y()] for q in (item.mapFromScene(p) for p in puntos)]
                padre = item.id
            else:
                lista = [[p.x(), p.y()] for p in puntos]
                padre = None
            self.antes()
            modelo.crear(self.tablero, "trazo", puntos=lista, padre=padre, tono=self.tono_lapiz,
                         grosor=self.grosor_lapiz / (1.0 if padre is None else 1.0))
            self.despues()
            return
        if tipo == "flecha":
            _, desde, inicio, linea = provisional
            self.escena.removeItem(linea)
            hasta = self.item_en(pos, ("imagen", "nota", "marco"))
            if (punto - inicio).manhattanLength() * self.zoom() < 8 and (hasta is None or hasta is desde):
                return
            if hasta is desde:
                hasta = None
            self.antes()
            modelo.crear(self.tablero, "flecha", desde=desde.id if desde else None, hasta=hasta.id if hasta else None,
                         p0=[inicio.x(), inicio.y()], p1=[punto.x(), punto.y()], tono=self.tono_lapiz)
            self.despues()

    def tomar_color(self, item, punto):
        uv = item.uv_en(item.mapFromScene(punto))
        if uv is None:
            return
        imagen = self.cache.original(item.e["archivo"])
        if imagen.isNull():
            return
        x = min(imagen.width() - 1, max(0, int(uv[0] * imagen.width())))
        y = min(imagen.height() - 1, max(0, int(uv[1] * imagen.height())))
        color = imagen.pixelColor(x, y)
        r, g, b = color.redF(), color.greenF(), color.blueF()
        if item.e["gris"]:
            from muro import escala
            r, g, b = escala.gris(r, g, b)
        from muro import escala
        valor = escala.rgb_a_hex(r, g, b)
        muestras = [m for m in self.tablero["muestras"] if m != valor] + [valor]
        self.tablero["muestras"] = muestras[-12:]
        self.cambiado.emit()
        self.color_tomado.emit(valor)

    # --- Teclado -------------------------------------------------------------------------
    TECLAS_PROPIAS = (Qt.Key_F, Qt.Key_A, Qt.Key_N, Qt.Key_L, Qt.Key_G, Qt.Key_H, Qt.Key_P, Qt.Key_W, Qt.Key_C,
                      Qt.Key_I, Qt.Key_V, Qt.Key_Z, Qt.Key_Y, Qt.Key_D, Qt.Key_Delete, Qt.Key_Backspace,
                      Qt.Key_Escape, Qt.Key_Space, Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down)

    def event(self, evento):
        # En Maya los atajos de la aplicación se llevarían estas teclas: las pedimos para el tablero.
        if evento.type() == QtCore.QEvent.ShortcutOverride:
            mods = evento.modifiers()
            if evento.key() in self.TECLAS_PROPIAS and not (mods & Qt.AltModifier):
                evento.accept()
                return True
            if isinstance(self.escena.focusItem(), items.EditorTexto):
                evento.accept()
                return True
        return super(Lienzo, self).event(evento)

    def keyPressEvent(self, evento):
        foco = self.escena.focusItem()
        if isinstance(foco, items.EditorTexto):
            super(Lienzo, self).keyPressEvent(evento)
            return
        tecla = evento.key()
        mods = evento.modifiers()
        control = bool(mods & (Qt.ControlModifier | Qt.MetaModifier))
        if tecla == Qt.Key_Space and not evento.isAutoRepeat():
            self._espacio = True
            self.viewport().setCursor(Qt.OpenHandCursor)
            return
        if control and tecla == Qt.Key_Z:
            self.rehacer() if mods & Qt.ShiftModifier else self.deshacer()
        elif control and tecla == Qt.Key_Y:
            self.rehacer()
        elif control and tecla == Qt.Key_V:
            self.pegar()
        elif control and tecla == Qt.Key_C:
            self.copiar_portapapeles()
        elif control and tecla == Qt.Key_D:
            self.duplicar()
        elif control and tecla == Qt.Key_G:
            self.nuevo_marco()
        elif control and tecla == Qt.Key_A:
            self.seleccionar([e["id"] for e in self.tablero["elementos"]])
        elif tecla in (Qt.Key_Delete, Qt.Key_Backspace):
            self.borrar()
        elif tecla == Qt.Key_Escape:
            if self.herramienta != "seleccion":
                self.usar_herramienta("seleccion")
            else:
                self.escena.clearSelection()
        elif mods & Qt.AltModifier:
            super(Lienzo, self).keyPressEvent(evento)
        elif tecla == Qt.Key_F:
            self.encuadrar(self.seleccionados() or None)
        elif tecla == Qt.Key_A:
            self.encuadrar(self.tablero["elementos"])
        elif tecla == Qt.Key_N:
            self.nueva_nota(self.posicion_raton())
        elif tecla == Qt.Key_L:
            self.nueva_nota(self.posicion_raton(), "lista")
        elif tecla == Qt.Key_G:
            self.alternar("gris")
        elif tecla == Qt.Key_H:
            self.alternar("volteo")
        elif tecla == Qt.Key_P:
            self.usar_herramienta("lapiz")
        elif tecla == Qt.Key_W:
            self.usar_herramienta("flecha")
        elif tecla == Qt.Key_C:
            self.usar_herramienta("recortar")
        elif tecla == Qt.Key_I:
            self.usar_herramienta("cuentagotas")
        elif tecla in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            paso = 10.0 if mods & Qt.ShiftModifier else 1.0
            dx = {Qt.Key_Left: -paso, Qt.Key_Right: paso}.get(tecla, 0.0)
            dy = {Qt.Key_Up: -paso, Qt.Key_Down: paso}.get(tecla, 0.0)
            self.mover_seleccion(dx, dy)
        else:
            super(Lienzo, self).keyPressEvent(evento)

    def keyReleaseEvent(self, evento):
        if evento.key() == Qt.Key_Space and not evento.isAutoRepeat():
            self._espacio = False
            self.viewport().unsetCursor()
            return
        super(Lienzo, self).keyReleaseEvent(evento)

    # --- Soltar y pegar ------------------------------------------------------------------
    def dragEnterEvent(self, evento):
        datos = evento.mimeData()
        if datos.hasUrls() or datos.hasImage() or datos.hasText():
            evento.acceptProposedAction()
        else:
            evento.ignore()

    def dragMoveEvent(self, evento):
        evento.acceptProposedAction()

    def dropEvent(self, evento):
        pos = evento.position().toPoint() if hasattr(evento, "position") else evento.pos()
        punto = self.mapToScene(pos)
        if self.anadir_mime(evento.mimeData(), punto):
            evento.acceptProposedAction()
            self.setFocus()

    def pegar(self):
        datos = QtWidgets.QApplication.clipboard().mimeData()
        if datos is None or not self.anadir_mime(datos, self.posicion_raton()):
            self.aviso.emit(t("portapapeles_vacio"))

    def copiar_portapapeles(self):
        """Copia la imagen seleccionada (como se ve) al portapapeles."""
        sel = [e for e in self.seleccionados() if e["tipo"] == "imagen"]
        if not sel:
            return
        imagen = self.imagen_procesada(sel[0])
        QtWidgets.QApplication.clipboard().setImage(imagen)
        self.aviso.emit(t("copiada"))

    def anadir_mime(self, datos, punto):
        rutas = []
        urls_web = []
        for url in datos.urls() if datos.hasUrls() else []:
            if url.isLocalFile():
                ruta = url.toLocalFile()
                if os.path.isdir(ruta):
                    rutas.extend(sorted(os.path.join(ruta, n) for n in os.listdir(ruta)
                                        if archivo.es_imagen(n)))
                else:
                    rutas.append(ruta)
            elif url.scheme() in ("http", "https"):
                urls_web.append(url.toString())
        imagenes = [r for r in rutas if archivo.es_imagen(r) or not QtGui.QImageReader(r).format().isEmpty()]
        if imagenes:
            self.anadir_imagenes(imagenes, punto)
            return True
        if datos.hasImage():
            imagen = datos.imageData()
            if isinstance(imagen, QtGui.QPixmap):
                imagen = imagen.toImage()
            if isinstance(imagen, QtGui.QImage) and not imagen.isNull():
                self.anadir_qimage(imagen, punto)
                return True
        if urls_web:
            from muro import descargas
            hecho = False
            for url in urls_web[:6]:
                contenido = descargas.bajar_imagen(url)
                if contenido is not None:
                    self.anadir_bytes(contenido[0], contenido[1], punto, descargas.nombre_de_url(url))
                    punto = punto + QPointF(30, 30)
                    hecho = True
            if not hecho:
                self.aviso.emit(t("no_se_pudo_bajar"))
            return hecho
        if datos.hasText() and datos.text().strip():
            self.nueva_nota(punto, texto=datos.text().strip(), editar=False)
            return True
        return False

    # --- Añadir --------------------------------------------------------------------------
    def _exigir_carpeta(self):
        if self.carpeta is None:
            raise RuntimeError("No hay ningún tablero abierto.")

    def anadir_imagenes(self, rutas, punto=None):
        self._exigir_carpeta()
        punto = punto or self.centro_escena()
        nuevos = []
        self.antes()
        x = punto.x()
        for ruta in rutas:
            try:
                relativa = archivo.importar_imagen(self.carpeta, ruta)
            except OSError:
                continue
            e = self._crear_imagen(relativa, os.path.basename(ruta), QPointF(x, punto.y()), centrar=False)
            if e is None:
                continue
            nuevos.append(e)
            x += e["ancho"] + 20
        if not nuevos:
            self.historial.descartar_ultimo()
            self.aviso.emit(t("imagen_no_valida"))
            return []
        desplazamiento = (x - 20 - punto.x()) / 2.0
        for e in nuevos:
            e["x"] -= desplazamiento
            e["y"] -= e["alto"] / 2.0
        self.despues()
        self.seleccionar([e["id"] for e in nuevos])
        return nuevos

    def anadir_bytes(self, datos, extension, punto=None, nombre=""):
        self._exigir_carpeta()
        self.antes()
        relativa = archivo.guardar_bytes(self.carpeta, datos, extension)
        e = self._crear_imagen(relativa, nombre or t("imagen_pegada"), punto or self.centro_escena())
        if e is None:
            self.aviso.emit(t("imagen_no_valida"))
            return None
        self.despues()
        self.seleccionar([e["id"]])
        return e

    def anadir_qimage(self, imagen, punto=None, nombre=""):
        buffer = QtCore.QBuffer()
        buffer.open(QtCore.QIODevice.WriteOnly)
        imagen.save(buffer, "PNG")
        return self.anadir_bytes(bytes(buffer.data()), ".png", punto, nombre)

    def _crear_imagen(self, relativa, nombre, punto, centrar=True):
        ancho_px, alto_px = self.cache.tamano(relativa)
        if QtGui.QImageReader(self.cache.ruta(relativa)).size().isEmpty() and \
                QtGui.QImage(self.cache.ruta(relativa)).isNull():
            return None
        ancho, alto = modelo.tamano_inicial(ancho_px, alto_px, 360.0 / max(self.zoom(), 0.2) if self.zoom() < 1 else 360.0)
        x = punto.x() - (ancho / 2 if centrar else 0)
        y = punto.y() - (alto / 2 if centrar else 0)
        return modelo.crear(self.tablero, "imagen", archivo=relativa, nombre=nombre, px=[ancho_px, alto_px],
                            x=x, y=y, ancho=ancho, alto=alto)

    def capturar_visor(self):
        self._exigir_carpeta()
        ruta = self.servicios.capturar_visor(self.carpeta)
        if not ruta:
            self.aviso.emit(t("captura_no_disponible"))
            return None
        try:
            with open(ruta, "rb") as f:
                datos = f.read()
        finally:
            try:
                os.remove(ruta)
            except OSError:
                pass
        nombre = t("captura_nombre", hora=time.strftime("%H:%M"))
        e = self.anadir_bytes(datos, ".png", self.centro_escena(), nombre)
        if e is not None:
            self.aviso.emit(t("captura_hecha"))
        return e

    def nueva_nota(self, punto=None, subtipo="texto", texto="", editar=True):
        punto = punto or self.centro_escena()
        self.antes()
        if subtipo == "lista" and texto:
            texto = modelo.texto_lista([(False, l) for _, l in modelo.lineas_lista(texto)])
        e = modelo.crear(self.tablero, "nota", subtipo=subtipo, texto=texto, x=punto.x() - 100,
                         y=punto.y() - 30, ancho=200.0)
        self.despues()
        self.seleccionar([e["id"]])
        if editar:
            self.editar_nota(e, guardar_antes=False)
        return e

    def nuevo_marco(self, titulo=None):
        sel = [e for e in self.seleccionados() if e["tipo"] != "marco"]
        self.antes()
        if sel:
            c = modelo.caja_conjunta(sel, self.tablero)
            x, y, ancho, alto = c[0] - 24, c[1] - 36, c[2] - c[0] + 48, c[3] - c[1] + 60
        else:
            centro = self.centro_escena()
            ancho, alto = 480.0 / max(self.zoom(), 0.25) if self.zoom() < 1 else 480.0, 0
            alto = ancho * 0.66
            x, y = centro.x() - ancho / 2, centro.y() - alto / 2
        e = modelo.crear(self.tablero, "marco", titulo=titulo if titulo is not None else t("marco_nuevo"),
                         x=x, y=y, ancho=ancho, alto=alto)
        modelo.al_fondo(self.tablero, [e["id"]])
        self.despues()
        self.seleccionar([e["id"]])
        self.editar_titulo(e)
        return e

    def marcador_en(self, imagen, punto=None):
        item = self.items.get(imagen["id"])
        if item is None:
            return None
        punto = punto if punto is not None else getattr(self, "_punto_menu", item.mapToScene(item.rect().center()))
        uv = item.uv_en(item.mapFromScene(punto)) or (modelo.imagen_u(imagen, 0.5), modelo.imagen_v(imagen, 0.5))
        self.antes()
        nota = modelo.anadir_marcador(self.tablero, imagen, uv[0], uv[1])
        self.despues()
        self.seleccionar([nota["id"]])
        self.editar_nota(nota, guardar_antes=False, borrar_si_vacia=False)
        return nota

    # --- Editar textos ----------------------------------------------------------------------
    def editar_nota(self, e, guardar_antes=True, borrar_si_vacia=None):
        item = self.items.get(e["id"])
        if item is None or e["bloqueado"]:
            return
        self.cancelar_edicion()
        cuerpo = item.rect_cuerpo()

        def al_terminar(texto):
            self.editor = None
            self.editando_id = None
            if modelo.buscar(self.tablero, e["id"]) is not e:
                return
            if texto is not None and texto != e["texto"]:
                if guardar_antes:
                    self.antes()
                if e["subtipo"] == "lista":
                    texto = modelo.texto_lista(modelo.lineas_lista(texto))
                e["texto"] = texto
                self.despues()
            elif (borrar_si_vacia if borrar_si_vacia is not None else not guardar_antes) \
                    and not e["texto"].strip() and texto is not None and not texto.strip():
                # Nota nueva que se queda vacía: no la dejamos.
                modelo.borrar(self.tablero, [e["id"]])
                self.historial.descartar_ultimo()
                self.despues()
            else:
                self.reconstruir()

        editor = items.EditorTexto(e["texto"], cuerpo.width() - 4, al_terminar, padre=item)
        editor.setPos(cuerpo.topLeft() + QPointF(0, -2))
        self.editando_id = e["id"]
        self.editor = editor
        item.update()
        editor.empezar()

    def editar_titulo(self, e):
        item = self.items.get(e["id"])
        if item is None:
            return
        self.cancelar_edicion()
        titulo = item.rect_titulo()

        def al_terminar(texto):
            self.editor = None
            self.editando_id = None
            if modelo.buscar(self.tablero, e["id"]) is not e:
                return
            if texto is not None and texto.strip() != e["titulo"]:
                self.antes()
                e["titulo"] = texto.strip()
                self.despues()
            else:
                self.reconstruir()

        editor = items.EditorTexto(e["titulo"], 300, al_terminar, una_linea=True, padre=item)
        editor.setPos(titulo.topLeft() + QPointF(4, -3))
        self.editando_id = e["id"]
        self.editor = editor
        item.update()
        editor.empezar()

    def cancelar_edicion(self):
        if self.editor is not None:
            self.editor.terminar(True)

    # --- Operaciones sobre la selección ----------------------------------------------------
    def _sel_o(self, elementos):
        return elementos if elementos is not None else self.seleccionados()

    def borrar(self, elementos=None):
        sel = self._sel_o(elementos)
        if not sel:
            return
        self.antes()
        modelo.borrar(self.tablero, [e["id"] for e in sel])
        self.despues()

    def duplicar(self, elementos=None):
        sel = self._sel_o(elementos)
        if not sel:
            return
        self.antes()
        nuevos = modelo.duplicar(self.tablero, [e["id"] for e in sel])
        self.despues()
        self.seleccionar(nuevos)

    def alternar(self, campo, elementos=None):
        sel = [e for e in self._sel_o(elementos) if e["tipo"] == "imagen"]
        if not sel:
            self.aviso.emit(t("elige_imagen"))
            return
        self.antes()
        valor = not sel[0][campo]
        for e in sel:
            if campo == "volteo" and e["volteo"] != valor:
                # Voltear sin que la imagen salte: el recorte se refleja.
                r = e["recorte"]
                e["recorte"] = [r[0], r[1], r[2], r[3]]
            e[campo] = valor
        self.despues()
        self.aviso.emit(t("aviso_" + campo + ("_si" if valor else "_no")))

    def fijar_opacidad(self, valor, elementos=None):
        sel = [e for e in self._sel_o(elementos) if e["tipo"] == "imagen"]
        if not sel:
            return
        self.antes()
        for e in sel:
            e["opacidad"] = max(0.05, min(1.0, valor))
        self.despues()

    def quitar_recorte(self, elementos=None):
        sel = [e for e in self._sel_o(elementos) if e["tipo"] == "imagen"]
        if not sel:
            return
        self.antes()
        for e in sel:
            modelo.recortar(e, [0.0, 0.0, 1.0, 1.0])
        self.despues()

    def alternar_bloqueo(self, elementos=None):
        sel = self._sel_o(elementos)
        if not sel:
            return
        self.antes()
        valor = not sel[0]["bloqueado"]
        for e in sel:
            e["bloqueado"] = valor
        self.despues()
        self.aviso.emit(t("bloqueado_si" if valor else "bloqueado_no"))

    def al_frente(self, elementos=None):
        sel = self._sel_o(elementos)
        self.antes()
        modelo.al_frente(self.tablero, [e["id"] for e in sel])
        self.despues()

    def al_fondo(self, elementos=None):
        sel = self._sel_o(elementos)
        self.antes()
        modelo.al_fondo(self.tablero, [e["id"] for e in sel])
        self.despues()

    def ordenar_rejilla(self, elementos=None):
        sel = self._sel_o(elementos)
        if len(sel) == 1 and sel[0]["tipo"] == "marco":
            marco = sel[0]
            dentro = modelo.dentro_de_marco(self.tablero, marco)
            if not dentro:
                return
            self.antes()
            modelo.ordenar_en_rejilla(self.tablero, dentro, (marco["x"] + 24, marco["y"] + 36))
            c = modelo.caja_conjunta(dentro, self.tablero)
            marco["ancho"] = max(marco["ancho"], c[2] - marco["x"] + 24)
            marco["alto"] = max(marco["alto"], c[3] - marco["y"] + 24)
        else:
            if len(sel) < 2:
                return
            self.antes()
            modelo.ordenar_en_rejilla(self.tablero, sel)
        self.despues()

    def alinear(self, modo, elementos=None):
        sel = self._sel_o(elementos)
        if len(sel) < 2:
            return
        self.antes()
        modelo.alinear(self.tablero, sel, modo)
        self.despues()

    def mover_seleccion(self, dx, dy):
        sel = [e for e in self.seleccionados() if not e["bloqueado"]]
        if not sel:
            return
        self.antes()
        for e in sel:
            modelo.mover(self.tablero, e, dx, dy)
        self.despues()

    def siguiente_tono(self, elementos=None):
        sel = [e for e in self._sel_o(elementos) if e["tipo"] in ("nota", "flecha", "trazo")]
        if not sel:
            return
        self.antes()
        for e in sel:
            e["tono"] = (e["tono"] + 1) % modelo.NUM_TONOS
        self.despues()

    def convertir_nota(self, elementos=None):
        sel = [e for e in self._sel_o(elementos) if e["tipo"] == "nota"]
        if not sel:
            return
        self.antes()
        for e in sel:
            modelo.convertir_nota(e)
        self.despues()

    def deshacer_marco(self, elementos=None):
        sel = [e for e in self._sel_o(elementos) if e["tipo"] == "marco"]
        self.borrar(sel)

    def ligar_objeto(self, elementos=None):
        sel = [e for e in self._sel_o(elementos) if e["tipo"] == "nota"]
        objeto = self.servicios.objeto_seleccionado()
        if not sel:
            return
        if objeto is None:
            self.aviso.emit(t("elige_objeto"))
            return
        self.antes()
        for e in sel:
            e["objeto"] = dict(objeto)
        self.despues()
        self.aviso.emit(t("ligada", nombre=objeto["nombre"]))

    def desligar_objeto(self, elementos=None):
        sel = [e for e in self._sel_o(elementos) if e["tipo"] == "nota" and e["objeto"]]
        if not sel:
            return
        self.antes()
        for e in sel:
            e["objeto"] = None
        self.despues()

    def ir_a_objeto(self, elementos=None):
        sel = [e for e in self._sel_o(elementos) if e["tipo"] == "nota" and e["objeto"]]
        if sel and not self.servicios.seleccionar_objeto(sel[0]["objeto"]):
            self.aviso.emit(t("objeto_no_encontrado", nombre=sel[0]["objeto"]["nombre"]))

    def quitar_muestra(self, color):
        self.tablero["muestras"] = [m for m in self.tablero["muestras"] if m != color]
        self.cambiado.emit()

    # --- Imágenes procesadas y exportar ------------------------------------------------------
    def imagen_procesada(self, e, gris=None):
        """QImage de la referencia como se ve en el tablero: recortada, volteada y en gris."""
        imagen = self.cache.original(e["archivo"])
        r = e["recorte"]
        rect = QtCore.QRect(int(r[0] * imagen.width()), int(r[1] * imagen.height()),
                            max(1, int((r[2] - r[0]) * imagen.width())), max(1, int((r[3] - r[1]) * imagen.height())))
        imagen = imagen.copy(rect)
        if e["volteo"]:
            imagen = imagen.mirrored(True, False) if hasattr(imagen, "mirrored") else imagen.flipped(Qt.Horizontal)
        if e["gris"] if gris is None else gris:
            imagen = imagen.convertToFormat(QtGui.QImage.Format_Grayscale8).convertToFormat(QtGui.QImage.Format_RGB32)
        return imagen

    def renderizar(self, elementos=None, escala=2.0, fondo=True):
        """QImage del tablero (o de los elementos dados), sin tiradores de selección."""
        lista = [self.items[e["id"]] for e in (elementos or self.tablero["elementos"]) if e["id"] in self.items]
        if elementos and len(elementos) == 1 and elementos[0]["tipo"] == "marco":
            lista += [self.items[e["id"]] for e in modelo.dentro_de_marco(self.tablero, elementos[0])
                      if e["id"] in self.items]
        caja = self.caja_items(lista)
        if caja is None:
            return None
        caja = caja.adjusted(-24, -24, 24, 24)
        lado_max = 12000.0
        escala = min(escala, lado_max / max(caja.width(), caja.height()))
        imagen = QtGui.QImage(max(1, int(caja.width() * escala)), max(1, int(caja.height() * escala)),
                              QtGui.QImage.Format_ARGB32_Premultiplied)
        imagen.fill(items.FONDO_TABLERO if fondo else Qt.transparent)
        self.exportando = True
        try:
            p = QtGui.QPainter(imagen)
            p.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.SmoothPixmapTransform
                             | QtGui.QPainter.TextAntialiasing)
            visibles = {}
            if elementos:
                ocultar = [i for i in self.escena.items() if i.parentItem() is None and i not in lista
                           and i is not self.conexiones]
                for i in ocultar:
                    visibles[i] = i.isVisible()
                    i.setVisible(False)
            fondo_antes = self.escena.backgroundBrush()
            self.escena.setBackgroundBrush(Qt.NoBrush)
            self.escena.render(p, QRectF(0, 0, imagen.width(), imagen.height()), caja)
            self.escena.setBackgroundBrush(fondo_antes)
            for i, v in visibles.items():
                i.setVisible(v)
            p.end()
        finally:
            self.exportando = False
        return imagen

    def exportar_png(self, ruta, elementos=None):
        imagen = self.renderizar(elementos)
        if imagen is None:
            return False
        return imagen.save(ruta, "PNG")
