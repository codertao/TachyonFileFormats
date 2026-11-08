#!/usr/bin/env python3
"""
PAK ("3DPK") model parser / validator / exporter for Tachyon: The Fringe.

Spec: decomp/notes/pak.md (reverse-engineered from space.exe Pak_Load 0x4b14b0 and
its helpers, validated against all 1,160 .PAK files in pff/).

Usage:
  pak.py info   FILE.PAK              summary: LODs, parts, meshes, textures, states
  pak.py check  [DIR]                 parse every *.PAK in DIR (default pff/), report problems
  pak.py export FILE.PAK OUTDIR [LOD] Wavefront OBJ + MTL + PNG textures (default LOD 0)

All integers are little-endian. Coordinates/UVs are 16.16 fixed point unless noted.
"""
import glob
import os
import struct
import sys
import zlib

DEFAULT_DIR = "/home/matt/Tach-play/pff"

MESH_STRIDES = (0x1C, 0x2C, 0x20, 0x10, 0x0C, 0x10)  # materials, verts, faces, normals, pts54, attach


def u32(d, o):
    return struct.unpack_from("<I", d, o)[0]


def i32(d, o):
    return struct.unpack_from("<i", d, o)[0]


def fx(v):
    return v / 65536.0


def cname(b):
    return b.split(b"\0")[0].decode("latin1").rstrip(" ")


def rle_decode(src, n):
    """PCX-style RLE: byte >= 0xC0 -> repeat next byte (byte - 0xC0) times (0 counts as 1)."""
    out = bytearray()
    i = 0
    while len(out) < n:
        b = src[i]
        if b < 0xC0:
            out.append(b)
            i += 1
        else:
            out += bytes([src[i + 1]]) * max(b - 0xC0, 1)
            i += 2
    return bytes(out[:n]), i


