#!/usr/bin/env python3
"""Decompile TTFMUSIC.BIN (the in-flight music script) into readable Python-like pseudocode.

Format and VM: decomp/notes/music.md.
- The script is a set of states; each is a theme.
- When the current segment ends, the game runs the script until it plays a segment (`play`)
  or yields; the next run resumes there.
- `goto` switches state, and the next run starts at that state's top.

usage: musscr.py TTFMUSIC.BIN [--sbf Ttfmusic.sbf] [--vars vars.cfg.inf] [--raw]

`--sbf` names the segments (otherwise they print as numbers). `--vars` (a cbindump / .inf text
of vars.cfg) names the job ids and mission statuses. `--raw` adds the bytecode offset to each
line.
"""
import re, struct, sys

# ---- vocab -------------------------------------------------------------------------------
OPS = {0: 'nop', 1: 'push8', 2: 'push32', 3: 'pushg', 4: 'pushl', 5: 'pushga', 6: 'pushla', 7: 'pushc',
       8: 'popg', 9: 'popl', 10: 'cpyg', 11: 'cpyl', 12: 'pushvm', 13: 'nop', 14: 'nop', 15: 'clr',
       16: '+', 17: '-', 18: '*', 19: '/', 20: '%', 21: '&', 22: '|', 23: '&', 24: '|', 25: '^',
       26: 'neg', 27: '~', 28: '<<', 29: '>>', 30: 'not', 31: 'nop',
       32: '==', 33: '!=', 34: '>=', 35: '<=', 36: '>', 37: '<', 38: 'nop', 39: 'nop',
       40: 'incg', 41: 'decg', 42: 'incl', 43: 'decl', 48: 'jmp', 49: 'jz', 50: 'jnz', 51: 'sys',
       52: 'call', 53: 'switch', 56: 'args', 57: 'ret', 58: 'yield', 59: 'goto', 60: 'nop',
       61: 'play16', 62: 'play8', 63: 'restart', 64: 'native'}
ARGLEN = {1: 1, 2: 4, 3: 1, 4: 1, 5: 2, 6: 2, 7: 1, 8: 1, 9: 1, 10: 2, 11: 2, 40: 1, 41: 1, 42: 1, 43: 1,
          48: 4, 49: 4, 50: 4, 51: 1, 52: 4, 56: 1, 59: 1, 61: 2, 62: 1, 64: 1}
BINOPS = {16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 28, 29, 32, 33, 34, 35, 36, 37}
# 21/22 compute "logical" flags they never use: they're bitwise like 23/24, but the compiler
# emits them for && / || on -1/0 booleans, so print them as and / or.
LOGIC = {21: 'and', 22: 'or'}
NATIVE_ARGS = {'GEcho': 1, 'GGRnd': 2, 'GSV': 1, 'GSDV': 1, 'FSet': 2, 'FClear': 2, 'FIsSet': 2,
               'FIsClear': 2, 'TStart': 1, 'TStop': 1}

# Game variable slots (byte offset = slot * 4), set by Music_UpdateFlightVars 0x415060.
GAME_VARS = {0: 'hostiles', 4: 'dialog_cue', 8: 'job_status', 12: 'shields', 16: 'slot4',
             20: 'dialog_timer', 24: 'sector', 28: 'job', 60: 'story_cue'}
# The script's own variables (byte offset from 0x40), named from how the states use them.
SCRIPT_VARS = {0: 'theme', 1: 'theme_sector', 2: 'stinger_played', 3: 'bar', 4: 'peak_hostiles',
               5: 'after_combat', 6: 'v6'}
REGIONS = ['EARTH', 'NEUTRAL', 'GALSPAN', 'BORA', 'FRONTIER', 'MYSTERY', 'DISPUTED', 'GDISPUTE',
           'BDISPUTE', 'NOVAWORLD']
SHIELDS = {0: 'OK', 1: 'LOW', 2: 'CRITICAL'}


def u32(b, o): return struct.unpack_from('<I', b, o)[0]
def i32(b, o): return struct.unpack_from('<i', b, o)[0]


