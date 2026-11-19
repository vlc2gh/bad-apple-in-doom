"""Minimal LE (DOS/4GW linear executable) parser for DOOM.EXE v1.9."""
import struct


class LE:
    def __init__(self, data):
        self.d = bytearray(data)
        d = self.d
        self.base = d.find(b"LE\0\0")
        assert self.base > 0
        b = self.base
        h = lambda off, fmt="<I": struct.unpack_from(fmt, d, b + off)[0]
        self.pagesize = h(0x28)
        self.lastpage = h(0x2C)
        self.objtab = b + h(0x40)
        self.nobj = h(0x44)
        self.pagemap = b + h(0x48)
        self.fixpage = b + h(0x68)
        self.fixrec = b + h(0x6C)
        # data pages offset is relative to the inner MZ header that owns the LE header
        mz = max(i for i in range(0, b, 2) if d[i:i + 2] == b"MZ"
                 and struct.unpack_from("<I", d, i + 0x3C)[0] + i == b) if False else d.rfind(b"MZ", 0, b)
        while struct.unpack_from("<I", d, mz + 0x3C)[0] + mz != b:
            mz = d.rfind(b"MZ", 0, mz)
        self.mz = mz
        self.datapages = mz + h(0x80)
        self.npages = h(0x14)
        self.eip_obj, self.eip = h(0x18), h(0x1C)
        self.objs = []
        for i in range(self.nobj):
            vsize, reloc, flags, pmidx, pmcnt, _ = struct.unpack_from("<6I", d, self.objtab + 24 * i)
            self.objs.append(dict(vsize=vsize, reloc=reloc, flags=flags, pmidx=pmidx, pmcnt=pmcnt))
        # page map: LE uses 4-byte entries (page number hi/lo + flags)
        self.pagefile = []
        for p in range(self.npages):
            e = d[self.pagemap + 4 * p: self.pagemap + 4 * p + 4]
            num = (e[0] << 16) | (e[1] << 8) | e[2]
            self.pagefile.append(self.datapages + (num - 1) * self.pagesize)
        self.parse_fixups()

    def obj_off_to_file(self, obj, off):
        o = self.objs[obj - 1]
        page = o["pmidx"] - 1 + off // self.pagesize
        return self.pagefile[page] + off % self.pagesize

    def file_to_obj(self, foff):
        for oi, o in enumerate(self.objs, 1):
            for k in range(o["pmcnt"]):
                pf = self.pagefile[o["pmidx"] - 1 + k]
                if pf <= foff < pf + self.pagesize:
                    return oi, k * self.pagesize + foff - pf
        return None

    def parse_fixups(self):
        d = self.d
        self.fixups = []   # dict(page, srcoff, src_type, flags, tobj, toff, rec_off, toff_pos, toff_size)
        for p in range(self.npages):
            s = struct.unpack_from("<I", d, self.fixpage + 4 * p)[0]
            e = struct.unpack_from("<I", d, self.fixpage + 4 * p + 4)[0]
            i = self.fixrec + s
            end = self.fixrec + e
            while i < end:
                rec = i
                src, flg = d[i], d[i + 1]; i += 2
                assert not (src & 0x20), "source lists not supported"
                srcoff = struct.unpack_from("<h", d, i)[0]; i += 2
                tt = flg & 3
                assert tt == 0, f"non-internal fixup type {tt}"
                if flg & 0x40:
                    tobj = struct.unpack_from("<H", d, i)[0]; i += 2
                else:
                    tobj = d[i]; i += 1
                stype = src & 0xF
                toff_pos, toff_size, toff = None, 0, 0
                if stype != 2:   # not a 16-bit selector fixup
                    toff_pos = i
                    if flg & 0x10:
                        toff = struct.unpack_from("<I", d, i)[0]; i += 4; toff_size = 4
                    else:
                        toff = struct.unpack_from("<H", d, i)[0]; i += 2; toff_size = 2
                self.fixups.append(dict(page=p, srcoff=srcoff, stype=stype, flags=flg, tobj=tobj,
                                        toff=toff, rec=rec, toff_pos=toff_pos, toff_size=toff_size))

    def fixups_at(self, obj, off_lo, off_hi):
        """fixups whose 4-byte source lies in [off_lo, off_hi) of object obj"""
        o = self.objs[obj - 1]
        res = []
        for f in self.fixups:
            k = f["page"] - (o["pmidx"] - 1)
            if 0 <= k < o["pmcnt"]:
                so = k * self.pagesize + f["srcoff"]
                if off_lo - 3 <= so < off_hi:
                    res.append((so, f))
        return res

    def set_fixup_target(self, f, toff):
        assert f["toff_size"] == 4 or toff < 0x10000
        fmt = "<I" if f["toff_size"] == 4 else "<H"
        struct.pack_into(fmt, self.d, f["toff_pos"], toff)
        f["toff"] = toff
