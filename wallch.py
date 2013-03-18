from __future__ import print_function

import ast
import collections
import contextlib
import os
import random
import socket
import subprocess
import sys
import time
import traceback

try:
  import SocketServer as socketserver
except ImportError:
  import socketserver


BG_PROG = 'feh'
PORT_FILE = os.path.join(os.environ['HOME'], '.wallch_port')
MAX_HISTORY = 500  # Don't set this to 0.
DEFAULT_DELAY = 180


@contextlib.contextmanager
def ignore(*exc_types):
  try:
    yield
  except (exc_types):
    pass


class WallchCommandHandler(object):
  def __init__(self, dirs, set_bg, max_history=MAX_HISTORY,
               delay=DEFAULT_DELAY):
    self._pause = False
    self._running = True
    self._last_change_time = 0
    self._errors = set()
    self._files = None
    self._history = collections.deque()

    self._delay = delay
    self._dirs = dirs
    self._set_bg = set_bg
    self._max_history = max_history

    self.reload()  # Load files

  def get(self, n=-1):
    """get [<n>]: Get the file for the current image, or nth in history."""
    return self._history[int(n)]

  def next(self):
    """next: Switch to a new random wall. [DEFAULT]"""
    self._last_change_time = 0

  def quit(self):
    """quit: Shut down the server."""
    self._running = False

  def set(self, image):
    """set <n/image>: Set image file to current wall, or index in history."""
    with ignore(TypeError, ValueError):
      n = int(image)  # Else break
      image = self._history[n]
    result = self._set_bg(image)
    if not result:
      self._history.append(image)
      if len(self._history) > self._max_history:
        self._history.popleft()
      self._last_change_time = time.time()
    else:
      self._errors.add(image)
    return ('error: %s' % (result,)) if result else '' 

  def reload(self):
    """reload: Reload images from the specified directories."""
    self._files = list(find_pics(self._dirs))
    return 'Reloaded.'

  def add_dir(self, directory):
    """add_dir <directory>: Add a new directory for loading images."""
    self._dirs.add(directory)
    return 'Added.'

  def list_dirs(self):
    """list_dirs: List all directory for loading images."""
    return '\n'.join(self._dirs)

  def list_images(self):
    """list_images: List all known images."""
    return '\n'.join(self._files)

  def history(self, max=None):
    """history [<head>]: Get a history of background file locations."""
    nl = len(str(len(self._history) - 1))
    hist = [('%0' + str(nl) + 'd:%s') % (i, h)
            for i, h in enumerate(self._history)]
    return '\n'.join(hist if max is None else hist[-int(max):])

  def pause(self):
    """pause: Pause, don't switch wall until play is called."""
    if self._pause:
      return 'Already paused.'
    self._pause = time.time()
    return 'Paused.'

  def play(self):
    """play: Unpause."""
    if self._pause:
      self._last_change_time += time.time() - self._pause
      self._pause = False
      return 'Unpaused.'
    return 'Already playing.'

  def delay(self, n=None):
    """delay <seconds>: Set the delay between changing wallpapers. Must be > 0."""
    if n is None:
      return str(self._delay)
    n = int(n)
    assert n > 0, 'Delay must be positive'
    self._delay = n
    return 'Delay set to %s.' % (n,)

  def errors(self):
    """errors: A list of any files which errored."""
    return '\n'.join(self._errors)

  def help(self, func='help'):
    """help [<command>]: Print this help message, or help on a specific command."""
    if func != 'help':
      with ignore(AttributeError):
        doc = getattr(self, func).__doc__.split(':', 1)
        return 'Usage: wallch %s\n\t%s' % (doc[0], doc[1])
    message = 'Usage: wallch [<command> [args...]]'
    docs = [getattr(self, fn).__doc__
            for fn in sorted(dir(self)) if not fn.startswith('_')]
    return '\n\t'.join([message] + list(format_docs(docs)))

  def _start(self, port):
    handler = tcp_handler(self)
    server = socketserver.TCPServer(('localhost', port), handler)
    server.timeout = self._delay

    while self._running:
      dt = (time.time() - self._last_change_time) 
      ttn = self._delay - (0 if self._pause else dt)
      if ttn < 0:
        while self.set(random.choice(self._files)):
          pass  #Keep going till it works
        server.timeout = self._delay
      else:
        server.timeout = ttn
      server.handle_request()

