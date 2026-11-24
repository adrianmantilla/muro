"""Pruebas sin Maya ni Qt del modelo del tablero, archivos y cuentas."""

import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "scripts"))

from muro import archivo, escala, modelo  # noqa: E402
from muro.i18n import claves  # noqa: E402


class Modelo(unittest.TestCase):
    def setUp(self):
        self.t = modelo.nuevo_tablero("prueba")

    def test_crear_da_ids_unicos(self):
        a = modelo.crear(self.t, "imagen", archivo="imagenes/a.png")
        b = modelo.crear(self.t, "nota", texto="hola")
        self.assertNotEqual(a["id"], b["id"])
        self.assertEqual(modelo.buscar(self.t, b["id"])["texto"], "hola")

    def test_normalizar_repara_datos_rotos(self):
        datos = {"elementos": [{"tipo": "imagen", "id": "e3", "recorte": [0.5, 0.5, 0.5, 0.5], "opacidad": 9},
                               {"tipo": "nota", "id": "e3", "tono": 99, "ancho": "mucho"},
                               {"tipo": "desconocido"}, "basura",
                               {"tipo": "flecha", "desde": "e404", "hasta": None}],
                 "muestras": ["#ffffff", "rojo"], "vista": {"zoom": -1}}
        t = modelo.normalizar(datos)
        self.assertEqual([e["tipo"] for e in t["elementos"]], ["imagen", "nota"])
        imagen, nota = t["elementos"]
        self.assertEqual(imagen["recorte"], [0.0, 0.0, 1.0, 1.0])
        self.assertEqual(imagen["opacidad"], 1.0)
        self.assertNotEqual(imagen["id"], nota["id"])
        self.assertEqual(nota["tono"], modelo.NUM_TONOS - 1)
        self.assertEqual(nota["ancho"], 200.0)
        self.assertEqual(t["muestras"], ["#ffffff"])
        self.assertGreater(t["vista"]["zoom"], 0)
        # Un id nuevo no repite los existentes
        self.assertNotIn(modelo.nuevo_id(t), {imagen["id"], nota["id"]})

    def test_borrar_arrastra_dependencias(self):
        img = modelo.crear(self.t, "imagen", archivo="a.png", ancho=100, alto=100)
        nota = modelo.anadir_marcador(self.t, img, 0.5, 0.5, "aquí")
        flecha = modelo.crear(self.t, "flecha", desde=nota["id"], hasta=img["id"])
        trazo = modelo.crear(self.t, "trazo", puntos=[[0, 0], [5, 5]], padre=img["id"])
        modelo.borrar(self.t, [nota["id"]])
        self.assertEqual(img["marcadores"], [])
        self.assertIsNone(modelo.buscar(self.t, flecha["id"]))
        self.assertIsNotNone(modelo.buscar(self.t, trazo["id"]))
        modelo.borrar(self.t, [img["id"]])
        self.assertEqual(self.t["elementos"], [])

    def test_duplicar_mantiene_enlaces_internos(self):
        img = modelo.crear(self.t, "imagen", archivo="a.png", x=0, y=0, ancho=100, alto=100)
        nota = modelo.anadir_marcador(self.t, img, 0.2, 0.3)
        modelo.crear(self.t, "trazo", puntos=[[0, 0], [5, 5]], padre=img["id"])
        nuevos = modelo.duplicar(self.t, [img["id"], nota["id"]])
        self.assertEqual(len(nuevos), 3)
        img2 = modelo.buscar(self.t, nuevos[0])
        nota2 = modelo.buscar(self.t, nuevos[1])
        self.assertEqual(img2["marcadores"][0]["nota"], nota2["id"])
        self.assertEqual(img2["x"], 24.0)
        trazo2 = modelo.buscar(self.t, nuevos[2])
        self.assertEqual(trazo2["padre"], img2["id"])
        # Duplicar solo la imagen no se lleva el marcador de otra nota
        solo = modelo.duplicar(self.t, [img["id"]])
        self.assertEqual(modelo.buscar(self.t, solo[0])["marcadores"], [])

    def test_marcadores_numerados(self):
        img = modelo.crear(self.t, "imagen", archivo="a.png", ancho=100, alto=100)
        modelo.anadir_marcador(self.t, img, 0.1, 0.1)
        modelo.anadir_marcador(self.t, img, 0.9, 0.9)
        self.assertEqual([m["n"] for m in img["marcadores"]], [1, 2])
        self.assertEqual(modelo.siguiente_marcador(self.t), 3)

    def test_recorte_y_volteo(self):
        img = modelo.crear(self.t, "imagen", archivo="a.png", x=0, y=0, ancho=200, alto=100)
        modelo.recortar(img, [0.5, 0.0, 1.0, 0.5])
        self.assertAlmostEqual(img["x"], 100.0)
        self.assertAlmostEqual(img["ancho"], 100.0)
        self.assertAlmostEqual(img["alto"], 50.0)
        self.assertAlmostEqual(modelo.visible_u(img, 0.75), 0.5)
        self.assertAlmostEqual(modelo.imagen_u(img, 0.5), 0.75)
        img["volteo"] = True
        self.assertAlmostEqual(modelo.visible_u(img, 0.6), 0.8)
        self.assertAlmostEqual(modelo.imagen_u(img, modelo.visible_u(img, 0.6)), 0.6)
        modelo.recortar(img, [0.0, 0.0, 1.0, 1.0])
        self.assertAlmostEqual(img["ancho"], 200.0)
        # Un recorte minúsculo se ignora
        modelo.recortar(img, [0.5, 0.5, 0.5, 0.5])
        self.assertAlmostEqual(img["ancho"], 200.0)

    def test_marco_y_rejilla(self):
        marco = modelo.crear(self.t, "marco", x=0, y=0, ancho=500, alto=500)
        dentro = modelo.crear(self.t, "imagen", archivo="a.png", x=10, y=10, ancho=50, alto=50)
        fuera = modelo.crear(self.t, "imagen", archivo="b.png", x=600, y=10, ancho=50, alto=50)
        self.assertEqual(modelo.dentro_de_marco(self.t, marco), [dentro])
        modelo.ordenar_en_rejilla(self.t, [dentro, fuera], origen=(0, 0), separacion=10, columnas=2)
        self.assertEqual((dentro["x"], fuera["x"]), (0, 60))
        modelo.alinear(self.t, [dentro, fuera], "arriba")
        self.assertEqual(dentro["y"], fuera["y"])

    def test_listas(self):
        texto = "- [x] Blocking\n[ ] Topología\nUVs\n\n* Render"
        self.assertEqual(modelo.lineas_lista(texto), [(True, "Blocking"), (False, "Topología"), (False, "UVs"),
                                                      (False, "Render")])
        texto = modelo.alternar_linea(modelo.texto_lista(modelo.lineas_lista(texto)), 2)
        self.assertEqual(modelo.lineas_lista(texto)[2], (True, "UVs"))
        nota = modelo.crear(self.t, "nota", texto="uno\ndos")
        modelo.convertir_nota(nota)
        self.assertEqual(nota["subtipo"], "lista")
        modelo.convertir_nota(nota)
        self.assertEqual(nota["texto"], "uno\ndos")

    def test_historial(self):
        h = modelo.Historial(limite=3)
        h.guardar(self.t)
        modelo.crear(self.t, "nota", texto="a")
        anterior = h.deshacer(self.t)
        self.assertEqual(anterior["elementos"], [])
        siguiente = h.rehacer(anterior)
        self.assertEqual(len(siguiente["elementos"]), 1)
        for _ in range(6):
            modelo.crear(self.t, "nota")
            h.guardar(self.t)
        self.assertEqual(len(h._atras), 3)


