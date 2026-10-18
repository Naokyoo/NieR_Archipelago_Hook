"""Diagnostic: dumps the Plug-in Chip table of a running NieRAutomata.exe.

Run it while 2B is in game (prologue, HUD chips still equipped):
    python dump_chips.py
"""
import ctypes
import ctypes.wintypes as wt
import struct
import sys

SAVE_DATA_BASE_RVA = 0x145BF58
CHIP_TABLE_START = 0x148E410
CHIP_TABLE_END = CHIP_TABLE_START + 300 * 48
CHIP_SIZE = 48

KNOWN_CHIPS = {
    3335: "HUD: HP Gauge", 3336: "HUD: Sound Waves", 3337: "HUD: Enemy Data",
    3338: "OS Chip", 3343: "HUD: Skill Gauge", 3344: "HUD: Text Log",
    3345: "HUD: Mini-map", 3346: "HUD: EXP Gauge", 3347: "HUD: Save Points",
    3348: "HUD: Damage Values", 3349: "HUD: Objectives", 3350: "HUD: Control",
}

TH32CS_SNAPPROCESS = 0x2
TH32CS_SNAPMODULE = 0x8 | 0x10
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
                ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", wt.DWORD),
                ("cntThreads", wt.DWORD), ("th32ParentProcessID", wt.DWORD),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
                ("szExeFile", ctypes.c_wchar * 260)]


class MODULEENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("th32ModuleID", wt.DWORD), ("th32ProcessID", wt.DWORD),
                ("GlblcntUsage", wt.DWORD), ("ProccntUsage", wt.DWORD),
                ("modBaseAddr", ctypes.c_void_p), ("modBaseSize", wt.DWORD),
                ("hModule", wt.HMODULE), ("szModule", ctypes.c_wchar * 256),
                ("szExePath", ctypes.c_wchar * 260)]


k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
k32.OpenProcess.restype = wt.HANDLE
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                  ctypes.POINTER(ctypes.c_size_t)]


def find_process():
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    pe = PROCESSENTRY32W()
    pe.dwSize = ctypes.sizeof(pe)
    ok = k32.Process32FirstW(snap, ctypes.byref(pe))
    while ok:
        if pe.szExeFile.lower() == "nierautomata.exe":
            k32.CloseHandle(snap)
            return pe.th32ProcessID
        ok = k32.Process32NextW(snap, ctypes.byref(pe))
    k32.CloseHandle(snap)
    return None


def find_base(pid):
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, pid)
    me = MODULEENTRY32W()
    me.dwSize = ctypes.sizeof(me)
    base = None
    if k32.Module32FirstW(snap, ctypes.byref(me)):
        base = me.modBaseAddr
    k32.CloseHandle(snap)
    return base


def read(handle, addr, size):
    buf = ctypes.create_string_buffer(size)
    n = ctypes.c_size_t()
    if not k32.ReadProcessMemory(handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(n)):
        raise OSError(f"ReadProcessMemory failed at {addr:#x} (err {ctypes.get_last_error()})")
    return buf.raw[:n.value]


def main():
    pid = find_process()
    if not pid:
        sys.exit("NieRAutomata.exe is not running")
    base = find_base(pid)
    handle = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    print(f"PID {pid}, base {base:#x}\n")

    # 1. Raw dump of the chip table as the hook currently sees it
    data = read(handle, base + CHIP_TABLE_START, CHIP_TABLE_END - CHIP_TABLE_START)
    print(f"=== Chip table @ RVA {CHIP_TABLE_START:#x} (non-empty entries, 12 dwords each) ===")
    shown = 0
    for i in range(len(data) // CHIP_SIZE):
        dw = struct.unpack_from("<12I", data, i * CHIP_SIZE)
        if all(d in (0, 0xFFFFFFFF) for d in dw):
            continue
        tag = next((KNOWN_CHIPS[d] for d in dw[:3] if d in KNOWN_CHIPS), "")
        print(f"[{i:3}] " + " ".join(f"{d:08X}" for d in dw) + (f"  <- {tag}" if tag else ""))
        shown += 1
        if shown >= 60:
            print("... (truncated)")
            break

    # 2. Locate every HUD/OS chip id anywhere in the save block, whatever the layout
    save = read(handle, base + SAVE_DATA_BASE_RVA, CHIP_TABLE_END - SAVE_DATA_BASE_RVA + 0x100)
    print("\n=== Occurrences of HUD/OS chip ids in the save block ===")
    for off in range(0, len(save) - 4, 4):
        v = struct.unpack_from("<I", save, off)[0]
        if v in KNOWN_CHIPS:
            ctx = struct.unpack_from("<12I", save, max(0, off - 8))
            print(f"save+{off:#07x} (RVA {SAVE_DATA_BASE_RVA + off:#x}) {KNOWN_CHIPS[v]:<20} ctx[-8]: "
                  + " ".join(f"{d:08X}" for d in ctx))
    k32.CloseHandle(handle)


if __name__ == "__main__":
    main()
