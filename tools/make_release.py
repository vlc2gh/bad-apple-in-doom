"""Assemble release/: a normal-looking DOOM install where plain `doom` runs Bad Apple.

  DOOM.EXE     <- BADAPPLE.EXE (patched)
  DOOM.WAD     <- original IWAD with BADAPPLE.WAD merged in (no -file, no "modified" banner)
  DEFAULT.CFG  <- BADAPPLE.CFG (full-screen view, sfx volume 15, Sound Blaster)
  everything else copied unchanged from the original install files.
"""
import os, struct, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "release")


def read_wad(path):
    d = open(path, "rb").read()
    n, off = struct.unpack_from("<ii", d, 4)
    return d[:4], [(struct.unpack_from("<8s", d, off + 16 * i + 8)[0].rstrip(b"\0").decode(),
                    d[struct.unpack_from("<i", d, off + 16 * i)[0]:][:struct.unpack_from("<i", d, off + 16 * i + 4)[0]])
                   for i in range(n)]


def write_wad(path, magic, lumps):
    with open(path, "wb") as f:
        f.write(magic + b"\0" * 8)
        dirs = []
        for name, blob in lumps:
            dirs.append((f.tell(), len(blob), name))
            f.write(blob)
        diroff = f.tell()
        for p, s, name in dirs:
            f.write(struct.pack("<ii8s", p, s, name.encode()))
        f.seek(4)
        f.write(struct.pack("<ii", len(lumps), diroff))


magic, iwad = read_wad(os.path.join(ROOT, "DOOM.WAD"))
assert magic == b"IWAD"
_, pwad = read_wad(os.path.join(ROOT, "BADAPPLE.WAD"))

# global lumps from the PWAD replace the IWAD's in place; the E4M6 map block and
# everything else is appended (map lumps stay together, after their marker)
iwad_names = {n for n, _ in iwad}
replace = {n: b for n, b in pwad if n in ("PNAMES", "TEXTURE1")}
merged = [(n, replace.get(n, b)) for n, b in iwad]
appended = [(n, b) for n, b in pwad if n not in replace]
for n, _ in appended:
    if n in iwad_names and n not in ("THINGS", "LINEDEFS", "SIDEDEFS", "VERTEXES", "SEGS",
                                      "SSECTORS", "NODES", "SECTORS", "REJECT", "BLOCKMAP"):
        raise SystemExit(f"PWAD lump {n} would shadow an IWAD lump")
merged += appended

os.makedirs(OUT, exist_ok=True)
write_wad(os.path.join(OUT, "DOOM.WAD"), b"IWAD", merged)
shutil.copyfile(os.path.join(ROOT, "BADAPPLE.EXE"), os.path.join(OUT, "DOOM.EXE"))
shutil.copyfile(os.path.join(ROOT, "BADAPPLE.CFG"), os.path.join(OUT, "DEFAULT.CFG"))
ORIGINAL = ["SETUP.EXE", "DM.EXE", "DM.DOC", "DWANGO.EXE", "DWANGO.DOC", "DWANGO.STR",
            "IPXSETUP.EXE", "SERSETUP.EXE", "MODEM.CFG", "MODEM.NUM", "MODEM.STR",
            "HELPME.TXT", "README.TXT", "ORDER.FRM",
            "DMFAQ66A.TXT", "DMFAQ66B.TXT", "DMFAQ66C.TXT", "DMFAQ66D.TXT"]
for f in ORIGINAL:
    src = os.path.join(ROOT, f)
    if os.path.exists(src):
        shutil.copyfile(src, os.path.join(OUT, f))
print(f"release/: DOOM.WAD {len(merged)} lumps, {os.path.getsize(os.path.join(OUT, 'DOOM.WAD')) // 1024} KB")
