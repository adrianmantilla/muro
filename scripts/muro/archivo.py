"""Guardar y abrir tableros en disco, sin Qt ni Maya.

Un tablero es una carpeta que termina en ``.muro``::

    robot.muro/
        tablero.json    posiciones, notas, marcos...
        imagenes/       copias de las referencias (nombre = huella del contenido)
        miniaturas/     versiones pequeñas para abrir rápido (las crea la interfaz)

Así se puede copiar, entregar o meter en un zip sin que se rompa nada.
"""

import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile

from muro import modelo

EXTENSION = ".muro"
JSON = "tablero.json"
IMAGENES = "imagenes"
MINIATURAS = "miniaturas"
EXTENSIONES_IMAGEN = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp", ".tga", ".exr", ".hdr")
_PROHIBIDOS = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')


def es_imagen(ruta):
    return os.path.splitext(ruta)[1].lower() in EXTENSIONES_IMAGEN


def nombre_seguro(nombre):
    """Nombre de archivo válido en Mac y Windows a partir de lo que escriba el alumno."""
    nombre = _PROHIBIDOS.sub("_", (nombre or "").strip()).strip(". ")
    return nombre[:80] or "tablero"


def es_tablero(carpeta):
    return os.path.isdir(carpeta) and os.path.isfile(os.path.join(carpeta, JSON))


def nombre_de(carpeta):
    base = os.path.basename(os.path.normpath(carpeta))
    return base[:-len(EXTENSION)] if base.lower().endswith(EXTENSION) else base


def ruta_libre(carpeta_padre, nombre):
    """``<carpeta_padre>/<nombre>.muro`` que no exista aún (añade « 2», « 3»...)."""
    base = nombre_seguro(nombre)
    ruta = os.path.join(carpeta_padre, base + EXTENSION)
    n = 2
    while os.path.exists(ruta):
        ruta = os.path.join(carpeta_padre, "{} {}{}".format(base, n, EXTENSION))
        n += 1
    return ruta


def crear(carpeta_padre, nombre):
    """Crea un tablero vacío y devuelve su carpeta."""
    ruta = ruta_libre(carpeta_padre, nombre)
    os.makedirs(os.path.join(ruta, IMAGENES))
    guardar(ruta, modelo.nuevo_tablero(nombre_de(ruta)))
    return ruta


def leer(carpeta):
    with open(os.path.join(carpeta, JSON), encoding="utf-8") as f:
        datos = json.load(f)
    tablero = modelo.normalizar(datos)
    tablero["nombre"] = nombre_de(carpeta)
    return tablero


def guardar(carpeta, tablero):
    """Escribe tablero.json sin dejarlo a medias si algo falla."""
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, JSON)
    temporal = ruta + ".tmp"
    with open(temporal, "w", encoding="utf-8") as f:
        f.write(modelo.a_json(tablero))
    os.replace(temporal, ruta)


def listar(carpeta_padre):
    """Tableros dentro de una carpeta, por nombre."""
    if not os.path.isdir(carpeta_padre):
        return []
    rutas = [os.path.join(carpeta_padre, n) for n in os.listdir(carpeta_padre) if n.lower().endswith(EXTENSION)]
    return sorted((r for r in rutas if es_tablero(r)), key=lambda r: nombre_de(r).lower())


def renombrar(carpeta, nombre_nuevo):
    padre = os.path.dirname(os.path.normpath(carpeta))
    destino = ruta_libre(padre, nombre_nuevo)
    os.rename(carpeta, destino)
    return destino


def huella(datos):
    return hashlib.sha1(datos).hexdigest()[:16]


def importar_imagen(carpeta, origen):
    """Copia una imagen al tablero (si ya estaba, no la duplica). Devuelve su ruta relativa."""
    with open(origen, "rb") as f:
        datos = f.read()
    extension = os.path.splitext(origen)[1].lower() or ".png"
    return guardar_bytes(carpeta, datos, extension)


def guardar_bytes(carpeta, datos, extension=".png"):
    if not extension.startswith("."):
        extension = "." + extension
    nombre = huella(datos) + extension.lower()
    destino_dir = os.path.join(carpeta, IMAGENES)
    os.makedirs(destino_dir, exist_ok=True)
    destino = os.path.join(destino_dir, nombre)
    if not os.path.exists(destino):
        temporal = destino + ".tmp"
        with open(temporal, "wb") as f:
            f.write(datos)
        os.replace(temporal, destino)
    return IMAGENES + "/" + nombre


