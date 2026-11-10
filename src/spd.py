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

Status: SPED objects, placements, sub-sector stages, triggers (see spxtrig.py), routes,
labels, group target rules, aliases, group names, region/sector ids and sector flags are mapped
(ksy/spd.ksy has the field-by-field layout; several header fields were first identified by
NovaHQ's NovaResearch and then checked here). Placement bodies are decoded per kind
(gate / asteroid / AI object / pickup); group/contents/name fields are resolved through
SHIPTEXT.BIN when it sits next to the SPX. Loader: Spx_LoadSector 0x4356e0.

For now this points directly at a file in the pff/ directory (override with argv[1]).
"""
import struct
import sys
import re

DEFAULT_PATH = "/home/matt/Tach-play/pff/BORA05.SPX"


def cstr(d, o):
    e = d.find(b"\x00", o)
    return d[o:(e if e >= 0 else len(d))].decode("latin1", "replace")


def shiptext_groups(spx_path):
    """(key -> global record index, FLIGHT_GROUPS base) from SHIPTEXT.BIN next to the SPX, or ({}, 0).

    Placement group / contents / name fields index the SPX's group-name table; the engine maps
    those names through SHIPTEXT.BIN (groups become index - FLIGHT_GROUPS base)."""
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import rtxt
    folder = os.path.dirname(os.path.abspath(spx_path))
    for n in os.listdir(folder):
        if n.lower() == "shiptext.bin":
            idx, base, i = {}, 0, 0
            for name, items in rtxt.parse(open(os.path.join(folder, n), "rb").read()):
                if name == "FLIGHT_GROUPS":
                    base = i
                for k, _, _ in items:
                    idx.setdefault(k, i)
                    i += 1
            return idx, base
    return {}, 0


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
    first = u32(d, 0)
    flags = u32(d, 0x88)
    print("sector flags : 0x%x%s" % (flags, "".join(n for b, n in ((1, " RADIATION"), (2, " FOG")) if flags & b)))
    if first >= 0x104:
        print("region/sector: %d / %d" % (u32(d, 0xfc), u32(d, 0x100)))
    if first >= 0x120 and (u32(d, 0x118) or u32(d, 0x11c)):
        print("BaseWars base: sector %d race %d" % (u32(d, 0x118), u32(d, 0x11c)))

    def names(cnt_off, rec, off_off):
        return [cstr(d, u32(d, off_off) + i * rec) for i in range(u32(d, cnt_off))]
    print("dialogs      : %s" % names(0x58, 0x10, 0x5c))
    print("scenes       : %s" % names(0x64, 0x10, 0x68))
    print("labels       : %s" % names(0x70, 0x20, 0x74))
    print("aliases      : %s" % names(0xf4, 0x20, 0xf8))
    if first >= 0x110:
        print("group names  : %s" % names(0x108, 0x20, 0x10c))

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
    # object's spawn position and orientation. This is where per-object x/y/z actually lives.
    place_off = u32(d, 0x18)
    place_count = u32(d, 0x14)
    def s32(o):
        return struct.unpack_from("<i", d, o)[0]
    def u16(o):
        return struct.unpack_from("<H", d, o)[0]
    gnames = [cstr(d, u32(d, 0x10c) + i * 0x20) for i in range(u32(d, 0x108))] if first >= 0x110 else []
    fg_index, fg_base = shiptext_groups(path)

    def gname(v, group=False):
        """Group-name-table index -> 'NAME' (+ final id for groups when SHIPTEXT.BIN is found)."""
        if v < 0 or v >= len(gnames):
            return "-" if v == -1 else "?%d" % v
        n = gnames[v]
        if group and n in fg_index:
            return "%s(=%d)" % (n, fg_index[n] - fg_base)
        return n

    if 0 < place_count < 4096 and 0 < place_off < len(d):
        print("\n-- object placements: %d @ 0x%x --" % (place_count, place_off))
        o = place_off
        for i in range(place_count):
            kind, size = u16(o), u16(o + 2)
            idx = s32(o + 0x04)
            pos = (s32(o + 0x08), s32(o + 0x0c), s32(o + 0x10))
            orient = (s32(o + 0x14), s32(o + 0x18), s32(o + 0x1c))   # 512 units per turn
            obj_id, flags = s32(o + 0x20), u32(d, o + 0x24)
            alias = sped[idx] if 0 <= idx < len(sped) else "-"
            if kind == 1:      # gate
                extra = "dest=%s open_var=%d:%d regional=%d->%d" % (
                    cstr(d, o + 0x38), struct.unpack_from("<h", d, o + 0x48)[0],
                    struct.unpack_from("<h", d, o + 0x4a)[0], u32(d, o + 0x58), s32(o + 0x5c))
            elif kind == 2:    # asteroid
                extra = "scale=%.2f" % (s32(o + 0x38) / 65536.0)
            elif kind == 3:    # AI object
                parts = []
                if d[o + 0x38]: parts.append("side=%d" % (d[o + 0x38] - 1))
                if d[o + 0x39]: parts.append("skill=%d" % (d[o + 0x39] - 1))
                if d[o + 0x3a]: parts.append("bwlvl=%d" % d[o + 0x3a])
                sec, key = struct.unpack_from("<hh", d, o + 0x3c)
                if sec != -1: parts.append("if var%d:%d==%d" % (sec, key, s32(o + 0x40)))
                if s32(o + 0x44) != -1: parts.append("label=%d" % s32(o + 0x44))
                if s32(o + 0x48) != -1: parts.append("route#%d.%d" % (s32(o + 0x48), max(0, s32(o + 0x4c))))
                if s32(o + 0x54) != -1: parts.append("grp=%s" % gname(s32(o + 0x54), True))
                if s32(o + 0x5c) != -1: parts.append("alias=%d" % s32(o + 0x5c))
                if s32(o + 0x60) != -1: parts.append("contents=%s" % gname(s32(o + 0x60)))
                if s32(o + 0x64) != -1: parts.append("name=%s" % gname(s32(o + 0x64)))
                extra = " ".join(parts)
            elif kind == 4:    # pickup
                extra = "respawn=%ds jitter=%d" % (s32(o + 0x38), s32(o + 0x3c))
            else:
                extra = ""
            print("  [%d] k%d %-26s id=%d pos=%s orient=%s flags=0x%x %s"
                  % (i, kind, alias, obj_id, pos, orient, flags, extra))
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

    # --- waypoint routes ("waygroups"): {count, offset} at +0x8c/+0x90, header 0x14, point 0x20 ---
    # Placements pick a route by index (+0x48); triggers and CHANGE_WP name it by `tag`.
    rc, ro = u32(d, 0x8c), u32(d, 0x90)
    if rc:
        print("\n-- waypoint routes: %d @ 0x%x --" % (rc, ro))
        acts = {0: "change route", 1: "hyper out", 2: "activate", 3: "enter gate/group order", 4: "unspawn"}
        for i in range(rc):
            o = ro + i * 0x14
            npt, po, tag = u32(d, o), u32(d, o + 4), s32(o + 8)
            pts = []
            for j in range(npt):
                q = po + j * 0x20
                p = "(%d,%d,%d)" % (s32(q), s32(q + 4), s32(q + 8))
                a = s32(q + 0x0c)
                if a in acts:
                    p += "[%s %d]" % (acts[a], s32(q + 0x10))
                pts.append(p)
            print("  [%d] tag=%d %s" % (i, tag, " ".join(pts)))

    # --- group AI target rules: {count, offset} at +0xe8/+0xec (Spx_LinkSection, Ai_TargetFilter) ---
    sc, so = u32(d, 0xe8), u32(d, 0xec)
    if sc:
        fg_names = {v - fg_base: k for k, v in fg_index.items()} if fg_index else {}
        rule = {0: "attack any", 1: "attack group", 2: "attack obj", 3: "prefer group",
                4: "prefer obj", 5: "ignore group", 6: "ignore obj", 9: "ignore players"}
        print("\n-- group target rules: %d lists @ 0x%x --" % (sc, so))
        o = so
        for i in range(sc):
            size, esz, gid, n, eo = struct.unpack_from("<IIiII", d, o)
            rs = []
            for j in range(n):
                t, tgt = struct.unpack_from("<ii", d, eo + j * esz)
                r = rule.get(t, "type %d" % t)
                if t in (1, 3, 5):
                    r += " %s" % fg_names.get(tgt, tgt)
                elif t in (2, 4, 6):
                    r += " %d" % tgt
                rs.append(r)
            print("  group %s: %s" % (fg_names.get(gid, gid), "; ".join(rs)))
            if size == 0:
                break
            o += size

    # NOTE: per-object world positions/orientations live in the placement section decoded above
    # (offset @ +0x18, count @ +0x14). The SPED decl record is just name[0x20]+ptr; the placement
    # record is the "def" fed to Sped_ConstructEntity, carrying pos (+0x08/0c/10) and orientation
    # (+0x14/18/1c Euler angles -- NOT velocity; stationary objects have non-zero facing here).
    # The variable-size record tail holds per-type params (orientation, gate dest, etc.) — not yet
    # fully decoded.

    # --- raw header directory (partially reversed) ---
    print("\n-- header directory dwords (+0x08..+0x33) --")
    # +08 SPED {size,count,off}; +14 placement {count,off}; +1c trigger {size,count,off};
    # +28 sub-sector {size,count,off}
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