class Script:
    def __init__(self, b):
        assert b[:4] == b'SCR0', 'not an SCR0 script'
        so = u32(b, u32(b, 0xc))
        h = lambda k: u32(b, so + k)
        self.b, self.so = b, so
        self.name = b[so + 8:so + 0x18].split(b'\0')[0].decode()
        self.code = so + h(0x20)
        self.end = so + h(0x30)
        self.consts = so + h(0x30)
        self.globals_size, self.locals_size, self.start = h(0x18), h(0x1c), h(0x2c)
        tab = so + h(0x24)
        self.states = [u32(b, tab + 4 * i) for i in range(h(0x28))]
        self.states = [so + s - self.code if s else None for s in self.states]
        self.imports, p = [], u32(b, 0x14)
        for _ in range(u32(b, 0x10)):
            n = b[p]
            self.imports.append(b[p + 1:p + n].split(b'\0')[0].decode())
            p += n

    def decode(self, off):
        """Instruction at code offset `off` -> (op, arg, size, extra)."""
        b, a = self.b, self.code + off
        op = b[a]
        if op == 53:
            cnt, _, es, tl = b[a + 1:a + 5]
            cases = []
            for k in range(cnt):
                e = a + 5 + k * es
                cases.append(self.decode(e - self.code)[:2] if b[e] else None)
            return op, cases, tl, None
        n = ARGLEN.get(op, 0)
        raw = b[a + 1:a + 1 + n]
        if n == 1:
            arg = raw[0]
        elif n == 2:
            arg = struct.unpack('<H', raw)[0] if op == 61 else raw[0]
        elif n == 4:
            arg = i32(b, a + 1)
        else:
            arg = None
        return op, arg, 1 + n, None


