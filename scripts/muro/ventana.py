"""Ventana del tablero: lienzo, barra flotante, zoom, muestras de color y menús."""

import os
import subprocess
import sys

from muro import archivo, estilo, iconos, modelo
from muro.fantasma import ESTILO_BOTON, Fantasma
from muro.i18n import t
from muro.lienzo import Lienzo, Servicios
from muro.menu_radial import MenuRadial
from muro.qt import QtCore, QtGui, QtWidgets

Qt = QtCore.Qt

ESTILO_MENU = """
QMenu{background:#26292d;color:#e6e6e6;border:1px solid rgba(255,255,255,40);padding:4px;border-radius:6px}
QMenu::item{padding:5px 22px 5px 12px;border-radius:4px}
QMenu::item:selected{background:#f4f4f4;color:#141414}
QMenu::item:disabled{color:#6f747a}
QMenu::separator{height:1px;background:rgba(255,255,255,30);margin:4px 6px}
"""


class Pastilla(QtWidgets.QFrame):
    """Contenedor redondeado y translúcido para los botones flotantes."""

    def __init__(self, padre=None, vertical=False):
        super(Pastilla, self).__init__(padre)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("pastilla")
        self._radio = 0
        self.resizeEvent(None)
        self.fila = QtWidgets.QVBoxLayout(self) if vertical else QtWidgets.QHBoxLayout(self)
        self.fila.setContentsMargins(4, 3, 4, 3)
        self.fila.setSpacing(1)

    def resizeEvent(self, evento):
        radio = max(4, min(self.height(), self.width()) // 2)
        if radio != self._radio:
            self._radio = radio
            self.setStyleSheet("#pastilla{{background:rgba(16,17,19,205);border:1px solid rgba(255,255,255,40);"
                               "border-radius:{}px}}".format(radio))
        if evento is not None:
            super(Pastilla, self).resizeEvent(evento)

    def boton(self, icono, ayuda, funcion, comprobable=False):
        b = QtWidgets.QToolButton(self)
        b.setIcon(iconos.icono(icono))
        b.setIconSize(QtCore.QSize(17, 17))
        b.setAutoRaise(True)
        b.setCheckable(comprobable)
        b.setFixedSize(30, 30)
        b.setToolTip(ayuda)
        b.setStyleSheet(ESTILO_BOTON)
        b.clicked.connect(lambda *_: funcion())
        self.fila.addWidget(b)
        return b

    def separador(self):
        linea = QtWidgets.QFrame(self)
        linea.setFixedSize(1, 18)
        linea.setStyleSheet("background:rgba(255,255,255,40)")
        self.fila.addSpacing(3)
        self.fila.addWidget(linea, 0, Qt.AlignVCenter)
        self.fila.addSpacing(3)


class Muestras(QtWidgets.QWidget):
    elegida = QtCore.Signal(str)
    quitada = QtCore.Signal(str)

    def __init__(self, padre=None):
        super(Muestras, self).__init__(padre)
        self.colores = []
        self.setMouseTracking(True)

    def fijar(self, colores):
        self.colores = list(colores)[-12:]
        self.setFixedSize(max(1, len(self.colores) * 28), 26)
        self.setVisible(bool(self.colores))
        self.update()

    def color_en(self, pos):
        i = int(pos.x() // 28)
        return self.colores[i] if 0 <= i < len(self.colores) else None

    def mousePressEvent(self, evento):
        pos = evento.position().toPoint() if hasattr(evento, "position") else evento.pos()
        color = self.color_en(pos)
        if color is None:
            return
        if evento.button() == Qt.RightButton:
            self.quitada.emit(color)
        else:
            self.elegida.emit(color)

    def mouseMoveEvent(self, evento):
        pos = evento.position().toPoint() if hasattr(evento, "position") else evento.pos()
        color = self.color_en(pos)
        self.setToolTip(t("muestra_ayuda", color=color) if color else "")

    def paintEvent(self, _evento):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        for i, color in enumerate(self.colores):
            p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 90), 1))
            p.setBrush(QtGui.QColor(color))
            p.drawEllipse(QtCore.QPointF(i * 28 + 13, 13), 11, 11)
        p.end()


