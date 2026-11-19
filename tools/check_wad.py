"""Decode BADAPPLE.WAD the way vanilla R_GetColumn does and dump preview frames."""
import struct, os, sys
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = open(os.path.join(ROOT, "BADAPPLE.WAD"), "rb").read()
n, off = struct.unpack_from("<ii", d, 4)
lumps = {}
for i in range(n):
    p, s, name = struct.unpack_from("<ii8s", d, off + 16 * i)
    lumps[name.rstrip(b"\0").decode()] = (p, s)
pal = np.frombuffer(open(os.path.join(ROOT, "DOOM.WAD"), "rb").read(), np.uint8)
iw = open(os.path.join(ROOT, "DOOM.WAD"), "rb").read()
ni, oi = struct.unpack_from("<ii", iw, 4)
for i in range(ni):
    p, s, name = struct.unpack_from("<ii8s", iw, oi + 16 * i)
    if name.rstrip(b"\0") == b"PLAYPAL":
        pal = np.frombuffer(iw[p:p + 768], np.uint8).reshape(256, 3)
        break

COLS, ROWS, CHUNK = 64, 82, 512

# parse TEXTURE1 / PNAMES like R_InitTextures and resolve our textures
p, s = lumps["PNAMES"]
npn = struct.unpack_from("<i", d, p)[0]
pnames = [d[p + 4 + 8 * i: p + 12 + 8 * i].rstrip(b"\0").decode() for i in range(npn)]
p, s = lumps["TEXTURE1"]
nt = struct.unpack_from("<i", d, p)[0]
for i in range(nt):
    o = p + struct.unpack_from("<i", d, p + 4 + 4 * i)[0]
    name, masked, w, h, cd, pc = struct.unpack_from("<8sihhih", d, o)
    name = name.rstrip(b"\0").decode()
    if name.startswith("BAPL"):
        x = int(name[4:])
        assert (w, pc) == (8192, 16), (name, w, pc)
        for ch in range(pc):
            ox, oy, pi, _, _ = struct.unpack_from("<5h", d, o + 22 + 10 * ch)
            assert ox == ch * CHUNK and pnames[pi] == f"BA{x:02d}{ch:02d}", (name, ch, ox, pi)
            assert pnames[pi] in lumps
print("TEXTURE1/PNAMES ok:", nt, "textures,", npn, "patch names")
maxsize = max(s for k, (p, s) in lumps.items() if k.startswith("BA") and len(k) == 6)
print("largest patch lump:", maxsize)
out = os.path.join(ROOT, "build", "preview")
os.makedirs(out, exist_ok=True)
for t in [int(a) for a in sys.argv[1:]] or [700, 1500, 2500, 4000, 6000, 7600]:
    img = np.zeros((ROWS, COLS), np.uint8)
    for x in range(COLS):
        p, s = lumps[f"BA{x:02d}{t // CHUNK:02d}"]
        colofs = struct.unpack_from("<i", d, p + 8 + 4 * (t % CHUNK))[0] + 3
        assert colofs < 65536
        img[:, x] = np.frombuffer(d, np.uint8, ROWS, p + colofs)
    rgb = pal[img]
    # show as DOOM would: each texel 2 units wide, 1.2 aspect
    Image.fromarray(rgb).resize((COLS * 2 * 4, int(ROWS * 1.2 * 4)), Image.NEAREST).save(f"{out}/t{t:05d}.png")
print("previews in", out)
