"""DOOM picture (patch) format helpers."""
import struct
import numpy as np


def decode(blob):
    """-> (pixels uint8 HxW, mask bool HxW, leftoff, topoff)"""
    w, h, lo, to = struct.unpack_from("<hhhh", blob)
    pix = np.zeros((h, w), np.uint8)
    mask = np.zeros((h, w), bool)
    for x in range(w):
        p = struct.unpack_from("<I", blob, 8 + 4 * x)[0]
        while blob[p] != 0xFF:
            top, n = blob[p], blob[p + 1]
            pix[top:top + n, x] = np.frombuffer(blob, np.uint8, n, p + 3)
            mask[top:top + n, x] = True
            p += n + 4
    return pix, mask, lo, to


def encode(pix, mask, lo=0, to=0):
    h, w = pix.shape
    cols = []
    for x in range(w):
        c = bytearray()
        y = 0
        while y < h:
            if not mask[y, x]:
                y += 1; continue
            y0 = y
            while y < h and mask[y, x] and y - y0 < 128:
                y += 1
            c += bytes([y0, y - y0, 0]) + pix[y0:y, x].tobytes() + b"\0"
        c += b"\xff"
        cols.append(bytes(c))
    out = bytearray(struct.pack("<hhhh", w, h, lo, to))
    off = 8 + 4 * w
    for c in cols:
        out += struct.pack("<I", off); off += len(c)
    for c in cols:
        out += c
    return bytes(out)
