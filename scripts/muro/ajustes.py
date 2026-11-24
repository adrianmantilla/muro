"""Preferencias del usuario: último tablero, opacidad del fantasma y otras.

Se guardan en ``<preferencias de Maya>/muro/ajustes.json``. No depende de Maya.
"""

import json
import os

_ARCHIVO = "ajustes.json"
DEFECTOS = {
    "ultimo_tablero": None,
    "opacidad_fantasma": 0.5,
    "abrir_con_escena": True,
    "unidad_altura": "m",
    "altura_plano": 1.8,
    "recientes": [],
}


class Ajustes(object):
    def __init__(self, carpeta):
        self.carpeta = carpeta
        self.ruta = os.path.join(carpeta, _ARCHIVO)
        self.datos = self._leer()

    def _leer(self):
        try:
            with open(self.ruta, encoding="utf-8") as f:
                datos = json.load(f)
            return datos if isinstance(datos, dict) else {}
        except (OSError, ValueError):
            return {}

    def guardar(self):
        try:
            os.makedirs(self.carpeta, exist_ok=True)
            temporal = self.ruta + ".tmp"
            with open(temporal, "w", encoding="utf-8") as f:
                json.dump(self.datos, f, ensure_ascii=False, indent=2)
            os.replace(temporal, self.ruta)
        except OSError:
            pass

    def __getitem__(self, clave):
        valor = self.datos.get(clave, DEFECTOS.get(clave))
        defecto = DEFECTOS.get(clave)
        if defecto is not None and not isinstance(valor, type(defecto)) and not (
                isinstance(defecto, float) and isinstance(valor, int) and not isinstance(valor, bool)):
            return defecto
        return valor

    def __setitem__(self, clave, valor):
        self.datos[clave] = valor
        self.guardar()

    def anadir_reciente(self, ruta, maximo=8):
        recientes = [r for r in self["recientes"] if isinstance(r, str) and r != ruta]
        self["recientes"] = [ruta] + recientes[:maximo - 1]
