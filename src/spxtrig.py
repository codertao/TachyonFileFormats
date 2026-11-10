#!/usr/bin/env python3
"""Pretty-print the mission trigger table embedded in a Tachyon .SPX sector file.

Reversed from space.exe (see decomp/notes/missions.md "Mission scripting"):
  SPX header +0x20 = trigger count, +0x24 = file offset of trigger array (stride 0x14)
  trigger  {u32 nConds, u32 nActs, u32 fired(runtime), u32 condsOff, u32 actsOff}
  cond     {cat, sub, code, value, a, b, join, flags, sat(rt), satFrame(rt)}   stride 0x28
  action   {cat, arg, code, arg2}                                               stride 0x10

usage: spxtrig.py FILE.SPX [...] [--vars vars.cfg]
"""
import os, re, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# ---- vocab --------------------------------------------------------------------------
JOIN = {0: "AND", 1: "AND NOT", 2: "OR"}

# condition (event) codes, by category.  value compare: '>=' where the exe uses its comparator
COND = {
    0: ("PLAYER", {0: "damage% >= v", 1: "within v*10 of obj b", 2: "entered sector",
                   3: "player joined (MP)", 4: "docked with obj b", 5: "undocked from obj b",
                   6: "dock-menu action v on obj b", 7: "interacted/picked up obj b",
                   8: "triggered obj b", 9: "left sector/aborted", 10: "credits changed"}),
    1: ("OBJ", {0: "attacked by player", 2: "destroyed", 3: "damage% >= v", 4: "damage%(2) >= v",
                5: "reached waypoint", 6: "AI activated", 7: "docked",
                10: "code 10 (expired?)", 11: "code 11 (b)", 12: "code 12 (b)",
                13: "code 13 (entered bay of b?)", 14: "code 14 (resource hit 0?)", 15: "spawned"}),
    2: ("GATE", {0: "state changed"}),
    3: ("VAR", {0: "== v", 1: "== v", 2: "> v", 3: "< v"}),
    4: ("ENEMIES", {0: "all dead", 1: "% killed >= v"}),
    5: ("GROUP", {0: "member destroyed (none left?)", 1: "damage% >= v",
                  2: "member reached waypoint", 3: "member spawned", 4: "member attacked by player",
                  5: "member event 5", 6: "member AI activated"}),
    6: ("CAT6", {}),
    7: ("DIALOG", {0: "reached line v"}),
    8: ("SIDE", {0: "side `sub` attacked by player"}),
}

SPED_ACT = {0: "HYPERSPACE", 1: "ACTIVATE", 2: "ENTERGATE", 3: "EXPLODE", 7: "SET_IDENTIFIED",
            8: "CHANGE_RACE", 10: "DOCK_WITH_OBJ", 11: "UNDOCK", 12: "ENTER_OBJ_BAY",
            13: "BEAM_AWAY", 14: "TAKEOFF", 15: "CHANGE_WP", 19: "ADD_AS_OBJECTIVE",
            20: "REMOVE_AS_OBJECTIVE", 24: "UNSPAWN", 25: "WEAPONS_ACTIVATE",
            29: "RESTORE_POWERPLANT", 30: "TIMED_EXPLODE"}
