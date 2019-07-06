import curses
import pff

import locale
locale.setlocale(locale.LC_ALL, '')
code = locale.getpreferredencoding()


def bounded_add(at, offset, max_val):
  at = at+offset
  return 0 if at < 0 else max_val if at > max_val else at

def main(window):
  
  curses.curs_set(False)
  window.clear()
  window.addstr(0,0, 'Size  %s x %s'%(curses.LINES,curses.COLS))
  window.addstr(curses.LINES-1,0, '... Loading PFF')
  window.refresh()

  with open('/media/tachyon/Tachyon.pff', 'rb') as r:
    a = pff.PFFArchive(r)
    window.addstr(curses.LINES-1,0, ' Loaded PFF    ', curses.A_BLINK)
    window.refresh()

  entry_count = len(a.file_entries)
  pad = curses.newpad(entry_count, 100)
  for i, entry in enumerate(a.file_entries):
    pad.addstr(i, 0, entry.file_name)
    pad.addstr(i, 17, 'X' if entry.deleted!=0 else '')
    pad.addstr(i, 20, str(entry.file_size))

  result = ''
  at = 0
  while result != 'q':
    
    if result == 'KEY_UP':
      at = bounded_add(at, -1, entry_count-1)
    if result == 'KEY_DOWN':
      at = bounded_add(at, 1, entry_count-1)
    if result == 'KEY_NPAGE':
      at = bounded_add(at, curses.LINES-2, entry_count-1)
    if result == 'KEY_PPAGE':
      at = bounded_add(at, 2-curses.LINES, entry_count-1)
    window.addstr(0,0, 'Size  %s x %s, %s  %s %s'%(curses.LINES,curses.COLS,i, result, result=='KEY_LEFT'), curses.A_REVERSE)
    pad.noutrefresh(at,0,1,0,curses.LINES-2,curses.COLS-1)
    
    result=window.getkey()



if __name__ == '__main__':
  curses.wrapper(main)

