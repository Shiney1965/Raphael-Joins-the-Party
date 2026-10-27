"""Compile a merged Osiris story (.div text) with the BG3 Toolkit's own Osiris.dll.

This is the real Larian compiler, so it reports the errors the game reports only as
"1 error(s)". Usage:

    python osiris_dll_compile.py <story.div> <out.log>

Prints the log and exits 0 when the compile succeeds, 1 when it fails.
Calls (exports of Osiris.dll, x64, so `this` is just the first argument):
    GetAllocator() -> CreateOsirisObject(alloc) -> GetOsirisObject()
    OpenLogFile(this, path, ios::app=8); Compile(this, path, L"r+"); CloseLogFile(this)
Run it in its own process: a crash inside the DLL then cannot take anything else down.
"""
import ctypes
import os
import sys

DLL = r"C:\Steam Library\steamapps\common\Baldurs Gate 3 Toolkit\Osiris.dll"


def make_allocator():
    """Build an IMemoryAllocator for Osiris: an object whose vtable has
    slot 0 = Alloc(this, size, flags) and slot 1 = Free(this, ptr, flags).
    (Disassembly of Osiris.dll: every allocator call goes through [vtbl+0] or [vtbl+8].)
    Each slot is a stub `mov rcx, rdx; mov rax, <crt fn>; jmp rax` into ucrt calloc-free/malloc.
    """
    k32 = ctypes.WinDLL("kernel32")
    k32.VirtualAlloc.restype = ctypes.c_void_p
    k32.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32]
    crt = ctypes.CDLL("ucrtbase")
    malloc = ctypes.cast(crt.malloc, ctypes.c_void_p).value
    free = ctypes.cast(crt.free, ctypes.c_void_p).value
    mem = k32.VirtualAlloc(None, 4096, 0x3000, 0x40)  # MEM_COMMIT|MEM_RESERVE, PAGE_EXECUTE_READWRITE

    def stub(target):
        return b"\x48\x89\xD1" + b"\x48\xB8" + target.to_bytes(8, "little") + b"\xFF\xE0"

    # Slot 2+ (e.g. [vtbl+0x10], called at Compile start with no args, result unused):
    # `xor eax, eax; ret`.
    code = stub(malloc).ljust(32, b"\xCC") + stub(free).ljust(32, b"\xCC") + b"\x31\xC0\xC3".ljust(32, b"\xCC")
    ctypes.memmove(mem, code, len(code))
    vtbl = mem + 256
    obj = mem + 1024
    slots = [mem, mem + 32] + [mem + 64] * 30
    ctypes.memmove(vtbl, (ctypes.c_uint64 * 32)(*slots), 8 * 32)
    ctypes.memmove(obj, (ctypes.c_uint64 * 1)(vtbl), 8)
    return obj


def main():
    src, log = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    if os.path.exists(log):
        open(log, "w").close()
    os.add_dll_directory(os.path.dirname(DLL))
    d = ctypes.CDLL(DLL)

    def fn(name, res, *args):
        f = d[name]
        f.restype = res
        f.argtypes = list(args)
        return f

    vp, ws = ctypes.c_void_p, ctypes.c_wchar_p

    # Debug aid: report where inside Osiris.dll an access violation happens (RVA).
    VEH = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)

    def on_exc(pointers):
        rec = ctypes.cast(pointers, ctypes.POINTER(ctypes.c_void_p))[0]
        code = ctypes.cast(rec, ctypes.POINTER(ctypes.c_uint32))[0]
        addr = ctypes.cast(rec + 16, ctypes.POINTER(ctypes.c_void_p))[0] or 0
        if code == 0xC0000005:
            ctx = ctypes.cast(pointers, ctypes.POINTER(ctypes.c_void_p))[1]
            rip = ctypes.cast(ctx + 0xF8, ctypes.POINTER(ctypes.c_uint64))[0]
            rsp = ctypes.cast(ctx + 0x98, ctypes.POINTER(ctypes.c_uint64))[0]
            stack = [ctypes.cast(rsp + 8 * i, ctypes.POINTER(ctypes.c_uint64))[0] for i in range(64)]
            near = ["0x%X" % (v - d._handle) for v in stack if 0 <= v - d._handle < 0x100000]
            print("[exception] addr=0x%X rip=0x%X dllbase=0x%X ripRVA=0x%X stackRVAs=%s"
                  % (addr, rip, d._handle, rip - d._handle, near[:12]), flush=True)
        return 0

    veh = VEH(on_exc)
    ctypes.windll.kernel32.AddVectoredExceptionHandler(1, veh)
    get_alloc = fn("?GetAllocator@@YAPEAVIMemoryAllocator@@XZ", vp)
    create = fn("?CreateOsirisObject@COsiris@@SAXPEAVIMemoryAllocator@@@Z", None, vp)
    get_obj = fn("?GetOsirisObject@COsiris@@SAPEAV1@XZ", vp)
    set_log = fn("?SetLogEnabled@COsiris@@SAX_N@Z", None, ctypes.c_bool)
    open_log = fn("?OpenLogFile@COsiris@@QEAA_NPEB_WH@Z", ctypes.c_bool, vp, ws, ctypes.c_int)
    close_log = fn("?CloseLogFile@COsiris@@QEAAXXZ", None, vp)
    compile_ = fn("?Compile@COsiris@@QEAA_NPEB_W0@Z", ctypes.c_bool, vp, ws, ws)

    register_div = fn("?RegisterDIVFunctions@COsiris@@QEAAXPEAUTOsirisInitFunction@@@Z", None, vp, vp)

    create(make_allocator())
    osi = get_obj()
    if not osi:
        print("CreateOsirisObject gave no object")
        return 2

    # DivFunctions (bg3se GameDefinitions/Osiris.h): Unknown0, Call, Query, ErrorMessage, Assert.
    # No game is attached, so Call/Query just fail; messages are echoed.
    CALL = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_uint32, vp)
    ERRMSG = ctypes.CFUNCTYPE(None, ctypes.c_char_p)
    ASSERT = ctypes.CFUNCTYPE(None, ctypes.c_bool, ctypes.c_char_p, ctypes.c_bool)
    keep = [CALL(lambda f, p: False), CALL(lambda f, p: False),
            ERRMSG(lambda m: print("[ErrorMessage]", (m or b"").decode("utf-8", "replace"))),
            ASSERT(lambda ok, m, u: None if ok else print("[Assert]", (m or b"").decode("utf-8", "replace")))]
    divf = (ctypes.c_void_p * 5)(None, *[ctypes.cast(k, ctypes.c_void_p).value for k in keep])
    register_div(osi, ctypes.addressof(divf))
    set_log(True)
    print("OpenLogFile:", open_log(osi, log, 8))
    ok = compile_(osi, src, "r+")
    close_log(osi)
    print("Compile returned:", ok)
    if os.path.exists(log):
        sys.stdout.write(open(log, encoding="utf-8", errors="replace").read())
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
