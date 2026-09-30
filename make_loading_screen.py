#!/usr/bin/env python3
"""Draw the Comet Panic loading screen as a ZX Spectrum .scr (plus a .png preview)."""

from pathlib import Path
import math
import random
import struct
import zlib

WIDTH, HEIGHT = 256, 192
COLS, ROWS = 32, 24
BLACK, BLUE, RED, MAGENTA, GREEN, CYAN, YELLOW, WHITE = range(8)

FONT = {
    " ": (0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00),
    "!": (0x00, 0x10, 0x10, 0x10, 0x10, 0x00, 0x10, 0x00),
    ".": (0x00, 0x00, 0x00, 0x00, 0x00, 0x18, 0x18, 0x00),
    "A": (0x00, 0x3C, 0x42, 0x42, 0x7E, 0x42, 0x42, 0x00),
    "C": (0x00, 0x3C, 0x42, 0x40, 0x40, 0x42, 0x3C, 0x00),
    "D": (0x00, 0x78, 0x44, 0x42, 0x42, 0x44, 0x78, 0x00),
    "E": (0x00, 0x7E, 0x40, 0x7C, 0x40, 0x40, 0x7E, 0x00),
    "G": (0x00, 0x3C, 0x42, 0x40, 0x4E, 0x42, 0x3C, 0x00),
    "H": (0x00, 0x42, 0x42, 0x7E, 0x42, 0x42, 0x42, 0x00),
    "I": (0x00, 0x3E, 0x08, 0x08, 0x08, 0x08, 0x3E, 0x00),
    "L": (0x00, 0x40, 0x40, 0x40, 0x40, 0x40, 0x7E, 0x00),
    "M": (0x00, 0x42, 0x66, 0x5A, 0x42, 0x42, 0x42, 0x00),
    "N": (0x00, 0x42, 0x62, 0x52, 0x4A, 0x46, 0x42, 0x00),
    "O": (0x00, 0x3C, 0x42, 0x42, 0x42, 0x42, 0x3C, 0x00),
    "P": (0x00, 0x7C, 0x42, 0x42, 0x7C, 0x40, 0x40, 0x00),
    "R": (0x00, 0x7C, 0x42, 0x42, 0x7C, 0x44, 0x42, 0x00),
    "S": (0x00, 0x3C, 0x40, 0x3C, 0x02, 0x42, 0x3C, 0x00),
    "T": (0x00, 0xFE, 0x10, 0x10, 0x10, 0x10, 0x10, 0x00),
    "V": (0x00, 0x42, 0x42, 0x42, 0x42, 0x24, 0x18, 0x00),
}

# Left half of the rocket (12 px); the right half is its mirror image.
ROCKET_LEFT = [
    "...........#", "...........#", "..........##", "..........##",
    ".........###", ".........###", "........####", "........####",
    ".......#####", ".......#####", ".......#####", ".......###..",
    ".......##...", ".......##...", ".......##...", ".......###..",
    ".......#####", ".......#####", ".......#####", ".......#####",
    ".......#####", ".......#####", ".......#####", ".......#####",
    "......######", ".....#######", "....########", "...#########",
    "..##########", "..###.######", "..##..######", "..#...######",
    "........####", "........####", "........####", "........####",
    ".........###", ".........###", ".........###", ".........###",
]


