"""Datos de un tablero de Muro, sin Qt ni Maya.

Un tablero es un diccionario que se guarda tal cual como JSON::

    {"formato": 1, "nombre": "robot", "vista": {"x": 0, "y": 0, "zoom": 1},
     "muestras": ["#a0b0c0"], "elementos": [ ... ]}

El orden de ``elementos`` es el orden de dibujo: el último queda encima.
Todos los elementos tienen ``id``, ``tipo``, ``x``, ``y``, ``ancho``, ``alto``,
``rot`` (grados) y ``bloqueado``. Cada tipo añade lo suyo:

* ``imagen``: ``archivo`` (relativo a la carpeta del tablero), ``px`` (ancho y
  alto en píxeles del original), ``recorte`` (u0, v0, u1, v1 entre 0 y 1),
  ``volteo``, ``gris``, ``opacidad``, ``nombre`` y ``marcadores``
  (``{"n", "u", "v", "nota"}``, con u y v sobre la imagen entera).
* ``nota``: ``subtipo`` («texto» o «lista»), ``texto``, ``tono`` (0 a 4) y
  ``objeto`` (``{"uuid", "nombre"}`` de un objeto de la escena, o None).
* ``marco``: ``titulo``.
* ``flecha``: ``desde`` y ``hasta`` (id de elemento o None), ``p0`` y ``p1``
  (puntos sueltos cuando no hay elemento) y ``tono``.
* ``trazo``: ``puntos`` (lista de [x, y]), ``padre`` (id de la imagen sobre
  la que se dibujó, con puntos relativos a ella, o None), ``tono`` y ``grosor``.
"""

import copy
import json

FORMATO = 1
TIPOS = ("imagen", "nota", "marco", "flecha", "trazo")
SUBTIPOS_NOTA = ("texto", "lista")
NUM_TONOS = 5
TONOS = ("#9aa0a6", "#d9c27a", "#8fc7a0", "#9bb8d6", "#d69bb0")
TONOS_TRAZO = ("#f4f4f4", "#ff5a4f", "#ffd34f", "#5fd38a", "#5fb4ff")
MARCA_HECHO = "[x] "
MARCA_PENDIENTE = "[ ] "

_COMUNES = {"x": 0.0, "y": 0.0, "ancho": 200.0, "alto": 150.0, "rot": 0.0, "bloqueado": False}
_POR_TIPO = {
    "imagen": {"archivo": "", "px": [1, 1], "recorte": [0.0, 0.0, 1.0, 1.0], "volteo": False,
               "gris": False, "opacidad": 1.0, "nombre": "", "marcadores": []},
    "nota": {"subtipo": "texto", "texto": "", "tono": 0, "objeto": None, "ancho": 200.0, "alto": 0.0},
    "marco": {"titulo": "", "ancho": 400.0, "alto": 300.0},
    "flecha": {"desde": None, "hasta": None, "p0": [0.0, 0.0], "p1": [100.0, 0.0], "tono": 0,
               "ancho": 0.0, "alto": 0.0},
    "trazo": {"puntos": [], "padre": None, "tono": 0, "grosor": 3.0, "ancho": 0.0, "alto": 0.0},
}


# --- Tablero ----------------------------------------------------------------------

def nuevo_tablero(nombre=""):
    return {"formato": FORMATO, "nombre": nombre, "vista": {"x": 0.0, "y": 0.0, "zoom": 1.0},
            "muestras": [], "elementos": [], "siguiente_id": 1}


def _numero(valor, defecto):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return defecto
    if valor != valor or valor in (float("inf"), float("-inf")):
        return defecto
    return float(valor)


def _limitar(valor, minimo, maximo):
    return max(minimo, min(maximo, valor))


