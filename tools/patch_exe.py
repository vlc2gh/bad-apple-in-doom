"""Patch DOOM.EXE v1.9 -> BADAPPLE.EXE: adds a "BAD APPLE" item to the main menu.

Everything is inert until the item is chosen; the original game is unchanged.

Main menu: NEW GAME, BAD APPLE, OPTIONS, LOAD GAME, SAVE GAME, QUIT GAME
  ("Read This!" is dropped from the main menu; F1 help still works).

Code (LE object 1), all in functions that are dead in DOOM 1:
  0x22b00 (was M_ReadThis) -> M_BadApple(choice):
        weaponinfo[wp_pistol].upstate = 35   ; hidden-pistol state chain
        G_DeferedInitNew(choice=1, 4, 6)     ; E4M6 (music index 33 = D_RUNNIN)
        menuactive = 0
  0x28a90 (was A_LoadShotgun2, used by state 41) -> A_BadAppleGo(player, psp):
        weaponinfo[wp_pistol].upstate = 12   ; restore the normal pistol
        jmp A_OpenShotgun2                   ; S_StartSound(player->mo, sfx_dbopn)
  G_InitNew episode clamp 3 -> 4.
Data:
  state 35: PISG A, DELAY tics, -> 41, psprite pushed off-screen (misc 1,1000)
  state 41: PISG A, forever, action A_BadAppleGo, off-screen
"""
import struct, sys, os, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from le import LE

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DELAY = int(sys.argv[1]) if len(sys.argv) > 1 else 105
MAP_EPISODE, MAP_NUMBER = 4, 6

raw = open(os.path.join(ROOT, "DOOM.EXE"), "rb").read()
assert hashlib.md5(raw).hexdigest() == "e2382b7dc47ae2433d26b6e6bc312999", "not DOOM.EXE v1.9"
l = LE(raw)
d = l.d

# ---- addresses (object-relative), verified against the binary below ----
STATES = 0x15A28          # obj3: states[]
WEAPONINFO = 0x12D90      # obj3: weaponinfo[]
PISTOL_UP = WEAPONINFO + 24 + 4
MENUACTIVE = 0x2B6CC      # obj3
MAINMENU = 0x12234        # obj3: MainMenu[6], 17-byte menuitem_t
G_DEFEREDINITNEW = 0x21540
M_READTHIS = 0x22B00
A_LOADSHOTGUN2 = 0x28A90
A_OPENSHOTGUN2 = 0x28A80
EPISODE_CLAMP = 0x21600   # cmp edx, 3
S_STARTSOUND = 0x3F370
SFX_TABLE = 0x1488C       # obj3: S_sfx[], 36-byte sfxinfo_t

def code(off, n):
    return bytes(d[l.obj_off_to_file(1, off): l.obj_off_to_file(1, off) + n])
def put_code(off, b):
    fo = l.obj_off_to_file(1, off)
    assert (off % 4096) + len(b) <= 4096
    d[fo:fo + len(b)] = b
def data_off(off):
    return l.obj_off_to_file(3, off)

# ---- sanity checks ----
assert code(G_DEFEREDINITNEW, 5) == bytes.fromhex("a3ecb20200")
assert code(EPISODE_CLAMP, 3) == bytes.fromhex("83fa03")
assert code(A_OPENSHOTGUN2, 5) == bytes.fromhex("ba05000000")
assert code(A_LOADSHOTGUN2, 5) == bytes.fromhex("ba07000000")
assert not l.fixups_at(1, A_LOADSHOTGUN2, A_LOADSHOTGUN2 + 0x30)
assert l.file_to_obj(0x9DA3C) == (3, STATES)

def state(i):
    return list(struct.unpack_from("<7i", d, data_off(STATES + 28 * i)))
def put_state(i, s):
    struct.pack_into("<7i", d, data_off(STATES + 28 * i), *s)
def action_fix(i):
    fx = l.fixups_at(3, STATES + 28 * i + 12, STATES + 28 * i + 16)
    return fx[0][1]["toff"] if fx else None

