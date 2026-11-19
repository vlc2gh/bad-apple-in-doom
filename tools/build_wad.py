"""Bad Apple!! for vanilla DOS DOOM v1.9 - PWAD builder.

Screen = 64 one-sided linedefs of special 48 (scroll texture left, 1 texel/tic).
Linedef i has its own texture BAPLxx, 8192 columns wide; texture column t holds
column i of video frame t, so the scroll plays the video at 35 fps.
Each texture is 16 single-patch chunks (512 columns each) so that every column
offset fits vanilla's unsigned-short texturecolumnofs. Column pointers point
into a shared superstring buffer, so repeated / overlapping columns cost nothing.
"""
import struct, sys, os
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IWAD = os.path.join(ROOT, "DOOM.WAD")
FRAMES = os.path.join(ROOT, "build", "frames_64x82.gray")
OUT = os.path.join(ROOT, "BADAPPLE.WAD")
MUS = os.path.join(ROOT, "build", "badapple.mus")

COLS, ROWS = 64, 82          # screen texels (columns = linedefs)
K = 2                        # map units per linedef
TEXW = 8192                  # texture width = loop period in tics
CHUNK = 512                  # columns per patch lump
LEVELS = int(sys.argv[1]) if len(sys.argv) > 1 else 4
MAXDATA = 65535 - 3 - (8 + 4 * CHUNK) - ROWS - 16


# ---------------- WAD io ----------------
def read_wad(path):
    d = open(path, "rb").read()
    n, off = struct.unpack_from("<ii", d, 4)
    lumps = []
    for i in range(n):
        p, s, name = struct.unpack_from("<ii8s", d, off + 16 * i)
        lumps.append((name.rstrip(b"\0").decode(), d[p:p + s]))
    return lumps


def write_wad(path, lumps):
    data = bytearray(b"PWAD" + b"\0" * 8)
    dirs = []
    for name, blob in lumps:
        dirs.append((len(data), len(blob), name))
        data += blob
    diroff = len(data)
    for p, s, name in dirs:
        data += struct.pack("<ii8s", p, s, name.encode())
    struct.pack_into("<ii", data, 4, len(lumps), diroff)
    open(path, "wb").write(data)


iwad = dict(read_wad(IWAD))

# ---------------- palette ----------------
pal = np.frombuffer(iwad["PLAYPAL"][:768], np.uint8).reshape(256, 3).astype(int)
levels = np.linspace(0, 255, LEVELS)
palidx = []
for v in levels:
    # prefer neutral grays: distance to (v,v,v)
    dist = ((pal - v) ** 2).sum(1)
    palidx.append(int(dist.argmin()))
print("levels", list(levels.astype(int)), "-> palette", palidx, [tuple(pal[i]) for i in palidx])
palidx = np.array(palidx, np.uint8)

# ---------------- frames ----------------
raw = np.fromfile(FRAMES, np.uint8)
nf = raw.size // (COLS * ROWS)
frames = raw[: nf * COLS * ROWS].reshape(nf, ROWS, COLS)
# the PV ends with dim credit cards (mean brightness < 6); keep only the real clip,
# everything after its last frame is pure black (also what wraps to before the start)
fmean = frames.reshape(nf, -1).mean(1)
last_real = int(np.nonzero(fmean >= 6)[0][-1])
frames = frames.copy()
frames[last_real + 1:] = 0
print(f"credits blanked: frames {last_real + 1}..{nf - 1}")
q = np.clip(np.rint(frames.astype(float) / 255 * (LEVELS - 1)), 0, LEVELS - 1).astype(np.uint8)
# sound starts at tic DELAY (see patch_exe.py); at that moment the wall shows
# column DELAY, so frame f goes to column DELAY+f (wrapping; the tail is black)
DELAY = int(sys.argv[2]) if len(sys.argv) > 2 else 105
vid = np.empty((TEXW, ROWS, COLS), np.uint8)
vid[:] = palidx[0]
cols = (DELAY + np.arange(nf)) % TEXW
vid[cols] = palidx[q]
print(f"{nf} frames ({nf/35:.2f}s), loop {TEXW} tics ({TEXW/35:.2f}s), shift {DELAY}")


# ---------------- audio: DMX sound lump ----------------
def dmx_sound(path, rate=11025):
    pcm = open(path, "rb").read()
    pad0, pad1 = pcm[:1] * 16, pcm[-1:] * 16
    body = pad0 + pcm + pad1
    return struct.pack("<HHI", 3, rate, len(body)) + body


def silent_mus():
    # one released note with a huge delay, then end of score
    score = bytes([0x00 | 0x80, 60]) + bytes([0x81, 0x80, 0x00]) + bytes([0x60])
    hdr = struct.pack("<4sHHHHHH", b"MUS\x1a", len(score), 16, 1, 0, 0, 0)
    return hdr + score


