#!/usr/bin/env python3

from construct import *
import datetime

PFF3_HEADER = Struct(
  "header_size" / Int32ul,
  "magic" / Const(b"PFF"),
  "version" / PaddedString(1, "ascii"),
  "file_count" / Int32ul,
  "file_segment_size" / Int32ul,
  "file_list_offset" / Int32ul
)

PFF_FOOTER = Struct(
  "system_ip" / Int32ub,
  "reserved1" / Int32ul,
  "king_tag" / Const(b"KING")
)

PFF_FILE_ENTRY_v1 = Struct(
  "deleted" / Int32ul,
  "file_location" / Int32ul,
  "file_size" / Int32ul,
  "packed_date" / Int32ul,
  "file_name" / PaddedString(0x10, "ascii"),
)

PFF_FILE_ENTRY_v2 = PFF_FILE_ENTRY_v1 + Struct(
  "crc" / Int32ul  # CRC-32/BZIP2 of the file body (MSB-first poly 0x04C11DB7, init/xorout ~0); see crc32_bzip2
)

PFF_FILE_ENTRY_v3 = PFF_FILE_ENTRY_v2 + Struct(
  "compression_level" / Int32ul # again, what other extractors say
)

def _crc_table():
  t = []
  for i in range(256):
    c = i << 24
    for _ in range(8):
      c = ((c << 1) ^ 0x04C11DB7) & 0xffffffff if c & 0x80000000 else (c << 1) & 0xffffffff
    t.append(c)
  return t

_CRC_TABLE = _crc_table()

def crc32_bzip2(data: bytes) -> int:
  """The checksum stored in 36/40-byte PFF entries (CRC-32/BZIP2: MSB-first, init/xorout ~0)."""
  c = 0xffffffff
  for b in data:
    c = ((c << 8) & 0xffffffff) ^ _CRC_TABLE[((c >> 24) ^ b) & 0xff]
  return c ^ 0xffffffff

def entry_for(entry_size: int):
  for entry_type in [PFF_FILE_ENTRY_v1, PFF_FILE_ENTRY_v2, PFF_FILE_ENTRY_v3]:
    if entry_size == entry_type.sizeof():
      return entry_type
  raise Exception("Unrecognized File Segment Size %s" % (entry_size))

class PFFFileEntry(object):
  def __init__(self, parent, entry):
    self.parent = parent
    self.entry = entry
    for key in entry.keys():
      if not key.startswith('_'):
        if key in ['packed_date']:
          setattr(self, key, datetime.datetime.utcfromtimestamp(entry[key]))
        else:
          setattr(self, key, entry[key])
   
  def __str__(self):
    return '{name: <16} {packed: <20} {size: <10}'.format(**{
      'name': self.file_name,
      'packed': str(self.packed_date),
      'size': self.file_size
    }) 

  def __repr__(self):
    return repr(self.entry)

  def load_bytes(self):
    return self.parent.load_bytes(self)

class PFFArchive(object):
  def __init__(self, stream):
    self.stream = stream
    self.file_entries = []
    
    self.stream.seek(0)
    self.header = PFF3_HEADER.parse(self.stream.read(PFF3_HEADER.sizeof()))

    self.stream.seek(-PFF_FOOTER.sizeof(), 2)
    self.footer = PFF_FOOTER.parse(self.stream.read(PFF_FOOTER.sizeof()))

    entry_size = self.header.file_segment_size
    entry_type = entry_for(entry_size)
    self.stream.seek(self.header.file_list_offset)
    for i in range(self.header.file_count):
      entry = entry_type.parse(self.stream.read(entry_size))
      self.file_entries.append(PFFFileEntry(self, entry))

  def load_bytes(self, entry):
    self.stream.seek(entry.file_location)
    return self.stream.read(entry.file_size)


if __name__ == '__main__':
  import ipaddress
  import cbin
  import json
  r = open('/home/matt/Tach-play/Tachyon.pff', 'rb')
  pff = PFFArchive(r)
  for entry in pff.file_entries:
    print(entry)
    with open(f'/home/matt/Tach-play/pff/{entry.file_name}', 'wb') as w:
        b = entry.load_bytes()
        w.write(b)
        if b.startswith(b'CBIN'):
            try:
                res = cbin.decrypt_cbin(b)
                with open(f'/home/matt/Tach-play/pff/{entry.file_name}.raw', 'wb') as w2:
                    w2.write(res)
                res = cbin.parse_cbin(b)
                with open(f'/home/matt/Tach-play/pff/{entry.file_name}.inf', 'wb') as w2:
                    w2.write(res)
            except:
                print(f"Error CBINing {entry.file_name}")
  print(pff.header)
  print(pff.footer)
  print(ipaddress.IPv4Address(pff.footer.system_ip))

