#!/usr/bin/env python3
"""Build comet_panic.tap: BASIC loader + loading screen + compiled game (Boriel ZX Basic)."""

from pathlib import Path
import math
import os
import re
import shutil
import struct
import subprocess

from make_loading_screen import FONT


TOKEN_NAMES = """
SPECTRUM
PLAY
RND
INKEY$
PI
FN
POINT
SCREEN$
ATTR
AT
TAB
VAL$
CODE
VAL
LEN
SIN
COS
TAN
ASN
ACS
ATN
LN
EXP
INT
SQR
SGN
ABS
PEEK
IN
USR
STR$
CHR$
NOT
BIN
OR
AND
<=
>=
<>
LINE
THEN
TO
STEP
DEF FN
CAT
FORMAT
MOVE
ERASE
OPEN #
CLOSE #
MERGE
VERIFY
BEEP
CIRCLE
INK
PAPER
FLASH
BRIGHT
INVERSE
OVER
OUT
LPRINT
LLIST
STOP
READ
DATA
RESTORE
NEW
BORDER
CONTINUE
DIM
REM
FOR
GO TO
GO SUB
INPUT
LOAD
LIST
LET
PAUSE
NEXT
POKE
PRINT
PLOT
RUN
SAVE
RANDOMIZE
IF
CLS
DRAW
CLEAR
RETURN
COPY
""".strip().splitlines()
TOKENS = {name: 0xA3 + index for index, name in enumerate(TOKEN_NAMES)}


def spectrum_number(value: str) -> bytes:
    number = float(value)
    if number.is_integer() and -32768 <= number <= 32767:
        return b"\x00\x00" + int(number).to_bytes(2, "little", signed=True) + b"\x00"
    if number == 0:
        return b"\x00\x00\x00\x00\x00"
    mantissa, exponent = math.frexp(number)
    exponent += 1
    fraction = int(round((mantissa * 2 - 1) * (1 << 31)))
    return bytes((exponent + 0x7F,)) + fraction.to_bytes(4, "big")


def encode_numbers(data: bytes) -> bytes:
    output = bytearray()
    index = 0
    in_string = False
    while index < len(data):
        byte = data[index]
        if byte == ord('"'):
            in_string = not in_string
            output.append(byte)
            index += 1
            continue
        if not in_string and (48 <= byte <= 57 or (byte == ord('.') and index + 1 < len(data) and data[index + 1] >= ord('0'))):
            match = re.match(rb"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", data[index:])
            if match:
                literal = match.group(0)
                output.extend(literal)
                output.append(0x0E)
                output.extend(spectrum_number(literal.decode("ascii")))
                index += len(literal)
                continue
        output.append(byte)
        index += 1
    return bytes(output)


def tokenize_segment(segment: str) -> bytes:
    result = bytearray()
    index = 0
    in_string = False
    keywords = sorted(TOKENS, key=len, reverse=True)
    while index < len(segment):
        if segment[index] == '"':
            in_string = not in_string
            result.append(ord('"'))
            index += 1
            continue
        if in_string:
            result.extend(segment[index].encode("ascii"))
            index += 1
            continue
        matched = False
        for keyword in keywords:
            if segment[index:index + len(keyword)].upper() != keyword:
                continue
            before = segment[index - 1] if index else " "
            after = segment[index + len(keyword)] if index + len(keyword) < len(segment) else " "
            if keyword[0].isalnum() and (before.isalnum() or before in "_$"):
                continue
            if keyword[-1].isalnum() and (after.isalnum() or after in "_$"):
                continue
            result.append(TOKENS[keyword])
            index += len(keyword)
            matched = True
            break
        if not matched:
            if segment[index] == " " and result and result[-1] == TOKENS["LET"]:
                index += 1
                continue
            result.extend(segment[index].encode("ascii"))
            index += 1
    return bytes(result)


def tokenize_line(text: str) -> bytes:
    return encode_numbers(tokenize_segment(text))


def basic_program(source: str) -> bytes:
    program = bytearray()
    for line in source.splitlines():
        if not line.strip():
            continue
        number_text, content = line.split(" ", 1)
        body = tokenize_line(content) + b"\r"
        program.extend(struct.pack(">H", int(number_text)))
        program.extend(struct.pack("<H", len(body)))
        program.extend(body)
    return bytes(program)


def tap_block(payload: bytes) -> bytes:
    block = payload + bytes((xor_checksum(payload),))
    return struct.pack("<H", len(block)) + block


def xor_checksum(payload: bytes) -> int:
    checksum = 0
    for byte in payload:
        checksum ^= byte
    return checksum


CODE_ORG = 32768
# Must match OBJT in comet_panic.bas (runtime tables live from here up)
TABLES_ADDRESS = 61440

