"""Build the M_BADAPL menu graphic ("Bad apple") from DOOM's own menu letters.

Glyphs are cut from the original menu graphics by exact column ranges (full mask:
in this font the dark red edge is part of the letter shading). The big B is made
from the big D of "Knee-Deep" plus a middle bar and a notch on the right side.
"""
import os, sys, struct
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from patches import decode, encode

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = open(os.path.join(ROOT, "DOOM.WAD"), "rb").read()
n, o = struct.unpack_from("<ii", d, 4)
L = {}
for i in range(n):
    p, s, nm = struct.unpack_from("<ii8s", d, o + 16 * i)
    L[nm.rstrip(b"\0").decode()] = d[p:p + s]
pal = np.frombuffer(L["PLAYPAL"][:768], np.uint8).reshape(256, 3).astype(int)
H = 15


def cut(name, x0, x1):
    px, m, _, _ = decode(L[name])
    return px[:H, x0:x1].copy(), m[:H, x0:x1].copy()


def letter(name, c0, c1, pad=2):
    """bright core columns [c0,c1); keep only pixels within `pad` of this letter's core,
    which drops edge pixels that belong to the neighbouring letters"""
    gp, gm = cut(name, c0 - pad, c1 + pad)
    core = gm & (pal[gp].sum(2) >= 150)
    core[:, :pad] = False
    core[:, -pad:] = False
    h, w = core.shape
    big = np.zeros((h + 2 * pad, w + 2 * pad), bool)
    for dy in range(-pad, pad + 1):
        for dx in range(-pad, pad + 1):
            big[pad + dy:pad + dy + h, pad + dx:pad + dx + w] |= core
    return gp, gm & big[pad:pad + h, pad:pad + w]


def show_ascii(g):
    gp, gm = g
    br = pal[gp].sum(2)
    for y in range(gp.shape[0]):
        print("".join(" " if not gm[y, x] else ("." if br[y, x] < 60 else ("o" if br[y, x] < 150 else "#"))
                      for x in range(gp.shape[1])))
    print()


# --- glyphs (column ranges chosen on the original graphics) ---
D = cut("M_EPI1", 71, 86)        # big D of "Deep"
a = letter("M_LOADG", 32, 44)
dd = letter("M_LOADG", 46, 58)
p = letter("M_OPTION", 18, 30)
l_ = letter("M_HURT", 116, 124)
e = letter("M_HURT", 126, 137)
# leftover single pixels of neighbouring letters (T after P, O before A, N before E)
p[1][2:6, 14:] = False
p[1][2, 0] = False
p[0][9, 11] = p[0][9, 10]     # lone bright pixel under the P's bowl reads as a stray dot
a[1][:12, 0] = False
e[1][13, 0] = False
e[1][:, 14:] = False          # column 14 is already the N of "plenty"

# --- B from D ---
bp, bm = D[0].copy(), D[1].copy()
w = bp.shape[1]
top_bar = bp[1].copy()             # bright top bar row of the D
# middle bar across the counter (rows 7-8), coloured like D's own bars
for y, src in ((7, 1), (8, 11)):
    for x in range(1, w - 3):
        if not bm[y, x] or pal[bp[y, x]].sum() < 150:
            bp[y, x] = bp[src, x] if bm[src, x] else top_bar[x]
            bm[y, x] = True
# notch on the right at the waist so it reads as B, not D
for y in (7, 8):
    xs = np.nonzero(bm[y])[0]
    bm[y, xs[-1]] = False
    if y == 7:
        bm[y, xs[-2]] = False
B = (bp, bm)

if "--ascii" in sys.argv:
    for g in (D, B, a, dd, p, l_, e):
        show_ascii(g)

word = [[B, a, dd], [a, p, p, l_, e]]
OVER, SPACE = 2, 8
canvas_p = np.zeros((H, 400), np.uint8)
canvas_m = np.zeros((H, 400), bool)
x = 0
for wi, wd in enumerate(word):
    if wi:
        x += SPACE
    for gi, (gp, gm) in enumerate(wd):
        if gi:
            x -= OVER
        rp, rm = canvas_p[:, x:x + gp.shape[1]], canvas_m[:, x:x + gp.shape[1]]
        take = gm & (~rm | (pal[gp].sum(2) > pal[rp].sum(2)))
        rp[take] = gp[take]
        rm |= gm
        x += gp.shape[1]
pix, mask = canvas_p[:, :x], canvas_m[:, :x]
# close 1-pixel seams where two glyphs meet (background showing through the edge):
# a transparent pixel with ink left and right of it gets the darker neighbour's colour
for y in range(H):
    for xx in range(1, x - 1):
        if not mask[y, xx] and mask[y, xx - 1] and mask[y, xx + 1]:
            l, r = pix[y, xx - 1], pix[y, xx + 1]
            pix[y, xx] = l if pal[l].sum() <= pal[r].sum() else r
            mask[y, xx] = True
# drop specks: edge pixels hanging on by at most one neighbour (not on the bottom row)
P = np.pad(mask, 1)
nb = sum(np.roll(np.roll(P, dy, 0), dx, 1) for dy in (-1, 0, 1) for dx in (-1, 0, 1))[1:-1, 1:-1] - mask
speck = mask & (nb <= 2)
speck[-1] = False
print("specks removed:", list(zip(*np.nonzero(speck))))
mask &= ~speck
used = np.nonzero(mask.any(0))[0]
pix, mask = pix[:, used[0]:used[-1] + 1], mask[:, used[0]:used[-1] + 1]

open(os.path.join(ROOT, "build", "M_BADAPL.lmp"), "wb").write(encode(pix, mask))
ref_p, ref_m, _, _ = decode(L["M_LOADG"])
Wd = max(pix.shape[1], ref_p.shape[1])
show = np.full((H * 2 + 3, Wd, 3), (40, 0, 60), np.uint8)
r = pal[ref_p[:H]].astype(np.uint8); r[~ref_m[:H]] = (40, 0, 60)
show[:H, :ref_p.shape[1]] = r
g = pal[pix].astype(np.uint8); g[~mask] = (40, 0, 60)
show[H + 3:, :pix.shape[1]] = g
Image.fromarray(show).resize((Wd * 8, show.shape[0] * 8), Image.NEAREST).save(
    os.path.join(ROOT, "build", "M_BADAPL.png"))
print("M_BADAPL", pix.shape)
