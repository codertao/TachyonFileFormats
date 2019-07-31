#!/usr/bin/env python3

import datetime
import subprocess
import urwid

import cbin
import pff

debug_box = urwid.Text('')

def to_hexdump(data):
  res = subprocess.run(['/usr/bin/xxd', '-c', '32'], input=data, stdout=subprocess.PIPE)

  return res.stdout

class PureTextTreeWidget(urwid.TreeWidget):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self._w = urwid.AttrWrap(self._w, None)
    self._w.attr = 'normal'
    self._w.focus_attr = 'focusd'
    self._selectable = True

  def get_display_text(self):
    return self.get_node().get_value()

  def render(self, size, focus=False):
    if hasattr(self.get_node(), 'has_focus'):
      self.get_node().has_focus(focus)
    return super().render(size, focus)

  def selectable(self):
    return hasattr(self.get_node(), 'has_focus')
    #return True

class FileNode(urwid.TreeNode):
  def __init__(self, parent, entry):
    self.is_focused = False
    self.entry = entry

    txt = '{} ({})'.format(entry.file_name, entry.file_size)
    urwid.TreeNode.__init__(self, txt, parent, depth=2, key=entry.file_name)

  def get_widget(self):
    return PureTextTreeWidget(self)

  def has_focus(self, val):
    global debug_box
    if val and not self.is_focused:
      content = self.entry.load_bytes()
      if cbin.is_cbin(content):
        content = cbin.parse_cbin(content)
      else:
        content = to_hexdump(content[:4096])
      debug_box.set_text(content)
    self.is_focused = val


class ExtensionNode(urwid.ParentNode):
  def __init__(self, parent, extension, entries):
    self.extension = extension
    self.keys = [e.file_name for e in entries]
    self.lookup = {e.file_name: e for e in entries}

    txt = '{} ({})'.format(extension, len(entries))
    urwid.ParentNode.__init__(self, txt, parent, depth=1, key=extension)

  def load_child_keys(self):
    return self.keys

  def get_widget(self):
    return PureTextTreeWidget(self)

  def load_child_node(self, key):
    entry = self.lookup[key]
    return FileNode(self, entry)


class ArchiveNode(urwid.ParentNode):
  def __init__(self, archive):
    self.archive = archive
  
    entry_lu = {}

    for entry in self.archive.file_entries:
      name = entry.file_name
      ext = name.rsplit('.', 1)[-1].upper()
      if ext not in entry_lu:
        entry_lu[ext] = []
      entry_lu[ext].append(entry)

    self.entry_list = list(sorted(entry_lu.items(), key=lambda t: t[0]))
    self.entry_lu = entry_lu

    text = 'PFF Archive ({})'.format(len(self.archive.file_entries))
    urwid.ParentNode.__init__(self, text, depth=0, key='')

  def load_child_keys(self):
    return [e[0] for e in self.entry_list]

  def load_child_node(self, key):
    return ExtensionNode(self, key, self.entry_lu[key])

  def get_widget(self):
    return PureTextTreeWidget(self)

def handle_input(key):
  if key in ('q', 'Q'):
    raise urwid.ExitMainLoop()

if __name__ == '__main__':
  with open('/media/tachyon/Tachyon.pff', 'rb') as r:
    a = pff.PFFArchive(r)

    tree_box = urwid.TreeListBox(urwid.TreeWalker(ArchiveNode(a)))
    tree_box.offset_rows = 10

    #debug_box = urwid.Text("Test Debug Etc\n"*30)

    cols_box = urwid.Columns([(30, tree_box), ('weight', 120, urwid.Filler(debug_box, 'top'))], 3)

    header = urwid.Text("The Header")
    footer = urwid.Text("The Footer")

    view = urwid.Frame(cols_box, header=header, footer=footer)

    palette = [
      ('focusd', 'black', 'dark green')
    ]

    loop = urwid.MainLoop(view, palette, handle_mouse=False, unhandled_input=handle_input)
    loop.run()





