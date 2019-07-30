from construct import *
import datetime
import json

"""
Disclaimer: this is all cribbed from the Devils Claw CBIN->TXT source code. Without that (for at least the decryption bit) I'd still be trying to make sense of it all.

CBIN is the general 'store all' for everything config-y. Probably half the files in tachyon are CBIN's.

The format is lightly encrypted by rotating a 32 bit key by 7 and xoring data. (gives a nice clear 32 bit pattern to the noise).

After that data is grouped semi-heirarchically as:

Groups ->
  Items ->
    Parameters

Where each can have several of it's descendent. 

Groups+Items have an id + child_count; the id is a (1 based) index into text array
Parameters have an i32 parameter, and an i32 type (1=int, 2=float, 4=string, other=crash)

Data layout is:
HEADER
NUM_GROUPS
GROUPS*num_groups
ITEMS*(sum(g.num_item+1?)) # each group ends with a null item?
PARAMS*(sum(i.num_params))
[null delimited strings]

"""

CBIN_HEADER = Struct(
  "magic" / Const(b"CBIN"),
  "text_offset" / Int32ul,
  "text_length" / Int32ul,
  "text_count" / Int32ul,
  "key" / Int32ul
)

CBIN_CONTENT = Struct(
  "header" / CBIN_HEADER,
  "group_count" / Int32ul,
  "groups" / Array(this.group_count, Struct(
    "group_id" / Int32ul,
    "entry_count" / Int32ul
  )),
  "entries" / Array(lambda t: sum(map(lambda g: g.entry_count+1 if g.entry_count else 0, t.groups)), Struct(
    "entry_id" / Int32ul,
    "param_count" / Int32ul
  )),
  "params" / Array(lambda t: sum(map(lambda i: i.param_count, t.entries)), Struct(
    "param" / Int32ul,
    "param_type" / Int32ul
  )),
  "strings" / Array(this.header.text_count, CString('ascii'))
)

def is_cbin(b):
  return b[0:4] == b'CBIN'


def decrypt_cbin(b):
  header = CBIN_HEADER.parse(b)
  data = b[CBIN_HEADER.sizeof():]
  ddata = b''
  key = header.key

  def rotate_left(k, l):
    nk = k<<l
    nk = (nk % 2**32) | (nk>>32)
    return nk

  for d in data:
    key = rotate_left(key, 7)
    ddata += bytes([(d^key) % 2**8])
  
  return b[:CBIN_HEADER.sizeof()]+ddata


def parse_cbin(b):
  b = decrypt_cbin(b)
  content = CBIN_CONTENT.parse(b)
  
  res = [str(content.group_count)]
  item_idx = 0
  param_idx = 0
  for group in content.groups:
    res.append(str(group.group_id))
    res.append(str(group.entry_count))
    if not group.entry_count:
      continue
    for i in range(group.entry_count+1):
      item = content.entries[item_idx]
      item_idx += 1
      res.append('  '+str(item.entry_id))
      res.append('  '+str(item.param_count))
      for j in range(item.param_count):
        param = content.params[param_idx]
        param_idx += 1
        res.append('    '+str(param.param))
        res.append('    '+str(param.param_type))

  return '\n'.join(res).encode('utf8')
  return json.dumps(res, indent=2).encode('utf8')
  #print(header)
  #return str(res).encode('utf8')

"""
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
  "unknown1" / Int32ul # other extractors say this is a modified date; but if it is it's a nonstandard format; haven't looked into it
)

PFF_FILE_ENTRY_v3 = PFF_FILE_ENTRY_v2 + Struct(
  "compression_level" / Int32ul # again, what other extractors say
)
"""

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



