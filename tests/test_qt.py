"""Pruebas sin Maya del tablero con Qt sin pantalla (ratón, teclado, herramientas).

Necesitan PySide6 (``pip install PySide6-Essentials``); si no está, se saltan.
"""

import os
import shutil
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "scripts"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6 import QtCore, QtGui, QtTest, QtWidgets
except ImportError:  # pragma: no cover
    QtWidgets = None

if QtWidgets is not None:
    from muro import archivo, items, modelo
    from muro.lienzo import Servicios
    from muro.ventana import VentanaMuro
    from muro.menu_radial import MenuRadial
    from muro.dialogo_plano import DialogoPlano

    Qt = QtCore.Qt
    QPoint = QtCore.QPoint
    QPointF = QtCore.QPointF
    APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class ServiciosFalsos(Servicios if QtWidgets else object):
    en_maya = True

    def __init__(self, carpeta):
        self.carpeta = carpeta
        self.colores = []
        self.planos = []
        self.objeto = {"uuid": "ABC", "nombre": "pCube1"}
        self.seleccionado = None

    def capturar_visor(self, carpeta):
        ruta = os.path.join(self.carpeta, "captura.png")
        imagen = QtGui.QImage(320, 180, QtGui.QImage.Format_RGB32)
        imagen.fill(QtGui.QColor("#4f5a66"))
        imagen.save(ruta)
        return ruta

    def aplicar_color(self, color):
        self.colores.append(color)
        return "puesto " + color

    def objeto_seleccionado(self):
        return self.objeto

    def seleccionar_objeto(self, objeto):
        self.seleccionado = objeto
        return True

    def plano_de_imagen(self, ruta, parametros):
        self.planos.append((ruta, parametros))
        return "plano"