def ruta_absoluta(carpeta, relativa):
    return os.path.join(carpeta, *relativa.split("/"))


def ruta_miniatura(carpeta, relativa):
    base = os.path.splitext(os.path.basename(relativa))[0]
    return os.path.join(carpeta, MINIATURAS, base + ".png")


def imagenes_usadas(tablero):
    return {e["archivo"] for e in tablero["elementos"] if e["tipo"] == "imagen" and e["archivo"]}


def limpiar(carpeta, tablero):
    """Borra copias de imágenes y miniaturas que ningún elemento usa. Devuelve cuántas."""
    usadas = {os.path.basename(r) for r in imagenes_usadas(tablero)}
    usadas_base = {os.path.splitext(u)[0] for u in usadas}
    borradas = 0
    for sub, comprobar in ((IMAGENES, lambda n: n in usadas),
                           (MINIATURAS, lambda n: os.path.splitext(n)[0] in usadas_base)):
        ruta = os.path.join(carpeta, sub)
        if not os.path.isdir(ruta):
            continue
        for nombre in os.listdir(ruta):
            if not comprobar(nombre):
                try:
                    os.remove(os.path.join(ruta, nombre))
                    borradas += 1
                except OSError:
                    pass
    return borradas


# --- Copiar, exportar e importar (plantillas y reparto a alumnos) ---------------------

def copiar_tablero(origen, carpeta_padre, nombre=None):
    """Copia un tablero entero (sin miniaturas) a otra carpeta. Devuelve la ruta nueva."""
    tablero = leer(origen)
    destino = ruta_libre(carpeta_padre, nombre or nombre_de(origen))
    os.makedirs(os.path.join(destino, IMAGENES))
    for relativa in imagenes_usadas(tablero):
        fuente = ruta_absoluta(origen, relativa)
        if os.path.isfile(fuente):
            shutil.copy2(fuente, ruta_absoluta(destino, relativa))
    tablero["nombre"] = nombre_de(destino)
    guardar(destino, tablero)
    return destino


def exportar_zip(carpeta, ruta_zip):
    """Empaqueta el tablero (json + imágenes usadas) en un .zip para repartirlo."""
    tablero = leer(carpeta)
    raiz = nombre_seguro(nombre_de(carpeta)) + EXTENSION
    with zipfile.ZipFile(ruta_zip, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(raiz + "/" + JSON, modelo.a_json(tablero))
        for relativa in sorted(imagenes_usadas(tablero)):
            fuente = ruta_absoluta(carpeta, relativa)
            if os.path.isfile(fuente):
                z.write(fuente, raiz + "/" + relativa)
    return ruta_zip


def importar_zip(ruta_zip, carpeta_padre, nombre=None):
    """Abre un .zip exportado con Muro como tablero nuevo. Devuelve la carpeta creada.

    Solo se extraen tablero.json y archivos de imagen de imagenes/; cualquier
    otra cosa del zip se ignora.
    """
    with zipfile.ZipFile(ruta_zip) as z:
        nombres = z.namelist()
        jsons = [n for n in nombres if n.replace("\\", "/").split("/")[-1] == JSON]
        if not jsons:
            raise ValueError("El zip no contiene un tablero de Muro.")
        principal = sorted(jsons, key=len)[0].replace("\\", "/")
        prefijo = principal[:-len(JSON)]
        datos = json.loads(z.read(principal).decode("utf-8"))
        tablero = modelo.normalizar(datos)
        base = nombre or (nombre_de(prefijo.rstrip("/")) if prefijo else os.path.splitext(os.path.basename(ruta_zip))[0])
        os.makedirs(carpeta_padre, exist_ok=True)
        destino = ruta_libre(carpeta_padre, base)
        temporal = tempfile.mkdtemp(prefix="muro_", dir=carpeta_padre)
        try:
            os.makedirs(os.path.join(temporal, IMAGENES))
            for n in nombres:
                limpio = n.replace("\\", "/")
                if not limpio.startswith(prefijo + IMAGENES + "/"):
                    continue
                archivo = limpio[len(prefijo + IMAGENES + "/"):]
                if not archivo or "/" in archivo or archivo.startswith(".") or not es_imagen(archivo):
                    continue
                with z.open(n) as fuente, open(os.path.join(temporal, IMAGENES, archivo), "wb") as salida:
                    shutil.copyfileobj(fuente, salida)
            tablero["nombre"] = nombre_de(destino)
            guardar(temporal, tablero)
            os.rename(temporal, destino)
        except Exception:
            shutil.rmtree(temporal, ignore_errors=True)
            raise
    return destino
