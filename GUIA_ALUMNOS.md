# Muro: guía rápida

Muro es un tablero para tus imágenes de referencia y tus notas, dentro de Maya.

## Abrirlo

Menú **Muro › Abrir tablero**. La primera vez crea un tablero llamado «referencias» dentro de tu proyecto
(`sourceimages/muro`). Si guardas la escena, la próxima vez que la abras se abrirá también su tablero.

## Meter referencias

- Arrastra imágenes desde tu carpeta o desde el navegador hasta el tablero.
- O cópialas y pulsa `Ctrl+V` (`⌘V` en Mac) con el ratón encima del tablero.
- El botón de la cámara con esquinas captura lo que ves en el visor de Maya.

Las imágenes se copian dentro del proyecto: aunque borres el original, el tablero las conserva.

## Moverte

- **Rueda**: acercar y alejar. En el trackpad, dos dedos para moverte y pellizcar para acercar.
- **Alt + botón central** o **Espacio + arrastrar**: moverte.
- **F**: encuadrar lo seleccionado. **A**: verlo todo.

## Ordenar

- Arrastra para mover. La esquina blanca escala y el punto de arriba gira.
- **Ctrl+G** mete lo seleccionado en un marco con título.
- Clic derecho: menú de puntos con lo que puedes hacer con cada cosa.

## Anotar

- **N**: nota. **L**: lista de tareas (clic en una línea para tacharla).
- Doble clic en una nota para escribir. `**negrita**` y `*cursiva*` funcionan.
- Clic derecho en una imagen › **Marcador aquí**: pone un número en ese punto con su nota.
- **W** dibuja flechas de un elemento a otro y **P** es el lápiz. `Esc` para dejar la herramienta.

## Ver mejor

- **G**: gris, para comparar valores.
- **H**: voltear. Con la imagen volteada se notan los fallos de proporción.
- **C**: recortar (arrastra un rectángulo sobre la imagen).

## Llevarlo a Maya

- Clic derecho en una imagen › **Plano de imagen**: marca A en la cabeza y B en los pies, escribe la altura real
  y elige la cámara (front, side o top). El plano aparece a escala con los pies en el suelo.
  Es un plano libre colocado detrás de la escena mirando a esa cámara, así que también se ve en la perspectiva;
  para ocultarlo, apaga la capa «muro_referencias».
- **I** (cuentagotas): haz clic en un color de la imagen. Si tienes un objeto seleccionado en Maya, su material
  toma ese color. Los colores quedan abajo a la izquierda para volver a usarlos.
- **Fantasma** (botón del fantasma): el tablero se queda transparente encima del visor y puedes seguir modelando.
  Vuelve a pulsar el fantasma de la pastilla para salir.

## Entregar o compartir

- Menú del tablero (☰) › **Exportar tablero (.zip)**: un archivo con todo para entregar o compartir.
- **Importar tablero (.zip)**: abre el que te pase el profesor.
- **Exportar imagen PNG**: una imagen del tablero entero (o de un marco, desde su clic derecho).

`Ctrl+Z` deshace solo dentro del tablero, sin tocar tu escena.