LOADER_SOURCE = f"""
10 CLEAR {CODE_ORG - 1}: BORDER 0: PAPER 0: INK 7: CLS
20 POKE 23624,0
30 LOAD ""SCREEN$
40 LOAD ""CODE
50 RANDOMIZE USR {CODE_ORG}
"""

# 16x16 sprites (rows may be fewer; they are padded). Order defines the SPR_* constants.
SPRITES = {
    "SHIP": [
        ".......##.......",
        ".......##.......",
        "......####......",
        "......####......",
        "......#..#......",
        ".....##..##.....",
        ".....######.....",
        ".....######.....",
        "..#..######..#..",
        "..#.########.#..",
        ".##.########.##.",
        ".##############.",
        "################",
        "###.##.##.##.###",
        "##...#....#...##",
        ".......##.......",
    ],
    "SHIP2": [
        ".......##.......",
        ".......##.......",
        "......####......",
        "......####......",
        "......#..#......",
        ".....##..##.....",
        ".....######.....",
        ".....######.....",
        "..#..######..#..",
        "..#.########.#..",
        ".##.########.##.",
        ".##############.",
        "################",
        "###.##.##.##.###",
        "##...#.##.#...##",
        "......#..#......",
    ],
    "SHOT": [".......##......."] * 8,
    "BOMB": [
        ".......##.......",
        "......####......",
        "......####......",
        ".......##.......",
        "......#..#......",
        ".......##.......",
    ],
    "COLDEYE": [
        "##............##",
        ".##..........##.",
        "..##...##...##..",
        "...##.####.##...",
        "....########....",
        "...###.##.###...",
        "..####.##.####..",
        ".##############.",
        "##..########..##",
        "#....######....#",
        ".....#.##.#.....",
        "....#..##..#....",
        "...#........#...",
    ],
    "COLDEYE2": [
        "................",
        "................",
        ".......##.......",
        "......####......",
        "....########....",
        "...###.##.###...",
        "..####.##.####..",
        ".##############.",
        "################",
        "##...######...##",
        "#....#.##.#....#",
        "#...#..##..#...#",
        "...#........#...",
    ],
    "SUPERFLY": [
        "..#..........#..",
        "...#........#...",
        "....#.####.#....",
        ".....######.....",
        "##..##.##.##..##",
        "####.######.####",
        ".###.######.###.",
        "..##..####..##..",
        "......####......",
        ".....#.##.#.....",
        "....#..##..#....",
        "...#...##...#...",
    ],
    "SUPERFLY2": [
        "................",
        "..#..........#..",
        "...#.######.#...",
        "....########....",
        "#...##.##.##...#",
        "##..#.####.#..##",
        "####.######.####",
        "###...####...###",
        "#.....####.....#",
        ".....#.##.#.....",
        "....#..##..#....",
        ".....#....#.....",
    ],
    "ATOMIC": [
        "......####......",
        "....##....##....",
        "...#..####..#...",
        "..#..#....#..#..",
        ".#..#..##..#..#.",
        ".#.#..####..#.#.",
        "#..#.######.#..#",
        "#..#.######.#..#",
        ".#.#..####..#.#.",
        ".#..#..##..#..#.",
        "..#..#....#..#..",
        "...#..####..#...",
        "....##....##....",
        "......####......",
    ],
    "ATOMIC2": [
        "................",
        "##............##",
        ".##..........##.",
        "..##..####..##..",
        "...###....###...",
        "....#.####.#....",
        "....#.####.#....",
        "....#.####.#....",
        "....#.####.#....",
        "...###....###...",
        "..##..####..##..",
        ".##..........##.",
        "##............##",
    ],
    "EXPL": [
        "................",
        "..#....#....#...",
        "...#...#...#....",
        "....#..#..#.....",
        ".....#.#.#......",
        "......###.......",
        "##..#######..###",
        "......###.......",
        ".....#.#.#......",
        "....#..#..#.....",
        "...#...#...#....",
        "..#....#....#...",
    ],
    "EXPL2": [
        "#.......#......#",
        "...#.......#....",
        ".#....#.#....#..",
        "....#.....#.....",
        "#..#..#.#..#...#",
        "......#.#.......",
        ".#..#.....#..#..",
        "......#.#.......",
        "#..#..#.#..#...#",
        "....#.....#.....",
        ".#....#.#....#..",
        "...#.......#....",
        "#.......#......#",
    ],
}


def preshifted(rows: list[str]) -> bytes:
    """8 copies (one per pixel offset) of 16 rows x 3 bytes, as drawn by drawSpr."""
    if len(rows) > 16 or any(len(row) != 16 or set(row) - {".", "#"} for row in rows):
        raise ValueError(f"Bad sprite: {rows}")
    values = [int(row.replace("#", "1").replace(".", "0"), 2) for row in rows]
    values += [0] * (16 - len(values))
    data = bytearray()
    for shift in range(8):
        for value in values:
            data.extend(((value << 8) >> shift).to_bytes(3, "big"))
    return bytes(data)


