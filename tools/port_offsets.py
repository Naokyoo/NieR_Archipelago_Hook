"""Finds the hook's hardcoded NieRAutomata.exe addresses in another build of the game.

The hook was written against the 2021 Steam exe. A game update moves code and data, so every hardcoded RVA
breaks (and a MinHook detour on a wrong address crashes the game). Given the old exe (the one the RVAs come
from) and the new one, this tool:
  - functions: matches the function containing each code RVA (.pdata bounds) by its normalized instruction
    stream (RIP-relative displacements and branch targets masked), then keeps the same instruction index
    (return addresses compared by the item hook are instructions inside a function);
  - data: finds the old instructions that reference the data RVA (RIP-relative), maps them to the new build
    the same way and reads their new target.

    python tools/port_offsets.py <old exe> <new exe>

Needs capstone and numpy. Prints a C++ table of the new RVAs, with how each one was found.
"""
import hashlib
import struct
import sys
from collections import Counter, defaultdict

import capstone
import numpy as np

# name -> (kind, old rva). kind: "func" (function start), "code" (instruction inside a function), "data"
ADDRESSES = {
    "PLAYER_ENTITY_PTR":        ("data", 0x1020948),
    "PHASE_MANAGER":            ("data", 0x102A020),
    "CHAPTER_DATA_PTR":         ("data", 0x11EA848),
    "ITEM_MANAGER":             ("data", 0x133B510),
    "SAVE_DATA_BASE":           ("data", 0x145BF58),
    "MONEY":                    ("data", 0x148C4C0),
    "TITLE_PHASE_NAME":         ("data", 0xCAC904),
    "PHASE_GLOBAL":             ("data", 0xF64A90),
    "PLAYER_DIE_FUNC":          ("func", 0x4E62F0),
    "PHASE_JUMP_FUNC":          ("func", 0x7610D0),
    "CHAPTER_GET_FUNC":         ("func", 0x7DCF10),
    "CHAPTER_COUNT_FUNC":       ("func", 0x7DE510),
    "CHAPTER_CHARACTER_FUNC":   ("func", 0x8A2B00),
    "CHAPTER_ROWS_REFRESH":     ("func", 0x95CF80),
    "TEST_GAME_FLAG_FUNC":      ("func", 0x9CA510),
    "TITLE_MENU_FLAG_RET":      ("code", 0x9B3D4D),
    "RET_NORMAL_CHEST":         ("code", 0x80032D),
    "RET_HACKING_CHEST":        ("code", 0x800573),
    "RET_HACKING_CHEST_CALLER": ("code", 0x7CA45F),
    "RET_MOB_DROP":             ("code", 0x7DA8AA),
    "RET_GROUND_PICKUP":        ("code", 0x898B42),
    "RET_FISHING":              ("code", 0x629000),
    "RET_POD_SLOT_INIT":        ("code", 0x328840),
    "RET_SAVE_LOAD":            ("code", 0x31DF78),
    "RET_INVENTORY_RESET":      ("code", 0x150BED),
    "SAVE_LOAD_RANGE_START":    ("code", 0x150A00),
    "SAVE_LOAD_RANGE_END":      ("code", 0x151200),
}


