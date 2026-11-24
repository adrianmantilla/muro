"""Prueba de Muro dentro de Maya, sin interfaz (herramienta de desarrollo).

Desde la terminal, con el mayapy de cada versión:

    /Applications/Autodesk/maya2027/Maya.app/Contents/bin/mayapy herramientas/prueba_maya.py
    "C:\\Program Files\\Autodesk\\Maya2027\\bin\\mayapy.exe" herramientas\\prueba_maya.py

No toca tus preferencias de Maya. Comprueba que el plugin carga, que se crean
las órdenes para el Editor de atajos, el plano de imagen a escala en front y
side, el color en distintos materiales, ligar notas a objetos y que la escena
recuerda su tablero. La ventana, la captura del visor y el modo fantasma
necesitan la interfaz: pruébalos abriendo Maya normalmente.
Termina con «RESULTADO: OK» o con la lista de fallos.
"""

import os
import shutil
import sys
import tempfile
import traceback

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "scripts"))

fallos = []


def comprobar(condicion, texto):
    print(("  ok    " if condicion else "  FALLO ") + texto)
    if not condicion:
        fallos.append(texto)


def cerca(a, b, tolerancia=1e-3):
    return abs(a - b) <= tolerancia * max(1.0, abs(b))


def main():
    import maya.standalone
    maya.standalone.initialize(name="python")
    from maya import cmds

    print("Maya", cmds.about(version=True), "-", cmds.about(operatingSystem=True))
    cmds.loadPlugin(os.path.join(RAIZ, "plug-ins", "muro_plugin.py"))
    comprobar(cmds.pluginInfo("muro_plugin", query=True, loaded=True), "el plugin se carga")
    from muro import interfaz_maya
    interfaz_maya.iniciar()
    for nombre in interfaz_maya.COMANDOS:
        comprobar(cmds.runTimeCommand(nombre, exists=True), "existe la orden " + nombre)

    from muro import escala, maya_servicios
    from muro.maya_servicios import ServiciosMaya
    s = ServiciosMaya()
    comprobar(s.unidad_escena() == "cm", "unidad de la escena: cm")
    comprobar(maya_servicios.carpeta_tableros().replace("\\", "/").endswith("/muro"), "carpeta de tableros")

    temporal = tempfile.mkdtemp()
    try:
        # Imagen de 400 x 800 px; cabeza en y=100, pies en y=700 -> 180 cm
        ruta = os.path.join(temporal, "ref.png")
        try:
            from PySide6 import QtGui
        except ImportError:
            from PySide2 import QtGui
        imagen = QtGui.QImage(400, 800, QtGui.QImage.Format_RGB32)
        imagen.fill(0x808080)
        imagen.save(ruta)
        parametros = {"camara": "front", "px": (400, 800), "punto_a": (200, 100), "punto_b": (200, 700),
                      "altura": 180.0, "opacidad": 0.5, "capa": True, "nombre": "robot frente"}
        mensaje = s.plano_de_imagen(ruta, parametros)
        print("   ", mensaje)
        planos = cmds.ls(type="imagePlane")
        comprobar(len(planos) == 1, "se crea un plano de imagen")
        if planos:
            forma = planos[0]
            esperado = escala.plano_de_imagen(400, 800, (200, 100), (200, 700), 180.0, "front")
            comprobar(cerca(cmds.getAttr(forma + ".width"), esperado["ancho"]), "ancho del plano a escala")
            comprobar(cerca(cmds.getAttr(forma + ".height"), esperado["alto"]), "alto del plano a escala")
            comprobar(cerca(cmds.getAttr(forma + ".imageCenterY"), esperado["centro"][1]), "los pies en el suelo")
            comprobar(cerca(cmds.getAttr(forma + ".alphaGain"), 0.5), "opacidad del plano")
            transformada = cmds.listRelatives(forma, parent=True, fullPath=True)[0]
            caja = cmds.exactWorldBoundingBox(transformada)
            print("    caja del plano:", [round(v, 2) for v in caja], "esperado", round(esperado["ancho"], 2), "x",
                  round(esperado["alto"], 2), "centro", [round(v, 2) for v in esperado["centro"]])
            comprobar(cerca(caja[4] - caja[1], esperado["alto"], 0.02), "el plano mide de verdad lo esperado (alto)")
            comprobar(cerca(caja[1], 0.0 - 100 * esperado["unidades_por_px"], 0.02), "los pies del dibujo en y=0")
            camaras = cmds.listConnections(forma, type="camera") or cmds.listRelatives(
                cmds.listRelatives(forma, parent=True)[0], parent=True) or []
            comprobar(any("front" in c for c in camaras), "el plano va en la cámara front")
            comprobar(cmds.objExists("muro_referencias") and cmds.getAttr("muro_referencias.displayType") == 2,
                      "capa de referencias bloqueada")
        parametros["camara"] = "side"
        s.plano_de_imagen(ruta, parametros)
        comprobar(len(cmds.ls(type="imagePlane")) == 2, "también en side")

        # Color en materiales
        cubo = cmds.polyCube(name="muro_cubo")[0]
        cmds.select(cubo)
        mensaje = s.aplicar_color("#ff0000")
        comprobar(mensaje is not None, "aplica color al material del objeto: {}".format(mensaje))
        lambert = s.materiales_seleccionados()[0]
        atributo = escala.ATRIBUTO_COLOR.get(cmds.nodeType(lambert), "color")
        valor = cmds.getAttr("{}.{}".format(lambert, atributo))[0]
        comprobar(valor[0] > 0.9 and valor[1] < 0.05, "el color llega al material ({})".format(lambert))
        for tipo in ("standardSurface", "aiStandardSurface", "openPBRSurface"):
            try:
                material = cmds.shadingNode(tipo, asShader=True)
            except RuntimeError:
                print("    (sin " + tipo + " en esta versión)")
                continue
            cmds.select(material)
            s.aplicar_color("#00ff00")
            valor = cmds.getAttr(material + ".baseColor")[0]
            comprobar(valor[1] > 0.9 and valor[0] < 0.05, "color base en " + tipo)
        cmds.select(clear=True)
        comprobar(s.aplicar_color("#ffffff") is None, "sin selección no aplica color")

        # Notas ligadas a objetos
        cmds.select(cubo)
        objeto = s.objeto_seleccionado()
        comprobar(objeto and objeto["nombre"] == cubo, "objeto seleccionado con uuid")
        cmds.select(clear=True)
        cmds.rename(cubo, "muro_cubo_renombrado")
        comprobar(s.seleccionar_objeto(objeto) and cmds.ls(selection=True) == ["muro_cubo_renombrado"],
                  "la nota encuentra el objeto aunque cambie de nombre")

        # La escena recuerda su tablero
        from muro import archivo
        carpeta = archivo.crear(os.path.join(temporal, "tableros"), "robot")
        s.ligar_escena(carpeta)
        escena = os.path.join(temporal, "escena.ma")
        cmds.file(rename=escena)
        cmds.file(save=True, type="mayaAscii")
        cmds.file(new=True, force=True)
        cmds.file(escena, open=True, force=True)
        comprobar(os.path.normpath(maya_servicios.tablero_de_escena() or "") == os.path.normpath(carpeta),
                  "la escena recuerda su tablero")
    finally:
        shutil.rmtree(temporal, ignore_errors=True)

    interfaz_maya.detener()
    cmds.unloadPlugin("muro_plugin")
    comprobar(not cmds.pluginInfo("muro_plugin", query=True, loaded=True), "el plugin se descarga")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        fallos.append("excepción")
    print()
    print("RESULTADO: OK" if not fallos else "RESULTADO: {} fallos\n - ".format(len(fallos)) + "\n - ".join(fallos))
    os._exit(0 if not fallos else 1)
