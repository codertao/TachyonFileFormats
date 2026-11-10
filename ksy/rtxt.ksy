meta:
  id: rtxt
  title: NovaLogic RTXT text table (Tachyon .bin string tables)
  file-extension: bin
  endian: le
  encoding: latin1
doc: |
  RTXT ("resource text") is NovaLogic's compiled string table. Tachyon ships 23
  of them as `.bin` files in the PFF: JOBS, ITEMS, NEWS, WINGMEN, HELPTEXT,
  SHIPTEXT, ingame, front, MPGAMES, the per-region BORA/EARTH/... tables, etc.
  Not encrypted.

  Model: a flat list of N records, each a value string. The records are split
  into consecutive groups; each group has a name and a key name per record.
  So it reads like an INI file:

      [GROUP]            <- group name
      KEY=VALUE          <- key string i, value string of record i

  Records are numbered globally (0..N-1) in file order. Group g owns records
  [sum(entry_count of groups < g), +entry_count).

  Engine (space.exe): `load_rtxt_bin 0x49df00` reads the whole file and
  `markup_rtxtbin_as_ptrs 0x49dea0` turns the offsets into pointers in place.
  It never checks the magic. Lookups are by (group, key) string compare,
  by key alone, or by record index; see decomp/notes/formats.md "RTXT".

  All 23 Tachyon files have groups. Their record `x`/`y`/`group` fields are
  0/0/group index, and the engine reads only the value pointer.
seq:
  - id: magic
    contents: "RTXT"
  - id: group_table_offset
    type: u4
    doc: Absolute offset of the group table (its leading group_count dword).
  - id: group_table_length
    type: u4
    doc: |
      Bytes in the group table AFTER the 4-byte group_count, so the file ends at
      group_table_offset + 4 + group_table_length.
  - id: record_count
    type: u4
  - id: records
    type: record
    repeat: expr
    repeat-expr: record_count
instances:
  values_base:
    value: 16 + record_count * 16
    doc: Value string offsets are relative to the end of the record table.
  group_table:
    pos: group_table_offset
    type: group_table
types:
  record:
    seq:
      - id: value_offset
        type: u4
        doc: Value string at values_base + value_offset.
      - id: x
        type: s2
        doc: Display offset X? Always 0 in Tachyon; unread by the engine.
      - id: y
        type: s2
        doc: Display offset Y? Always 0 in Tachyon; unread by the engine.
      - id: group
        type: s2
        doc: Owning group index, -1 for none. Redundant with the group partition.
      - id: reserved
        size: 6
    instances:
      value:
        io: _root._io
        pos: _root.values_base + value_offset
        type: strz
  group_table:
    seq:
      - id: group_count
        type: u4
      - id: groups
        type: group_header
        repeat: expr
        repeat-expr: group_count
      - id: group_names
        type: strz
        repeat: expr
        repeat-expr: group_count
        doc: One name per group, right after the headers.
      - id: keys
        type: strz
        repeat: expr
        repeat-expr: _root.record_count
        doc: |
          One key name per record, in record order (all groups back to back).
          Group g's keys start at groups[g].keys_offset.
  group_header:
    seq:
      - id: keys_offset
        type: u4
        doc: |
          Offset of this group's first key string, relative to the first group
          header (= group_table_offset + 4). The engine relocates it and walks
          the key list from group 0's pointer.
      - id: entry_count
        type: u4
        doc: Number of records (keys) in this group.
