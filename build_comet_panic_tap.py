#!/usr/bin/env python3
"""Build a standard ZX Spectrum BASIC TAP from comet_panic.bas."""

from pathlib import Path
import math
import re
import struct


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


def main() -> None:
    folder = Path(__file__).parent
    source = (folder / "comet_panic.bas").read_text(encoding="ascii")
    program = basic_program(source)
    filename = b"COMETPANIC"
    filename = filename[:10].ljust(10, b" ")
    header = bytes((0, 0)) + filename + struct.pack("<H", len(program)) + struct.pack("<H", 10) + struct.pack("<H", len(program))
    tap = tap_block(header) + tap_block(bytes((0xFF,)) + program)
    (folder / "comet_panic.tap").write_bytes(tap)
    print(f"Created comet_panic.tap ({len(tap)} bytes)")


if __name__ == "__main__":
    main()