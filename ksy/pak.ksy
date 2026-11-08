meta:
  id: pak
  title: Tachyon PAK ("3DPK") 3D model
  file-extension: pak
  endian: le
  encoding: ISO-8859-1
doc: |
  A .PAK is one 3D model for Tachyon: The Fringe: a table of detail levels
  (LODs), each a hierarchy of rigid parts pointing at triangle meshes
  ("3DO1"), plus optional collision mesh, optional named procedural-animation
  states, and an embedded texture section at the end of the file.

  Conventions:
  - All offsets in the 3DPK header, LOD table, part records and state block are
    absolute file offsets. Offsets inside a 3DO1 mesh and inside the collision
    block are relative to the start of that mesh / block (they're parsed here as
    substreams so the relative offsets work directly).
  - "fx" values are signed 16.16 fixed point (divide by 65536).
  - Mesh coordinates are in *file* axes; the engine converts (x, y, z) to
    (x, z, -y) at load. The collision block is already in engine axes.
  - Texture pixels are PCX-style RLE (byte >= 0xC0: repeat next byte
    (byte - 0xC0) times, 0 counting as 1; otherwise a literal). Kaitai has no
    built-in for this, so `texture.data` is left compressed; see
    `rle_decode` in ../src/pak.py.

  Reverse-engineered from space.exe (Pak_Load 0x4b14b0 and helpers). See
  decomp/notes/pak.md for field semantics. Parses all 1,160 shipped .PAK files.
seq:
  - id: header
    type: header
  - id: lods
    type: lod_entry
    repeat: expr
    repeat-expr: header.n_lods
instances:
  collision:
    if: (header.flags & 1) != 0
    pos: header.collision_ofs
    size: header.main_end - header.collision_ofs
    type: collision_block
  states:
    if: (header.flags & 4) != 0
    pos: header.states_ofs
    type: state_block
  textures:
    if: header.main_end < _io.size
    pos: header.main_end
    type: texture_section
