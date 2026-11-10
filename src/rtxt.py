#!/usr/bin/env python3
"""RTXT text tables (Tachyon's string-table .bin files: JOBS.BIN, ITEMS.BIN, HELPTEXT.BIN, ...).

Format: ksy/rtxt.ksy and decomp/notes/formats.md "RTXT". In short:

    header   "RTXT", u32 group_table_offset, u32 group_table_length, u32 record_count
    records  record_count x 16 B: u32 value_offset (from end of this table), s16 x, s16 y,
             s16 group, 6 B zero
    values   NUL-terminated strings
    groups   @group_table_offset: u32 group_count, group_count x {u32 keys_offset, u32 entry_count},
             group_count names, then record_count key names (record order)

Records are numbered globally; group g owns the next entry_count of them.

usage:
  rtxt.py dump  FILE.BIN              # INI-like: [GROUP] / KEY=VALUE
  rtxt.py check DIR                   # parse every RTXT in DIR, report problems
"""
import os
import struct
import sys


def _cstr(b, o):
    e = b.index(b"\0", o)
    return b[o:e].decode("latin1"), e + 1


def parse(b):
    """Return [(group_name, [(key, value, (x, y, group_field)), ...]), ...].

    Files without groups (allowed by the format, none in Tachyon) come back as a single
    group named None whose keys are None.
    """
    if b[:4] != b"RTXT":
        raise ValueError("not an RTXT file")
    gto, gtl, n = struct.unpack_from("<III", b, 4)
    base = 16 + n * 16
    recs = []
    for i in range(n):
        vo, x, y, g = struct.unpack_from("<Ihhh", b, 16 + i * 16)
        recs.append((_cstr(b, base + vo)[0], (x, y, g)))

    gc = struct.unpack_from("<I", b, gto)[0] if gto + 4 <= len(b) else 0
    if gc == 0:
        return [(None, [(None, v, f) for v, f in recs])]

    hdrs = [struct.unpack_from("<II", b, gto + 4 + 8 * i) for i in range(gc)]
    p = gto + 4 + 8 * gc
    names = []
    for _ in range(gc):
        s, p = _cstr(b, p)
        names.append(s)
    out, idx = [], 0
    for name, (ko, ec) in zip(names, hdrs):
        p = gto + 4 + ko
        items = []
        for _ in range(ec):
            key, p = _cstr(b, p)
            v, f = recs[idx]
            items.append((key, v, f))
            idx += 1
        out.append((name, items))
    return out


def dump(b):
    lines = []
    for name, items in parse(b):
        if name is not None:
            lines.append("[%s]" % name)
        for key, val, _ in items:
            val = val.replace("\r\n", "\\n").replace("\n", "\\n")
            lines.append(val if key is None else "%s=%s" % (key, val))
        lines.append("")
    return "\n".join(lines)


def check(b):
    """List of problems (empty = clean)."""
    probs = []
    gto, gtl, n = struct.unpack_from("<III", b, 4)
    if gto + 4 + gtl != len(b):
        probs.append("group table end %d != file size %d" % (gto + 4 + gtl, len(b)))
    gs = parse(b)
    if sum(len(i) for _, i in gs) != n:
        probs.append("sum(entry_count) != record_count")
    idx = 0
    for gi, (_, items) in enumerate(gs):
        for _, _, (x, y, g) in items:
            if gs[0][0] is not None and g != gi:
                probs.append("record %d group field %d != %d" % (idx, g, gi))
            idx += 1
    return probs


def main(argv):
    if len(argv) < 3 or argv[1] not in ("dump", "check"):
        print(__doc__)
        return 2
    if argv[1] == "dump":
        sys.stdout.write(dump(open(argv[2], "rb").read()))
        return 0
    bad = total = 0
    for n in sorted(os.listdir(argv[2])):
        p = os.path.join(argv[2], n)
        if not os.path.isfile(p):
            continue
        with open(p, "rb") as f:
            if f.read(4) != b"RTXT":
                continue
            b = b"RTXT" + f.read()
        total += 1
        try:
            probs = check(b)
        except Exception as e:  # noqa: BLE001 - report and keep going
            probs = ["parse error: %s" % e]
        if probs:
            bad += 1
            print("%s: %s" % (n, "; ".join(probs[:5])))
    print("%d RTXT files, %d with problems" % (total, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