def normalizar_elemento(datos):
    """Elemento con todos sus campos y valores razonables, o None si no sirve."""
    if not isinstance(datos, dict) or datos.get("tipo") not in TIPOS:
        return None
    tipo = datos["tipo"]
    base = dict(_COMUNES)
    base.update(_POR_TIPO[tipo])
    elemento = {"id": str(datos.get("id") or ""), "tipo": tipo}
    for clave, defecto in base.items():
        valor = datos.get(clave, defecto)
        if isinstance(defecto, bool):
            valor = bool(valor)
        elif isinstance(defecto, float):
            valor = _numero(valor, defecto)
        elif isinstance(defecto, int):
            valor = int(_numero(valor, defecto))
        elif isinstance(defecto, str):
            valor = valor if isinstance(valor, str) else defecto
        elif isinstance(defecto, list):
            valor = copy.deepcopy(valor) if isinstance(valor, list) else copy.deepcopy(defecto)
        elemento[clave] = valor
    if tipo == "imagen":
        px = elemento["px"]
        if len(px) != 2:
            px = [1, 1]
        elemento["px"] = [max(1, int(_numero(px[0], 1))), max(1, int(_numero(px[1], 1)))]
        r = elemento["recorte"]
        if len(r) != 4:
            r = [0.0, 0.0, 1.0, 1.0]
        r = [_limitar(_numero(v, d), 0.0, 1.0) for v, d in zip(r, (0.0, 0.0, 1.0, 1.0))]
        if r[2] - r[0] < 0.01 or r[3] - r[1] < 0.01:
            r = [0.0, 0.0, 1.0, 1.0]
        elemento["recorte"] = r
        elemento["opacidad"] = _limitar(elemento["opacidad"], 0.05, 1.0)
        marcadores = []
        for m in elemento["marcadores"]:
            if isinstance(m, dict):
                marcadores.append({"n": max(1, int(_numero(m.get("n"), 1))),
                                   "u": _limitar(_numero(m.get("u"), 0.5), 0.0, 1.0),
                                   "v": _limitar(_numero(m.get("v"), 0.5), 0.0, 1.0),
                                   "nota": m.get("nota") if isinstance(m.get("nota"), str) else None})
        elemento["marcadores"] = marcadores
    elif tipo == "nota":
        if elemento["subtipo"] not in SUBTIPOS_NOTA:
            elemento["subtipo"] = "texto"
        elemento["tono"] = int(_limitar(elemento["tono"], 0, NUM_TONOS - 1))
        objeto = datos.get("objeto")
        elemento["objeto"] = ({"uuid": str(objeto.get("uuid", "")), "nombre": str(objeto.get("nombre", ""))}
                              if isinstance(objeto, dict) else None)
    elif tipo == "flecha":
        for clave in ("desde", "hasta"):
            elemento[clave] = datos.get(clave) if isinstance(datos.get(clave), str) else None
        for clave in ("p0", "p1"):
            p = elemento[clave]
            elemento[clave] = ([_numero(p[0], 0.0), _numero(p[1], 0.0)] if len(p) == 2 else [0.0, 0.0])
        elemento["tono"] = int(_limitar(elemento["tono"], 0, NUM_TONOS - 1))
    elif tipo == "trazo":
        puntos = []
        for p in elemento["puntos"]:
            if isinstance(p, (list, tuple)) and len(p) == 2:
                puntos.append([_numero(p[0], 0.0), _numero(p[1], 0.0)])
        elemento["puntos"] = puntos
        elemento["padre"] = datos.get("padre") if isinstance(datos.get("padre"), str) else None
        elemento["tono"] = int(_limitar(elemento["tono"], 0, NUM_TONOS - 1))
        elemento["grosor"] = _limitar(elemento["grosor"], 0.5, 40.0)
    if tipo in ("imagen", "marco"):
        elemento["ancho"] = max(4.0, elemento["ancho"])
        elemento["alto"] = max(4.0, elemento["alto"])
    if tipo == "nota":
        elemento["ancho"] = max(60.0, elemento["ancho"])
    return elemento


