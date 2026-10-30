#!/usr/bin/env python3
"""
SPD / .SPX sector ("space") file parser + printer for Tachyon: The Fringe.

An .SPX file defines one sector of space: its backdrop, the SPED objects
(ships/stations/gates/asteroids/...) that populate it, sub-sector stages, and
links to adjacent sectors. Magic is "SPD\\x01" at file offset +4.

Reverse-engineered from BORA05.SPX + space.exe:
  - Each space object is a "SPED" (SPace EDitor object?). Its alias name maps to a
    .des model via the SPED name registry, and its DESC_TYPE (in the .des) selects
    its entity class (SHIP/ASTEROID/CAPITOL_SHIP/HYPER_GATE/STARBASE/MINE/CARGO/
    BEACON/SPEED_RING/COURSE/MISC_OBJECT/POWERUP/...).

Status: the SPED-object section and the fixed QUAD/BDF fields are confirmed; the
rest of the header directory + the nav/sub-sector record internals are partially
reversed (dumped raw below). The in-game byte-parser function was not pinned.

For now this points directly at a file in the pff/ directory (override with argv[1]).
"""
import struct
import sys
import re

DEFAULT_PATH = "/home/matt/Tach-play/pff/BORA05.SPX"


def cstr(d, o):
    e = d.find(b"\x00", o)
    return d[o:(e if e >= 0 else len(d))].decode("latin1", "replace")


def u32(d, o):
    return struct.unpack_from("<I", d, o)[0]


