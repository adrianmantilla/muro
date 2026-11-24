"""Une Muro con Maya: menú Muro, panel acoplable, órdenes para atajos y escena."""

import os

from maya import cmds

import muro
from muro import archivo, pack
from muro.ajustes import Ajustes
from muro.i18n import t
from muro.qt import QtWidgets, destruir, shiboken, sigue_vivo, ventana_maya

CONTROL = "MuroWorkspaceControl"
MENU = "MuroMenu"
COMANDOS = {
    "MuroAbrir": ("cmd_abrir", "alternar()"),
    "MuroFantasma": ("cmd_fantasma", "fantasma()"),
    "MuroCapturarVisor": ("cmd_capturar", "capturar()"),
    "MuroNotaNueva": ("cmd_nota", "nota()"),
}

_estado = {"ventana": None, "ajustes": None, "servicios": None, "trabajos": [], "abrir_escena": None}


def carpeta_preferencias():
    return os.path.join(cmds.internalVar(userAppDir=True), "muro")


def carpeta_plantillas():
    return os.path.join(carpeta_preferencias(), "plantillas")


def ajustes():
    if _estado["ajustes"] is None:
        _estado["ajustes"] = Ajustes(carpeta_preferencias())
    return _estado["ajustes"]


def servicios():
    if _estado["servicios"] is None:
        from muro.maya_servicios import ServiciosMaya
        _estado["servicios"] = ServiciosMaya()
    return _estado["servicios"]


def ventana():
    v = _estado["ventana"]
    return v if sigue_vivo(v) else None


# --- Panel acoplable ------------------------------------------------------------------

def _crear_ventana():
    from muro import maya_servicios
    from muro.ventana import VentanaMuro
    v = VentanaMuro(servicios=servicios(), ajustes=ajustes(), carpeta_tableros=maya_servicios.carpeta_tableros,
                    carpeta_plantillas=carpeta_plantillas, padre_ventanas=ventana_maya())
    v.tablero_abierto.connect(_al_abrir_tablero)
    _estado["ventana"] = v
    return v


def restaurar():
    """Maya lo llama al crear (o recuperar) el panel: mete la ventana dentro."""
    from maya import OpenMayaUI as omui
    puntero = omui.MQtUtil.getCurrentParent()
    padre = shiboken.wrapInstance(int(puntero), QtWidgets.QWidget)
    v = ventana() or _crear_ventana()
    padre.layout().addWidget(v)
    _abrir_tablero_inicial(v)


def _abrir_tablero_inicial(v):
    from muro import maya_servicios
    deseado = _estado.pop("abrir_escena", None) or maya_servicios.tablero_de_escena()
    try:
        if deseado and archivo.es_tablero(deseado):
            if os.path.normpath(deseado) != os.path.normpath(v.lienzo.carpeta or ""):
                v.abrir_tablero(deseado)
        else:
            v.asegurar_tablero()
    except Exception as error:  # carpeta sin permisos, json roto...
        cmds.warning("Muro: {}".format(error))
        v.nuevo_tablero()


def mostrar(tablero=None):
    if tablero:
        _estado["abrir_escena"] = tablero
    if cmds.workspaceControl(CONTROL, exists=True):
        cmds.workspaceControl(CONTROL, edit=True, restore=True, visible=True)
        v = ventana()
        if v is None:
            cmds.deleteUI(CONTROL)
        else:
            _abrir_tablero_inicial(v)
            v.lienzo.setFocus()
            return v
    cmds.workspaceControl(CONTROL, label="Muro", retain=False, floating=True, initialWidth=960, initialHeight=640,
                          minimumWidth=320, uiScript="import muro.interfaz_maya as m\nm.restaurar()",
                          closeCommand="import muro.interfaz_maya as m\nm.al_cerrar()")
    v = ventana()
    if v is not None:
        v.lienzo.setFocus()
    return v


def alternar():
    if cmds.workspaceControl(CONTROL, exists=True) and cmds.workspaceControl(CONTROL, query=True, visible=True):
        cmds.workspaceControl(CONTROL, edit=True, visible=False)
        v = ventana()
        if v is not None:
            v.guardar()
    else:
        mostrar()


def al_cerrar():
    v = ventana()
    if v is not None:
        v.cerrar()
    _estado["ventana"] = None