def sine_table(amplitude: float, offset: int = 0, phase: float = 0.0) -> list[int]:
    return [offset + round(amplitude * math.sin(2 * math.pi * i / 64 + phase)) for i in range(64)]


def integer_array(name: str, values: list[int]) -> str:
    return f"dim {name}({len(values) - 1}) as integer => {{" + ", ".join(map(str, values)) + "}"


def title_logo(text: str = "COMET PANIC") -> bytes:
    """Bold font scaled 2x wide and 3x tall: 24 pixel rows of 2 bytes per character."""
    rows = []
    for glyph_row in range(8):
        bits = 0
        for char in text:
            value = FONT[char][glyph_row]
            value |= value >> 1
            wide = 0
            for bit in range(8):
                if value & (0x80 >> bit):
                    wide |= 0xC000 >> (bit * 2)
            bits = (bits << 16) | wide
        rows += [bits.to_bytes(2 * len(text), "big")] * 3
    return b"".join(rows)


def sprites_include() -> str:
    data = b"".join(preshifted(rows) for rows in SPRITES.values())
    logo = title_logo()
    lines = ["' Generated by build_comet_panic_tap.py - do not edit."]
    lines += [f"const SPR_{name} as ubyte = {index}" for index, name in enumerate(SPRITES)]
    lines.append(f"const NSPR as ubyte = {len(SPRITES)}")
    lines.append(f"dim titleGfx({len(logo) - 1}) as ubyte => {{" + ", ".join(map(str, logo)) + "}")
    lines.append(f"dim sprData({len(data) - 1}) as ubyte => {{ _")
    rows = [", ".join(str(b) for b in data[i:i + 24]) for i in range(0, len(data), 24)]
    lines.append(", _\n".join(rows) + " _")
    lines.append("}")
    # Motion tables in 1/16 pixel units: per-enemy orbit and flock sway
    lines.append(integer_array("orbX", sine_table(320)))
    lines.append(integer_array("orbY", sine_table(192, phase=math.pi / 2)))
    lines.append(integer_array("swayX", sine_table(896, 1920)))
    lines.append(integer_array("swayY", sine_table(128, 640, math.pi / 2)))
    return "\n".join(lines) + "\n"


def find_zxbc(folder: Path) -> str:
    for candidate in (os.environ.get("ZXBC"), shutil.which("zxbc"), folder / ".venv" / "bin" / "zxbc"):
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise SystemExit("zxbc not found: install Boriel ZX Basic (pip install zxbasic) or set ZXBC")


def compile_game(folder: Path) -> bytes:
    build = folder / "build"
    build.mkdir(exist_ok=True)
    (build / "sprites.bas").write_text(sprites_include(), encoding="ascii")
    output = build / "comet_panic.bin"
    subprocess.run(
        [find_zxbc(folder), str(folder / "comet_panic.bas"), "--org", str(CODE_ORG), "-O2",
         "-I", str(build), "-M", str(build / "comet_panic.map"), "-o", str(output)],
        check=True,
    )
    code = output.read_bytes()
    if CODE_ORG + len(code) > TABLES_ADDRESS:
        raise SystemExit(f"Game code ({len(code)} bytes) overlaps the data tables at {TABLES_ADDRESS}")
    return code


def tap_file(header: bytes, data: bytes) -> bytes:
    return tap_block(header) + tap_block(bytes((0xFF,)) + data)


def program_file(name: bytes, program: bytes, autostart: int) -> bytes:
    header = bytes((0, 0)) + name.ljust(10, b" ") + struct.pack("<HHH", len(program), autostart, len(program))
    return tap_file(header, program)


def code_file(name: bytes, data: bytes, start: int) -> bytes:
    header = bytes((0, 3)) + name.ljust(10, b" ") + struct.pack("<HHH", len(data), start, 32768)
    return tap_file(header, data)


def main() -> None:
    folder = Path(__file__).parent
    screen = (folder / "assets" / "comet_panic_loading.scr").read_bytes()
    if len(screen) != 6912:
        raise SystemExit("assets/comet_panic_loading.scr must be 6912 bytes (run make_loading_screen.py)")
    game = compile_game(folder)
    tap = (
        program_file(b"COMETPANIC", basic_program(LOADER_SOURCE), 10)
        + code_file(b"SCREEN", screen, 16384)
        + code_file(b"CP-GAME", game, CODE_ORG)
    )
    (folder / "comet_panic.tap").write_bytes(tap)
    print(f"Created comet_panic.tap ({len(tap)} bytes)")


if __name__ == "__main__":
    main()