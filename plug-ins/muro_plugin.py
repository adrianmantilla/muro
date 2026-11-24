"""Plugin de Maya para Muro.

Aparece en el Plug-in Manager como «muro_plugin». Al cargarlo crea el menú
Muro en la barra de Maya y las órdenes para el Editor de atajos; al
descargarlo lo quita todo. El instalador lo marca para que se cargue solo.
"""

import maya.api.OpenMaya as om
from maya import cmds


def maya_useNewAPI():
    pass


def initializePlugin(objeto):
    import muro
    plugin = om.MFnPlugin(objeto, "Muro", muro.__version__, "Any")
    try:
        from muro import interfaz_maya
        cmds.evalDeferred(interfaz_maya.iniciar, lowestPriority=True)
    except Exception as error:
        cmds.warning("Muro no se pudo cargar: {}".format(error))
    return plugin


def uninitializePlugin(objeto):
    try:
        from muro import interfaz_maya
        interfaz_maya.detener()
    except Exception:
        pass