types:
  header:
    seq:
      - id: magic
        contents: "3DPK"
      - id: version
        type: u4
        doc: 0x2003 (most files) or 0x2002. The loader accepts 0x2001..0x10000.
      - id: name
        type: str
        size: 32
        terminator: 0
        doc: Model name, space padded.
      - id: flags
        type: u4
        doc: |
          1 = has collision block, 2 = palette remappable,
          4 = has state (procedural animation) block.
      - id: n_lods
        type: u4
      - id: radius
        type: s4
        doc: fx exporter radius; overwritten at load by a computed bounding radius.
      - id: reserved_34
        type: u4
      - id: header_size
        type: u4
        doc: Always 0x60; the LOD table follows immediately.
      - id: main_end
        type: u4
        doc: End of the main block = start of the texture section.
      - id: file_size
        type: u4
      - id: reserved_44
        type: u4
      - id: collision_ofs
        type: u4
      - id: states_ofs
        type: u4
      - id: reserved_50
        size: 16
  lod_entry:
    seq:
      - id: switch_distance
        type: s4
        doc: fx view distance up to which this LOD is used.
      - id: group_ofs
        type: u4
    instances:
      group:
        io: _root._io
        pos: group_ofs
        type: lod_group
  lod_group:
    seq:
      - id: scale
        type: s4
        doc: fx, always 1.0.
      - id: n_parts
        type: u4
      - id: parts_ofs
        type: u4
        doc: Relative to the group start; always 0xc (parts follow directly).
      - id: parts
        type: part
        repeat: expr
        repeat-expr: n_parts
  part:
    doc: |
      Rigid sub-object. Part 0 is the root. Parts carry no translation: all
      geometry is in model space and rotations pivot on the model origin,
      composed up the parent chain.
    seq:
      - id: mesh_ofs
        type: u4
      - id: rotation
        type: s4
        repeat: expr
        repeat-expr: 3
        doc: Engine angles; 0 on disk, written at runtime by .anm and state animation.
      - id: flags
        type: u4
        doc: |
          0x02 tint with `tint` at load; 0x40 billboard (no rotation);
          0x80 hidden (runtime); 0x100 don't propagate rotation to children;
          0x200 ignore object rotation (uncertain).
      - id: record_size
        type: u4
        doc: Always 0x2c.
      - id: reserved_18
        size: 3
      - id: n_children
        type: u1
      - id: tint
        size: 3
      - id: reserved_1f
        type: u1
      - id: parent_ofs
        type: u4
        doc: Byte offset of the parent within the part array; 0 = root/none.
      - id: first_child_ofs
        type: u4
        doc: Byte offset of the first child; children are contiguous.
      - id: runtime_28
        type: u4
    instances:
      parent_index:
        value: parent_ofs / 0x2c
      first_child_index:
        value: first_child_ofs / 0x2c
      mesh:
        io: _root._io
        pos: mesh_ofs
        size: _root.header.main_end - mesh_ofs
        type: mesh
  mesh:
    seq:
      - id: magic
        contents: "3DO1"
      - id: version
        type: u4
        doc: 0x101.
      - id: name
        type: str
        size: 8
        terminator: 0
        pad-right: 0x20
      - id: radius
        type: s4
        doc: fx bounding radius.
      - id: bbox
        type: s4
        repeat: expr
        repeat-expr: 6
        doc: fx min/max pairs in file-axis order Z, Y, X.
      - id: n_materials
        type: u4
      - id: n_verts
        type: u4
      - id: n_faces
        type: u4
      - id: n_normals
        type: u4
      - id: n_points54
        type: u4
      - id: n_attach
        type: u4
      - id: materials_ofs
        type: u4
      - id: verts_ofs
        type: u4
      - id: faces_ofs
        type: u4
      - id: normals_ofs
        type: u4
      - id: points54_ofs
        type: u4
      - id: attach_ofs
        type: u4
    instances:
      materials:
        pos: materials_ofs
        type: material
        repeat: expr
        repeat-expr: n_materials
      verts:
        pos: verts_ofs
        type: vertex
        repeat: expr
        repeat-expr: n_verts
      faces:
        pos: faces_ofs
        type: face
        repeat: expr
        repeat-expr: n_faces
      normals:
        pos: normals_ofs
        type: normal
        repeat: expr
        repeat-expr: n_normals
      points54:
        pos: points54_ofs
        type: vec3_fx
        repeat: expr
        repeat-expr: n_points54
        doc: |
          Child pivots: child k of a part using this mesh sits at part position +
          part matrix * points54[k]. After load, part 0's children are all the other parts.
      attach_points:
        pos: attach_ofs
        type: attach_point
        repeat: expr
        repeat-expr: n_attach
        doc: Indexed by .des `connect` (ENGINE_POINT etc.) and OCF ATTACH.
  material:
    seq:
      - id: texture_name
        type: str
        size: 12
        terminator: 0
        doc: Texture (.PCX) name; may contain junk after the NUL.
      - id: unknown_0c
        type: u1
      - id: unknown_0d
        type: u1
      - id: unknown_0e
        type: u1
      - id: alpha
        type: u1
        doc: Translucency level.
      - id: rgb
        size: 3
        doc: Flat colour when untextured (flags & 8 clear).
      - id: unknown_13
        type: u1
      - id: unknown_14
        type: u1
      - id: unknown_15
        type: u1
      - id: flags
        type: u2
        doc: |
          0x8 textured, 0x40 double-sided, 0x2000 animated texture; other bits
          select blend/transparency modes (see pak.md).
      - id: unknown_18
        type: u1
      - id: anim_frames
        type: u1
        doc: Animated texture frame count; frames are the following materials.
      - id: anim_slot
        type: u1
        doc: Animation counter slot (0x7d-0x7f special).
      - id: unknown_1b
        type: u1
  vertex:
    seq:
      - id: pos
        type: vec3_fx
      - id: runtime_0c
        size: 20
      - id: u
        type: s4
        doc: fx; 1.0 = full texture width, tiles outside [0,1].
      - id: v
        type: s4
      - id: runtime_28
        type: u4
  face:
    doc: Triangle. References are byte offsets into the mesh's arrays.
    seq:
      - id: reserved
        type: u4
      - id: material_ofs
        type: u4
      - id: vert_ofs
        type: u4
        repeat: expr
        repeat-expr: 3
      - id: normal_ofs
        type: u4
        repeat: expr
        repeat-expr: 3
    instances:
      material_index:
        value: material_ofs / 0x1c
      v0:
        value: vert_ofs[0] / 0x2c
      v1:
        value: vert_ofs[1] / 0x2c
      v2:
        value: vert_ofs[2] / 0x2c
      n0:
        value: normal_ofs[0] / 0x10
      n1:
        value: normal_ofs[1] / 0x10
      n2:
        value: normal_ofs[2] / 0x10
  normal:
    seq:
      - id: dir
        type: vec3_fx
        doc: Length ~0.5 (0x8000 = unit).
      - id: reserved
        type: u4
  attach_point:
    seq:
      - id: pos
        type: vec3_fx
      - id: runtime_0c
        type: u4
        doc: Overwritten at load with a pointer to the transformed position.
  vec3_fx:
    seq:
      - id: x
        type: s4
      - id: y
        type: s4
      - id: z
        type: s4
  vec3_f:
    seq:
      - id: x
        type: f4
      - id: y
        type: f4
      - id: z
        type: f4
  collision_block:
    doc: Simplified collision mesh, floats, already in engine axes.
    seq:
      - id: reserved
        type: u4
      - id: header_size
        type: u4
        doc: 0x38.
      - id: n_verts
        type: u4
      - id: n_tris
        type: u4
      - id: n_normals
        type: u4
      - id: verts_ofs
        type: u4
      - id: tris_ofs
        type: u4
      - id: normals_ofs
        type: u4
    instances:
      verts:
        pos: verts_ofs
        type: vec3_f
        repeat: expr
        repeat-expr: n_verts
      tris:
        pos: tris_ofs
        type: collision_tri
        repeat: expr
        repeat-expr: n_tris
      normals:
        pos: normals_ofs
        type: vec3_f
        repeat: expr
        repeat-expr: n_normals
  collision_tri:
    doc: One-sided triangle; references are byte offsets (stride 12).
    seq:
      - id: vert_ofs
        type: u4
        repeat: expr
        repeat-expr: 3
      - id: normal_ofs
        type: u4
      - id: precomputed
        type: f4
        repeat: expr
        repeat-expr: 13
      - id: runtime_hit
        type: u4
    instances:
      v0:
        value: vert_ofs[0] / 12
      v1:
        value: vert_ofs[1] / 12
      v2:
        value: vert_ofs[2] / 12
      normal_index:
        value: normal_ofs / 12
  state_block:
    seq:
      - id: header_size
        type: u4
        doc: 0x18.
      - id: animator_size
        type: u4
        doc: 0x2c.
      - id: state_size
        type: u4
        doc: 0x74.
      - id: counter_size
        type: u4
        doc: 8.
      - id: n_states
        type: u4
      - id: states_ofs
        type: u4
    instances:
      states:
        pos: states_ofs
        type: state
        repeat: expr
        repeat-expr: n_states
  state:
    doc: Named procedural animation ("ON", "OFF").
    seq:
      - id: n_animators
        type: u4
      - id: animators_ofs
        type: u4
      - id: n_counters
        type: u4
      - id: counters_ofs
        type: u4
      - id: name
        type: str
        size: 16
        terminator: 0
      - id: effect_flags
        type: u4
        doc: |
          1 glow curve, 2 uniform scale, 4/8/0x10 scale x/y/z,
          0x20/0x40/0x80 paired axes.
      - id: glow
        type: curve
      - id: scale_x
        type: curve
      - id: scale_y
        type: curve
      - id: scale_z
        type: curve
    instances:
      animators:
        io: _root._io
        pos: animators_ofs
        type: part_animator
        repeat: expr
        repeat-expr: n_animators
      counters:
        io: _root._io
        pos: counters_ofs
        type: anim_counter
        repeat: expr
        repeat-expr: n_counters
  curve:
    doc: |
      mode 1: a + c * random; mode 2: a / b alternating by frame;
      mode 4: a + c * sin(d * t); otherwise constant b.
    seq:
      - id: mode
        type: u4
      - id: a
        type: s4
      - id: b
        type: s4
      - id: c
        type: s4
      - id: d
        type: s4
  part_animator:
    doc: rotation = base_rot + rot_rate * t; mode 1/2/4 = random / periodic / copied blink.
    seq:
      - id: part_index
        type: u4
      - id: mode
        type: u4
      - id: rot_rate
        type: s4
        repeat: expr
        repeat-expr: 3
      - id: threshold
        type: u4
      - id: other
        type: u4
      - id: period
        type: u4
      - id: base_rot
        type: s4
        repeat: expr
        repeat-expr: 3
  anim_counter:
    doc: counter[slot] = rate * t; drives animated materials.
    seq:
      - id: slot
        type: u4
      - id: rate
        type: s4
  texture_section:
    seq:
      - id: n_textures
        type: u4
      - id: textures
        type: texture
        repeat: expr
        repeat-expr: n_textures
  texture:
    doc: |
      Essentially a PCX file with its 128-byte header replaced by this record.
    seq:
      - id: name
        type: str
        size: 12
        terminator: 0
      - id: n_palette
        type: u2
        doc: 256, or 0 for no palette.
      - id: flags
        type: u2
        doc: Same bits as material flags.
      - id: width
        type: u4
      - id: height
        type: u4
      - id: data_size
        type: u4
      - id: data
        size: data_size
        doc: |
          PCX RLE, decodes to width*height palette indices. Some files keep the
          PCX palette marker byte 0x0C as the last byte.
      - id: palette
        size: n_palette * 3
        doc: 8-bit RGB triples.