ACT = {
    0: ("GATE", {0: "enable (instant)", 1: "disable (instant)", 2: "enable", 3: "disable"}),
    1: ("VAR", {0: "set = arg2", 1: "add arg2", 2: "sub arg2"}),
    2: ("DIALOG", {0: "play dialog[arg] from line arg2"}),
    3: ("SCENE", {0: "play cutscene[arg2]"}),
    4: ("COUNTER", {0: "start", 1: "stop"}),
    5: ("OBJ", {0: "spawn", 1: "spawn by class", 2: "dock with obj arg2", 3: "hyperspace in",
                4: "hyperspace out", 5: "activate", 6: "deactivate", 7: "explode",
                8: "CHANGE_RACE", 9: "DOCK_WITH_OBJ", 10: "UNDOCK", 11: "ENTER_OBJ_BAY",
                12: "TAKEOFF", 13: "CHANGE_WP", 14: "ADD_AS_OBJECTIVE", 15: "REMOVE_AS_OBJECTIVE",
                16: "BEAM_AWAY", 17: "weapons on", 18: "weapons off", 19: "UNSPAWN",
                20: "RESTORE_POWERPLANT", 21: "TIMED_EXPLODE"}),
    6: ("GROUP", {0: "spawn", 1: "spawn staggered", 2: "activate", 3: "set AI order arg2",
                  4: "CHANGE_RACE", 5: "ENTER_OBJ_BAY", 6: "deactivate", 7: "TAKEOFF next",
                  8: "CHANGE_WP"}),
    7: ("NAV", {0: "set player nav destination"}),  # arg = region<<16 | sector
    8: ("ORDER+", {}),     # add objective of type `code` about obj/group arg (this sector)
    9: ("ORDER-", {}),     # remove objective (10 = clear all, 11 = reset order state)
    10: ("ORDER_OK", {}),  # mark objective complete
    11: ("ORDER*", {0: "add (all sectors)", 1: "remove (all sectors)", 2: "complete (all sectors)",
                   3: "reset player inventory vars", 4: "set var-store tick = arg2*50"}),
    # 12..14 index past the 12-entry table in the exe and alias into cat 11 (+1, +2, +3)
    12: ("ORDER-*", {0: "remove (all sectors)"}),
    13: ("ORDER_OK*", {0: "complete (all sectors)"}),
    14: ("CAT14", {0: "reset player inventory vars", 1: "set var-store tick = arg2*50"}),
}


def load_vars(path):
    """vars.cfg -> {(catIndex, varIndex): 'SECTION.NAME'}"""
    try:
        import cbin
        txt = cbin.parse_cbin(open(path, "rb").read()).decode("latin-1")
    except Exception:
        return {}
    cats, sections, cur = {}, {}, None
    for line in txt.splitlines():
        if not line.startswith(" ") and line.strip():
            cur = line.strip().lower(); sections.setdefault(cur, {}); continue
        m = re.match(r"\s+CATEGORY:\s*(\w+),\s*(\d+)", line)
        if m and cur == "var_categories":
            cats[int(m.group(2))] = m.group(1).lower(); continue
        m = re.match(r"\s+VAR:\s*(\w+),\s*(\d+)", line)
        if m and cur:
            sections[cur][int(m.group(2))] = m.group(1)
    out = {}
    for ci, name in cats.items():
        for vi, vn in sections.get(name, {}).items():
            out[(ci, vi)] = "%s.%s" % (name.upper(), vn)
    return out


def main(argv):
    vars_path = os.path.join(os.path.dirname(HERE), "..", "pff", "vars.cfg")
    if "--vars" in argv:
        i = argv.index("--vars"); vars_path = argv[i + 1]; del argv[i:i + 2]
    V = load_vars(vars_path)
    for path in argv:
        dump(path, V)


