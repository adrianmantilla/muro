"""Lo que el tablero necesita de Maya: visor, materiales, cámaras, objetos y escena."""

import os
import tempfile

from maya import cmds

from muro import escala
from muro.i18n import t
from muro.lienzo import Servicios
from muro.qt import QtCore, QtWidgets, shiboken

CLAVE_ESCENA = "muro_tablero"
CAPA = "muro_referencias"
UNIDADES = {"millimeter": "mm", "centimeter": "cm", "meter": "m", "kilometer": "km", "inch": "in",
            "foot": "ft", "yard": "yd", "mile": "mi"}


def raiz_proyecto():
    return cmds.workspace(query=True, rootDirectory=True)


def carpeta_tableros():
    """<proyecto>/sourceimages/muro (o la carpeta de imágenes que tenga el proyecto)."""
    regla = cmds.workspace(fileRuleEntry="sourceImages") or "sourceimages"
    carpeta = regla if os.path.isabs(regla) else os.path.join(raiz_proyecto(), regla)
    return os.path.join(carpeta, "muro")


def panel_modelo():
    """El visor activo (o el primero visible)."""
    panel = cmds.getPanel(withFocus=True)
    if panel and cmds.getPanel(typeOf=panel) == "modelPanel":
        return panel
    try:
        panel = cmds.playblast(activeEditor=True)
        panel = panel.split("|")[-1]
        if cmds.getPanel(typeOf=panel) == "modelPanel":
            return panel
    except RuntimeError:
        pass
    visibles = [p for p in (cmds.getPanel(visiblePanels=True) or []) if cmds.getPanel(typeOf=p) == "modelPanel"]
    return visibles[0] if visibles else None


def widget_de(nombre):
    from maya import OpenMayaUI as omui
    puntero = omui.MQtUtil.findControl(nombre)
    if not puntero:
        return None
    return shiboken.wrapInstance(int(puntero), QtWidgets.QWidget)


# Giro del plano libre para que mire a cada cámara ortográfica (sale mirando a +Z, hacia front).
ROTACION_PLANO = {"front": (0.0, 0.0, 0.0), "side": (0.0, 90.0, 0.0), "top": (-90.0, 0.0, 0.0)}