assert action_fix(39) == A_OPENSHOTGUN2 and action_fix(41) == A_LOADSHOTGUN2
assert all(action_fix(s) is not None for s in (43, 44, 36))
assert code(0x28A87, 5) == b"\xe9" + struct.pack("<i", S_STARTSOUND - 0x28A8C)
for sfx in (101, 102, 103, 104):     # chunk sounds: no `link` (would redirect to another sound)
    assert not l.fixups_at(3, SFX_TABLE + 36 * sfx + 12, SFX_TABLE + 36 * sfx + 16)
    assert struct.unpack_from("<i", d, data_off(SFX_TABLE + 36 * sfx + 12))[0] == 0
assert state(35)[:3] == [6, 0, 3] and action_fix(35) is None
assert struct.unpack_from("<6i", d, data_off(WEAPONINFO + 24)) == (0, 12, 11, 10, 13, 17)

# ---- main menu ----
items = []
for k in range(6):
    o = MAINMENU + 17 * k
    status, name = struct.unpack_from("<h10s", d, data_off(o))
    (rfo, rfix), = l.fixups_at(3, o + 12, o + 16)
    assert rfo == o + 12
    items.append(dict(status=status, name=name, fix=rfix, routine=rfix["toff"], key=d[data_off(o + 16)]))
names = [it["name"].split(b"\0")[0] for it in items]
assert names == [b"M_NGAME", b"M_OPTION", b"M_LOADG", b"M_SAVEG", b"M_RDTHIS", b"M_QUITG"], names
assert items[4]["routine"] == M_READTHIS
new = [items[0], dict(status=1, name=b"M_BADAPL".ljust(10, b"\0"), routine=M_READTHIS, key=ord("b")),
       items[1], items[2], items[3], items[5]]
for k, it in enumerate(new):
    o = MAINMENU + 17 * k
    struct.pack_into("<h10s", d, data_off(o), it["status"], it["name"])
    d[data_off(o + 16)] = it["key"]
    l.set_fixup_target(items[k]["fix"], it["routine"])

# ---- M_BadApple at 0x22b00 (exactly 32 bytes) ----
rf = sorted(l.fixups_at(1, M_READTHIS, M_READTHIS + 0x1A), key=lambda t: t[0])
assert [a for a, _ in rf] == [0x22B02, 0x22B08, 0x22B0E, 0x22B14], rf
A1, A2 = 0x22B06, 0x22B18
cave1 = bytearray()
cave1 += b"\x53\x52"                                  # push ebx; push edx
cave1 += b"\x6a\x23"                                  # push 35
cave1 += b"\x8f\x05" + b"\0" * 4                      # pop dword [PISTOL_UP]   (fixup @A1)
cave1 += bytes([0x6A, MAP_EPISODE, 0x5A])             # edx = episode
cave1 += bytes([0x6A, MAP_NUMBER, 0x5B])              # ebx = map      (eax = choice = skill 1)
cave1 += b"\xe8" + struct.pack("<i", G_DEFEREDINITNEW - (M_READTHIS + len(cave1) + 5))
cave1 += b"\x31\xc0"                                  # xor eax, eax
cave1 += b"\xa3" + b"\0" * 4                          # mov [menuactive], eax   (fixup @A2)
cave1 += b"\x5a\x5b\xc3"                              # pop edx; pop ebx; ret
cave1 += b"\x90" * (32 - len(cave1))
assert len(cave1) == 32 and cave1[A1 - M_READTHIS - 2:A1 - M_READTHIS] == b"\x8f\x05"
assert cave1[A2 - M_READTHIS - 1] == 0xA3
put_code(M_READTHIS, bytes(cave1))

