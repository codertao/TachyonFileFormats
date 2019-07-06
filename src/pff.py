from construct import *

PFF3_HEADER = Struct(
  "header_size" / Int32ul,
  "magic" / Const(b"PFF"),
  "version" / PaddedString(1, "ascii"),
  "file_count" / Int32ul,
  "file_segment_size" / Int32ul,
  "file_list_offset" / Int32ul
)

PFF_FOOTER = Struct(
  "system_ip" / Int32ul,
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
  "modified_date" / Int32ul
)

PFF_FILE_ENTRY_v3 = PFF_FILE_ENTRY_v2 + Struct(
  "compression_level" / Int32ul
)

def entry_for(entry_size: int):
  for entry_type in [PFF_FILE_ENTRY_v1, PFF_FILE_ENTRY_v2, PFF_FILE_ENTRY_v3]:
    if entry_size == entry_type.sizeof():
      return entry_type
  raise Exception("Unrecognized File Segment Size %s" % (entry_size))

class PFFArchive(object):
  def __init__(self, stream):
    self.stream = stream
    self.load()

  def load(self):
    self.stream.seek(0)
    self.header = PFF3_HEADER.parse(self.stream.read(PFF3_HEADER.sizeof()))

    self.stream.seek(-PFF_FOOTER.sizeof(), 2)
    self.footer = PFF_FOOTER.parse(self.stream.read(PFF_FOOTER.sizeof()))

    entry_type = entry_for(self.header["file_segment_size"])
    self.stream.seek(self.header["file_list_offset"])
    self.file_entries = []
    for i in range(self.header["file_count"]):
      self.file_entries.append(entry_type.parse(self.stream.read(entry_type.sizeof())))


if __name__ == '__main__':
  r = open('/media/tachyon/Tachyon.pff', 'rb')
  pff = PFFArchive(r)
  for entry in pff.file_entries:
    print(entry)
  print(pff.header)
  print(pff.footer)