# ---- expressions -------------------------------------------------------------------------
class Dec:
    def __init__(self, s, segs, jobs, statuses, raw):
        self.s, self.segs, self.jobs, self.statuses, self.raw = s, segs, jobs, statuses, raw
        self.out = []

    def var(self, base, off):
        if base == 'g':
            if off in GAME_VARS:
                return GAME_VARS[off]
            if off < 0x40:
                return 'game_var%d' % (off // 4)
            return SCRIPT_VARS.get((off - 0x40) // 4, 'v%d' % ((off - 0x40) // 4))
        return 'local%d' % (off // 4)

    def seg(self, n):
        return repr(self.segs[n]) if n < len(self.segs) else str(n)

    def const(self, other, v):
        """Render a constant compared with / assigned to `other`."""
        if other == 'sector' and v >= 0 and v // 1000 < len(REGIONS):
            return 'SECTOR(%s, %d)' % (REGIONS[v // 1000], v % 1000)
        if other in ('job', 'dialog_cue') and v in self.jobs:
            return self.jobs[v]
        if other == 'story_cue' and v >= 10000 and v % 10000 in self.jobs:
            return 'CUE(%d, %s)' % (v // 10000, self.jobs[v % 10000])
        if other == 'job_status' and v in self.statuses:
            return self.statuses[v]
        if other == 'shields' and v in SHIELDS:
            return SHIELDS[v]
        return str(v)

    def binop(self, op, x, y):
        sym = LOGIC.get(op, OPS[op])
        if op in (32, 33, 34, 35, 36, 37):
            if isinstance(y, int):
                y = self.const(x, y)
            elif isinstance(x, int):
                x = self.const(y, x)
        # job + 20000 etc. as computed constants
        if isinstance(x, int) and isinstance(y, int) and op in (16, 17):
            return x + y if op == 16 else x - y
        return '(%s %s %s)' % (self.ex(x), sym, self.ex(y))

    def ex(self, e):
        if isinstance(e, int):
            return str(e)
        s = str(e)
        if s.startswith('(') and s.endswith(')') and s.count('(') == 1:
            return s
        return s

    # ---- statements ----------------------------------------------------------------------
    def emit(self, depth, text, off=None):
        pre = ('/*%04x*/ ' % off) if (self.raw and off is not None) else ''
        self.out.append('    ' * depth + pre + text)

    def block(self, lo, hi, depth, stack=None):
        """Decompile code offsets [lo, hi) as structured statements."""
        s = self.s
        st = list(stack or [])
        pc = lo
        while pc < hi:
            op, arg, size, _ = s.decode(pc)
            nxt = pc + size
            name = OPS.get(op, '?%d' % op)
            if pc in self.labels and pc != lo:
                self.emit(depth - 1 if depth else 0, 'label_%04x:' % pc)
            if op in (0, 13, 14, 31, 38, 39, 60):
                pass
            elif op == 1:
                st.append(arg)
            elif op == 2:
                st.append(arg)
            elif op in (3, 4):
                st.append(self.var('g' if op == 3 else 'l', arg))
            elif op in (5, 6):
                st.append('&' + self.var('g' if op == 5 else 'l', arg))
            elif op == 7:
                st.append(i32(s.b, s.consts + 4 * arg))
            elif op in (8, 9):
                v = st.pop() if st else '?'
                tgt = self.var('g' if op == 8 else 'l', arg)
                if isinstance(v, int):
                    v = self.const(tgt, v)
                self.emit(depth, '%s = %s' % (tgt, self.ex(v)), pc)
            elif op in BINOPS:
                y = st.pop() if st else '?'
                x = st.pop() if st else '?'
                st.append(self.binop(op, x, y))
            elif op == 26:
                st.append('-%s' % self.ex(st.pop()))
            elif op == 27:
                st.append('~%s' % self.ex(st.pop()))
            elif op == 30:
                st.append('(not %s)' % self.ex(st.pop()))
            elif op in (40, 41, 42, 43):
                tgt = self.var('g' if op < 42 else 'l', arg)
                self.emit(depth, '%s %s= 1  # low byte' % (tgt, '+' if op % 2 == 0 else '-'), pc)
            elif op == 15:
                for e in st:
                    if isinstance(e, str) and '(' in e and e.split('(')[0].isidentifier():
                        self.emit(depth, e, pc)
                st = []
            elif op == 64:
                nm = s.imports[arg] if arg < len(s.imports) else 'native%d' % arg
                n = NATIVE_ARGS.get(nm, 0)
                args = st[len(st) - n:] if n else []
                del st[len(st) - n:]
                if nm == 'GGRnd':
                    st.append('rand(%s, %s)' % tuple(self.ex(a) for a in args))
                elif nm in ('GSV', 'GSDV'):
                    self.emit(depth, '%s(%s)' % ('set_volume' if nm == 'GSV' else 'fade_to',
                                                 self.ex(args[0])), pc)
                    st.append(None)
                elif nm in ('FSet', 'FClear'):
                    self.emit(depth, '%s |= %s' % (args[1].lstrip('&'), self.ex(args[0])) if nm == 'FSet'
                              else '%s &= ~%s' % (args[1].lstrip('&'), self.ex(args[0])), pc)
                    st.append(None)
                elif nm in ('FIsSet', 'FIsClear'):
                    f, m = args[1].lstrip('&'), self.ex(args[0])
                    st.append('(%s & %s %s)' % (f, m, '== %s' % m if nm == 'FIsSet' else '== 0'))
                else:
                    st.append('%s(%s)' % (nm, ', '.join(self.ex(a) for a in args)))
            elif op in (61, 62):
                self.emit(depth, 'play(%s)  # then wait for it to end' % self.seg(arg), pc)
            elif op == 58:
                self.emit(depth, 'wait()  # until the current segment ends', pc)
            elif op == 57:
                self.emit(depth, 'return', pc)
            elif op == 59:
                self.emit(depth, 'goto(state_%d)' % arg, pc)
            elif op == 63:
                last = self.out[-1] if self.out else ''
                if last.startswith('    ' * depth + 'goto(') or last.startswith('    ' * depth + 'return'):
                    pc = nxt
                    continue  # unreachable: every state ends with one
                self.emit(depth, 'goto(state_%d)  # restart' % s.start, pc)
            elif op == 53:
                v = st.pop() if st else '?'
                self.emit(depth, 'match %s:' % self.ex(v), pc)
                for k, c in enumerate(arg):
                    if c is None:
                        self.emit(depth + 1, 'case %d: pass' % k)
                        continue
                    cop, carg = c
                    if cop in (61, 62):
                        txt = 'play(%s)' % self.seg(carg)
                    elif cop == 59:
                        txt = 'goto(state_%d)' % carg
                    elif cop == 48:
                        txt = 'jump(label_%04x)' % carg
                    else:
                        txt = '%s %s' % (OPS.get(cop, cop), carg)
                    self.emit(depth + 1, 'case %d: %s' % (k, txt))
            elif op in (49, 50):
                cond = st.pop() if st else '?'
                tgt = arg
                if op == 49 and lo <= pc < tgt <= hi:
                    # if cond: [nxt, tgt)   optionally  else: [tgt, end) when tgt-5 is a forward jmp
                    then_end, else_end = tgt, None
                    jop, jarg, jsz, _ = s.decode(tgt - 5) if tgt - 5 >= nxt else (None, None, 0, None)
                    if jop == 48 and tgt < jarg <= hi and self.is_insn(tgt - 5):
                        then_end, else_end = tgt - 5, jarg
                    self.emit(depth, 'if %s:' % self.strip(cond), pc)
                    n0 = len(self.out)
                    self.block(nxt, then_end, depth + 1, st)
                    if len(self.out) == n0:
                        self.emit(depth + 1, 'pass')
                    if else_end is not None:
                        self.emit(depth, 'else:')
                        n0 = len(self.out)
                        self.block(tgt, else_end, depth + 1, st)
                        if len(self.out) == n0:
                            self.emit(depth + 1, 'pass')
                        nxt = else_end
                    else:
                        nxt = tgt
                else:
                    c = self.strip(cond)
                    self.emit(depth, 'if %s%s: jump(label_%04x)' % ('not ' if op == 49 else '', c, tgt), pc)
                    self.labels.add(tgt)
            elif op == 48:
                # while loop: jmp C; body: ...; C: cond; jnz body
                loop = self.while_at(pc, arg, hi)
                if loop:
                    body, cond_lo, end = loop
                    cond = self.expr_of(cond_lo, end - 5)
                    self.emit(depth, 'while %s:' % self.strip(cond), pc)
                    self.block(body, cond_lo, depth + 1)
                    nxt = end
                else:
                    self.emit(depth, 'jump(label_%04x)' % arg, pc)
                    self.labels.add(arg)
            else:
                self.emit(depth, '%s %s' % (name, arg), pc)
            pc = nxt

    def strip(self, c):
        c = self.ex(c)
        return c[1:-1] if isinstance(c, str) and c.startswith('(') and c.endswith(')') and self.balanced(c[1:-1]) else c

    @staticmethod
    def balanced(t):
        d = 0
        for ch in t:
            d += ch == '('
            d -= ch == ')'
            if d < 0:
                return False
        return d == 0

    def is_insn(self, off):
        return off in self.insns

    def while_at(self, pc, tgt, hi):
        """`jmp C` at pc whose C..jnz loops back to pc+5: returns (body, C, after)."""
        if not (pc < tgt < hi):
            return None
        q = tgt
        while q < hi:
            op, arg, size, _ = self.s.decode(q)
            if op in (48, 49, 53, 57, 58, 59, 61, 62, 63):
                if op == 50:
                    break
                return None
            if op == 50:
                break
            q += size
        else:
            return None
        op, arg, size, _ = self.s.decode(q)
        if op == 50 and arg == pc + 5:
            return pc + 5, tgt, q + size
        return None

    def expr_of(self, lo, hi):
        """Expression left on the stack by the straight-line code [lo, hi]."""
        st = self.stack_after(lo, hi)
        return st[-1] if st else '?'

    def stack_after(self, lo, hi):
        pc = lo
        st = []
        s = self.s
        while pc < hi + 1:
            op, arg, size, _ = s.decode(pc)
            if op == 50:
                break
            if op in (1, 2):
                st.append(arg)
            elif op in (3, 4):
                st.append(self.var('g' if op == 3 else 'l', arg))
            elif op == 7:
                st.append(i32(s.b, s.consts + 4 * arg))
            elif op in BINOPS:
                y, x = st.pop(), st.pop()
                st.append(self.binop(op, x, y))
            elif op == 30:
                st.append('(not %s)' % self.ex(st.pop()))
            elif op == 64:
                nm = s.imports[arg]
                n = NATIVE_ARGS.get(nm, 0)
                args = st[len(st) - n:]
                del st[len(st) - n:]
                if nm in ('FIsSet', 'FIsClear'):
                    f, m = args[1].lstrip('&'), self.ex(args[0])
                    st.append('(%s & %s %s)' % (f, m, '== %s' % m if nm == 'FIsSet' else '== 0'))
                elif nm == 'GGRnd':
                    st.append('rand(%s, %s)' % tuple(self.ex(a) for a in args))
                else:
                    st.append('%s(...)' % nm)
            elif op in (5, 6):
                st.append('&' + self.var('g' if op == 5 else 'l', arg))
            pc += size
        return st

    def run(self):
        s = self.s
        # instruction starts (for sanity checks on jump targets)
        self.insns, pc = set(), 0
        end = s.end - s.code
        while pc < end:
            self.insns.add(pc)
            pc += s.decode(pc)[2]
        self.labels = set()
        starts = sorted((o, i) for i, o in enumerate(s.states) if o is not None)
        bounds = [o for o, _ in starts] + [end]
        names = {}
        for o, i in starts:
            names.setdefault(o, []).append(i)
        seen = set()
        for k, (o, i) in enumerate(starts):
            if o in seen:
                continue
            seen.add(o)
            hi = next(b for b in bounds if b > o)
            alias = names[o]
            self.emit(0, '')
            self.emit(0, 'def state_%d():%s' % (alias[0], ('  # also state ' + ', '.join(map(str, alias[1:])))
                                                if len(alias) > 1 else ''))
            n0 = len(self.out)
            self.block(o, hi, 1)
            if len(self.out) == n0:
                self.emit(1, 'pass')
        return self.out


def load_vars(path):
    jobs, statuses, cat = {}, {}, None
    for line in open(path, errors='replace'):
        if not line.startswith(' '):
            cat = line.strip()
            continue
        m = re.match(r'\s*DEFINE:\s*(\w+),\s*(-?\d+)', line)
        if m and cat == 'jobs':
            jobs[int(m.group(2))] = m.group(1)
        elif m and cat == 'mission_status':
            statuses[int(m.group(2))] = m.group(1)
    return jobs, statuses


def load_sbf(path):
    d = open(path, 'rb').read()
    assert d[:4] == b'SBF0'
    n = u32(d, 0x14)
    return [d[0x18 + i * 0x20:0x28 + i * 0x20].split(b'\0')[0].decode() for i in range(n)]


HEADER = '''\
# {name}: the in-flight music script, decompiled from TTFMUSIC.BIN by musscr.py.
#
# How the game runs it (decomp/notes/music.md):
#   - When the current segment ends, the game runs the script from where it stopped until
#     it plays a segment (play), waits (wait), or switches state (goto). A goto starts
#     the new state from its top on the next run.
#   - Each run executes at least 32 instructions before it may stop on an empty stack;
#     that doesn't change the logic.
#   - set_volume() sets the music volume (0..255) now; fade_to() sets the volume reached by
#     the end of the next segment.
#   - rand(lo, hi) is inclusive.
#
# Game variables (Music_UpdateFlightVars 0x415060), set every frame in flight:
#   hostiles      number of hostile ships
#   job_status    the current job's status in this region (NOT_ATTEMPTED / FAILED / SUCCESS /
#                 PARTIAL_SUCCESS)
#   shields       OK / LOW / CRITICAL
#   slot4         a context value >> 16 (source not identified)
#   dialog_timer  time left on the dialog line being spoken
#   sector        region * 1000 + sector number   (SECTOR(BORA, 4) = 3004)
#   job           CURRENT_JOB (vars.cfg "jobs")
#   dialog_cue    a job id; set only by dialog lines that carry a music cue
#   story_cue     slot 15, also set by dialog lines: CUE(k, JOB) = k * 10000 + job id, a
#                 numbered story moment within that job
#   game_varN     other slots (dialog lines can set any slot)
# The script's own variables (zero at start; names are mine, from how they're used):
#   theme           which theme is running (state 3 resumes it by number)
#   theme_sector    the sector the theme started in; a sector change resets via state_20
#   stinger_played  a one-off cue has played in this sector
#   bar             position within the theme's segment list
#   peak_hostiles   most hostiles seen during this fight
#   after_combat    which theme to go to once the fight is over
# localN are scratch.
'''


def main():
    args = sys.argv[1:]
    raw = '--raw' in args
    args = [a for a in args if a != '--raw']
    sbf = vars_ = None
    if '--sbf' in args:
        i = args.index('--sbf'); sbf = args[i + 1]; del args[i:i + 2]
    if '--vars' in args:
        i = args.index('--vars'); vars_ = args[i + 1]; del args[i:i + 2]
    if not args:
        sys.exit(__doc__)
    s = Script(open(args[0], 'rb').read())
    segs = load_sbf(sbf) if sbf else []
    jobs, statuses = load_vars(vars_) if vars_ else ({}, {})
    print(HEADER.format(name=s.name))
    print('# start state: %d; %d states; %d segments named' % (s.start, len(s.states), len(segs)))
    for line in Dec(s, segs, jobs, statuses, raw).run():
        print(line)


if __name__ == '__main__':
    main()
