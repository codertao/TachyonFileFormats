meta:
  id: cbin
  title: Tachyon CBIN config container
  file-extension: cbin
  endian: le
  encoding: ISO-8859-1
doc: |
  CBIN is Tachyon: The Fringe's general-purpose, config-ish store (probably
  half the files in the game are CBINs). Data is grouped hierarchically:

      group -> item -> parameter

  Each group/item carries a 1-based id that indexes the trailing string table;
  each parameter is an i32 value plus a type tag (1=int, 2=float, 4=string).

  ====================================================================
  TWO LIMITATIONS make this spec HEADER-ONLY as a standalone KSY:

  1. ENCRYPTION. Everything after the 20-byte header is encrypted with a
     rotating-XOR keystream that Kaitai's `process:` cannot express (its only
     stream ciphers are a fixed repeating xor and rol/ror). The keystream,
     starting from `header.key`:

         k = header.key
         for each ciphertext byte c:
             k = rotl32(k, 7)          # 32-bit rotate-left by 7
             plaintext = c ^ (k & 0xFF)

     So `body` below is the raw ciphertext. Decrypt it externally, then parse
     the result with the `decrypted` type documented below.

  2. DATA-DEPENDENT ARRAY SIZES. Even on the decrypted stream, the `items` and
     `params` section lengths are *sums* over earlier arrays
     (sum of group.item_count+1, and sum of item.param_count). Kaitai's
     expression language has no fold/sum, so those two arrays cannot be sized
     declaratively. They are described in `decrypted` as doc only. The groups,
     the group_count, and the string table (addressed directly via text_offset)
     ARE expressible.
  ====================================================================
seq:
  - id: header
    type: header
  - id: body
    size-eos: true
    doc: Encrypted payload (ciphertext). See limitation #1 above.
types:
  header:
    doc: 20-byte plaintext header (not encrypted).
    seq:
      - id: magic
        contents: "CBIN"
      - id: text_offset
        type: u4
        doc: Absolute offset of the string table (in the decrypted stream).
      - id: text_length
        type: u4
        doc: Byte length of the string table.
      - id: text_count
        type: u4
        doc: Number of NUL-terminated strings.
      - id: key
        type: u4
        doc: Initial 32-bit key for the rotating-XOR keystream.
  # -------------------------------------------------------------------
  # `decrypted` is NOT reachable from the file root. Apply it to the
  # externally-decrypted stream (header bytes left intact + decrypted body).
  # -------------------------------------------------------------------
  decrypted:
    doc: |
      Logical layout of a CBIN once the body has been decrypted.

      On-disk order after the header is:
        group_count : u4
        groups      : group_count x group
        items       : (sum over groups of item_count+1 where item_count>0) x item
        params      : (sum over items  of param_count)                     x param
        strings     : text_count x strz   (also directly at header.text_offset)

      `items` and `params` are shown as 0-length here because their real counts
      are sums KSY cannot compute (limitation #2). Walk them manually: for each
      group with item_count>0 read item_count+1 items (the last is a NUL
      terminator, item_id==0); for each item read param_count params.
    seq:
      - id: header
        type: header
      - id: group_count
        type: u4
      - id: groups
        type: group
        repeat: expr
        repeat-expr: group_count
      - id: items
        type: item
        repeat: expr
        repeat-expr: 0
        doc: See doc above — true count is a sum KSY cannot express.
      - id: params
        type: param
        repeat: expr
        repeat-expr: 0
        doc: See doc above — true count is a sum KSY cannot express.
    instances:
      strings:
        pos: header.text_offset
        type: strz
        repeat: expr
        repeat-expr: header.text_count
        doc: String table, addressed directly via the header.
  group:
    seq:
      - id: group_id
        type: u4
        doc: 1-based index into the string table (0 = none).
      - id: item_count
        type: u4
  item:
    seq:
      - id: item_id
        type: u4
        doc: 1-based index into the string table; 0 marks a group terminator.
      - id: param_count
        type: u4
  param:
    seq:
      - id: raw_value
        size: 4
        doc: |
          4-byte value, reinterpreted per `param_type`: as s4 (int=1), as f4
          (float=2), or, for strings (type=4), as a 1-based index into the
          string table. (The three readings share the same bytes; KSY can't
          expose all of them from one field, so the raw bytes are kept here.)
      - id: param_type
        type: u4
        enum: param_type
enums:
  param_type:
    1: int
    2: float
    4: string
