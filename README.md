# Goals

Provide a repository of documentation and source code for file formats used in the all time classic best game of all time "_Tachyon: The Fringe_". 

This is done mostly because I want to steal some of the resources for my own personal projects, but also because reverse engineering the file formats is a fun bit of archaeology. 

# File Types

* PFF
* RTXT
* SPX
* SBF
* PCX
* OCF
* PAK
* etc


# PFF

PFF's are basically a giant tar file of all game assets- it's a format used across several NovaLogic games, probably to help save on disk space by decreasing file system overhead (a 1k texture doesn't need a 4k block and a filesystem entry). The version used in Tachyon doesn't support compressed content. The file has a header section, which includes the list of file entries, and then a nice soup of files catted together.

There are several versions of the format (`PFF0`, `PFF2`, `PFF3`, `PFF4`), told apart by the version digit and the size of a file entry: 32, 36, or 40 bytes. Tachyon's is `PFF3` with 36-byte entries:

```
header (20 B)  u32 header_size (20), "PFF3", u32 file_count, u32 entry_size (36), u32 table_offset
...            file bodies
table          file_count x { u32 deleted, u32 offset, u32 size, u32 unix_time, char name[16], u32 crc }
footer (12 B)  u32 packer IP (big-endian), u32 0, "KING"
```

`crc` is CRC-32/BZIP2 of the file body (MSB-first poly `0x04C11DB7`, init and xorout `0xFFFFFFFF`). That's the non-reflected variant, so zlib's `crc32` won't match; `src/pff.py` has `crc32_bzip2`.

# RTXT

The compiled string tables: `JOBS.BIN`, `ITEMS.BIN`, `HELPTEXT.BIN`, `NEWS.BIN`, the region tables, 23 files in all. Each is an INI-style `[group] key=value` table: a record table of value strings, then a group table of group names and key names. Not encrypted.

```sh
python3 src/rtxt.py dump  JOBS.BIN               # [JOBS] / JOB_BORA00=Gate Blueprints / ...
python3 src/rtxt.py check path/to/extracted/     # parse every RTXT
```

Spec: `ksy/rtxt.ksy`. How the engine loads and queries them: `decomp/notes/formats.md` "RTXT". [NovaHQ's NovaResearch](https://github.com/Novahq-net/NovaResearch) documents the same format for the other NovaLogic games.

# SPX

Sector files: objects and their per-kind placement records, waypoint routes, per-group AI target rules, the mission trigger script, sub-sector stages. Magic `SPD\x01` at offset 4. `src/spd.py FILE.SPX` prints the layout and `src/spxtrig.py FILE.SPX` prints the trigger script with names resolved (group ids are named when `SHIPTEXT.BIN` sits next to the SPX); the spec is `ksy/spd.ksy`, and engine notes are in `decomp/notes/formats.md` and `missions.md`. Several header fields (labels, aliases, group names, the per-group lists, region ids, the radiation/fog flags) were first mapped by NovaResearch's SPX doc and then checked against the data and `space.exe`.




# PAK

PAKs are the 3D models: one ship, station chunk, asteroid, missile, cockpit overlay, whatever, per file. Magic is `3DPK`. Everything's little-endian, and almost every number that's a coordinate or a distance is 16.16 fixed point (divide by 65536). The textures are baked into the end of the file, so a PAK is self-contained.

Rough layout:

```
0x00   header (0x60 bytes): magic, version (0x2003 or 0x2002), name, flags,
       LOD count, offsets to the texture section / collision block / state block
0x60   LOD table: n_lods x {fx switch distance, u32 offset of LOD group}
...    LOD groups -> part records -> 3DO1 meshes
...    collision block   (if flags & 1)
...    state block       (if flags & 4)
main_end  texture section, runs to EOF
```

Flags: 1 = has a collision mesh, 2 = palette remappable, 4 = has animation states.

**LODs and parts.** Each LOD is a group of rigid parts (0x2c-byte records). Part 0 is the root; each part has a parent and a contiguous run of children, referenced as *byte offsets* into the part array (divide by 0x2c). Parts have no translation at all, all the geometry is already in model space, and rotation pivots on the model origin. That's how the Enforcer swings its arms: rotate the arm part, the mesh rotates around the ship's centre. Part flags cover billboarding, tinting and "don't pass my rotation on to my kids".

**Meshes (`3DO1`).** Each part points at a mesh: a small header (name, radius, bounding box) then six arrays: materials (0x1c), vertices (0x2c), triangles (0x20), normals (0x10), an unknown point list (0xc), and attach points (0x10, where engines/guns/etc. hang off; indexed by `.des` and `.ocf` files). Offsets inside a mesh are relative to the mesh start, and triangles reference vertices/normals/materials by byte offset again (`/0x2c`, `/0x10`, `/0x1c`). Mesh coordinates are in file axes; the game converts (x, y, z) to (x, z, -y) when it loads them. UVs live on the vertex, so a vertex shared by two faces shares its UV.

**Materials** name a texture (12 chars, sometimes with junk after the NUL), carry a flat RGB for untextured faces, an alpha level, and flags: 0x8 textured, 0x40 double-sided, 0x2000 animated (the next N materials are the frames, driven by a counter from the state block). The other flag bits pick blend modes and are still fuzzy.

**Textures.** At `main_end`: a count, then records that are basically a PCX file with its header swapped out: `name[12], u16 palette entries (256 or 0), u16 flags, u32 width, u32 height, u32 data size`, then PCX RLE data (a byte >= 0xC0 means "repeat the next byte (b - 0xC0) times", anything else is a literal), then `3 x n` bytes of RGB palette. A few dozen files leave the PCX `0x0C` palette marker as the last byte of the data.

**Collision mesh.** A separate, simpler, float32 triangle soup (vertices, triangles with 13 precomputed floats each, normals), already in engine axes, one per PAK in rest pose. It's what the player's ship and projectiles actually hit; 740 of the 1,160 shipped PAKs have one, and anything without one is intangible.

**States.** Named procedural animations (usually `ON` / `OFF`): per-part spin rates and blink patterns, glow and scale curves, and counters that step animated textures.

`src/pak.py` parses, validates and exports them (and parses every shipped PAK cleanly):

```sh
python3 src/pak.py info   CUTLESS.PAK          # LODs, parts, meshes, textures, states
python3 src/pak.py check  path/to/extracted/   # parse every *.PAK, report problems
python3 src/pak.py export CUTLESS.PAK out/ 0   # OBJ + MTL + PNG textures for LOD 0
```

There's also a Kaitai spec at `ksy/pak.ksy`. The full field-by-field write-up, with the engine functions that read each field, is in `decomp/notes/pak.md`.
