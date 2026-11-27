"""Decode LR2 ghost judgments for broad section analysis (ordinal, not timestamps).

The native PLAYSCORE codec is in GOMazk/OpenLR2/LR2/LR2_ghost.cpp.
The getghost.cgi envelope is documented by NETWORK::LR2IR_GetTargetInfo in
LR2_ir.cpp. Returning an empty-POOR count separately keeps the chart note
index stable. A ghost represents one score attempt, not a player's best lamp.
"""
import re
import zlib

MAX_BYTES = 1 << 20
SYMBOL = re.compile(rb"([@A-Ya-z])([0-9]*)")
TRAILER = re.compile(rb"Z{1,3}\Z")

# A literal prefix, terminal judgment and decimal count prefix per input token.
TOKEN = {c: (b"", c - 64, 0) for c in b"@ABCDE"}
for letters, judge, start in [(b"FGHIJKLMN",5,1),(b"STUVW",4,2),
                              (b"cdef",3,2),(b"op",1,2)]:
    for n, c in enumerate(letters,start):
        TOKEN[c] = (b"", judge, n)
for letters, lead, tails in [(b"PQR",5,(3,2,1)),(b"XYab",4,(5,3,2,1)),
                             (b"ghij",3,(5,4,2,1)),(b"klmn",1,(2,3,4,5))]:
    for c, last in zip(letters,tails):
        TOKEN[c] = (bytes([lead]), last, 0)
TOKEN[ord("q")] = (bytes([4,5,4]),5,0)
for n,c in enumerate(b"rstuvwxyz",1):
    TOKEN[c] = (bytes([4]),5,n)


def _plain(blob):
    if not isinstance(blob,(bytes,bytearray,memoryview)):
        raise ValueError("expected bytes")
    data = bytes(blob)
    if not data or len(data)>MAX_BYTES:
        raise ValueError("encoded size")
    if data.startswith(b"\x1f\x8b") or data[:2] in (b"x\x01",b"x\x5e",b"x\x9c",b"x\xda"):
        try:
            decoder = zlib.decompressobj(47)
            data = decoder.decompress(data,MAX_BYTES+1)
        except zlib.error as exc:
            raise ValueError("compression") from exc
        if not decoder.eof or decoder.unused_data or len(data)>MAX_BYTES:
            raise ValueError("compressed payload")
    data = data.strip(b"\x00\r\n\t ")
    if b"," in data:
        name, option, seed, data = data.rsplit(b",",3)
        if not name or not option.lstrip(b"-").isdigit() or not seed.lstrip(b"-").isdigit():
            raise ValueError("unsupported ghost envelope")
    return data


def decode(blob):
    """Return note-bearing judgments as bytes with values 1..5, and empty POOR count."""
    data = _plain(blob)
    end = TRAILER.search(data)
    if end is None or end.start()==0:
        raise ValueError("missing ghost judgments or terminator")
    data = data[:end.start()]
    notes = bytearray()
    empty = 0
    pos = 0
    while pos<len(data):
        symbol = SYMBOL.match(data,pos)
        if symbol is None:
            raise ValueError("invalid token")
        token = TOKEN.get(symbol[1][0])
        if token is None:
            raise ValueError("unsupported token")
        prefix,judge,first = token
        digits = symbol[2]
        if len(digits)>7:
            raise ValueError("repeat length")
        count = max(1,first * 10**len(digits) + int(digits or b"0"))
        if len(notes) + empty + len(prefix) + count>MAX_BYTES:
            raise ValueError("decoded size")
        notes.extend(prefix)
        if judge:
            notes.extend(bytes([judge])*count)
        else:
            empty+=count
        pos=symbol.end()
    if not notes:
        raise ValueError("no chart judgments")
    return bytes(notes),empty


if __name__=="__main__":
    from collections import Counter
    cases = [
        (b"ABCDE@ZZ", bytes([1,2,3,4,5]), 1),
        (b"qT@3Z", bytes([4,5,4,5,4,4,4]), 3),
        (b"player,127,245,qZZ", bytes([4,5,4,5]),0),
        (b"n2r0oZ", bytes([1,5,5,4])+bytes([5])*10+bytes([1,1]),0),
        (zlib.compress(b"PQQb3ZZ"),bytes([5,3,5,2,5,2,4,1,1,1]),0),
    ]
    for raw,expected,empty in cases:
        assert decode(raw)==(expected,empty)
    for raw in (b"",b"XYZ123",b"OZ",b"A12345678Z",b"Z",b"<html>Z",b"@65Z",b"A\nBZ"):
        try:
            decode(raw)
        except ValueError:
            continue
        raise AssertionError(raw)
    print("All LR2 ghost enum, repeat, compound, wrapper and rejection controls passed.")