class Archivo(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.png = os.path.join(self.dir, "ref.png")
        with open(self.png, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\nfalso")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_crear_guardar_leer(self):
        carpeta = archivo.crear(self.dir, "Robot: vistas?")
        self.assertTrue(archivo.es_tablero(carpeta))
        self.assertEqual(archivo.nombre_de(carpeta), "Robot_ vistas_")
        t = archivo.leer(carpeta)
        rel = archivo.importar_imagen(carpeta, self.png)
        self.assertEqual(rel, archivo.importar_imagen(carpeta, self.png))  # no se duplica
        modelo.crear(t, "imagen", archivo=rel)
        archivo.guardar(carpeta, t)
        self.assertEqual(archivo.leer(carpeta)["elementos"][0]["archivo"], rel)
        self.assertEqual(archivo.listar(self.dir), [carpeta])
        otra = archivo.crear(self.dir, "Robot: vistas?")
        self.assertTrue(otra.endswith("Robot_ vistas_ 2.muro"))

    def test_limpiar(self):
        carpeta = archivo.crear(self.dir, "a")
        t = archivo.leer(carpeta)
        rel = archivo.importar_imagen(carpeta, self.png)
        archivo.guardar_bytes(carpeta, b"otra", ".png")
        modelo.crear(t, "imagen", archivo=rel)
        self.assertEqual(archivo.limpiar(carpeta, t), 1)
        self.assertEqual(os.listdir(os.path.join(carpeta, archivo.IMAGENES)), [os.path.basename(rel)])

    def test_zip_ida_y_vuelta(self):
        carpeta = archivo.crear(self.dir, "clase 1")
        t = archivo.leer(carpeta)
        rel = archivo.importar_imagen(carpeta, self.png)
        modelo.crear(t, "imagen", archivo=rel)
        modelo.crear(t, "nota", texto="Entrega el viernes")
        archivo.guardar(carpeta, t)
        ruta_zip = archivo.exportar_zip(carpeta, os.path.join(self.dir, "clase.zip"))
        destino = os.path.join(self.dir, "alumno")
        nueva = archivo.importar_zip(ruta_zip, destino)
        self.assertEqual(archivo.nombre_de(nueva), "clase 1")
        t2 = archivo.leer(nueva)
        self.assertEqual(len(t2["elementos"]), 2)
        self.assertTrue(os.path.isfile(archivo.ruta_absoluta(nueva, rel)))
        self.assertEqual(archivo.nombre_de(archivo.importar_zip(ruta_zip, destino)), "clase 1 2")

    def test_zip_malicioso_no_escapa(self):
        ruta_zip = os.path.join(self.dir, "malo.zip")
        with zipfile.ZipFile(ruta_zip, "w") as z:
            z.writestr("x.muro/tablero.json", json.dumps({"elementos": []}))
            z.writestr("x.muro/imagenes/../../fuera.png", b"x")
            z.writestr("x.muro/imagenes/script.py", b"x")
            z.writestr("x.muro/imagenes/bien.png", b"x")
        nueva = archivo.importar_zip(ruta_zip, os.path.join(self.dir, "dest"))
        self.assertEqual(os.listdir(os.path.join(nueva, archivo.IMAGENES)), ["bien.png"])
        self.assertFalse(os.path.exists(os.path.join(self.dir, "fuera.png")))

    def test_zip_sin_tablero(self):
        ruta_zip = os.path.join(self.dir, "vacio.zip")
        with zipfile.ZipFile(ruta_zip, "w") as z:
            z.writestr("hola.txt", "x")
        with self.assertRaises(ValueError):
            archivo.importar_zip(ruta_zip, self.dir)

    def test_copiar_tablero(self):
        carpeta = archivo.crear(self.dir, "plantilla")
        t = archivo.leer(carpeta)
        modelo.crear(t, "imagen", archivo=archivo.importar_imagen(carpeta, self.png))
        archivo.guardar(carpeta, t)
        copia = archivo.copiar_tablero(carpeta, os.path.join(self.dir, "otro"), "mío")
        self.assertEqual(archivo.nombre_de(copia), "mío")
        self.assertEqual(len(os.listdir(os.path.join(copia, archivo.IMAGENES))), 1)


class Escala(unittest.TestCase):
    def test_plano_front(self):
        # 100 px de cabeza (y=100) a pies (y=300) = 1.8 unidades; imagen 400x400
        d = escala.plano_de_imagen(400, 400, (200, 100), (200, 300), 1.8, "front", profundidad=10)
        self.assertAlmostEqual(d["unidades_por_px"], 0.009)
        self.assertAlmostEqual(d["alto"], 3.6)
        x, y, z = d["centro"]
        self.assertAlmostEqual(x, 0.0)
        self.assertAlmostEqual(y, 0.9)  # los pies quedan en y=0
        self.assertAlmostEqual(y - d["alto"] / 2 + (400 - 300) * d["unidades_por_px"], 0.0)
        self.assertEqual(z, -10)

    def test_plano_side_y_top(self):
        side = escala.plano_de_imagen(400, 400, (100, 100), (100, 300), 2.0, "side", profundidad=5)
        self.assertEqual(side["centro"][0], -5)
        self.assertAlmostEqual(side["centro"][2], -1.0)  # el punto está a la izquierda: el centro va hacia -Z
        top = escala.plano_de_imagen(400, 400, (200, 100), (200, 300), 2.0, "top", profundidad=5)
        self.assertEqual(top["centro"][1], -5)

    def test_plano_errores(self):
        with self.assertRaises(ValueError):
            escala.plano_de_imagen(10, 10, (1, 1), (1, 1), 1.0)
        with self.assertRaises(ValueError):
            escala.plano_de_imagen(10, 10, (1, 1), (1, 5), 0)

    def test_unidades_y_colores(self):
        self.assertAlmostEqual(escala.convertir(1.8, "m", "cm"), 180.0)
        self.assertEqual(escala.rgb_a_hex(*escala.hex_a_rgb("#a0b1c2")), "#a0b1c2")
        self.assertAlmostEqual(escala.srgb_a_lineal(1.0), 1.0)
        self.assertLess(escala.srgb_a_lineal(0.5), 0.5)


class Textos(unittest.TestCase):
    def test_claves_usadas_existen(self):
        import re
        usadas = set()
        dinamicas = {"aviso_gris_si", "aviso_gris_no", "aviso_volteo_si", "aviso_volteo_no", "bloqueado_no",
                     "ayuda_flecha", "ayuda_lapiz", "ayuda_recortar", "ayuda_cuentagotas", "alinear_izquierda",
                     "alinear_arriba", "alinear_centro_v", "alinear_centro_h", "cmd_fantasma", "cmd_capturar",
                     "cmd_nota", "instalado_titulo", "instalado_texto", "boton_aceptar"}
        dinamicas |= {"color_{}".format(i) for i in range(5)}
        for carpeta, _, nombres in os.walk(os.path.join(RAIZ, "scripts")):
            for n in nombres:
                if n.endswith(".py"):
                    with open(os.path.join(carpeta, n), encoding="utf-8") as f:
                        usadas |= set(re.findall(r'\bt\("([a-z0-9_]+[a-z0-9])"', f.read()))
        faltan = (usadas | dinamicas) - claves("es")
        self.assertEqual(faltan, set())


if __name__ == "__main__":
    unittest.main()