def format_docs(docs):
  lines = [doc.split(':', 1) for doc in docs]
  max_sig_len = max(len(doc[0]) for doc in lines)
  for doc in lines:
    spaces = ' ' * ((max_sig_len - len(doc[0])) + 2)
    yield spaces.join(doc)

def tcp_handler(command_handler):
  class WallchTCPHandler(socketserver.StreamRequestHandler):
    def handle(self):
      # For now, any request just changes the image.
      line = self.rfile.readline()
      line_str = str(line.decode()).strip()  # works in python2 and python3
      request = line_str.split() or ('next',)
      try:
        response = getattr(command_handler, request[0])(*request[1:])
      except Exception as e:
        traceback.print_exc()
        response = "%s: %s\n%s" % (
            type(e).__name__, e, command_handler.help(request[0]))
      response = (response + '\n') if response else ''
      self.wfile.write(response.encode())
  return WallchTCPHandler


def find_pics(paths):
  all_files = set()
  for path in paths:
    for dir, dirs, files in os.walk(path):
      all_files |= set(os.path.join(dir, file) for file in files)
  return all_files


def kill_old_wallchs(port_filename):
  with ignore(Exception):  # Probably dead already
    with open(port_filename) as portfile:
      port = int(portfile.readline())
      sock = socket.socket()
      sock.connect(('localhost', port))
      sock.send('quit\n'.encode())  #Works in python2 and python3


on = object()
off = object()


class BGHandler(object):
  bg_prog = ''
  default_args = {}

  @classmethod
  def parse_args(cls, args):
    result = dict(cls.default_args)
    dirs = set()
    prev = None
    for arg in args:
      if arg.startswith('--'):
        if prev:
          print("Expected a value for " + prev)
          sys.exit(1)
        prev = arg
      elif prev:
        try:
          arg = ast.literal_eval(arg)
        except ValueError:
          result[prev[2:]] = arg
      else:
        dirs.add(arg)
    return dirs, result

  @classmethod
  def set_bg(cls, args):
    args = dict(args)
    bg_type = args.pop('type')
    cmd = [cls.bg_prog, '--bg-%s' % (bg_type)]
    for k, v in args.items():
      if v is on:
        cmd.append('--%s' % (k,))
      elif v is off:
        pass
      else:
        cmd += ['--%s' % (k,), str(v)]
    def raw_set_bg(filename):
      return subprocess.call(cmd + [str(filename)])
    return raw_set_bg


class FehHandler(BGHandler):
  bg_prog = 'feh'
  default_args = {
    'image-bg': 'black',
    'no-menu': on,
    'type': 'scale'
  }


HANDLERS = {
  'feh': FehHandler,
}


def main(args):
  bg_prog = BG_PROG
  if '--bg-prog' in args:
    i = args.find('--bg-prog')
    args.pop(i)
    bg_prog = args.pop(i)

  handler = HANDLERS[bg_prog]
  dirs, args = handler.parse_args(args)

  port = args.pop('port', random.randint(40000, 50000))
  delay = args.pop('delay', DEFAULT_DELAY)
  portfile = args.pop('portfile', PORT_FILE)
  max_history = args.pop('max-history', MAX_HISTORY)

  set_bg_func = handler.set_bg(args)

  kill_old_wallchs(portfile)
  with open(portfile, 'w') as pf:
    pf.write(str(port))

  WallchCommandHandler(dirs, set_bg_func, max_history, delay)._start(port)


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
