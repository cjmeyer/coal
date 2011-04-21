# util.py

import os
import struct
import sys
import textwrap
import traceback

import error


def mkdir(p):
    """
    Create a new directory and parents.

    This function is equivalent to the shell command ``mkdir -p``. It will also
    make sure that the created directory has a mode of 0755. If the directory
    already exists (whether as a directory or file), the directory is not
    created and no error is generated.
    """
    if not os.path.exists(p):
        os.makedirs(p, 0755)


def checksignature(fn, *args, **kw):
    """
    Throws an exception if the given function is called with invalid arguments.

    The provided function, ``fn``, is called, passing in the list of positional
    arguments and keyword arguments. If an exception is thrown as a result of
    calling the function with an incorrect set of arguments, it will be result
    in a ``SignatureError`` exception being thrown instead.

    :Parameters:
      - `fn`: The function to call
      - `*args`: All position arguments to pass to ``fn``
      - `**kw`: All keyword arguments to pass to ``fn``
    """
    try:
        fn(*args, **kw)
    except TypeError as e:
        if len(traceback.extract_tb(sys.exc_info()[2])) == 1:
            raise error.SignatureError
        raise


def wrap(s, width, indent="", subindent=""):
    """
    Wraps a string at the specified width and indentation.

    :Parameters:
      - `s`: The string to wrap
      - `width`: The width to wrap the string to, in characters
      - `indent`: The indentation string of the first line
      - `subindent`: The indentation of all lines after the first
    """
    return textwrap.fill(s, width=width, initial_indent=indent,
                         subsequent_indent=subindent)


def termwidth():
    """
    Returns the width of the current console in number of characters.

    This function currently only works for *nix systems. It operates by using
    the *nix standard ``ioctl`` calls to determine the size of the window. If
    the system is not a *nix system the default value of 80 is returned.
    """
    try:
        import fcntl, termios
        for dev in (sys.stdin, sys.stdout, sys.stderr):
            try:
                fd = dev.fileno()
            except AttributeError as e:
                continue
            data = fcntl.ioctl(fd, termios.TIOCGWINSZ, "\0" * 8)
            return struct.unpack("hhhh", data)[1]
    except ImportError:
        pass
    return 80


_esc = "\033["

_styles = {
        'reset'     : _esc + "0m",
        'bold'      : _esc + "1m",
        'italic'    : _esc + "3m",
        'underline' : _esc + "4m",
        'strike'    : _esc + "9m" }

_colors = {
        'black'     : _esc + "30m",
        'red'       : _esc + "31m",
        'green'     : _esc + "32m",
        'yellow'    : _esc + "33m",
        'blue'      : _esc + "34m",
        'magenta'   : _esc + "35m",
        'cyan'      : _esc + "36m",
        'white'     : _esc + "37m" }


def colorize(s, color):
    """
    Wrap a given message string in ANSI color codes.

    This permits messages to be printed to the console output in color and with
    other attributes as permitted by ASNI color codes. The desired is specified
    as a string and can be any of the following values:

      - "black"
      - "red"
      - "green"
      - "yellow"
      - "blue"
      - "magenta"
      - "cyan"
      - "white"

    In addition to the specified color, the text can be made to take on
    additional characteristics: bold, italic, underline, strikethrough. These
    can be specified by altering the specified color name. Below are the various
    ways to change the visual appearance of red text:

      - "*red*": Red, Bold
      - "'red'": Red, Italic
      - "_red_": Red, Underline
      - "-red-": Red, Strikethrough

    :Parameters:
      - `s`: The string to colorize.
      - `color`: The color specification string.
    """        
    result = []
    if not color:
        return s
    if color[0] == color[-1]:
        if color[0] == "*":
            result.append(_styles['bold'])
        elif color[0] == "/":
            result.append(_styles['italic'])
        elif color[0] == "_":
            result.append(_styles['underline'])
        elif color[0] == "-":
            result.append(_styles['strike'])
        if result:
            color = color[1:-1]
    result.append(_colors[color])
    result.append(s)
    result.append(_styles['reset'])
    return "".join(result)