def parse_mesh(d, m):
    if d[m:m + 4] != b"3DO1":
        raise ValueError("mesh @%#x: bad magic %r" % (m, d[m:m + 4]))
    mesh = {
        "offset": m,
        "version": u32(d, m + 4),
        "name": cname(d[m + 8:m + 0x10]),
        "radius": fx(i32(d, m + 0x10)),
        # min/max pairs, stored in file-axis order Z, Y, X
        "bbox_zyx": [fx(i32(d, m + 0x14 + 4 * k)) for k in range(6)],
    }
    cnt = struct.unpack_from("<6I", d, m + 0x2C)
    ofs = struct.unpack_from("<6I", d, m + 0x44)
    if ofs[0] != 0x5C or any(ofs[k] + cnt[k] * MESH_STRIDES[k] != ofs[k + 1] for k in range(5)):
        raise ValueError("mesh @%#x: sections don't tile: cnt=%s ofs=%s" % (m, cnt, ofs))
    mats = []
    for k in range(cnt[0]):
        o = m + ofs[0] + k * 0x1C
        mats.append({
            "texture": cname(d[o:o + 12]),
            "b0c": d[o + 0xC], "b0d": d[o + 0xD], "b0e": d[o + 0xE],
            "alpha": d[o + 0xF],
            "rgb": tuple(d[o + 0x10:o + 0x13]),
            "b14": d[o + 0x14], "b15": d[o + 0x15],
            "flags": struct.unpack_from("<H", d, o + 0x16)[0],
            "frames": d[o + 0x19],
            "anim_slot": d[o + 0x1A],
        })
    verts = []
    for k in range(cnt[1]):
        v = struct.unpack_from("<11i", d, m + ofs[1] + k * 0x2C)
        verts.append((fx(v[0]), fx(v[1]), fx(v[2]), fx(v[8]), fx(v[9])))
    faces = []
    for k in range(cnt[2]):
        f = struct.unpack_from("<8I", d, m + ofs[2] + k * 0x20)
        for x in f[2:5]:
            if x % 0x2C or x // 0x2C >= cnt[1]:
                raise ValueError("mesh @%#x face %d: bad vertex offset %#x" % (m, k, x))
        if f[1] % 0x1C or f[1] // 0x1C >= max(cnt[0], 1):
            raise ValueError("mesh @%#x face %d: bad material offset %#x" % (m, k, f[1]))
        faces.append({
            "material": f[1] // 0x1C,
            "v": [x // 0x2C for x in f[2:5]],
            "n": [x // 0x10 for x in f[5:8]],
        })
    normals = [tuple(fx(x) * 2 for x in struct.unpack_from("<3i", d, m + ofs[3] + k * 0x10))
               for k in range(cnt[3])]
    pts54 = [tuple(fx(x) for x in struct.unpack_from("<3i", d, m + ofs[4] + k * 0xC))
             for k in range(cnt[4])]
    attach = [tuple(fx(x) for x in struct.unpack_from("<4i", d, m + ofs[5] + k * 0x10))
              for k in range(cnt[5])]
    mesh.update(materials=mats, verts=verts, faces=faces, normals=normals,
                points54=pts54, attach=attach, end=m + ofs[5] + cnt[5] * 0x10)
    return mesh


def parse(path):
    d = open(path, "rb").read()
    if d[:4] != b"3DPK":
        raise ValueError("not a 3DPK file")
    hdr = {
        "version": u32(d, 4),
        "name": d[8:0x28].split(b"\0")[0].decode("latin1").rstrip(" "),
        "flags": u32(d, 0x28),
        "n_lods": u32(d, 0x2C),
        "file_radius": fx(i32(d, 0x30)),
        "header_size": u32(d, 0x38),
        "main_end": u32(d, 0x3C),
        "file_size": u32(d, 0x40),
        "collision_ofs": u32(d, 0x48),
        "states_ofs": u32(d, 0x4C),
    }
    if hdr["header_size"] != 0x60:
        raise ValueError("unexpected header size %#x" % hdr["header_size"])
    if hdr["file_size"] != len(d):
        raise ValueError("header file size %d != actual %d" % (hdr["file_size"], len(d)))
    lods, meshes = [], {}
    for l in range(hdr["n_lods"]):
        dist, go = struct.unpack_from("<iI", d, 0x60 + l * 8)
        scale, nparts, pofs = struct.unpack_from("<iII", d, go)
        parts = []
        for p in range(nparts):
            e = struct.unpack_from("<11I", d, go + pofs + p * 0x2C)
            parts.append({
                "mesh": e[0], "rot": e[1:4], "flags": e[4],
                "n_children": (e[6] >> 24) & 0xFF,
                "parent": e[8] // 0x2C if e[8] else None,    # 0 = none / root
                "first_child": e[9] // 0x2C if e[9] else None,
            })
            if e[0] not in meshes:
                meshes[e[0]] = parse_mesh(d, e[0])
        lods.append({"distance": fx(dist), "scale": fx(scale), "parts": parts})
    coll = None
    if hdr["flags"] & 1:
        c = hdr["collision_ofs"]
        hs, nv, nt, nn, vo, to, no = struct.unpack_from("<7I", d, c + 4)
        verts = [struct.unpack_from("<3f", d, c + vo + k * 12) for k in range(nv)]
        tris = []
        for k in range(nt):
            t = struct.unpack_from("<4I", d, c + to + k * 0x48)
            tris.append(([x // 12 for x in t[:3]], t[3] // 12))
        normals = [struct.unpack_from("<3f", d, c + no + k * 12) for k in range(nn)]
        coll = {"verts": verts, "tris": tris, "normals": normals}
    states = []
    if hdr["flags"] & 4:
        s = hdr["states_ofs"]
        n, eo = u32(d, s + 0x10), u32(d, s + 0x14)
        for k in range(n):
            e = eo + k * 0x74
            npa, pa, nctr, ctr = struct.unpack_from("<4I", d, e)
            states.append({
                "name": cname(d[e + 0x10:e + 0x20]),
                "flags": u32(d, e + 0x20),
                "part_anims": [struct.unpack_from("<11i", d, pa + j * 0x2C) for j in range(npa)],
                "counters": [struct.unpack_from("<Ii", d, ctr + j * 8) for j in range(nctr)],
            })
    textures = []
    o = hdr["main_end"]
    if o < len(d):
        n = u32(d, o)
        o += 4
        for _ in range(n):
            npal, flags, w, h, size = struct.unpack_from("<HHIII", d, o + 12)
            px, used = rle_decode(d[o + 0x1C:o + 0x1C + size], w * h)
            # 84 files keep the PCX palette marker byte 0x0C after the RLE body
            if used != size and not (used == size - 1 and d[o + 0x1C + used] == 0x0C):
                raise ValueError("texture %s: RLE used %d of %d bytes" % (cname(d[o:o + 12]), used, size))
            pal = d[o + 0x1C + size:o + 0x1C + size + 3 * npal] if npal else None
            textures.append({"name": cname(d[o:o + 12]), "flags": flags, "w": w, "h": h,
                             "pixels": px, "palette": pal})
            o += 0x1C + size + 3 * npal
        if o != len(d):
            raise ValueError("texture section ends at %#x, file is %#x" % (o, len(d)))
    return {"header": hdr, "lods": lods, "meshes": meshes, "collision": coll,
            "states": states, "textures": textures}


def write_png(path, w, h, rgb):
    raw = b"".join(b"\0" + rgb[y * w * 3:(y + 1) * w * 3] for y in range(h))

    def chunk(t, b):
        return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b))
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def export(path, outdir, lod=0):
    pak = parse(path)
    os.makedirs(outdir, exist_ok=True)
    base = os.path.splitext(os.path.basename(path))[0].lower()
    texnames = {}
    for t in pak["textures"]:
        if not t["palette"]:
            continue
        pal = t["palette"]
        rgb = bytes(c for i in t["pixels"] for c in pal[i * 3:i * 3 + 3])
        fn = os.path.splitext(t["name"])[0].lower() + ".png"
        write_png(os.path.join(outdir, fn), t["w"], t["h"], rgb)
        texnames[t["name"].upper()] = fn
    mtl, obj = [], ["mtllib %s.mtl" % base]
    vbase, seen = 1, {}
    for pi, part in enumerate(pak["lods"][lod]["parts"]):
        mesh = pak["meshes"][part["mesh"]]
        obj.append("o part%02d_%s" % (pi, mesh["name"]))
        for x, y, z, u, v in mesh["verts"]:
            obj.append("v %.5f %.5f %.5f" % (x, z, -y))   # file axes -> engine (x, z, -y)
        for x, y, z, u, v in mesh["verts"]:
            obj.append("vt %.5f %.5f" % (u, 1.0 - v))
        cur = None
        for f in mesh["faces"]:
            m = mesh["materials"][f["material"]] if mesh["materials"] else None
            key = (m["texture"].upper() if m and m["flags"] & 8 else "rgb%02x%02x%02x" % (m["rgb"] if m else (128, 128, 128)))
            if key not in seen:
                seen[key] = "m%d" % len(seen)
                mtl.append("newmtl %s" % seen[key])
                if key in texnames:
                    mtl.append("map_Kd %s" % texnames[key])
                elif key.startswith("rgb"):
                    r, g, b = (int(key[3 + 2 * k:5 + 2 * k], 16) / 255 for k in range(3))
                    mtl.append("Kd %.3f %.3f %.3f" % (r, g, b))
            if seen[key] != cur:
                cur = seen[key]
                obj.append("usemtl %s" % cur)
            # engine winding after the axis swap: emit as-is
            obj.append("f " + " ".join("%d/%d" % (vbase + i, vbase + i) for i in f["v"]))
        vbase += len(mesh["verts"])
    open(os.path.join(outdir, base + ".obj"), "w").write("\n".join(obj) + "\n")
    open(os.path.join(outdir, base + ".mtl"), "w").write("\n".join(mtl) + "\n")
    print("wrote %s/%s.obj (%d parts, %d textures)" % (outdir, base, len(pak["lods"][lod]["parts"]), len(texnames)))


def info(path):
    p = parse(path)
    h = p["header"]
    print("%s: '%s' v%#x flags=%#x lods=%d textures=%d collision=%s states=%s" % (
        os.path.basename(path), h["name"], h["version"], h["flags"], h["n_lods"], len(p["textures"]),
        "%d tris" % len(p["collision"]["tris"]) if p["collision"] else "-",
        ",".join(s["name"] for s in p["states"]) or "-"))
    for li, lod in enumerate(p["lods"]):
        print("  LOD %d: switch at %.0f, %d parts" % (li, lod["distance"], len(lod["parts"])))
        for pi, part in enumerate(lod["parts"]):
            m = p["meshes"][part["mesh"]]
            print("    part %2d flags=%#05x parent=%s children=%d mesh %-8s r=%.2f %5d verts %5d faces %3d mats %2d attach" % (
                pi, part["flags"], part["parent"], part["n_children"], m["name"], m["radius"],
                len(m["verts"]), len(m["faces"]), len(m["materials"]), len(m["attach"])))
    for t in p["textures"]:
        print("  tex %-12s %3dx%-3d flags=%#06x" % (t["name"], t["w"], t["h"], t["flags"]))


def check(directory):
    files = sorted(set(glob.glob(os.path.join(directory, "*.PAK")) + glob.glob(os.path.join(directory, "*.pak"))))
    ok, bad = 0, []
    for f in files:
        try:
            parse(f)
            ok += 1
        except Exception as e:  # noqa: BLE001 - report every failure
            bad.append((os.path.basename(f), str(e)))
    print("%d/%d parsed cleanly" % (ok, len(files)))
    for name, err in bad:
        print("  %s: %s" % (name, err))


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] not in ("info", "check", "export"):
        print(__doc__)
        sys.exit(1)
    if a[0] == "info":
        info(a[1])
    elif a[0] == "check":
        check(a[1] if len(a) > 1 else DEFAULT_DIR)
    else:
        export(a[1], a[2], int(a[3]) if len(a) > 3 else 0)