page_base = (M_READTHIS // 4096) * 4096
def move_fix(f, newsrc, toff=None):
    struct.pack_into("<h", d, f["rec"] + 2, newsrc - page_base)
    f["srcoff"] = newsrc - page_base
    if toff is not None:
        l.set_fixup_target(f, toff)
# padding after M_QuitResponse's ret (0x22bb3) up to 0x22bc0 is never executed
assert code(0x22BB3, 1) == b"\xc3" and code(0x22BB4, 12) == bytes.fromhex("8d80000000008d9200000000")
move_fix(rf[0][1], A1, PISTOL_UP)
move_fix(rf[1][1], A2, MENUACTIVE)
move_fix(rf[2][1], 0x22BB4)
move_fix(rf[3][1], 0x22BB8)

# ---- A_BadAppleGo at 0x28a90 ----
c4 = bytearray()
c4 += b"\x51"                                         # push ecx
c4 += b"\xe8\0\0\0\0"                                 # call $+5
here = A_LOADSHOTGUN2 + len(c4)
c4 += b"\x59"                                         # pop ecx  (ecx = runtime addr of `here`)
c4 += b"\x8b\x89" + struct.pack("<i", A1 - here)      # mov ecx, [ecx + (A1-here)] -> &upstate
c4 += b"\xc7\x01" + struct.pack("<i", 12)             # mov dword [ecx], S_PISTOLUP
c4 += b"\x59"                                         # pop ecx
# falls through into A_PlayChunk(player, psp): S_StartSound(player->mo, psp->state->misc1)
A_PLAYCHUNK = A_LOADSHOTGUN2 + len(c4)
c4 += b"\x8b\x12"                                     # mov edx, [edx]      psp->state
c4 += b"\x8b\x52\x14"                                 # mov edx, [edx+20]   state->misc1
c4 += b"\x8b\x00"                                     # mov eax, [eax]      player->mo
c4 += b"\xe9" + struct.pack("<i", S_STARTSOUND - (A_LOADSHOTGUN2 + len(c4) + 5))
assert A_LOADSHOTGUN2 + len(c4) <= 0x28AC0
put_code(A_LOADSHOTGUN2, bytes(c4))

# ---- episode clamp ----
put_code(EPISODE_CLAMP, bytes.fromhex("83fa04"))

# ---- states: delay, then one state per audio chunk (exact tic lengths) ----
import json
chunks = json.load(open(os.path.join(ROOT, "build", "audio_chunks.json")))
SPR_PISG = 3
CHAIN = [41, 43, 44, 36]          # SSG states (DOOM II only); 41 = restore + play
assert len(chunks) <= len(CHAIN)
for st in CHAIN[1:len(chunks)]:
    (_, f), = l.fixups_at(3, STATES + 28 * st + 12, STATES + 28 * st + 16)
    l.set_fixup_target(f, A_PLAYCHUNK)
put_state(35, [SPR_PISG, 0, DELAY, state(35)[3], CHAIN[0], 1, 1000])
for i, c in enumerate(chunks):
    last = i == len(chunks) - 1
    nxt = CHAIN[i] if last else CHAIN[i + 1]
    put_state(CHAIN[i], [SPR_PISG, 0, -1 if last else c["tics"], state(CHAIN[i])[3], nxt, c["sfx"], 1000])
print("audio chain:", [(CHAIN[i], c["sfx"], c["tics"]) for i, c in enumerate(chunks)])

# ---- finale: after the last chunk (+ PAUSE tics of black) start DOOM's E3 victory ----
# A_BadAppleEnd at 0x28ac0 (was A_BrainAwake, only used by the DOOM II boss eye):
#   gameepisode = 3; F_StartFinale(); finaletext = BADAPPLE_TEXT
#   -> our text on the E3 background, then the bunny scroll and THE END.
# The text lives where DOOM II's c2text was (never shown in DOOM 1); the real E3
# text is untouched, so the normal game's ending is unchanged.
BADAPPLE_TEXT = """YOU CAME FOR THE SPIDERDEMON.
YOU FOUND A SILHOUETTE INSTEAD.

FOR THREE MINUTES AND THIRTY SEVEN
SECONDS THE MARINE SET DOWN HIS GUN
AND WATCHED A GIRL DANCE ACROSS A
WALL HE COULD NOT EXPLAIN. SIXTY-FOUR
COLUMNS. THIRTY-FIVE FRAMES A SECOND.
NOT ONE DEMON MADE A SOUND.

HELL HAS NO RULES. THE INTERNET HAS
RULE 86: IF IT EXISTS, BAD APPLE
RUNS ON IT. HE TRIED THE BFG ON THE
WALL. IT DID NOT HELP.

THE INVASION IS OVER. THE APPLE
REMAINS. IT ALWAYS DOES."""
PAUSE = 35
A_BRAINAWAKE = 0x28AC0
F_STARTFINALE = 0x1C330
FINALETEXT = 0x292A0
C2TEXT = 0x20BD8
GAMEEPISODE = 0x2B3F8
assert code(A_BRAINAWAKE, 2) == b"\x53\x52"
assert code(F_STARTFINALE, 6) == bytes.fromhex("535152565755")
c2fo = data_off(C2TEXT)
c2len = d.index(b"\0", c2fo) - c2fo
assert d[c2fo:c2fo + 13] == b"YOU HAVE WON!" and len(BADAPPLE_TEXT) < c2len
assert all(33 <= ord(ch) <= 95 or ch in " \n" for ch in BADAPPLE_TEXT)   # HU font range
assert max(map(len, BADAPPLE_TEXT.split("\n"))) <= 38
d[c2fo:c2fo + c2len] = BADAPPLE_TEXT.encode().ljust(c2len, b"\0")

c5 = bytearray()
c5 += b"\x51"                                         # push ecx
c5 += b"\xe8\0\0\0\0"                                 # call $+5
here5 = A_BRAINAWAKE + len(c5)
c5 += b"\x59"                                         # pop ecx
c5 += b"\x8b\x89" + struct.pack("<i", A1 - here5)     # ecx = &weaponinfo[pistol].upstate (obj3)
c5 += b"\xc7\x81" + struct.pack("<i", GAMEEPISODE - PISTOL_UP) + struct.pack("<i", 3)
c5 += b"\xe8" + struct.pack("<i", F_STARTFINALE - (A_BRAINAWAKE + len(c5) + 5))
c5 += b"\x8d\x81" + struct.pack("<i", C2TEXT - PISTOL_UP)          # lea eax, [our text]
c5 += b"\x89\x81" + struct.pack("<i", FINALETEXT - PISTOL_UP)      # finaletext = eax
c5 += b"\x59\xc3"                                     # pop ecx; ret
END5 = A_BRAINAWAKE + len(c5)
# relocations that would land inside the new code go to unused spots further in the dead body
occupied = {a for a, _ in l.fixups_at(1, A_BRAINAWAKE, 0x28B20)}
inside = sorted((a, f) for a, f in l.fixups_at(1, A_BRAINAWAKE, END5) if a + 4 > A_BRAINAWAKE)
spots = [s for s in range(END5 + 4, 0x28B1C, 4) if all(abs(s - o) >= 4 for o in occupied)]
pb28 = (A_BRAINAWAKE // 4096) * 4096
for (a, f), s in zip(inside, spots):
    struct.pack_into("<h", d, f["rec"] + 2, s - pb28)
    occupied.discard(a); occupied.add(s)
assert len(inside) <= len(spots)
put_code(A_BRAINAWAKE, bytes(c5))
assert not [a for a, _ in l.fixups_at(1, A_BRAINAWAKE, END5) if a + 4 > A_BRAINAWAKE and False]

VICTORY_STATE = 39
(_, f39), = l.fixups_at(3, STATES + 28 * VICTORY_STATE + 12, STATES + 28 * VICTORY_STATE + 16)
l.set_fixup_target(f39, A_BRAINAWAKE)
last = CHAIN[len(chunks) - 1]
s = state(last); s[2] = chunks[-1]["tics"] + PAUSE; s[4] = VICTORY_STATE
put_state(last, s)
put_state(VICTORY_STATE, [SPR_PISG, 0, -1, state(VICTORY_STATE)[3], VICTORY_STATE, 1, 1000])
print(f"finale: state {VICTORY_STATE} -> E3 victory, {PAUSE} tics after the audio ends; moved {len(inside)} relocs")

open(os.path.join(ROOT, "BADAPPLE.EXE"), "wb").write(d)
print(f"BADAPPLE.EXE written: menu item M_BADAPL -> E{MAP_EPISODE}M{MAP_NUMBER}, sound after {DELAY} tics")