def normalizar(datos):
    """Tablero leído de un archivo, completado y sin elementos rotos."""
    if not isinstance(datos, dict):
        datos = {}
    tablero = nuevo_tablero(datos.get("nombre") if isinstance(datos.get("nombre"), str) else "")
    vista = datos.get("vista") if isinstance(datos.get("vista"), dict) else {}
    tablero["vista"] = {"x": _numero(vista.get("x"), 0.0), "y": _numero(vista.get("y"), 0.0),
                        "zoom": _limitar(_numero(vista.get("zoom"), 1.0), 0.02, 50.0)}
    tablero["muestras"] = [m for m in datos.get("muestras", []) if es_color(m)][-24:] \
        if isinstance(datos.get("muestras"), list) else []
    vistos = set()
    mayor = 0
    elementos = []
    for bruto in datos.get("elementos", []) if isinstance(datos.get("elementos"), list) else []:
        elemento = normalizar_elemento(bruto)
        if elemento is None:
            continue
        if not elemento["id"] or elemento["id"] in vistos:
            elemento["id"] = ""
        else:
            vistos.add(elemento["id"])
            mayor = max(mayor, _numero_de_id(elemento["id"]))
        elementos.append(elemento)
    tablero["elementos"] = elementos
    tablero["siguiente_id"] = max(int(_numero(datos.get("siguiente_id"), 1)), mayor + 1)
    for elemento in elementos:
        if not elemento["id"]:
            elemento["id"] = nuevo_id(tablero)
    _limpiar_referencias(tablero)
    return tablero


def _numero_de_id(identificador):
    digitos = identificador[1:] if identificador[:1] == "e" else ""
    return int(digitos) if digitos.isdigit() else 0


def nuevo_id(tablero):
    numero = tablero.get("siguiente_id", 1)
    tablero["siguiente_id"] = numero + 1
    return "e{}".format(numero)


def es_color(valor):
    return (isinstance(valor, str) and len(valor) == 7 and valor[0] == "#"
            and all(c in "0123456789abcdefABCDEF" for c in valor[1:]))


def a_json(tablero):
    return json.dumps(tablero, ensure_ascii=False, indent=1)


def copiar(tablero):
    return json.loads(json.dumps(tablero))


# --- Elementos ----------------------------------------------------------------------

def crear(tablero, tipo, **campos):
    """Crea un elemento de ``tipo`` con ``campos``, lo añade encima de todo y lo devuelve."""
    datos = dict(campos)
    datos["tipo"] = tipo
    elemento = normalizar_elemento(datos)
    elemento["id"] = nuevo_id(tablero)
    tablero["elementos"].append(elemento)
    return elemento


def buscar(tablero, identificador):
    for elemento in tablero["elementos"]:
        if elemento["id"] == identificador:
            return elemento
    return None


def indice(tablero, identificador):
    for i, elemento in enumerate(tablero["elementos"]):
        if elemento["id"] == identificador:
            return i
    return -1


def _limpiar_referencias(tablero):
    """Quita marcadores, flechas y trazos que apuntan a elementos que ya no existen."""
    ids = {e["id"] for e in tablero["elementos"]}
    restantes = []
    for e in tablero["elementos"]:
        if e["tipo"] == "imagen":
            e["marcadores"] = [m for m in e["marcadores"] if m["nota"] is None or m["nota"] in ids]
        elif e["tipo"] == "flecha":
            if e["desde"] is not None and e["desde"] not in ids:
                continue
            if e["hasta"] is not None and e["hasta"] not in ids:
                continue
        elif e["tipo"] == "trazo" and e["padre"] is not None and e["padre"] not in ids:
            continue
        restantes.append(e)
    cambiado = len(restantes) != len(tablero["elementos"])
    tablero["elementos"] = restantes
    if cambiado:
        _limpiar_referencias(tablero)


def borrar(tablero, ids):
    """Borra los elementos y lo que depende de ellos (flechas, trazos encima, marcadores)."""
    ids = set(ids)
    tablero["elementos"] = [e for e in tablero["elementos"] if e["id"] not in ids]
    _limpiar_referencias(tablero)