def dump(path, V):
    d = open(path, "rb").read()
    u = lambda o, n=1: struct.unpack_from("<%di" % n, d, o)
    cstr = lambda o, n: d[o:o + n].split(b"\0")[0].decode("latin-1")

    # objects: id (+0x20) -> alias, group (+0x54)
    sped = [cstr(u(0x10)[0] + i * 0x24, 0x20) for i in range(u(0xc)[0])]
    objs, o = {}, u(0x18)[0]
    for _ in range(u(0x14)[0]):
        sz = struct.unpack_from("<H", d, o + 2)[0]
        if sz == 0: break
        idx = u(o + 4)[0]
        objs[u(o + 0x20)[0]] = (sped[idx] if 0 <= idx < len(sped) else "?", u(o + 0x54)[0])
        o += sz
    dialogs = [cstr(u(0x5c)[0] + i * 0x10, 0x10) for i in range(u(0x58)[0])]
    scenes = [cstr(u(0x68)[0] + i * 0x10, 0x10) for i in range(u(0x64)[0])]
    # waypoint routes: 0x14-byte headers, +0x08 = tag. Events say tag<<16 | point index.
    route_tag = {u(u(0x90)[0] + i * 0x14 + 8)[0]: i for i in range(u(0x8c)[0])}

    def wp(v):
        t, pt = v >> 16, v & 0xffff
        return "route tag %d%s point %d" % (t, " (#%d)" % route_tag[t] if t in route_tag else " (missing)", pt)

    from spd import shiptext_groups
    fg_index, fg_base = shiptext_groups(path)
    fg_names = {v - fg_base: k for k, v in fg_index.items() if v >= fg_base}

    def grp(g): return "group %d(%s)" % (g, fg_names[g]) if g in fg_names else "group %d" % g

    def obj(i): return "obj %d(%s)" % (i, objs[i][0]) if i in objs else "obj %d" % i
    def var(s): return V.get((s >> 16, s & 0xffff), "var %d:%d" % (s >> 16, s & 0xffff))

    n, off = u(0x20, 2)
    print("== %s: %d triggers, dialogs=%s scenes=%s" % (os.path.basename(path), n, dialogs, scenes))
    for t in range(n):
        nc, na, _, co, ao = u(off + t * 0x14, 5)
        print("T%d:" % t)
        join = None
        for i in range(nc):
            cat, sub, code, val, a, b, j, fl = u(co + i * 0x28, 8)
            cname, codes = COND.get(cat, ("CAT%d" % cat, {}))
            desc = codes.get(code, "code %d" % code)
            if cat == 3:   subj = var(sub)
            elif cat == 1: subj = obj(sub)
            elif cat == 5: subj = grp(sub)
            elif cat == 7: subj = "dialog[%d]" % sub
            else:          subj = "" if sub == 0 else "sub %d" % sub
            extra = []
            if fl & 2: extra.append("a=%d b=%s" % (a, obj(b) if a == 1 else b))
            elif cat == 0 and code == 1: extra.append("b=%s" % obj(b))
            if fl & 1: extra.append("momentary")
            if fl & 4: extra.append("repeat")
            if (cat, code) in ((1, 5), (5, 2)):
                desc = "%s %s" % (desc, wp(val))
            pre = "  IF      " if join is None else "  %-8s" % JOIN.get(join, "J%d" % join)
            print("%s%s %s %s  v=%d %s" % (pre, cname, subj, desc, val,
                                            ("[" + ", ".join(extra) + "]") if extra else ""))
            join = j
        for i in range(na):
            cat, arg, code, arg2 = u(ao + i * 0x10, 4)
            if cat < 0:
                print("  DO      (none)"); continue
            aname, codes = ACT.get(cat, ("CAT%d" % cat, {}))
            desc = codes.get(code, "type %d" % code)
            if cat in (1,):    subj = var(arg)
            elif cat == 4:     subj = var(arg)
            elif cat == 5:     subj = obj(arg)
            elif cat == 6:     subj = grp(arg)
            elif cat == 2:     subj = dialogs[arg] if 0 <= arg < len(dialogs) else "dialog[%d]" % arg
            elif cat == 3:     subj = scenes[arg2] if 0 <= arg2 < len(scenes) else "scene[%d]" % arg2
            elif cat in (8, 9, 10, 11, 12, 13):
                print("  DO      %s type %d about %s" % (aname, code, obj(arg2))); continue
            elif cat == 0:     subj = obj(arg)
            elif cat == 7:     subj = "region %d sector %d" % (arg >> 16, arg & 0xffff)
            else:              subj = "arg 0x%x" % arg
            if (cat, code) in ((5, 13), (6, 8)):   # CHANGE_WP: arg2 = route tag<<16 | point
                print("  DO      %s %s: %s %s" % (aname, subj, desc, wp(arg2))); continue
            print("  DO      %s %s: %s  arg2=%d" % (aname, subj, desc, arg2))


if __name__ == "__main__":
    main(sys.argv[1:])