def _imagen(ruta, ancho, alto, color, mitad=None):
    imagen = QtGui.QImage(ancho, alto, QtGui.QImage.Format_RGB32)
    imagen.fill(QtGui.QColor(color))
    if mitad:
        p = QtGui.QPainter(imagen)
        p.fillRect(ancho // 2, 0, ancho - ancho // 2, alto, QtGui.QColor(mitad))
        p.end()
    imagen.save(ruta)
    return ruta


@unittest.skipIf(QtWidgets is None, "PySide6 no está instalado")
class Tablero(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.servicios = ServiciosFalsos(self.dir)
        self.v = VentanaMuro(servicios=self.servicios, carpeta_tableros=lambda: os.path.join(self.dir, "t"),
                             carpeta_plantillas=lambda: os.path.join(self.dir, "p"))
        self.v.resize(1000, 700)
        self.v.show()
        APP.processEvents()
        self.v.nuevo_tablero("prueba")
        self.L = self.v.lienzo
        self.rojo = _imagen(os.path.join(self.dir, "rojo.png"), 400, 200, "#ff0000", "#0000ff")
        self.verde = _imagen(os.path.join(self.dir, "verde.jpg"), 300, 300, "#00ff00")

    def tearDown(self):
        self.v.cerrar()
        self.v.deleteLater()
        APP.processEvents()
        shutil.rmtree(self.dir, ignore_errors=True)

    # --- utilidades
    def vp(self):
        return self.L.viewport()

    def punto_de(self, e, fx=0.5, fy=0.5):
        item = self.L.items[e["id"]]
        return self.L.mapFromScene(item.mapToScene(QPointF(e["ancho"] * fx, item.e["alto"] * fy)))

    def arrastrar(self, desde, hasta, boton=Qt.LeftButton, mods=Qt.NoModifier, pasos=5):
        QtTest.QTest.mousePress(self.vp(), boton, mods, desde)
        for i in range(1, pasos + 1):
            p = desde + (hasta - desde) * i / pasos
            evento = QtGui.QMouseEvent(QtCore.QEvent.MouseMove, QPointF(p), QPointF(self.vp().mapToGlobal(p)),
                                       Qt.NoButton, boton, mods)
            APP.sendEvent(self.vp(), evento)
        QtTest.QTest.mouseRelease(self.vp(), boton, mods, hasta)
        APP.processEvents()

    def tecla(self, tecla, mods=Qt.NoModifier):
        self.L.setFocus()
        QtTest.QTest.keyClick(self.L, tecla, mods)
        APP.processEvents()

    def dos_imagenes(self):
        a, b = self.L.anadir_imagenes([self.rojo, self.verde], QPointF(0, 0))
        self.L.encuadrar(self.L.tablero["elementos"])
        APP.processEvents()
        return a, b

    # --- pruebas
    def test_anadir_guardar_y_abrir(self):
        a, b = self.dos_imagenes()
        self.assertEqual(a["px"], [400, 200])
        self.assertAlmostEqual(a["ancho"] / a["alto"], 2.0)
        self.assertLess(a["x"] + a["ancho"], b["x"])
        self.v.guardar()
        self.L.abrir(self.L.carpeta)
        self.assertEqual(len(self.L.items), 2)
        self.assertFalse(self.v.vacio.isVisible())

    def test_imagen_grande_usa_miniatura(self):
        grande = _imagen(os.path.join(self.dir, "g.png"), 3000, 1500, "#808080")
        e, = self.L.anadir_imagenes([grande])
        mini = self.L.cache.miniatura(e["archivo"])
        self.assertEqual(mini.width(), items.MINIATURA_MAX)
        self.assertTrue(os.path.isfile(archivo.ruta_miniatura(self.L.carpeta, e["archivo"])))
        self.assertEqual(self.L.cache.pixmap(e["archivo"], False, 2900).width(), 3000)
        self.assertEqual(self.L.cache.pixmap(e["archivo"], False, 500).width(), items.MINIATURA_MAX)

    def test_mover_con_raton_y_deshacer(self):
        a, _ = self.dos_imagenes()
        x0 = a["x"]
        self.arrastrar(self.punto_de(a), self.punto_de(a) + QPoint(60, 0))
        self.assertGreater(a["x"], x0 + 10)
        self.tecla(Qt.Key_Z, Qt.ControlModifier)
        self.assertAlmostEqual(modelo.buscar(self.L.tablero, a["id"])["x"], x0)
        self.tecla(Qt.Key_Z, Qt.ControlModifier | Qt.ShiftModifier)
        self.assertGreater(modelo.buscar(self.L.tablero, a["id"])["x"], x0 + 10)

    def test_tiradores_escalar_y_girar(self):
        a, _ = self.dos_imagenes()
        self.L.seleccionar([a["id"]])
        APP.processEvents()
        item = self.L.items[a["id"]]
        proporcion = a["ancho"] / a["alto"]
        esquina = self.L.mapFromScene(item.mapToScene(item.tirador_escala().center()))
        self.arrastrar(esquina, esquina + QPoint(80, 10))
        self.assertGreater(a["ancho"], 270)
        self.assertAlmostEqual(a["ancho"] / a["alto"], proporcion)
        giro = self.L.mapFromScene(item.mapToScene(item.tirador_giro().center()))
        centro = self.L.mapFromScene(item.mapToScene(item.rect().center()))
        self.arrastrar(giro, centro + QPoint(200, 0))
        self.assertAlmostEqual(a["rot"], 90.0, delta=3)
        self.tecla(Qt.Key_Z, Qt.ControlModifier)
        self.assertAlmostEqual(modelo.buscar(self.L.tablero, a["id"])["rot"], 0.0)

    def test_marco_arrastra_lo_de_dentro(self):
        a, b = self.dos_imagenes()
        self.L.seleccionar([a["id"]])
        marco = self.L.nuevo_marco("Vistas")
        self.L.cancelar_edicion()
        APP.processEvents()
        a = modelo.buscar(self.L.tablero, a["id"])
        b = modelo.buscar(self.L.tablero, b["id"])
        xa, xb = a["x"], b["x"]
        # Arrastrar desde el borde izquierdo del marco
        item = self.L.items[marco["id"]]
        borde = self.L.mapFromScene(item.mapToScene(QPointF(0, marco["alto"] / 2)))
        self.arrastrar(borde, borde + QPoint(40, 0))
        self.assertGreater(a["x"], xa + 5)
        self.assertAlmostEqual(b["x"], xb)
        self.assertEqual(marco["titulo"], "Vistas")

    def test_seleccion_por_rectangulo(self):
        a, b = self.dos_imagenes()
        self.L.escena.clearSelection()
        esquina = self.L.mapFromScene(QPointF(min(a["x"], b["x"]) - 30, min(a["y"], b["y"]) - 30))
        fin = self.L.mapFromScene(QPointF(max(a["x"] + a["ancho"], b["x"] + b["ancho"]) + 30,
                                          max(a["y"] + a["alto"], b["y"] + b["alto"]) + 30))
        self.arrastrar(esquina, fin)
        self.assertEqual({e["id"] for e in self.L.seleccionados()}, {a["id"], b["id"]})

    def test_teclas(self):
        a, _ = self.dos_imagenes()
        self.L.seleccionar([a["id"]])
        self.tecla(Qt.Key_G)
        self.assertTrue(modelo.buscar(self.L.tablero, a["id"])["gris"])
        self.L.seleccionar([a["id"]])
        self.tecla(Qt.Key_H)
        self.assertTrue(modelo.buscar(self.L.tablero, a["id"])["volteo"])
        self.L.seleccionar([a["id"]])
        self.tecla(Qt.Key_D, Qt.ControlModifier)
        self.assertEqual(len(self.L.tablero["elementos"]), 3)
        self.tecla(Qt.Key_Delete)
        self.assertEqual(len(self.L.tablero["elementos"]), 2)
        self.tecla(Qt.Key_N)
        self.assertIsNotNone(self.L.editor)
        QtTest.QTest.keyClicks(self.L, "Pliegue **aqui**")
        self.L.cancelar_edicion()
        APP.processEvents()
        notas = [e for e in self.L.tablero["elementos"] if e["tipo"] == "nota"]
        self.assertEqual(notas[0]["texto"], "Pliegue **aqui**")
        self.L.seleccionar([a["id"]])
        self.tecla(Qt.Key_Right, Qt.ShiftModifier)
        self.assertEqual(self.L.transform().m11() > 0, True)

    def test_atajos_no_se_los_lleva_maya(self):
        evento = QtGui.QKeyEvent(QtCore.QEvent.ShortcutOverride, Qt.Key_F, Qt.NoModifier, "f")
        self.assertTrue(self.L.event(evento))
        self.assertTrue(evento.isAccepted())

    def test_nota_vacia_desaparece_y_lista_se_marca(self):
        self.L.nueva_nota(QPointF(0, 0))
        self.L.cancelar_edicion()
        APP.processEvents()
        self.assertEqual(self.L.tablero["elementos"], [])
        self.assertFalse(self.L.historial.puede_deshacer)
        lista = self.L.nueva_nota(QPointF(0, 0), "lista", "uno\ndos", editar=False)
        item = self.L.items[lista["id"]]
        fila = item._filas[1][0]
        punto = self.L.mapFromScene(item.mapToScene(fila.center()))
        QtTest.QTest.mouseClick(self.vp(), Qt.LeftButton, Qt.NoModifier, punto)
        APP.processEvents()
        self.assertEqual(modelo.lineas_lista(modelo.buscar(self.L.tablero, lista["id"])["texto"]),
                         [(False, "uno"), (True, "dos")])

    def test_doble_clic_en_el_fondo_crea_nota(self):
        QtTest.QTest.mouseDClick(self.vp(), Qt.LeftButton, Qt.NoModifier, QPoint(500, 400))
        APP.processEvents()
        self.assertIsNotNone(self.L.editor)

    def test_marcador_y_conexion(self):
        a, _ = self.dos_imagenes()
        nota = self.L.marcador_en(a, self.L.items[a["id"]].mapToScene(QPointF(10, 10)))
        self.L.cancelar_edicion()
        APP.processEvents()
        self.assertIsNotNone(modelo.buscar(self.L.tablero, nota["id"]))
        self.assertEqual(modelo.buscar(self.L.tablero, a["id"])["marcadores"][0]["n"], 1)
        self.assertEqual(len(self.L.conexiones.lineas), 1)
        self.assertIn("1", self.L.items[nota["id"]].cabecera_texto())

    def test_lapiz_sobre_imagen(self):
        a, _ = self.dos_imagenes()
        self.L.usar_herramienta("lapiz")
        self.arrastrar(self.punto_de(a, 0.2, 0.2), self.punto_de(a, 0.6, 0.6), pasos=8)
        trazos = [e for e in self.L.tablero["elementos"] if e["tipo"] == "trazo"]
        self.assertEqual(len(trazos), 1)
        self.assertEqual(trazos[0]["padre"], a["id"])
        self.assertIs(self.L.items[trazos[0]["id"]].parentItem(), self.L.items[a["id"]])

    def test_flecha_entre_elementos(self):
        a, b = self.dos_imagenes()
        self.L.usar_herramienta("flecha")
        self.arrastrar(self.punto_de(a), self.punto_de(b))
        flechas = [e for e in self.L.tablero["elementos"] if e["tipo"] == "flecha"]
        self.assertEqual((flechas[0]["desde"], flechas[0]["hasta"]), (a["id"], b["id"]))
        item = self.L.items[flechas[0]["id"]]
        # La flecha empieza en el borde de A, no en su centro
        self.assertAlmostEqual(item.a.x(), a["x"] + a["ancho"], delta=1.0)

    def test_recortar_y_cuentagotas(self):
        a, _ = self.dos_imagenes()
        self.L.usar_herramienta("recortar")
        self.arrastrar(self.punto_de(a, 0.55, 0.1), self.punto_de(a, 0.95, 0.9))
        a = modelo.buscar(self.L.tablero, a["id"])
        self.assertGreater(a["recorte"][0], 0.5)
        self.assertEqual(self.L.herramienta, "seleccion")
        self.L.usar_herramienta("cuentagotas")
        QtTest.QTest.mouseClick(self.vp(), Qt.LeftButton, Qt.NoModifier, self.punto_de(a))
        APP.processEvents()
        self.assertEqual(self.servicios.colores[-1], "#0000ff")
        self.assertEqual(self.L.tablero["muestras"], ["#0000ff"])
        procesada = self.L.imagen_procesada(a)
        self.assertLess(procesada.width(), 400)

    def test_pegar_imagen_y_texto(self):
        imagen = QtGui.QImage(50, 40, QtGui.QImage.Format_RGB32)
        imagen.fill(QtGui.QColor("#123456"))
        QtWidgets.QApplication.clipboard().setImage(imagen)
        self.tecla(Qt.Key_V, Qt.ControlModifier)
        self.assertEqual(self.L.tablero["elementos"][-1]["px"], [50, 40])
        QtWidgets.QApplication.clipboard().setText("Mirar la silueta")
        self.L.pegar()
        self.assertEqual(self.L.tablero["elementos"][-1]["texto"], "Mirar la silueta")

    def test_soltar_archivos(self):
        datos = QtCore.QMimeData()
        datos.setUrls([QtCore.QUrl.fromLocalFile(self.rojo), QtCore.QUrl.fromLocalFile(self.verde)])
        self.assertTrue(self.L.anadir_mime(datos, QPointF(0, 0)))
        self.assertEqual(len(self.L.tablero["elementos"]), 2)
        datos = QtCore.QMimeData()
        datos.setUrls([QtCore.QUrl.fromLocalFile(self.dir)])
        self.assertTrue(self.L.anadir_mime(datos, QPointF(0, 0)))
        self.assertEqual(len(self.L.tablero["elementos"]), 4)

    def test_capturar_visor(self):
        e = self.L.capturar_visor()
        self.assertEqual(e["px"], [320, 180])

    def test_menu_radial_por_tipo(self):
        a, _ = self.dos_imagenes()
        nota = self.L.nueva_nota(QPointF(0, 0), texto="x", editar=False)
        self.L.seleccionar([a["id"]])
        nombres = [n for _, n, _ in self.v.acciones_radial(self.L.items[a["id"]])]
        self.assertEqual(len(nombres), 6)
        self.assertIn("Plano de imagen", nombres)
        self.L.seleccionar([nota["id"]])
        acciones = self.v.acciones_radial(self.L.items[nota["id"]])
        acciones[2][2]()  # ligar a la selección de Maya
        self.assertEqual(modelo.buscar(self.L.tablero, nota["id"])["objeto"]["nombre"], "pCube1")
        self.L.ir_a_objeto()
        self.assertEqual(self.servicios.seleccionado["uuid"], "ABC")
        self.assertEqual(len(self.v.acciones_radial(None)), 6)
        menu = MenuRadial(self.v.acciones_radial(None), self.v)
        llamado = []
        menu.acciones[0] = ("pegar", "x", lambda: llamado.append(1))
        menu.abrir(QPoint(300, 300))
        menu.ejecutar(0)
        APP.processEvents()
        self.assertEqual(llamado, [1])

    def test_clic_derecho_pide_menu(self):
        a, _ = self.dos_imagenes()
        recibido = []
        self.L.pide_menu.disconnect()
        self.L.pide_menu.connect(lambda item, pos: recibido.append(item))
        QtTest.QTest.mousePress(self.vp(), Qt.RightButton, Qt.NoModifier, self.punto_de(a))
        QtTest.QTest.mouseRelease(self.vp(), Qt.RightButton, Qt.NoModifier, self.punto_de(a))
        self.assertIs(recibido[0], self.L.items[a["id"]])

    def test_plano_de_imagen(self):
        a, _ = self.dos_imagenes()
        dialogo = DialogoPlano(self.L.imagen_procesada(a), "rojo", None, False, "cm")
        p = dialogo.parametros()
        self.assertEqual(p["px"], (400, 200))
        self.assertAlmostEqual(p["altura"], 180.0)
        self.assertEqual(p["camara"], "front")

    def test_exportar_png_y_zip(self):
        a, b = self.dos_imagenes()
        ruta = os.path.join(self.dir, "t.png")
        self.assertTrue(self.L.exportar_png(ruta))
        imagen = QtGui.QImage(ruta)
        self.assertGreater(imagen.width(), a["ancho"] + b["ancho"])
        solo = self.L.renderizar([a])
        self.assertLess(solo.width(), imagen.width())
        self.v.guardar()
        ruta_zip = archivo.exportar_zip(self.L.carpeta, os.path.join(self.dir, "t.zip"))
        nueva = self.v.importar_zip(ruta_zip)
        self.assertEqual(len(self.L.tablero["elementos"]), 2)
        self.assertEqual(self.L.carpeta, nueva)

    def test_plantillas(self):
        self.dos_imagenes()
        self.v.guardar()
        copia = archivo.copiar_tablero(self.L.carpeta, os.path.join(self.dir, "p"), "Ejercicio 1")
        self.assertIn(copia, archivo.listar(os.path.join(self.dir, "p")))
        menu = self.v.construir_menu_tablero()
        textos = [a.text() for a in menu.actions()]
        self.assertIn("Plantillas", textos)

    def test_fantasma(self):
        self.dos_imagenes()
        self.v.alternar_fantasma()
        f = self.v.fantasma
        self.assertTrue(f.activo)
        self.assertTrue(f.capa.windowFlags() & Qt.WindowTransparentForInput)
        f.control.boton_ajustar.setChecked(True)
        self.assertFalse(f.capa.windowFlags() & Qt.WindowTransparentForInput)
        f.control.deslizador.setValue(30)
        self.assertAlmostEqual(f.opacidad, 0.3)
        self.v.alternar_fantasma()
        self.assertFalse(f.activo)
        self.assertFalse(self.v.botones["fantasma"].isChecked())

    def test_zoom_rueda_y_trackpad(self):
        z = self.L.zoom()
        evento = QtGui.QWheelEvent(QPointF(400, 300), QPointF(400, 300), QPoint(0, 0), QPoint(0, 120),
                                   Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
        APP.sendEvent(self.vp(), evento)
        self.assertGreater(self.L.zoom(), z)
        centro = self.L.centro_escena()
        evento = QtGui.QWheelEvent(QPointF(400, 300), QPointF(400, 300), QPoint(0, 40), QPoint(0, 40),
                                   Qt.NoButton, Qt.NoModifier, Qt.ScrollUpdate, False)
        APP.sendEvent(self.vp(), evento)
        self.assertNotAlmostEqual(self.L.centro_escena().y(), centro.y())


if __name__ == "__main__":
    unittest.main()
