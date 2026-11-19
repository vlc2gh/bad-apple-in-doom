"""Disassemble DOOM.EXE code object (obj 1) ranges, annotating fixups."""
import sys, struct
sys.path.insert(0, __import__("os").path.dirname(__file__))
from le import LE
from capstone import Cs, CS_ARCH_X86, CS_MODE_32

l = LE(open(sys.argv[1], "rb").read())
md = Cs(CS_ARCH_X86, CS_MODE_32)
code = bytearray()
o = l.objs[0]
for k in range(o["pmcnt"]):
    pf = l.pagefile[o["pmidx"] - 1 + k]
    code += l.d[pf:pf + l.pagesize]
fix = {}
for so, f in l.fixups_at(1, 0, len(code)):
    fix[so] = f

def dis(start, n):
    for ins in md.disasm(bytes(code[start:start + 400]), start):
        notes = [f"FIX@{a:x}->obj{fix[a]['tobj']}:{fix[a]['toff']:x}" for a in range(ins.address, ins.address + ins.size) if a in fix]
        print(f"{ins.address:06x}: {ins.bytes.hex():<20} {ins.mnemonic} {ins.op_str} {' '.join(notes)}")
        n -= 1
        if n == 0 or ins.mnemonic == "ret" and n < 0:
            break

for a in sys.argv[2:]:
    addr, _, cnt = a.partition(":")
    print(f"---- {addr}")
    dis(int(addr, 16), int(cnt or 40))
