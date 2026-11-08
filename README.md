# Goals

Provide a repository of documentation and source code for file formats used in the all time classic best game of all time "_Tachyon: The Fringe_". 

This is done mostly because I want to steal some of the resources for my own personal projects, but also because reverse engineering the file formats is a fun bit of archaeology. 

# File Types

* PFF
* SBF
* PCX
* OCF
* PAK
* etc


# PFF

PFF's are basically a giant tar file of all game assets- it's a format used across several NovaLogic games, probably to help save on disk space by decreasing file system overhead (a 1k texture doesn't need a 4k block and a filesystem entry). The version used in Tachyon doesn't support compressed content. The file has a header section, which includes the list of file entries, and then a nice soup of files catted together.

There are apparently at least 3 different versions of the file format, version 3, version 3, and version 4. Mostly differentiated by the size of the file entry- 32 bytes, 36 bytes, or 40 bytes. 

## Header




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