def parse(path):
    d = open(path, "rb").read()
    if d[4:8] != b"SPD\x01":
        raise ValueError("not an SPD/.SPX file (magic@+4 is %r, expected b'SPD\\x01')" % d[4:8])

    print("== SPD sector file: %s (%d bytes) ==" % (path, len(d)))
    print("first_offset : 0x%x" % u32(d, 0))
    print("QUAD name    : %s" % cstr(d, 0x34))
    print("BDF backdrop : %s" % cstr(d, 0x78))

    # --- SPED object section (confirmed): {recSize, count, offset} at +8/+0xc/+0x10 ---
    rec_size = u32(d, 0x08)
    count = u32(d, 0x0c)
    offset = u32(d, 0x10)
    print("\n-- SPED objects: %d x 0x%x bytes @ 0x%x --" % (count, rec_size, offset))
    sped = []
    for i in range(count):
        o = offset + i * rec_size
        if o + rec_size > len(d):
            break
        name = cstr(d, o)                      # alias (inline, up to ~0x20 bytes)
        sped.append(name)
        runtime_ptr = u32(d, o + 0x20)         # resolved at load; stale on disk
        print("  [%d] %-32s  tailptr=0x%08x" % (i, name, runtime_ptr))

    # --- placement / SPED-def section (CONFIRMED from space.exe Spx_ApplyPlacements 0x4351e0) ---
    # {offset, count} at +0x18 / +0x14. Variable-stride records: u16 recSize @ +0x02, u32 SPED-decl
    # index @ +0x04. The record IS the "def" passed to Sped_ConstructEntity (0x434ac0): it carries the
    # object's spawn position and velocity. This is where per-object x/y/z actually lives.
    place_off = u32(d, 0x18)
    place_count = u32(d, 0x14)
    def s32(o):
        return struct.unpack_from("<i", d, o)[0]
    def u16(o):
        return struct.unpack_from("<H", d, o)[0]
    if 0 < place_count < 4096 and 0 < place_off < len(d):
        print("\n-- object placements (x/y/z spawn): %d @ 0x%x --" % (place_count, place_off))
        o = place_off
        for i in range(place_count):
            if o + 0x5c > len(d):
                print("  [%d] truncated @0x%x" % (i, o)); break
            kind = u16(o + 0x00)      # category tag (0=null 1=gate 2=roid/debris 3=ship/station
                                      # 4=MP pickup); set by the editor, NOT read by the load path
            size = u16(o + 0x02)      # record stride
            idx = s32(o + 0x04)       # index into the SPED decl section above
            pos = (s32(o + 0x08), s32(o + 0x0c), s32(o + 0x10))   # world position x,y,z
            # orientation = 3 Euler angles; unit is 512 per full circle (0.703125 deg/unit),
            # i.e. 128=90deg, 256=180deg. (<<16 at runtime so the trig table can interpolate.)
            orient = (s32(o + 0x14), s32(o + 0x18), s32(o + 0x1c))
            flags = u32(d, o + 0x24)
            obj_id = s32(o + 0x5c)    # object id (-1 = none)
            alias = sped[idx] if 0 <= idx < len(sped) else "?"
            # +0x38 is per-kind: ships = team/side byte; gates = destination sector .spx name
            if kind == 1:
                extra = "dest=%s" % cstr(d, o + 0x38)
            else:
                extra = "team=%d" % d[o + 0x38]
            print("  [%d] %-26s pos=%s orient=%s %s id=%d flags=0x%x (kind=%d sz=0x%x)"
                  % (i, alias, pos, orient, extra, obj_id, flags, kind, size))
            if size == 0:
                break
            o += size

    # --- sub-sector ("stage") section: {count, offset} at +0x2c/+0x30, recSize 0x2c ---
    # Confirmed from Spx_SelectSubSector (0x435410): the engine loads the FIRST stage whose
    # VarStore condition holds, so a sector morphs by mission variables. Record layout:
    #   name[0x10] + varSection@+0x10, varKey@+0x14, value@+0x18, op@+0x1c (0=AND-eq 1=AND-neq
    #   2=OR), optional 2nd var @+0x20/+0x24 with value @+0x28.
    sub_count = u32(d, 0x2c)
    sub_off = u32(d, 0x30)
    if 0 < sub_count < 64 and sub_off + sub_count * 0x2c <= len(d):
        print("\n-- sub-sector stages (conditional): %d x 0x2c @ 0x%x --" % (sub_count, sub_off))
        for i in range(sub_count):
            o = sub_off + i * 0x2c
            name = cstr(d, o)
            vsec, vkey, val, op = (s32(o + 0x10), s32(o + 0x14), s32(o + 0x18), s32(o + 0x1c))
            # var[section,key] indexes the player var store; [0,4] = player_main_vars.CURRENT_JOB
            # (enum 'jobs', e.g. BC06=2008) -- i.e. sub-sectors usually switch on the current job.
            label = "CURRENT_JOB" if (vsec, vkey) == (0, 4) else "var[%d,%d]" % (vsec, vkey)
            print("  [%d] %-16s  if %s==%d (op=%d)" % (i, name, label, val, op))

    # NOTE: per-object world positions/orientations live in the placement section decoded above
    # (offset @ +0x18, count @ +0x14). The SPED decl record is just name[0x20]+ptr; the placement
    # record is the "def" fed to Sped_ConstructEntity, carrying pos (+0x08/0c/10) and orientation
    # (+0x14/18/1c Euler angles -- NOT velocity; stationary objects have non-zero facing here).
    # The variable-size record tail holds per-type params (orientation, gate dest, etc.) — not yet
    # fully decoded.

    # --- raw header directory (partially reversed) ---
    print("\n-- header directory dwords (+0x08..+0x33) --")
    for o in range(0x08, 0x34, 4):
        print("  +%02x: 0x%x (%d)" % (o, u32(d, o), u32(d, o)))

    # --- embedded references / strings (sub-sectors, adjacent sectors, .scr, etc.) ---
    print("\n-- embedded strings (offset: value) --")
    for m in re.finditer(rb"[\x20-\x7e]{4,}", d):
        s = m.group().decode()
        tag = ""
        low = s.lower()
        if low.endswith(".spx"):
            tag = "  <- sub/adjacent sector"
        elif low.endswith(".bdf"):
            tag = "  <- backdrop"
        elif low.endswith(".scr"):
            tag = "  <- craft/script"
        print("  +%04x %s%s" % (m.start(), s, tag))


if __name__ == "__main__":
    parse(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH)