def _al_abrir_tablero(carpeta):
    nombre = archivo.nombre_de(carpeta)
    if cmds.workspaceControl(CONTROL, exists=True):
        cmds.workspaceControl(CONTROL, edit=True, label="Muro · " + nombre)
    # La escena abierta recuerda su tablero (si ya tiene nombre).
    if cmds.file(query=True, sceneName=True):
        servicios().ligar_escena(carpeta)


def fantasma():
    v = ventana() or mostrar()
    if v is not None:
        v.alternar_fantasma()


def capturar():
    v = ventana() or mostrar()
    if v is not None:
        v.lienzo.capturar_visor()


def nota():
    v = ventana() or mostrar()
    if v is not None:
        v.lienzo.nueva_nota()


def nuevo():
    v = ventana() or mostrar()
    if v is not None:
        v.pedir_nuevo()


def importar():
    v = ventana() or mostrar()
    if v is not None:
        v.importar_zip()


def atajos():
    v = ventana() or mostrar()
    if v is not None:
        v.mostrar_atajos()


# --- Escena ------------------------------------------------------------------------

def _al_abrir_escena():
    from muro import maya_servicios
    if not ajustes()["abrir_con_escena"]:
        return
    tablero = maya_servicios.tablero_de_escena()
    if not tablero or not archivo.es_tablero(tablero):
        return
    v = ventana()
    if v is not None:
        if os.path.normpath(tablero) != os.path.normpath(v.lienzo.carpeta or ""):
            v.abrir_tablero(tablero)
    else:
        mostrar(tablero)


def _al_guardar_escena():
    v = ventana()
    if v is not None:
        v.guardar()
        if v.lienzo.carpeta:
            servicios().ligar_escena(v.lienzo.carpeta)


def _alternar_abrir_con_escena(valor):
    ajustes()["abrir_con_escena"] = bool(valor)


# --- Menú y órdenes ----------------------------------------------------------------------

def _crear_ordenes():
    for nombre, (clave, llamada) in COMANDOS.items():
        codigo = "import muro.interfaz_maya as m\nm.{}".format(llamada)
        if cmds.runTimeCommand(nombre, exists=True):
            cmds.runTimeCommand(nombre, edit=True, command=codigo, commandLanguage="python",
                                annotation=t(clave))
        else:
            cmds.runTimeCommand(nombre, command=codigo, commandLanguage="python", annotation=t(clave),
                                category="Custom Scripts.Muro")


def _crear_menu():
    pack.crear_menu(MENU, "Muro")
    cmds.menuItem(label=t("menu_abrir"), command=lambda *_: mostrar(), annotation=t("cmd_abrir"))
    cmds.menuItem(label=t("menu_nuevo"), command=lambda *_: nuevo())
    cmds.menuItem(label=t("menu_importar"), command=lambda *_: importar())
    cmds.menuItem(divider=True)
    cmds.menuItem(label=t("menu_capturar"), command=lambda *_: capturar())
    cmds.menuItem(label=t("menu_fantasma"), command=lambda *_: fantasma())
    cmds.menuItem(divider=True)
    cmds.menuItem(label=t("menu_abrir_con_escena"), checkBox=ajustes()["abrir_con_escena"],
                  command=_alternar_abrir_con_escena)
    cmds.menuItem(label=t("menu_atajos"), command=lambda *_: atajos())
    cmds.menuItem(label=t("menu_acerca", version=muro.__version__), enable=False)


def iniciar():
    _crear_ordenes()
    if cmds.about(batch=True):
        return
    _crear_menu()
    _estado["trabajos"] = [
        cmds.scriptJob(event=["SceneOpened", _al_abrir_escena]),
        cmds.scriptJob(event=["SceneSaved", _al_guardar_escena]),
        cmds.scriptJob(event=["quitApplication", lambda: (ventana() and ventana().guardar())]),
    ]


def detener():
    for trabajo in _estado["trabajos"]:
        if cmds.scriptJob(exists=trabajo):
            cmds.scriptJob(kill=trabajo, force=True)
    _estado["trabajos"] = []
    v = ventana()
    if v is not None:
        v.cerrar()
    if cmds.workspaceControl(CONTROL, exists=True):
        cmds.deleteUI(CONTROL)
    if v is not None:
        destruir(v)
    _estado["ventana"] = None
    pack.quitar_menu(MENU)