class Screen:
    def __init__(self) -> None:
        self.pixels = [[0] * WIDTH for _ in range(HEIGHT)]
        self.attrs = [[WHITE] * COLS for _ in range(ROWS)]
        self.used = [[False] * COLS for _ in range(ROWS)]

    def attr(self, col: int, row: int, ink: int, paper: int = BLACK, bright: bool = True, flash: bool = False) -> None:
        if 0 <= col < COLS and 0 <= row < ROWS:
            self.attrs[row][col] = (flash << 7) | (bright << 6) | (paper << 3) | ink
            self.used[row][col] = True

    def plot(self, x: int, y: int, ink: int | None = None) -> None:
        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
            self.pixels[y][x] = 1
            if ink is not None:
                self.attr(x // 8, y // 8, ink)

    def text(self, col: int, row: int, string: str, ink: int, flash: bool = False) -> None:
        for index, char in enumerate(string):
            for gy, bits in enumerate(FONT[char]):
                for gx in range(8):
                    if bits & (0x80 >> gx):
                        self.plot((col + index) * 8 + gx, row * 8 + gy)
            self.attr(col + index, row, ink, flash=flash)

    def big_text(self, col: int, row: int, string: str, top_ink: int, bottom_ink: int) -> None:
        for index, char in enumerate(string):
            x0 = (col + index * 2) * 8
            for gy, bits in enumerate(FONT[char]):
                bits |= bits >> 1
                for gx in range(8):
                    if bits & (0x80 >> gx):
                        for dy in range(2):
                            for dx in range(2):
                                self.plot(x0 + gx * 2 + dx, row * 8 + gy * 2 + dy)
            for c in range(col + index * 2, col + index * 2 + 2):
                self.attr(c, row, top_ink)
                self.attr(c, row + 1, bottom_ink)

    def to_scr(self) -> bytes:
        data = bytearray(6912)
        for y in range(HEIGHT):
            base = ((y & 0xC0) << 5) | ((y & 0x07) << 8) | ((y & 0x38) << 2)
            for col in range(COLS):
                byte = 0
                for bit in range(8):
                    byte = (byte << 1) | self.pixels[y][col * 8 + bit]
                data[base + col] = byte
        for row in range(ROWS):
            for col in range(COLS):
                data[6144 + row * COLS + col] = self.attrs[row][col]
        return bytes(data)


def draw_earth(screen: Screen) -> None:
    cx, cy, radius = 127.5, 146 + 260, 260
    for row in range(18, 22):
        for col in range(COLS):
            cells = [(col * 8 + dx, row * 8 + dy) for dy in range(8) for dx in range(8)]
            inside = [(x, y) for x, y in cells if (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2]
            if not inside:
                continue
            if len(inside) == 64:
                screen.attr(col, row, GREEN, paper=BLUE)
                for x, y in inside:
                    land = math.sin(x * 0.07) + math.sin(y * 0.21 + x * 0.03) + 1.3 * math.sin((x + y) * 0.045)
                    if land > 0.9:
                        screen.plot(x, y)
            else:
                screen.attr(col, row, BLUE)
                for x, y in inside:
                    screen.plot(x, y)


def draw_rocket(screen: Screen, x0: int, y0: int, rng: random.Random) -> None:
    for y, left in enumerate(ROCKET_LEFT):
        for x, char in enumerate(left + left[::-1]):
            if char == "#":
                screen.plot(x0 + x, y0 + y, WHITE)
    flame_top = y0 + len(ROCKET_LEFT)
    for y in range(16):
        half = 3.5 - y * 0.2 + rng.uniform(-0.8, 0.8)
        for x in range(24):
            if abs(x - 11.5) < half and rng.random() > 0.15:
                screen.plot(x0 + x, flame_top + y)
    for col in range(x0 // 8, x0 // 8 + 3):
        screen.attr(col, flame_top // 8, RED)
        screen.attr(col, flame_top // 8 + 1, YELLOW)


def draw_comet(screen: Screen, hx: int, hy: int, radius: int, length: int, tail_ink: int, rng: random.Random) -> None:
    dx, dy = 0.83, -0.56
    for t in range(length):
        fade = 1 - t / length
        width = radius * fade + 0.5
        for s in range(-int(width), int(width) + 1):
            if rng.random() < fade:
                screen.plot(round(hx + dx * t - dy * s), round(hy + dy * t + dx * s), tail_ink)
    for y in range(-radius, radius + 1):
        for x in range(-radius, radius + 1):
            if x * x + y * y <= radius * radius:
                screen.plot(hx + x, hy + y, WHITE)


def draw_stars(screen: Screen, rng: random.Random) -> None:
    for _ in range(90):
        col, row = rng.randrange(COLS), rng.randrange(18)
        if screen.used[row][col]:
            continue
        x, y = col * 8 + rng.randint(1, 6), row * 8 + rng.randint(1, 6)
        screen.plot(x, y)
        if rng.random() < 0.25:
            for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                screen.plot(x + ox, y + oy)
        screen.attr(col, row, rng.choice((WHITE, WHITE, CYAN, YELLOW)), bright=rng.random() < 0.6)


def build_screen() -> Screen:
    rng = random.Random(1982)
    screen = Screen()
    screen.big_text(5, 1, "COMET PANIC", YELLOW, RED)
    screen.text(8, 4, "SAVE THE EARTH!", CYAN)
    draw_rocket(screen, 48, 72, rng)
    draw_comet(screen, 184, 92, 5, 60, YELLOW, rng)
    draw_comet(screen, 116, 120, 3, 36, CYAN, rng)
    draw_comet(screen, 226, 136, 4, 40, MAGENTA, rng)
    screen.text(11, 17, "LOADING...", WHITE, flash=True)
    draw_earth(screen)
    draw_stars(screen, rng)
    return screen


def write_png(path: Path, screen: Screen, scale: int = 2) -> None:
    rows = []
    for y in range(HEIGHT):
        row = bytearray()
        for x in range(WIDTH):
            attr = screen.attrs[y // 8][x // 8]
            colour = attr & 7 if screen.pixels[y][x] else (attr >> 3) & 7
            level = 0xFF if attr & 0x40 else 0xD7
            rgb = bytes((level if colour & 2 else 0, level if colour & 4 else 0, level if colour & 1 else 0))
            row.extend(rgb * scale)
        rows.extend([b"\x00" + bytes(row)] * scale)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    header = struct.pack(">IIBBBBB", WIDTH * scale, HEIGHT * scale, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b"")
    path.write_bytes(png)


def main() -> None:
    assets = Path(__file__).parent / "assets"
    screen = build_screen()
    (assets / "comet_panic_loading.scr").write_bytes(screen.to_scr())
    write_png(assets / "comet_panic_loading.png", screen)
    print("Created assets/comet_panic_loading.scr (6912 bytes) and assets/comet_panic_loading.png")


if __name__ == "__main__":
    main()
