meta:
  id: pff
  title: "NovaLogic PFF archive (Tachyon: The Fringe)"
  file-extension: pff
  endian: le
  encoding: ASCII
doc: |
  PFF ("Packed File Format") is NovaLogic's asset archive: a header, a flat
  table of file entries, and the raw file bodies concatenated together. Used
  across several NovaLogic titles. The Tachyon build stores content uncompressed.

  Three on-disk variants are distinguished only by the size of a file-table
  entry (`file_segment_size`): 32, 36, or 40 bytes. The extra trailing dwords
  are a (non-standard) modified-date and a compression level; neither is used
  by the Tachyon data.

  The archive is closed by a 12-byte footer at end-of-file carrying the
  packer's IP address (big-endian) and a "KING" tag.
seq:
  - id: header
    type: header
instances:
  entries:
    pos: header.file_list_offset
    type: file_entry
    size: header.file_segment_size
    repeat: expr
    repeat-expr: header.file_count
    doc: File table. Each record is `file_segment_size` bytes.
  footer:
    pos: _io.size - 12
    type: footer
    doc: 12-byte trailer at the very end of the file.
types:
  header:
    seq:
      - id: header_size
        type: u4
        doc: Size of this header in bytes.
      - id: magic
        contents: "PFF"
      - id: version
        type: str
        size: 1
        doc: Single ASCII version digit ('3' or '4' seen in the wild).
      - id: file_count
        type: u4
      - id: file_segment_size
        type: u4
        doc: Size of one entry in the file table (32, 36, or 40).
      - id: file_list_offset
        type: u4
        doc: Absolute offset of the file table.
  file_entry:
    doc: |
      One file in the archive. Base layout is 32 bytes; the two trailing
      dwords are present only in the 36- and 40-byte variants.
    seq:
      - id: deleted
        type: u4
        doc: Non-zero marks a tombstoned (deleted) entry.
      - id: file_location
        type: u4
        doc: Absolute offset of this file's bytes within the archive.
      - id: file_size
        type: u4
      - id: packed_date
        type: u4
        doc: Pack time as a Unix timestamp (seconds, UTC).
      - id: file_name
        type: strz
        size: 0x10
      - id: modified_date
        type: u4
        if: _root.header.file_segment_size >= 36
        doc: Present when entry size >= 36. Format is non-standard / unverified.
      - id: compression_level
        type: u4
        if: _root.header.file_segment_size >= 40
        doc: Present when entry size == 40. Unused in Tachyon (no compression).
    instances:
      body:
        pos: file_location
        size: file_size
        io: _root._io
        doc: The raw file contents this entry points at.
  footer:
    seq:
      - id: system_ip
        type: u4be
        doc: Packing machine's IPv4 address, stored big-endian.
      - id: reserved1
        type: u4
      - id: king_tag
        contents: "KING"