def duplicar(tablero, ids, desplazamiento=24.0):
    """Copia los elementos (y los trazos dibujados encima de las imágenes copiadas)."""
    ids = [i for i in ids if buscar(tablero, i)]
    mapa = {}
    nuevos = []
    origen = [e for e in tablero["elementos"] if e["id"] in ids]
    for e in origen:
        copia = copy.deepcopy(e)
        copia["id"] = nuevo_id(tablero)
        mapa[e["id"]] = copia["id"]
        if copia["tipo"] == "flecha":
            copia["p0"] = [copia["p0"][0] + desplazamiento, copia["p0"][1] + desplazamiento]
            copia["p1"] = [copia["p1"][0] + desplazamiento, copia["p1"][1] + desplazamiento]
        elif copia["tipo"] == "trazo" and copia["padre"] is None:
            copia["puntos"] = [[x + desplazamiento, y + desplazamiento] for x, y in copia["puntos"]]
        else:
            copia["x"] += desplazamiento
            copia["y"] += desplazamiento
        if copia["tipo"] == "imagen":
            copia["marcadores"] = [m for m in copia["marcadores"] if m["nota"] in ids]
        nuevos.append(copia)
    # Trazos hijos de imágenes copiadas
    for e in list(tablero["elementos"]):
        if e["tipo"] == "trazo" and e["padre"] in mapa and e["id"] not in ids:
            copia = copy.deepcopy(e)
            copia["id"] = nuevo_id(tablero)
            nuevos.append(copia)
    for copia in nuevos:
        if copia["tipo"] == "imagen":
            for m in copia["marcadores"]:
                m["nota"] = mapa.get(m["nota"], m["nota"])
        elif copia["tipo"] == "flecha":
            copia["desde"] = mapa.get(copia["desde"], copia["desde"])
            copia["hasta"] = mapa.get(copia["hasta"], copia["hasta"])
        elif copia["tipo"] == "trazo" and copia["padre"] is not None:
            copia["padre"] = mapa.get(copia["padre"], copia["padre"])
    tablero["elementos"].extend(nuevos)
    return [c["id"] for c in nuevos]


def al_frente(tablero, ids):
    ids = set(ids)
    tablero["elementos"] = ([e for e in tablero["elementos"] if e["id"] not in ids]
                            + [e for e in tablero["elementos"] if e["id"] in ids])


def al_fondo(tablero, ids):
    ids = set(ids)
    tablero["elementos"] = ([e for e in tablero["elementos"] if e["id"] in ids]
                            + [e for e in tablero["elementos"] if e["id"] not in ids])


# --- Geometría ------------------------------------------------------------------

def caja(elemento, tablero=None):
    """(x0, y0, x1, y1) del elemento en el tablero, sin contar el giro."""
    if elemento["tipo"] == "trazo":
        puntos = elemento["puntos"] or [[0.0, 0.0]]
        dx = dy = 0.0
        if elemento["padre"] is not None and tablero is not None:
            padre = buscar(tablero, elemento["padre"])
            if padre is not None:
                dx, dy = padre["x"], padre["y"]
        xs = [p[0] + dx for p in puntos]
        ys = [p[1] + dy for p in puntos]
        return min(xs), min(ys), max(xs), max(ys)
    if elemento["tipo"] == "flecha":
        x0, y0 = elemento["p0"]
        x1, y1 = elemento["p1"]
        return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)
    alto = elemento["alto"] if elemento["alto"] > 0 else 80.0
    return elemento["x"], elemento["y"], elemento["x"] + elemento["ancho"], elemento["y"] + alto


def caja_conjunta(elementos, tablero=None):
    cajas = [caja(e, tablero) for e in elementos]
    if not cajas:
        return None
    return (min(c[0] for c in cajas), min(c[1] for c in cajas),
            max(c[2] for c in cajas), max(c[3] for c in cajas))


def dentro_de_marco(tablero, marco):
    """Elementos cuyo centro cae dentro del marco (sin otros marcos ni hijos de imágenes)."""
    x0, y0, x1, y1 = caja(marco)
    resultado = []
    for e in tablero["elementos"]:
        if e is marco or e["tipo"] in ("marco", "flecha") or (e["tipo"] == "trazo" and e["padre"]):
            continue
        cx0, cy0, cx1, cy1 = caja(e, tablero)
        cx, cy = (cx0 + cx1) / 2.0, (cy0 + cy1) / 2.0
        if x0 <= cx <= x1 and y0 <= cy <= y1:
            resultado.append(e)
    return resultado