class VentanaMuro(QtWidgets.QWidget):
    tablero_abierto = QtCore.Signal(str)

    def __init__(self, servicios=None, ajustes=None, carpeta_tableros=None, carpeta_plantillas=None,
                 padre=None, padre_ventanas=None):
        super(VentanaMuro, self).__init__(padre)
        self.setObjectName("MuroVentana")
        self.setMinimumSize(320, 240)
        self.servicios = servicios or Servicios()
        self.ajustes = ajustes
        self._carpeta_tableros = carpeta_tableros or (lambda: os.path.join(os.path.expanduser("~"), "Muro"))
        self._carpeta_plantillas = carpeta_plantillas or (lambda: os.path.join(os.path.expanduser("~"), "Muro",
                                                                                "plantillas"))
        self.padre_ventanas = padre_ventanas
        self.fantasma = None

        self.lienzo = Lienzo(self)
        self.lienzo.servicios = self.servicios
        disposicion = QtWidgets.QVBoxLayout(self)
        disposicion.setContentsMargins(0, 0, 0, 0)
        disposicion.addWidget(self.lienzo)

        self.barra = Pastilla(self)
        self.botones = {}
        b = self.barra.boton
        self.botones["imagen"] = b("imagen", t("bt_imagen"), self.abrir_imagenes)
        self.botones["nota"] = b("nota", t("bt_nota"), lambda: self.lienzo.nueva_nota())
        self.botones["lista"] = b("lista", t("bt_lista"), lambda: self.lienzo.nueva_nota(subtipo="lista"))
        self.botones["marco"] = b("marco", t("bt_marco"), lambda: self.lienzo.nuevo_marco())
        self.botones["captura"] = b("captura", t("bt_captura"), self.lienzo.capturar_visor)
        self.barra.separador()
        self.botones["flecha"] = b("flecha", t("bt_flecha"), lambda: self.lienzo.usar_herramienta("flecha"), True)
        self.botones["lapiz"] = b("lapiz", t("bt_lapiz"), lambda: self.lienzo.usar_herramienta("lapiz"), True)
        self.botones["recortar"] = b("recortar", t("bt_recortar"),
                                     lambda: self.lienzo.usar_herramienta("recortar"), True)
        self.botones["cuentagotas"] = b("gotas", t("bt_cuentagotas"),
                                        lambda: self.lienzo.usar_herramienta("cuentagotas"), True)
        self.botones["gris"] = b("gris", t("bt_gris"), lambda: self.lienzo.alternar("gris"))
        self.botones["voltear"] = b("voltear", t("bt_voltear"), lambda: self.lienzo.alternar("volteo"))
        self.barra.separador()
        self.botones["encuadrar"] = b("encuadrar", t("bt_encuadrar"),
                                      lambda: self.lienzo.encuadrar(self.lienzo.tablero["elementos"]))
        self.botones["fantasma"] = b("fantasma", t("bt_fantasma"), self.alternar_fantasma, True)
        self.botones["menu"] = b("menu", t("bt_menu"), self.mostrar_menu_tablero)

        self.zoom = Pastilla(self)
        self.zoom.fila.setContentsMargins(3, 2, 3, 2)
        self.zoom.boton("mas", t("bt_alejar"), lambda: self.lienzo.zoom_en(1 / 1.25)).setText("−")
        self.etiqueta_zoom = QtWidgets.QPushButton("100%", self.zoom)
        self.etiqueta_zoom.setFlat(True)
        self.etiqueta_zoom.setToolTip(t("bt_zoom_100"))
        self.etiqueta_zoom.setStyleSheet("QPushButton{color:#cfd3d7;border:0;font-family:Menlo,Consolas,monospace;"
                                         "font-size:11px;min-width:44px;background:transparent}")
        self.etiqueta_zoom.clicked.connect(lambda: self.lienzo.zoom_en(1.0 / self.lienzo.zoom()))
        self.zoom.fila.addWidget(self.etiqueta_zoom)
        self.zoom.boton("mas", t("bt_acercar"), lambda: self.lienzo.zoom_en(1.25))
        for boton in self.zoom.findChildren(QtWidgets.QToolButton):
            boton.setIcon(QtGui.QIcon())
            boton.setFixedSize(24, 24)
            boton.setStyleSheet(ESTILO_BOTON.replace("15px", "12px") + "QToolButton{color:#e6e6e6;font-size:14px}"
                                "QToolButton:hover{color:#141414}")
        botones_zoom = self.zoom.findChildren(QtWidgets.QToolButton)
        botones_zoom[0].setText("−")
        botones_zoom[1].setText("+")

        self.muestras = Muestras(self)
        self.muestras.elegida.connect(self.aplicar_color)
        self.muestras.quitada.connect(lambda c: (self.lienzo.quitar_muestra(c), self.refrescar_muestras()))
        self.titulo = QtWidgets.QLabel(self)
        self.titulo.setStyleSheet("color:#8f959a;font-size:11px;background:transparent")
        self.titulo.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.aviso = QtWidgets.QLabel(self)
        self.aviso.setStyleSheet("background:rgba(16,17,19,225);color:#eeeeee;font-size:12px;padding:6px 12px;"
                                 "border-radius:6px")
        self.aviso.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.aviso.hide()
        self.reloj_aviso = QtCore.QTimer(self)
        self.reloj_aviso.setSingleShot(True)
        self.reloj_aviso.timeout.connect(self.aviso.hide)
        self.vacio = QtWidgets.QLabel(t("tablero_vacio"), self)
        self.vacio.setAlignment(Qt.AlignCenter)
        self.vacio.setWordWrap(True)
        self.vacio.setStyleSheet("color:#7d8388;font-size:13px;background:transparent")
        self.vacio.setAttribute(Qt.WA_TransparentForMouseEvents)

        self.reloj_guardar = QtCore.QTimer(self)
        self.reloj_guardar.setSingleShot(True)
        self.reloj_guardar.setInterval(1500)
        self.reloj_guardar.timeout.connect(self.guardar)

        self.lienzo.cambiado.connect(self.al_cambiar)
        self.lienzo.aviso.connect(self.mostrar_aviso)
        self.lienzo.vista_cambiada.connect(self.al_mover_vista)
        self.lienzo.herramienta_cambiada.connect(self.al_cambiar_herramienta)
        self.lienzo.color_tomado.connect(self.al_tomar_color)
        self.lienzo.pide_menu.connect(self.mostrar_radial)
        self.setStyleSheet(ESTILO_MENU)
        self.colocar_flotantes()

    # --- Colocación de lo flotante --------------------------------------------------------
    def resizeEvent(self, evento):
        super(VentanaMuro, self).resizeEvent(evento)
        self.colocar_flotantes()

    def colocar_flotantes(self):
        self.barra.adjustSize()
        self.barra.move(12, 12)
        self.zoom.adjustSize()
        self.zoom.move(self.width() - self.zoom.width() - 12, self.height() - self.zoom.height() - 12)
        self.muestras.move(14, self.height() - 26 - 14)
        self.titulo.adjustSize()
        x_titulo = self.width() - self.titulo.width() - 16
        if x_titulo < self.barra.geometry().right() + 12:
            self.titulo.move(16, self.barra.geometry().bottom() + 8)
        else:
            self.titulo.move(x_titulo, 22)
        self.vacio.setGeometry(40, self.height() // 2 - 60, max(10, self.width() - 80), 120)
        self.aviso.adjustSize()
        self.aviso.move(max(8, (self.width() - self.aviso.width()) // 2), self.barra.geometry().bottom() + 12)
        for w in (self.barra, self.zoom, self.muestras, self.titulo, self.aviso):
            w.raise_()

    # --- Tablero ---------------------------------------------------------------------------
    def carpeta_tableros(self):
        return self._carpeta_tableros()

    def abrir_tablero(self, carpeta):
        self.guardar()
        self.lienzo.abrir(carpeta)
        if self.ajustes is not None:
            self.ajustes["ultimo_tablero"] = carpeta
            self.ajustes.anadir_reciente(carpeta)
        self.actualizar_titulo()
        self.refrescar_muestras()
        self.tablero_abierto.emit(carpeta)
        self.al_mover_vista()
        return carpeta

    def nuevo_tablero(self, nombre=None, carpeta_padre=None):
        carpeta_padre = carpeta_padre or self.carpeta_tableros()
        os.makedirs(carpeta_padre, exist_ok=True)
        carpeta = archivo.crear(carpeta_padre, nombre or t("tablero_nombre_defecto"))
        return self.abrir_tablero(carpeta)

    def asegurar_tablero(self):
        """Abre el último tablero, o el primero del proyecto, o crea uno."""
        if self.lienzo.carpeta and archivo.es_tablero(self.lienzo.carpeta):
            return self.lienzo.carpeta
        ultimo = self.ajustes["ultimo_tablero"] if self.ajustes is not None else None
        if ultimo and archivo.es_tablero(ultimo):
            return self.abrir_tablero(ultimo)
        existentes = archivo.listar(self.carpeta_tableros())
        if existentes:
            return self.abrir_tablero(existentes[0])
        return self.nuevo_tablero()

    def guardar(self):
        self.reloj_guardar.stop()
        if self.lienzo.carpeta and archivo.es_tablero(self.lienzo.carpeta):
            try:
                self.lienzo.guardar()
                return True
            except OSError as error:
                self.mostrar_aviso(t("no_se_pudo_guardar", error=error))
        return False

    def al_cambiar(self):
        self.reloj_guardar.start()
        self.refrescar_muestras()
        self.actualizar_vacio()

    def actualizar_titulo(self):
        nombre = archivo.nombre_de(self.lienzo.carpeta) if self.lienzo.carpeta else ""
        self.titulo.setText(nombre)
        self.setWindowTitle("Muro · " + nombre if nombre else "Muro")
        self.colocar_flotantes()
        self.actualizar_vacio()

    def actualizar_vacio(self):
        self.vacio.setVisible(not self.lienzo.tablero["elementos"])

    def refrescar_muestras(self):
        self.muestras.fijar(self.lienzo.tablero["muestras"])
        self.colocar_flotantes()

    def al_mover_vista(self):
        self.etiqueta_zoom.setText("{}%".format(int(round(self.lienzo.zoom() * 100))))
        if self.lienzo.carpeta:
            self.reloj_guardar.start()

    def al_cambiar_herramienta(self, nombre):
        for clave in ("flecha", "lapiz", "recortar", "cuentagotas"):
            self.botones[clave].setChecked(clave == nombre)

    def mostrar_aviso(self, texto):
        self.aviso.setText(texto)
        self.aviso.adjustSize()
        self.aviso.show()
        self.colocar_flotantes()
        self.reloj_aviso.start(2800)

    # --- Imágenes ---------------------------------------------------------------------------
    def abrir_imagenes(self):
        filtro = t("filtro_imagenes") + " (" + " ".join("*" + e for e in archivo.EXTENSIONES_IMAGEN) + ")"
        rutas, _ = QtWidgets.QFileDialog.getOpenFileNames(self, t("bt_imagen"), "", filtro)
        if rutas:
            self.lienzo.anadir_imagenes(rutas, self.lienzo.centro_escena())

    def al_tomar_color(self, color):
        self.refrescar_muestras()
        self.lienzo.usar_herramienta("seleccion")
        self.aplicar_color(color)

    def aplicar_color(self, color):
        mensaje = self.servicios.aplicar_color(color)
        if mensaje:
            self.mostrar_aviso(mensaje)
        else:
            QtWidgets.QApplication.clipboard().setText(color)
            self.mostrar_aviso(t("color_copiado", color=color))

    def crear_plano(self, e):
        from muro.dialogo_plano import DialogoPlano
        if not self.servicios.en_maya:
            self.mostrar_aviso(t("solo_en_maya"))
        imagen = self.lienzo.imagen_procesada(e, gris=False)
        dialogo = DialogoPlano(imagen, e["nombre"] or t("imagen"), self.ajustes, e["gris"],
                               self.servicios.unidad_escena(), self)
        if dialogo.exec() != QtWidgets.QDialog.Accepted:
            return
        parametros = dialogo.parametros()
        if parametros["gris"]:
            imagen = imagen.convertToFormat(QtGui.QImage.Format_Grayscale8)
        carpeta = os.path.join(self.lienzo.carpeta, "planos")
        os.makedirs(carpeta, exist_ok=True)
        ruta = os.path.join(carpeta, "{}_{}.png".format(e["id"], archivo.nombre_seguro(
            os.path.splitext(e["nombre"] or "plano")[0])))
        imagen.save(ruta, "PNG")
        parametros["nombre"] = os.path.splitext(e["nombre"] or "referencia")[0]
        mensaje = self.servicios.plano_de_imagen(ruta, parametros)
        self.mostrar_aviso(mensaje or t("solo_en_maya"))

    def abrir_en_sistema(self, e):
        ruta = archivo.ruta_absoluta(self.lienzo.carpeta, e["archivo"])
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(ruta))

    # --- Fantasma ---------------------------------------------------------------------------
    def alternar_fantasma(self):
        if self.fantasma is not None and self.fantasma.activo:
            self.fantasma.salir()
            return
        if self.fantasma is None:
            opacidad = self.ajustes["opacidad_fantasma"] if self.ajustes is not None else 0.5
            self.fantasma = Fantasma(self.lienzo, self.servicios, opacidad, self.padre_ventanas)
            self.fantasma.terminado.connect(self.al_salir_fantasma)
            self.fantasma.control.opacidad.connect(self._guardar_opacidad)
        self.fantasma.iniciar()
        self.botones["fantasma"].setChecked(True)
        self.mostrar_aviso(t("fantasma_activo"))

    def _guardar_opacidad(self, valor):
        if self.ajustes is not None:
            self.ajustes.datos["opacidad_fantasma"] = valor
            self.ajustes.guardar()

    def al_salir_fantasma(self):
        self.botones["fantasma"].setChecked(False)

    def cerrar(self):
        self.guardar()
        if self.fantasma is not None:
            self.fantasma.destruir()
            self.fantasma = None

    # --- Menú radial y «Más…» -----------------------------------------------------------------
    def acciones_radial(self, item):
        L = self.lienzo
        sel = L.seleccionados()
        mas = ("mas", t("ac_mas"), lambda: self.menu_mas(item, sel))
        if item is None:
            return [("pegar", t("ac_pegar"), L.pegar),
                    ("nota", t("ac_nota"), lambda: L.nueva_nota(getattr(L, "_punto_menu", None))),
                    ("imagen", t("ac_abrir_imagen"), self.abrir_imagenes),
                    ("captura", t("ac_capturar"), L.capturar_visor),
                    ("encuadrar", t("ac_encuadrar_todo"), lambda: L.encuadrar(L.tablero["elementos"])),
                    mas]
        if len(sel) > 1:
            return [("rejilla", t("ac_rejilla"), L.ordenar_rejilla),
                    ("marco", t("ac_enmarcar"), L.nuevo_marco),
                    ("duplicar", t("ac_duplicar"), L.duplicar),
                    ("encuadrar", t("ac_encuadrar"), lambda: L.encuadrar(sel)),
                    ("borrar", t("ac_borrar"), L.borrar),
                    mas]
        e = item.e
        if e["tipo"] == "imagen":
            return [("gris", t("ac_gris"), lambda: L.alternar("gris", [e])),
                    ("voltear", t("ac_voltear"), lambda: L.alternar("volteo", [e])),
                    ("marcador", t("ac_marcador"), lambda: L.marcador_en(e)),
                    ("plano", t("ac_plano"), lambda: self.crear_plano(e)),
                    ("gotas", t("ac_cuentagotas"), lambda: L.usar_herramienta("cuentagotas")),
                    mas]
        if e["tipo"] == "nota":
            return [("tono", t("ac_tono"), lambda: L.siguiente_tono([e])),
                    ("lista", t("ac_lista_texto"), lambda: L.convertir_nota([e])),
                    ("enlace", t("ac_ligar") if not e["objeto"] else t("ac_ir_objeto"),
                     (lambda: L.ligar_objeto([e])) if not e["objeto"] else (lambda: L.ir_a_objeto([e]))),
                    ("duplicar", t("ac_duplicar"), lambda: L.duplicar([e])),
                    ("borrar", t("ac_borrar"), lambda: L.borrar([e])),
                    mas]
        if e["tipo"] == "marco":
            return [("renombrar", t("ac_renombrar"), lambda: L.editar_titulo(e)),
                    ("rejilla", t("ac_rejilla"), lambda: L.ordenar_rejilla([e])),
                    ("encuadrar", t("ac_encuadrar"), lambda: L.encuadrar([e])),
                    ("exportar", t("ac_exportar_png"), lambda: self.exportar_png([e])),
                    ("desagrupar", t("ac_deshacer_marco"), lambda: L.deshacer_marco([e])),
                    mas]
        return [("tono", t("ac_tono"), lambda: L.siguiente_tono([e])),
                ("frente", t("ac_al_frente"), lambda: L.al_frente([e])),
                ("borrar", t("ac_borrar"), lambda: L.borrar([e])),
                mas]

    def mostrar_radial(self, item, posicion_global):
        menu = MenuRadial(self.acciones_radial(item), self)
        self._radial = menu
        menu.abrir(posicion_global)

    def _menu(self, padre=None):
        menu = QtWidgets.QMenu(padre or self)
        menu.setStyleSheet(ESTILO_MENU)
        return menu

    def menu_mas(self, item, sel):
        L = self.lienzo
        menu = self._menu()
        e = item.e if item is not None else None
        if e is not None and e["tipo"] == "imagen":
            menu.addAction(t("ac_recortar"), lambda: L.usar_herramienta("recortar"))
            menu.addAction(t("ac_quitar_recorte"), lambda: L.quitar_recorte(sel))
            opacidad = menu.addMenu(t("ac_opacidad"))
            opacidad.setStyleSheet(ESTILO_MENU)
            for valor in (1.0, 0.75, 0.5, 0.25):
                opacidad.addAction("{}%".format(int(valor * 100)), lambda v=valor: L.fijar_opacidad(v, sel))
            menu.addAction(t("ac_copiar_imagen"), L.copiar_portapapeles)
            menu.addAction(t("ac_abrir_sistema"), lambda: self.abrir_en_sistema(e))
            menu.addSeparator()
        if e is not None and e["tipo"] == "nota":
            menu.addAction(t("ac_editar"), lambda: L.editar_nota(e))
            menu.addAction(t("ac_ligar"), lambda: L.ligar_objeto(sel))
            if e["objeto"]:
                menu.addAction(t("ac_ir_objeto"), lambda: L.ir_a_objeto([e]))
                menu.addAction(t("ac_desligar"), lambda: L.desligar_objeto(sel))
            menu.addSeparator()
        if sel:
            if len(sel) > 1:
                alinear = menu.addMenu(t("ac_alinear"))
                alinear.setStyleSheet(ESTILO_MENU)
                for modo in ("izquierda", "arriba", "centro_v", "centro_h"):
                    alinear.addAction(t("alinear_" + modo), lambda m=modo: L.alinear(m, sel))
                menu.addAction(t("ac_rejilla"), lambda: L.ordenar_rejilla(sel))
            menu.addAction(t("ac_enmarcar"), L.nuevo_marco)
            menu.addAction(t("ac_duplicar"), lambda: L.duplicar(sel))
            menu.addAction(t("ac_al_frente"), lambda: L.al_frente(sel))
            menu.addAction(t("ac_al_fondo"), lambda: L.al_fondo(sel))
            menu.addAction(t("ac_desbloquear") if sel[0]["bloqueado"] else t("ac_bloquear"),
                           lambda: L.alternar_bloqueo(sel))
            if any(x["tipo"] in ("nota", "flecha", "trazo") for x in sel):
                menu.addAction(t("ac_tono"), lambda: L.siguiente_tono(sel))
            menu.addAction(t("ac_exportar_png"), lambda: self.exportar_png(sel))
            menu.addSeparator()
            menu.addAction(t("ac_borrar"), lambda: L.borrar(sel))
            menu.addSeparator()
        else:
            menu.addAction(t("ac_nota_lista"), lambda: L.nueva_nota(getattr(L, "_punto_menu", None), "lista"))
            menu.addAction(t("ac_marco"), L.nuevo_marco)
            menu.addAction(t("ac_seleccionar_todo"), lambda: L.seleccionar([x["id"] for x in L.tablero["elementos"]]))
            menu.addSeparator()
        lapiz = menu.addMenu(t("ac_color_lapiz"))
        lapiz.setStyleSheet(ESTILO_MENU)
        for i, _color in enumerate(modelo.TONOS_TRAZO):
            accion = lapiz.addAction(t("color_{}".format(i)), lambda i=i: setattr(L, "tono_lapiz", i))
            accion.setCheckable(True)
            accion.setChecked(L.tono_lapiz == i)
        menu.addAction(t("ac_deshacer"), L.deshacer).setEnabled(L.historial.puede_deshacer)
        menu.addAction(t("ac_rehacer"), L.rehacer).setEnabled(L.historial.puede_rehacer)
        menu.exec(QtGui.QCursor.pos())

    # --- Menú del tablero ------------------------------------------------------------------------
    def mostrar_menu_tablero(self):
        menu = self.construir_menu_tablero()
        boton = self.botones["menu"]
        menu.exec(boton.mapToGlobal(QtCore.QPoint(0, boton.height() + 6)))

    def construir_menu_tablero(self):
        menu = self._menu()
        menu.addAction(t("m_nuevo"), self.pedir_nuevo)
        abrir = menu.addMenu(t("m_abrir"))
        abrir.setStyleSheet(ESTILO_MENU)
        tableros = archivo.listar(self.carpeta_tableros())
        for carpeta in tableros:
            accion = abrir.addAction(archivo.nombre_de(carpeta), lambda c=carpeta: self.abrir_tablero(c))
            accion.setCheckable(True)
            accion.setChecked(self.lienzo.carpeta is not None and
                              os.path.normpath(carpeta) == os.path.normpath(self.lienzo.carpeta))
        if not tableros:
            abrir.addAction(t("m_sin_tableros")).setEnabled(False)
        recientes = [r for r in (self.ajustes["recientes"] if self.ajustes is not None else [])
                     if archivo.es_tablero(r) and r not in tableros]
        if recientes:
            abrir.addSeparator()
            for carpeta in recientes:
                abrir.addAction(carpeta, lambda c=carpeta: self.abrir_tablero(c))
        abrir.addSeparator()
        abrir.addAction(t("m_abrir_carpeta"), self.pedir_abrir)
        menu.addAction(t("m_renombrar"), self.pedir_renombrar)
        if self.servicios.en_maya:
            menu.addAction(t("m_ligar_escena"), self.ligar_escena)
        menu.addSeparator()
        plantillas = menu.addMenu(t("m_plantillas"))
        plantillas.setStyleSheet(ESTILO_MENU)
        lista = archivo.listar(self._carpeta_plantillas())
        for carpeta in lista:
            plantillas.addAction(t("m_nuevo_desde", nombre=archivo.nombre_de(carpeta)),
                                 lambda c=carpeta: self.desde_plantilla(c))
        if not lista:
            plantillas.addAction(t("m_sin_plantillas")).setEnabled(False)
        plantillas.addSeparator()
        plantillas.addAction(t("m_guardar_plantilla"), self.guardar_como_plantilla)
        plantillas.addAction(t("m_carpeta_plantillas"), lambda: self.mostrar_carpeta(self._carpeta_plantillas()))
        menu.addSeparator()
        menu.addAction(t("m_exportar_png"), lambda: self.exportar_png(None))
        menu.addAction(t("m_exportar_zip"), self.exportar_zip)
        menu.addAction(t("m_importar_zip"), self.importar_zip)
        menu.addSeparator()
        menu.addAction(t("m_mostrar_carpeta"), lambda: self.mostrar_carpeta(self.lienzo.carpeta))
        menu.addAction(t("m_limpiar"), self.limpiar)
        menu.addAction(t("m_atajos"), self.mostrar_atajos)
        return menu

    def _pedir_texto(self, titulo, etiqueta, valor=""):
        dialogo = QtWidgets.QInputDialog(self)
        estilo.aplicar(dialogo, "MuroDialogo")
        dialogo.setWindowTitle(titulo)
        dialogo.setLabelText(etiqueta)
        dialogo.setTextValue(valor)
        ok = dialogo.exec_() if hasattr(dialogo, "exec_") else dialogo.exec()
        texto = dialogo.textValue()
        return texto.strip() if ok and texto.strip() else None

    def pedir_nuevo(self):
        nombre = self._pedir_texto(t("m_nuevo"), t("pregunta_nombre"))
        if nombre:
            self.nuevo_tablero(nombre)

    def pedir_abrir(self):
        carpeta = QtWidgets.QFileDialog.getExistingDirectory(self, t("m_abrir_carpeta"), self.carpeta_tableros())
        if carpeta:
            if archivo.es_tablero(carpeta):
                self.abrir_tablero(carpeta)
            else:
                self.mostrar_aviso(t("no_es_tablero"))

    def pedir_renombrar(self):
        if not self.lienzo.carpeta:
            return
        nombre = self._pedir_texto(t("m_renombrar"), t("pregunta_nombre"), archivo.nombre_de(self.lienzo.carpeta))
        if not nombre or nombre == archivo.nombre_de(self.lienzo.carpeta):
            return
        self.guardar()
        vieja = self.lienzo.carpeta
        try:
            nueva = archivo.renombrar(vieja, nombre)
        except OSError as error:
            self.mostrar_aviso(str(error))
            return
        if self.ajustes is not None:
            self.ajustes["recientes"] = [r for r in self.ajustes["recientes"] if r != vieja]
        self.abrir_tablero(nueva)
        if self.servicios.en_maya:
            self.servicios.ligar_escena(nueva)

    def ligar_escena(self):
        if self.lienzo.carpeta and self.servicios.ligar_escena(self.lienzo.carpeta):
            self.mostrar_aviso(t("ligado_escena"))

    def desde_plantilla(self, plantilla):
        self.guardar()
        nombre = self._pedir_texto(t("m_plantillas"), t("pregunta_nombre"), archivo.nombre_de(plantilla))
        if not nombre:
            return
        destino = archivo.copiar_tablero(plantilla, self.carpeta_tableros(), nombre)
        self.abrir_tablero(destino)

    def guardar_como_plantilla(self):
        if not self.lienzo.carpeta:
            return
        self.guardar()
        nombre = self._pedir_texto(t("m_guardar_plantilla"), t("pregunta_nombre"),
                                   archivo.nombre_de(self.lienzo.carpeta))
        if not nombre:
            return
        carpeta = self._carpeta_plantillas()
        os.makedirs(carpeta, exist_ok=True)
        archivo.copiar_tablero(self.lienzo.carpeta, carpeta, nombre)
        self.mostrar_aviso(t("plantilla_guardada", nombre=nombre))

    def exportar_png(self, elementos):
        if not self.lienzo.tablero["elementos"]:
            return
        base = archivo.nombre_de(self.lienzo.carpeta or "muro")
        if elementos and len(elementos) == 1 and elementos[0]["tipo"] == "marco" and elementos[0]["titulo"]:
            base = archivo.nombre_seguro(elementos[0]["titulo"])
        ruta, _ = QtWidgets.QFileDialog.getSaveFileName(self, t("m_exportar_png"),
                                                        os.path.join(os.path.expanduser("~"), base + ".png"), "PNG (*.png)")
        if not ruta:
            return
        if not ruta.lower().endswith(".png"):
            ruta += ".png"
        if self.lienzo.exportar_png(ruta, elementos):
            self.mostrar_aviso(t("exportado", ruta=os.path.basename(ruta)))

    def exportar_zip(self):
        if not self.lienzo.carpeta:
            return
        self.guardar()
        base = archivo.nombre_de(self.lienzo.carpeta)
        ruta, _ = QtWidgets.QFileDialog.getSaveFileName(self, t("m_exportar_zip"),
                                                        os.path.join(os.path.expanduser("~"), base + ".zip"), "Zip (*.zip)")
        if not ruta:
            return
        if not ruta.lower().endswith(".zip"):
            ruta += ".zip"
        archivo.exportar_zip(self.lienzo.carpeta, ruta)
        self.mostrar_aviso(t("exportado", ruta=os.path.basename(ruta)))

    def importar_zip(self, ruta=None):
        if ruta is None:
            ruta, _ = QtWidgets.QFileDialog.getOpenFileName(self, t("m_importar_zip"), os.path.expanduser("~"),
                                                            "Zip (*.zip)")
        if not ruta:
            return None
        try:
            carpeta = archivo.importar_zip(ruta, self.carpeta_tableros())
        except Exception as error:  # zip roto o que no es de Muro
            self.mostrar_aviso(t("zip_no_valido", error=error))
            return None
        return self.abrir_tablero(carpeta)

    def limpiar(self):
        if not self.lienzo.carpeta:
            return
        self.guardar()
        borradas = archivo.limpiar(self.lienzo.carpeta, self.lienzo.tablero)
        self.lienzo.historial.vaciar()
        self.mostrar_aviso(t("limpiado", n=borradas))

    def mostrar_carpeta(self, carpeta):
        if not carpeta:
            return
        os.makedirs(carpeta, exist_ok=True)
        if sys.platform == "darwin":
            subprocess.Popen(["open", carpeta])
        else:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(carpeta))

    def mostrar_atajos(self):
        caja = QtWidgets.QMessageBox(self)
        estilo.aplicar(caja, "MuroDialogo")
        caja.setWindowTitle(t("m_atajos"))
        caja.setTextFormat(Qt.RichText)
        caja.setText(t("atajos_html"))
        caja.exec()
