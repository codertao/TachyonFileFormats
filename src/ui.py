#!/usr/bin/env python3

import datetime
import urwid

import pff

class PureTextTreeWidget(urwid.TreeWidget):
  def get_display_text(self):
    return self.get_node().get_value()


class FileNode(urwid.TreeNode):
  def __init__(self, parent, entry):
    self.entry = entry

    txt = '{} ({})'.format(entry.file_name, entry.file_size)
    urwid.TreeNode.__init__(self, txt, parent, depth=2, key=entry.file_name)

  def get_widget(self):
    return PureTextTreeWidget(self)

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
  header = urwid.Text("The Header")
  footer = urwid.Text("The Footer")

  view = urwid.Frame(tree_box, header=header, footer=footer)

  loop = urwid.MainLoop(view, unhandled_input=handle_input)
  loop.run()
  print("stuff")