def mover(tablero, elemento, dx, dy):
    if elemento["tipo"] == "flecha":
        elemento["p0"] = [elemento["p0"][0] + dx, elemento["p0"][1] + dy]
        elemento["p1"] = [elemento["p1"][0] + dx, elemento["p1"][1] + dy]
    elif elemento["tipo"] == "trazo":
        if elemento["padre"] is None:
            elemento["puntos"] = [[x + dx, y + dy] for x, y in elemento["puntos"]]
    else:
        elemento["x"] += dx
        elemento["y"] += dy


def ordenar_en_rejilla(tablero, elementos, origen=None, separacion=20.0, columnas=None):
    """Coloca los elementos en filas, de izquierda a derecha, sin solaparse."""
    elementos = [e for e in elementos if e["tipo"] not in ("flecha", "trazo")]
    if not elementos:
        return
    if origen is None:
        c = caja_conjunta(elementos, tablero)
        origen = (c[0], c[1])
    if columnas is None:
        columnas = max(1, int(round(len(elementos) ** 0.5 + 0.49)))
    x, y = origen
    alto_fila = 0.0
    for i, e in enumerate(elementos):
        if i and i % columnas == 0:
            x = origen[0]
            y += alto_fila + separacion
            alto_fila = 0.0
        x0, y0, x1, y1 = caja(e, tablero)
        mover(tablero, e, x - x0, y - y0)
        x += (x1 - x0) + separacion
        alto_fila = max(alto_fila, y1 - y0)


def alinear(tablero, elementos, modo):
    """Alinea por «izquierda», «arriba», «centro_h» o «centro_v»."""
    elementos = [e for e in elementos if e["tipo"] not in ("flecha", "trazo")]
    if len(elementos) < 2:
        return
    c = caja_conjunta(elementos, tablero)
    for e in elementos:
        x0, y0, x1, y1 = caja(e, tablero)
        if modo == "izquierda":
            mover(tablero, e, c[0] - x0, 0)
        elif modo == "arriba":
            mover(tablero, e, 0, c[1] - y0)
        elif modo == "centro_h":
            mover(tablero, e, 0, (c[1] + c[3]) / 2.0 - (y0 + y1) / 2.0)
        elif modo == "centro_v":
            mover(tablero, e, (c[0] + c[2]) / 2.0 - (x0 + x1) / 2.0, 0)


# --- Marcadores numerados -----------------------------------------------------------

def siguiente_marcador(tablero):
    numeros = [m["n"] for e in tablero["elementos"] if e["tipo"] == "imagen" for m in e["marcadores"]]
    return max(numeros) + 1 if numeros else 1


def anadir_marcador(tablero, imagen, u, v, texto=""):
    """Pone un número en (u, v) de la imagen y crea su nota a la derecha. Devuelve la nota."""
    numero = siguiente_marcador(tablero)
    vy = imagen["y"] + visible_v(imagen, v) * imagen["alto"]
    nota = crear(tablero, "nota", x=imagen["x"] + imagen["ancho"] + 40.0, y=vy - 20.0, ancho=190.0,
                 texto=texto, tono=3)
    imagen["marcadores"].append({"n": numero, "u": _limitar(u, 0.0, 1.0), "v": _limitar(v, 0.0, 1.0),
                                 "nota": nota["id"]})
    return nota


def visible_u(imagen, u):
    """Posición horizontal (0-1 sobre lo que se ve) de un punto u de la imagen entera."""
    r = imagen["recorte"]
    pos = (u - r[0]) / (r[2] - r[0])
    return 1.0 - pos if imagen["volteo"] else pos


def visible_v(imagen, v):
    r = imagen["recorte"]
    return (v - r[1]) / (r[3] - r[1])


def imagen_u(imagen, pos):
    """Inverso de visible_u: de lo que se ve a la imagen entera."""
    r = imagen["recorte"]
    if imagen["volteo"]:
        pos = 1.0 - pos
    return r[0] + pos * (r[2] - r[0])


def imagen_v(imagen, pos):
    r = imagen["recorte"]
    return r[1] + pos * (r[3] - r[1])