# ---------------- column chunk encoder ----------------
def encode_chunk(colseq):
    """colseq: list of bytes (ROWS each). returns (buffer, positions)."""
    buf = bytearray()
    pos = []
    cache = {}
    lossy = 0
    for c in colseq:
        if c in cache:
            pos.append(cache[c]); continue
        p = buf.find(c)
        if p < 0:
            # max overlap of buffer suffix with column prefix
            ov = 0
            for o in range(min(len(c) - 1, len(buf)), 0, -1):
                if buf.endswith(c[:o]):
                    ov = o; break
            if len(buf) + len(c) - ov > MAXDATA:
                # out of space: nearest existing window
                arr = np.frombuffer(bytes(buf), np.uint8)
                win = np.lib.stride_tricks.sliding_window_view(arr, ROWS)
                p = int((win != np.frombuffer(c, np.uint8)).sum(1).argmin())
                lossy += 1
            else:
                p = len(buf) - ov
                buf += c[ov:]
        cache[c] = p
        pos.append(p)
    return bytes(buf), pos, lossy


def make_patch(colseq):
    buf, pos, lossy = encode_chunk(colseq)
    hdr = 8 + 4 * CHUNK
    start = hdr + 3
    blob = bytearray(struct.pack("<hhhh", CHUNK, ROWS, 0, 0))
    for p in pos:
        blob += struct.pack("<i", start + p - 3)
    blob += b"\0" * 3 + buf + b"\0" * 16
    assert start + max(pos) + ROWS <= 65535
    return bytes(blob), len(buf), lossy