class PE:
    def __init__(self, path):
        self.b = open(path, "rb").read()
        b = self.b
        pe = struct.unpack_from("<I", b, 0x3C)[0]
        nsec = struct.unpack_from("<H", b, pe + 6)[0]
        optsz = struct.unpack_from("<H", b, pe + 20)[0]
        self.timestamp = struct.unpack_from("<I", b, pe + 8)[0]
        self.size_of_image = struct.unpack_from("<I", b, pe + 24 + 56)[0]
        self.sections = []
        for i in range(nsec):
            o = pe + 24 + optsz + i * 40
            name = b[o:o + 8].rstrip(b"\0").decode()
            vs, va, rs, ro = struct.unpack_from("<IIII", b, o + 8)
            self.sections.append((name, va, vs, ro, rs))
        # Exception directory = .pdata (RUNTIME_FUNCTION: begin, end, unwind)
        exc_rva, exc_size = struct.unpack_from("<II", b, pe + 24 + 112 + 3 * 8)
        o = self.off(exc_rva)
        funcs = np.frombuffer(b, dtype="<u4", count=exc_size // 4, offset=o).reshape(-1, 3)
        self.funcs = sorted({(int(s), int(e)) for s, e, _ in funcs if s < e})
        self.starts = np.array([s for s, _ in self.funcs], dtype=np.int64)
        self.cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        self.cs.detail = True
        self._insn_cache = {}

    def off(self, rva):
        for _, va, vs, ro, rs in self.sections:
            if va <= rva < va + max(vs, rs):
                return ro + rva - va
        raise ValueError(hex(rva))

    def section_of(self, rva):
        for name, va, vs, _, rs in self.sections:
            if va <= rva < va + max(vs, rs):
                return name
        return None

    def func_at(self, rva):
        i = int(np.searchsorted(self.starts, rva, side="right")) - 1
        if i >= 0:
            s, e = self.funcs[i]
            if s <= rva < e:
                return s, e
        return None

    def insns(self, func):
        if func not in self._insn_cache:
            s, e = func
            code = self.b[self.off(s):self.off(s) + (e - s)]
            self._insn_cache[func] = list(self.cs.disasm(code, s))
        return self._insn_cache[func]

    def rip_target(self, insn):
        for op in insn.operands:
            if op.type == capstone.x86.X86_OP_MEM and op.mem.base == capstone.x86.X86_REG_RIP:
                return insn.address + insn.size + op.mem.disp
        return None

    def norm(self, func):
        """Instruction stream with every address masked (identical code in another build matches)."""
        out = []
        for insn in self.insns(func):
            text = insn.mnemonic
            ops = insn.op_str
            if self.rip_target(insn) is not None:
                ops = "RIPMEM"
            elif insn.group(capstone.CS_GRP_JUMP) or insn.group(capstone.CS_GRP_CALL):
                if insn.operands and insn.operands[0].type == capstone.x86.X86_OP_IMM:
                    ops = "REL"
            out.append(f"{text} {ops}")
        return out

    def fhash(self, func):
        return hashlib.md5("\n".join(self.norm(func)).encode()).hexdigest()


def build_index(pe, sizes):
    """hash -> functions, only for functions of the given sizes (disassembling everything is slow)."""
    index = defaultdict(list)
    for f in pe.funcs:
        if (f[1] - f[0]) in sizes:
            index[pe.fhash(f)].append(f)
    return index


def match_function(old, new, func, new_by_size):
    """New function matching an old one: same normalized code, sizes allowed to differ a little."""
    h = old.fhash(func)
    size = func[1] - func[0]
    for delta in range(0, 65):
        for sz in {size - delta, size + delta}:
            for f in new_by_size.get(sz, []):
                if new.fhash(f) == h:
                    return f, f"exact code match (size {size}->{sz})"
    # Fallback: most similar instruction stream among functions of close size, same first instructions
    import difflib
    a = old.norm(func)
    best, best_ratio = None, 0.0
    for sz in range(int(size * 0.9), int(size * 1.1) + 2):
        for f in new_by_size.get(sz, []):
            b = new.norm(f)
            if b[:3] != a[:3]:
                continue
            r = difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
            if r > best_ratio:
                best, best_ratio = f, r
    if best and best_ratio >= 0.9:
        return best, f"similar code ({best_ratio:.0%})"
    return None, f"no match (best {best_ratio:.0%})"


def map_code(old, new, rva, new_by_size, cache):
    func = old.func_at(rva)
    if not func:
        return None, "not inside a known function"
    if func not in cache:
        cache[func] = match_function(old, new, func, new_by_size)
    nf, how = cache[func]
    if not nf:
        return None, how
    if rva == func[0]:
        return nf[0], how
    old_ins = old.insns(func)
    idx = next((i for i, ins in enumerate(old_ins) if ins.address == rva), None)
    if idx is None:
        # end of a range (not an instruction start): keep the offset from the function start
        return nf[0] + (rva - func[0]), how + ", offset kept"
    new_ins = new.insns(nf)
    if idx >= len(new_ins):
        return None, how + ", instruction index out of range"
    return new_ins[idx].address, how + f", instruction #{idx}"


def rip_refs(pe, target, slack=0x40):
    """Instructions of .text that reference [target - slack, target + slack] RIP-relatively: (insn rva, ref)."""
    name, va, vs, ro, rs = next(s for s in pe.sections if s[0] == ".text")
    text = np.frombuffer(pe.b, dtype=np.uint8, count=rs, offset=ro)
    hits = []
    for align in range(4):
        n = (rs - align) // 4
        disp = np.frombuffer(text.tobytes()[align:align + n * 4], dtype="<i4").astype(np.int64)
        pos = va + align + 4 * np.arange(n, dtype=np.int64)
        # disp at pos: target = next instruction address = pos + 4 + (0..4 bytes of immediate) + disp
        for tail in range(0, 5):
            tgt = pos + 4 + tail + disp
            sel = np.nonzero(np.abs(tgt - target) <= slack)[0]
            hits += [int(pos[i]) for i in sel]
    found = set()
    for p in sorted(set(hits)):
        func = pe.func_at(p)
        if not func:
            continue
        for ins in pe.insns(func):
            if ins.address <= p < ins.address + ins.size:
                t = pe.rip_target(ins)
                if t is not None and abs(t - target) <= slack:
                    found.add((ins.address, t))
                break
    return sorted(found)


def main():
    old, new = PE(sys.argv[1]), PE(sys.argv[2])
    print(f"// old build: PE timestamp {old.timestamp:#x}, image {old.size_of_image:#x}")
    print(f"// new build: PE timestamp {new.timestamp:#x}, image {new.size_of_image:#x}")
    new_by_size = defaultdict(list)
    for f in new.funcs:
        new_by_size[f[1] - f[0]].append(f)
    cache = {}
    results = {}
    for name, (kind, rva) in ADDRESSES.items():
        if kind in ("func", "code"):
            new_rva, how = map_code(old, new, rva, new_by_size, cache)
        else:
            votes = Counter()
            refs = rip_refs(old, rva)
            for ins_rva, ref in refs[:40]:
                mapped, _ = map_code(old, new, ins_rva, new_by_size, cache)
                if mapped is None:
                    continue
                nfunc = new.func_at(mapped)
                ins = next((i for i in new.insns(nfunc) if i.address == mapped), None) if nfunc else None
                t = new.rip_target(ins) if ins else None
                if t is not None:
                    votes[t + (rva - ref)] += 1
            if votes:
                (new_rva, n), = votes.most_common(1)
                how = f"{n}/{sum(votes.values())} references agree ({len(refs)} found in the old build)"
                if len(votes) > 1:
                    how += f"; others: {', '.join(hex(v) for v in list(votes)[1:4])}"
            else:
                new_rva, how = None, f"no usable reference ({len(refs)} found in the old build)"
        results[name] = new_rva
        shown = f"{new_rva:#x}" if new_rva is not None else "???"
        print(f"{name:26} {rva:#09x} -> {shown:>10}   // {how}")


if __name__ == "__main__":
    main()