def recortar(imagen, recorte):
    """Aplica un recorte nuevo (sobre la imagen entera) manteniendo la escala en pantalla."""
    viejo = imagen["recorte"]
    escala_x = imagen["ancho"] / (viejo[2] - viejo[0])
    escala_y = imagen["alto"] / (viejo[3] - viejo[1])
    u0, v0, u1, v1 = [_limitar(v, 0.0, 1.0) for v in recorte]
    if u1 - u0 < 0.01 or v1 - v0 < 0.01:
        return
    if imagen["volteo"]:
        imagen["x"] += (viejo[2] - u1) * escala_x
    else:
        imagen["x"] += (u0 - viejo[0]) * escala_x
    imagen["y"] += (v0 - viejo[1]) * escala_y
    imagen["ancho"] = (u1 - u0) * escala_x
    imagen["alto"] = (v1 - v0) * escala_y
    imagen["recorte"] = [u0, v0, u1, v1]


def tamano_inicial(px_ancho, px_alto, lado=360.0):
    """Tamaño en el tablero de una imagen nueva: su lado mayor mide ``lado``."""
    mayor = float(max(px_ancho, px_alto, 1))
    return px_ancho * lado / mayor, px_alto * lado / mayor


# --- Notas con lista de tareas --------------------------------------------------------

def lineas_lista(texto):
    """[(hecho, texto)] de una nota de lista. Las líneas «[x] algo» están hechas."""
    lineas = []
    for linea in texto.splitlines():
        limpia = linea.strip()
        if not limpia:
            continue
        hecho = False
        for marca in ("[x]", "[X]", "- [x]", "- [X]"):
            if limpia.startswith(marca):
                hecho, limpia = True, limpia[len(marca):].strip()
                break
        else:
            for marca in ("[ ]", "- [ ]", "- ", "* "):
                if limpia.startswith(marca):
                    limpia = limpia[len(marca):].strip()
                    break
        lineas.append((hecho, limpia))
    return lineas


def texto_lista(lineas):
    return "\n".join((MARCA_HECHO if hecho else MARCA_PENDIENTE) + texto for hecho, texto in lineas)


def alternar_linea(texto, indice_linea):
    lineas = lineas_lista(texto)
    if 0 <= indice_linea < len(lineas):
        hecho, contenido = lineas[indice_linea]
        lineas[indice_linea] = (not hecho, contenido)
    return texto_lista(lineas)


def convertir_nota(nota):
    """Cambia una nota entre texto y lista sin perder lo escrito."""
    if nota["subtipo"] == "texto":
        nota["texto"] = texto_lista([(False, l) for _, l in lineas_lista(nota["texto"])])
        nota["subtipo"] = "lista"
    else:
        nota["texto"] = "\n".join(l for _, l in lineas_lista(nota["texto"]))
        nota["subtipo"] = "texto"


# --- Deshacer --------------------------------------------------------------------------

class Historial(object):
    """Deshacer y rehacer guardando copias del tablero entero (son pequeños)."""

    def __init__(self, limite=100):
        self.limite = limite
        self._atras = []
        self._adelante = []

    def guardar(self, tablero):
        """Llamar ANTES de cambiar el tablero."""
        self.guardar_foto(a_json(tablero))

    def guardar_foto(self, foto):
        """Como guardar, con una copia en texto tomada antes (por ejemplo al empezar a arrastrar)."""
        if self._atras and self._atras[-1] == foto:
            return
        self._atras.append(foto)
        del self._atras[:-self.limite]
        self._adelante = []

    def descartar_ultimo(self):
        """Olvida la última copia guardada (un cambio que al final no se hizo)."""
        if self._atras:
            self._atras.pop()

    def deshacer(self, actual):
        if not self._atras:
            return None
        self._adelante.append(a_json(actual))
        return json.loads(self._atras.pop())

    def rehacer(self, actual):
        if not self._adelante:
            return None
        self._atras.append(a_json(actual))
        return json.loads(self._adelante.pop())

    @property
    def puede_deshacer(self):
        return bool(self._atras)

    @property
    def puede_rehacer(self):
        return bool(self._adelante)

    def vaciar(self):
        self._atras = []
        self._adelante = []
