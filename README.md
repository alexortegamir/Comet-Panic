# Comet Panic

<p align="center">
  <img src="assets/comet_panic_cover.jpeg" alt="Portada de Comet Panic" width="480">
</p>

Juego arcade sencillo para **ZX Spectrum 48K**, escrito en Sinclair BASIC y probado con el emulador [ZEsarUX](https://github.com/chernandezba/zesarux).

## Cómo se juega

Los cometas (`*`) caen desde la parte superior de la pantalla en una columna aleatoria. Controlas la nave (`A`) en la parte inferior y debes colocarte justo debajo de cada cometa antes de que llegue abajo.

- Si la nave está en la misma columna que el cometa al llegar abajo: **+1 punto** (sonido agudo).
- Si no: **pierdes una vida** (sonido grave).
- Empiezas con **3 vidas**.
- Consigue **10 puntos** para ganar (`GANASTE!`).
- Si te quedas sin vidas, aparece `FIN DEL JUEGO`.

### Controles

| Tecla | Acción    |
|-------|-----------|
| `O`   | Izquierda |
| `P`   | Derecha   |
| `X`   | Salir     |

## Estructura del proyecto

| Archivo                                                  | Descripción                                          |
|----------------------------------------------------------|------------------------------------------------------|
| [comet_panic.bas](comet_panic.bas)                       | Código fuente del juego en Sinclair BASIC (texto).   |
| [build_comet_panic_tap.py](build_comet_panic_tap.py)     | Script que tokeniza el BASIC y genera la cinta TAP.  |
| [comet_panic.tap](comet_panic.tap)                       | Cinta lista para cargar en un emulador.              |
| [assets/comet_panic_cover.jpeg](assets/comet_panic_cover.jpeg) | Portada del juego.                             |

## Generar la cinta TAP

Requiere Python 3 (sin dependencias externas). Desde la raíz del repositorio:

```bash
python3 build_comet_panic_tap.py
```

Esto genera `comet_panic.tap` con autoarranque en la línea 10.

## Probar el juego

### ZEsarUX

Desde la carpeta del ejecutable de ZEsarUX (ajusta la ruta al TAP según dónde hayas clonado el repositorio):

```bash
./zesarux --tape ruta/a/comet_panic/comet_panic.tap --fastautoload
```

### Otros emuladores

El archivo `comet_panic.tap` es una cinta estándar, así que funciona en cualquier emulador de ZX Spectrum (Fuse, Spectaculator, JSSpeccy, etc.). Normalmente basta con abrir el archivo; si no arranca solo, escribe `LOAD ""` (teclas `J`, `Symbol Shift + P` dos veces) y pulsa `Enter`.