patch_lumps = []
texnames = []
total = 0
tot_lossy = 0
for x in range(COLS):
    pn = []
    for ch in range(TEXW // CHUNK):
        seq = [vid[t, :, x].tobytes() for t in range(ch * CHUNK, (ch + 1) * CHUNK)]
        blob, n, lossy = make_patch(seq)
        name = f"BA{x:02d}{ch:02d}"
        patch_lumps.append((name, blob))
        pn.append(name)
        total += len(blob)
        tot_lossy += lossy
    texnames.append((f"BAPL{x:02d}", pn))
print(f"patch data total {total/1024/1024:.2f} MB, lossy columns {tot_lossy}")

# ---------------- PNAMES / TEXTURE1 ----------------
pn_raw = iwad["PNAMES"]
npn = struct.unpack_from("<i", pn_raw)[0]
pnames = [pn_raw[4 + 8 * i: 12 + 8 * i] for i in range(npn)]
pindex = {}
for _, pl in texnames:
    for p in pl:
        pindex[p] = len(pnames)
        pnames.append(p.encode().ljust(8, b"\0"))
PNAMES = struct.pack("<i", len(pnames)) + b"".join(pnames)

t1 = iwad["TEXTURE1"]
nt = struct.unpack_from("<i", t1)[0]
offs = struct.unpack_from(f"<{nt}i", t1, 4)
entries = []
for i in range(nt):
    o = offs[i]
    end = offs[i + 1] if i + 1 < nt else len(t1)
    entries.append(t1[o:end])
for tname, pl in texnames:
    e = bytearray(struct.pack("<8sihhih", tname.encode(), 0, TEXW, 128, 0, len(pl)))
    for ch, p in enumerate(pl):
        e += struct.pack("<hhhhh", ch * CHUNK, 0, pindex[p], 1, 0)
    entries.append(bytes(e))
n = len(entries)
TEXTURE1 = bytearray(struct.pack("<i", n))
o = 4 + 4 * n
for e in entries:
    TEXTURE1 += struct.pack("<i", o); o += len(e)
for e in entries:
    TEXTURE1 += e

# ---------------- map ----------------
W = COLS * K            # 128
D = W // 2              # viewing distance that exactly fills 90 deg FOV
Y = D + 32              # north wall y
verts = []
def v(x, y):
    verts.append((x, y)); return len(verts) - 1

north = [v(x * K, Y) for x in range(COLS + 1)]
sw, se = v(0, 0), v(W, 0)
nw, ne = north[0], north[-1]

sides, lines = [], []
def side(tex, xo=0):
    sides.append((xo, 0, "-", "-", tex, 0)); return len(sides) - 1
def line(a, b, tex, special=0):
    lines.append((a, b, 1, special, 0, side(tex), -1)); return len(lines) - 1

for x in range(COLS):
    line(north[x], north[x + 1], f"BAPL{x:02d}", 48)
lw = line(sw, nw, "BROWN1")
le = line(ne, se, "BROWN1")
ls = line(se, sw, "BROWN1")

VERTEXES = b"".join(struct.pack("<hh", *p) for p in verts)
LINEDEFS = b"".join(struct.pack("<hhhhhhh", *l) for l in lines)
SIDEDEFS = b"".join(struct.pack("<hh8s8s8sh", a, b, c.encode(), d.encode(), e.encode(), f) for a, b, c, d, e, f in sides)
SECTORS = struct.pack("<hh8s8shhh", 0, ROWS, b"FLAT5_4", b"CEIL3_5", 255, 0, 0)
# 1 unit closer than the exact-fit distance: the screen slightly overfills the
# 90-degree view, so the side walls never show as a 1-pixel strip at the edges
THINGS = struct.pack("<hhhhh", W // 2, Y - D + 1, 90, 1, 7)

# BSP: one node splitting the room at y = Y/2
my = Y // 2
mw, me = v(0, my), v(W, my)
VERTEXES = b"".join(struct.pack("<hh", *p) for p in verts)
segs = []
def seg(a, b, ang, ln, off):
    segs.append(struct.pack("<hhhhhh", a, b, ang, ln, 0, off))
# upper subsector (north half): north wall segs, east upper, west upper
for x in range(COLS):
    seg(north[x], north[x + 1], 0, x, 0)
seg(ne, me, -16384, le, 0)              # east wall going south: angle 270
seg(mw, nw, 16384, lw, my)             # west wall going north: angle 90
nup = COLS + 2
# lower subsector
seg(me, se, -16384, le, Y - my)
seg(se, sw, -32768, ls, 0)              # south wall going west: angle 180
seg(sw, mw, 16384, lw, 0)
SEGS = b"".join(segs)
SSECTORS = struct.pack("<hh", nup, 0) + struct.pack("<hh", 3, nup)
# partition from (0,my) towards east: right side = south (lower) = ss1
NODES = struct.pack("<hhhh", 0, my, W, 0) \
    + struct.pack("<hhhh", my, 0, 0, W) \
    + struct.pack("<hhhh", Y, my, 0, W) \
    + struct.pack("<HH", 0x8000 | 1, 0x8000 | 0)
REJECT = b"\0"

# BLOCKMAP
ox, oy = -8, -8
bw = (W + 16) // 128 + 1
bh = (Y + 16) // 128 + 1
blocks = [[] for _ in range(bw * bh)]
for li, (a, b, *_r) in enumerate(lines):
    (x1, y1), (x2, y2) = verts[a], verts[b]
    for by in range(bh):
        for bx in range(bw):
            l, r = ox + bx * 128, ox + bx * 128 + 128
            bo, t = oy + by * 128, oy + by * 128 + 128
            # sample the line densely (lines are axis-aligned and short)
            steps = max(abs(x2 - x1), abs(y2 - y1)) + 1
            for s in range(steps + 1):
                px = x1 + (x2 - x1) * s / steps
                py = y1 + (y2 - y1) * s / steps
                if l <= px < r and bo <= py < t:
                    blocks[by * bw + bx].append(li); break
hdr = struct.pack("<hhhh", ox, oy, bw, bh)
off = 4 + bw * bh
offsets, lists = [], b""
for bl in blocks:
    offsets.append(off + len(lists) // 2)
    lists += struct.pack(f"<{len(bl)+2}h", 0, *bl, -1)
BLOCKMAP = hdr + struct.pack(f"<{len(offsets)}H", *offsets) + lists

# E4M6: chosen by the patched menu; S_Start maps it to music index 33 (D_RUNNIN, DOOM II only)
lumps = [("E4M6", b""), ("THINGS", THINGS), ("LINEDEFS", LINEDEFS), ("SIDEDEFS", SIDEDEFS),
         ("VERTEXES", VERTEXES), ("SEGS", SEGS), ("SSECTORS", SSECTORS), ("NODES", NODES),
         ("SECTORS", SECTORS), ("REJECT", REJECT), ("BLOCKMAP", BLOCKMAP),
         ("PNAMES", PNAMES), ("TEXTURE1", bytes(TEXTURE1))]
lumps.append(("D_RUNNIN", silent_mus()))
lumps.append(("M_BADAPL", open(os.path.join(ROOT, "build", "M_BADAPL.lmp"), "rb").read()))
# audio: split at tic boundaries (11025/35 = 315 samples per tic) into chunks small
# enough for the 8 MB zone; patch_exe.py chains them with exact tic durations
import json
AUDIO = os.path.join(ROOT, "build", "audio_11025_u8.raw")
pcm = open(AUDIO, "rb").read()
SPT = 11025 // 35
# the track is silent during the PV's end credits: stop the audio where the picture
# ends (+10 tics of tail) so the finale follows right after the last dance frame
pcm = pcm[:(last_real + 1 + 10) * SPT]
CHUNK_SFX = [("sssit", 101), ("ssdth", 102), ("keenpn", 103), ("keendt", 104)]
total_tics = -(-len(pcm) // SPT)
pcm = pcm + pcm[-1:] * (total_tics * SPT - len(pcm))
bounds = [round(total_tics * i / len(CHUNK_SFX)) for i in range(len(CHUNK_SFX) + 1)]
chunks = []
for i, (name, sfx) in enumerate(CHUNK_SFX):
    part = pcm[bounds[i] * SPT: bounds[i + 1] * SPT]
    pad0, pad1 = part[:1] * 16, part[-1:] * 16
    body = pad0 + part + pad1
    lumps.append(("DS" + name.upper(), struct.pack("<HHI", 3, 11025, len(body)) + body))
    chunks.append(dict(sfx=sfx, tics=bounds[i + 1] - bounds[i]))
json.dump(chunks, open(os.path.join(ROOT, "build", "audio_chunks.json"), "w"))
print("audio chunks:", [(c["sfx"], c["tics"], f"{c['tics']/35:.1f}s") for c in chunks])
lumps += patch_lumps
write_wad(OUT, lumps)
print("wrote", OUT, os.path.getsize(OUT) // 1024, "KB")
