"""Second pass of port_offsets.py: leaf functions (no .pdata entry), return-address sanity, data strings.

    python tools/port_verify.py <old exe> <new exe>
"""
import sys

import capstone

sys.path.insert(0, __import__("os").path.dirname(__file__))
from port_offsets import PE  # noqa: E402

old, new = PE(sys.argv[1]), PE(sys.argv[2])
cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
cs.detail = True


def disasm(pe, rva, n=12):
    o = pe.off(rva)
    return list(cs.disasm(pe.b[o:o + 96], rva))[:n]


def pattern(pe, rva, length=40):
    """Bytes of the leaf function until its ret, RIP-relative displacements and rel32 branches masked."""
    out = []
    for ins in disasm(pe, rva, 40):
        raw = list(ins.bytes)
        mask = [True] * len(raw)
        disp_off = getattr(ins, "disp_offset", 0)
        if pe.rip_target(ins) is not None and disp_off:
            for k in range(disp_off, disp_off + 4):
                mask[k] = False
        if (ins.group(capstone.CS_GRP_JUMP) or ins.group(capstone.CS_GRP_CALL)) and ins.size >= 5 \
                and ins.operands and ins.operands[0].type == capstone.x86.X86_OP_IMM:
            for k in range(ins.size - 4, ins.size):
                mask[k] = False
        out += [b if m else None for b, m in zip(raw, mask)]
        if ins.mnemonic in ("ret", "jmp") or len(out) >= length:
            break
    return out[:length]


def search(pe, pat, lo, hi):
    hits = []
    o_lo, o_hi = pe.off(lo), pe.off(hi)
    data = pe.b
    first = next(i for i, b in enumerate(pat) if b is not None)
    needle = bytes([pat[first]])
    pos = data.find(needle, o_lo)
    while 0 <= pos < o_hi:
        start = pos - first
        if all(b is None or data[start + i] == b for i, b in enumerate(pat)):
            hits.append(start)
        pos = data.find(needle, pos + 1)
    text = next(s for s in pe.sections if s[0] == ".text")
    return [h - text[3] + text[1] for h in hits]


print("== Leaf functions (searched within +-0x10000 of the old RVA)")
for name, rva in (("CHAPTER_GET_FUNC", 0x7DCF10), ("CHAPTER_COUNT_FUNC", 0x7DE510),
                  ("CHAPTER_CHARACTER_FUNC", 0x8A2B00), ("TEST_GAME_FLAG_FUNC", 0x9CA510)):
    pat = pattern(old, rva)
    hits = search(new, pat, rva - 0x10000, rva + 0x10000)
    print(f"{name:24} old {rva:#x} pattern {len(pat)} bytes -> {[hex(h) for h in hits]}")
    for ins in disasm(old, rva, 6):
        print(f"      old {ins.address:#x}: {ins.mnemonic} {ins.op_str}")
    for h in hits[:1]:
        for ins in disasm(new, h, 6):
            print(f"      new {ins.address:#x}: {ins.mnemonic} {ins.op_str}")
        o = new.off(h)
        print(f"      new padding before: {new.b[o - 4:o].hex(' ')}")

print("\n== Return addresses: the instruction before must be the same call in both builds")
RETS = {"TITLE_MENU_FLAG_RET": (0x9B3D4D, 0x9B442D), "RET_NORMAL_CHEST": (0x80032D, 0x80074D),
        "RET_HACKING_CHEST": (0x800573, 0x800993), "RET_HACKING_CHEST_CALLER": (0x7CA45F, 0x7CA85F),
        "RET_MOB_DROP": (0x7DA8AA, 0x7DACAA), "RET_GROUND_PICKUP": (0x898B42, 0x898F82),
        "RET_FISHING": (0x629000, 0x629100), "RET_POD_SLOT_INIT": (0x328840, 0x328940),
        "RET_SAVE_LOAD": (0x31DF78, 0x31E078), "RET_INVENTORY_RESET": (0x150BED, 0x150CDD)}


def prev_insn(pe, rva):
    for back in range(1, 16):
        ins = list(cs.disasm(pe.b[pe.off(rva - back):pe.off(rva - back) + back], rva - back))
        if ins and ins[-1].address + ins[-1].size == rva and len(ins) == 1:
            return ins[0]
    return None


for name, (o_rva, n_rva) in RETS.items():
    a, b = prev_insn(old, o_rva), prev_insn(new, n_rva)
    fa = f"{a.mnemonic} {a.op_str}" if a else "?"
    fb = f"{b.mnemonic} {b.op_str}" if b else "?"
    print(f"{name:26} old: {fa:28} new: {fb}")

print("\n== Strings")
for rva in (0xCAC904,):
    print(f"old {rva:#x}: {old.b[old.off(rva):old.off(rva) + 8]}")
for rva in (0xCAC91C, 0xCA8620):
    print(f"new {rva:#x}: {new.b[new.off(rva):new.off(rva) + 8]}")