class ServiciosMaya(Servicios):
    en_maya = True

    def unidad_escena(self):
        return UNIDADES.get(cmds.currentUnit(query=True, linear=True, fullName=True), "cm")

    # --- Visor -----------------------------------------------------------------
    def geometria_visor(self):
        panel = panel_modelo()
        if not panel:
            return None
        editor = cmds.modelPanel(panel, query=True, modelEditor=True)
        widget = widget_de(editor) or widget_de(panel)
        if widget is None or not widget.isVisible():
            return None
        return QtCore.QRect(widget.mapToGlobal(QtCore.QPoint(0, 0)), widget.size())

    def capturar_visor(self, carpeta):
        panel = panel_modelo()
        if not panel:
            return None
        editor = cmds.modelPanel(panel, query=True, modelEditor=True)
        widget = widget_de(editor)
        ancho, alto = 1280, 720
        if widget is not None:
            escala_px = widget.devicePixelRatioF() if hasattr(widget, "devicePixelRatioF") else 1.0
            ancho, alto = int(widget.width() * escala_px), int(widget.height() * escala_px)
        destino = os.path.join(tempfile.gettempdir(), "muro_captura_{}.png".format(os.getpid()))
        if os.path.exists(destino):
            os.remove(destino)
        formato = cmds.getAttr("defaultRenderGlobals.imageFormat")
        try:
            cmds.playblast(frame=[cmds.currentTime(query=True)], format="image", compression="png",
                           completeFilename=destino, viewer=False, showOrnaments=False, offScreen=True,
                           percent=100, quality=100, forceOverwrite=True, editorPanelName=panel,
                           widthHeight=[max(16, ancho), max(16, alto)], clearCache=True)
        except RuntimeError as error:
            cmds.warning("Muro: {}".format(error))
            return None
        finally:
            cmds.setAttr("defaultRenderGlobals.imageFormat", formato)
        return destino if os.path.isfile(destino) else None

    # --- Materiales --------------------------------------------------------------
    def materiales_seleccionados(self):
        materiales = []
        for nodo in cmds.ls(selection=True, long=True) or []:
            if cmds.nodeType(nodo) in escala.ATRIBUTO_COLOR:
                materiales.append(nodo)
                continue
            formas = cmds.listRelatives(nodo, shapes=True, fullPath=True) or []
            if cmds.objectType(nodo, isAType="shape"):
                formas.append(nodo)
            if "." in nodo:  # caras seleccionadas
                formas.append(nodo.split(".")[0])
            for forma in formas:
                for grupo in cmds.listConnections(forma, type="shadingEngine") or []:
                    for material in cmds.listConnections(grupo + ".surfaceShader") or []:
                        materiales.append(material)
        vistos = []
        for m in materiales:
            if m not in vistos:
                vistos.append(m)
        return vistos

    def aplicar_color(self, color_hex):
        materiales = self.materiales_seleccionados()
        if not materiales:
            return None
        r, g, b = escala.hex_a_rgb(color_hex)
        try:
            lineal = cmds.colorManagementPrefs(query=True, cmEnabled=True)
        except RuntimeError:
            lineal = False
        if lineal:
            r, g, b = escala.srgb_a_lineal(r), escala.srgb_a_lineal(g), escala.srgb_a_lineal(b)
        hechos = []
        cmds.undoInfo(openChunk=True, chunkName="MuroColor")
        try:
            for material in materiales:
                atributo = escala.ATRIBUTO_COLOR.get(cmds.nodeType(material), "color")
                plug = "{}.{}".format(material, atributo)
                if not cmds.objExists(plug):
                    continue
                if cmds.listConnections(plug, source=True, destination=False):
                    continue  # tiene una textura conectada: no se toca
                cmds.setAttr(plug, r, g, b, type="double3")
                hechos.append(material)
        finally:
            cmds.undoInfo(closeChunk=True)
        if not hechos:
            return t("color_material_con_textura")
        return t("color_aplicado", color=color_hex, material=", ".join(hechos[:3]))

    # --- Objetos -----------------------------------------------------------------
    def objeto_seleccionado(self):
        seleccion = cmds.ls(selection=True, long=True, objectsOnly=True) or []
        if not seleccion:
            return None
        nodo = seleccion[0]
        uuid = (cmds.ls(nodo, uuid=True) or [""])[0]
        return {"uuid": uuid, "nombre": nodo.split("|")[-1]}

    def seleccionar_objeto(self, objeto):
        nodos = []
        if objeto.get("uuid"):
            nodos = cmds.ls(objeto["uuid"], long=True) or []
        if not nodos and objeto.get("nombre"):
            nodos = cmds.ls(objeto["nombre"], long=True) or []
        if not nodos:
            return False
        cmds.select(nodos[0], replace=True)
        return True

    # --- Plano de imagen -----------------------------------------------------------
    def plano_de_imagen(self, ruta_png, p):
        camara = p["camara"]
        if not cmds.objExists(camara):
            return t("plano_sin_camara", camara=camara)
        datos = escala.plano_de_imagen(p["px"][0], p["px"][1], p["punto_a"], p["punto_b"], p["altura"], camara)
        nombre = "muro_" + "".join(c if c.isalnum() else "_" for c in p.get("nombre", "plano"))[:40]
        cmds.undoInfo(openChunk=True, chunkName="MuroPlano")
        try:
            # Plano libre en el mundo, no pegado a la cámara: un plano pegado a una cámara
            # ortográfica se ajusta al encuadre (llena toda la vista) e ignora width/height.
            # Maya no deja usar fileName junto con width/height: se crea y luego se dimensiona.
            transformada, forma = cmds.imagePlane(fileName=ruta_png, name=nombre)
            transformada = cmds.ls(transformada, long=True)[0]
            cmds.setAttr(forma + ".width", datos["ancho"])
            cmds.setAttr(forma + ".height", datos["alto"])
            for eje in "XYZ":
                cmds.setAttr(forma + ".imageCenter" + eje, 0.0)
            cmds.xform(transformada, worldSpace=True, translation=datos["centro"],
                       rotation=ROTACION_PLANO.get(camara, (0.0, 0.0, 0.0)))
            if cmds.attributeQuery("alphaGain", node=forma, exists=True):
                cmds.setAttr(forma + ".alphaGain", p["opacidad"])
            if p.get("capa"):
                if not cmds.objExists(CAPA):
                    cmds.createDisplayLayer(name=CAPA, empty=True, noRecurse=True)
                cmds.editDisplayLayerMembers(CAPA, transformada, noRecurse=True)
                cmds.setAttr(CAPA + ".displayType", 2)
        finally:
            cmds.undoInfo(closeChunk=True)
        return t("plano_creado", camara=camara, ancho=datos["ancho"], alto=datos["alto"],
                 unidad=self.unidad_escena())

    # --- Escena ------------------------------------------------------------------
    def ligar_escena(self, carpeta):
        raiz = os.path.normpath(raiz_proyecto())
        ruta = os.path.normpath(carpeta)
        try:
            relativa = os.path.relpath(ruta, raiz)
        except ValueError:  # otra unidad en Windows
            relativa = ruta
        if relativa.startswith(".."):
            relativa = ruta
        relativa = relativa.replace("\\", "/")
        actual = cmds.fileInfo(CLAVE_ESCENA, query=True)
        if actual and actual[0] == relativa:
            return True
        cmds.fileInfo(CLAVE_ESCENA, relativa)
        return True


def tablero_de_escena():
    """Carpeta del tablero ligado a la escena abierta, o None."""
    valor = cmds.fileInfo(CLAVE_ESCENA, query=True)
    if not valor:
        return None
    ruta = valor[0].replace("\\\\", "/")
    if not os.path.isabs(ruta):
        ruta = os.path.join(raiz_proyecto(), ruta)
    return os.path.normpath(ruta)
