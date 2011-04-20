# shell.py


import difflib
import minirst
import sys
import util


class Shell(object):
    def __init__(self, stdin=None, stdout=None, stderr=None):
        self.stdin = stdin or sys.stdin
        self.stdout = stdout or sys.stdout
        self.stderr = stderr or sys.stderr

        self.debug_on = False
        self.verbose = False
        self.quiet = False

        self.indent = 0
        self.width = None

    def termwidth(self):
        return self.width or util.termwidth()

    @property
    def indent(self):
        return len(self._indent)

    @indent.setter
    def indent(self, value):
        self._indent = " " * max(value, 0)

    def write(self, msg, **opts):
        """
        Write a message to the registered standard output stream.

        All none error messages should eventually be written to the output
        stream via the ``write`` method. Subclasses of ``Shell`` may override
        this method to handle how messages are written to the output stream. See
        the ``ColorShell`` class for an example of providing colored output.

        All keyword arguments are accepted but not used. This permits subclasses
        to add their own keywords that. Again, see the ``ColorShell`` class as
        an example.
        """
        self.stdout.write("%s%s" % (self._indent, msg))

    def write_err(self, msg, **opts):
        """
        Write a message to the registers standard error stream.

        This method operates like the ``write`` method except that messages are
        written to the standard error stream. All error messages eventually will
        be passed to ``write_err``.
        """
        self.stderr.write("%s%s" % (self._indent, msg))

    def prompt(self, prompt=None, default=None):
        return self._input(prompt) or default

    def choose(self, prompt, choices, default=None, case_sensitive=False):
        choices_ = case_sensitive and choices or [c.lower() for c in choices]
        while True:
            choice = self.prompt(prompt, default=default)
            if choice is not None:
                if not case_sensitive:
                    choice = choice.lower()
                if choice in choices_:
                    return choices[choices_.index(choice)]
                self.write("Invalid choice\n")

    def diff(self, left, right, lname=None, rname=None):
        for l in self._diff(left, right, lname, rname):
            self.write(l)

    def debug(self, msg, **opts):
        """ Write a message to stdout if ``debug_on`` is ``True``. """
        if self.debug_on:
            self.write(msg, **opts)

    def note(self, msg, **opts):
        """ Write a message to stdout if ``verbose`` is ``True``. """
        if self.verbose:
            self.write(msg, **opts)

    def status(self, msg, **opts):
        """ Write a message to stdout if ``quiet`` is ``False``. """
        if not self.quiet:
            self.write(msg, **opts)

    def warn(self, msg, **opts):
        """ Write a message to stderr, always. """
        self.write_err(msg, **opts)

    def rst(self, txt, width=None, indent="", keep=None):
        """
        Format restructured text source to be displayed on the console.

        By default the text will be re-formatted to the terminal width unless a
        different width is specified by the ``width`` keyword option.

        All restructured text containers are pruned from the output unless
        listed in the ``keep`` containers array. If ``verbose`` is set to
        ``True``, then the container *verbose* is added automatically to the
        array of containers to keep.
        """
        keep = keep or []
        if self.verbose and "verbose" not in keep:
            keep.append("verbose")
        return minirst.format_rst(txt, width=(width or self.termwidth() - 2),
                                  indent=indent, keep=keep)

    def _input(self, prompt=None):
        if prompt is not None:
            self.write(prompt)
        return self.stdin.readline().strip()

    def _diff(self, left, right, lname=None, rname=None):
        left = left.splitlines(True)
        lname = lname or "left"

        right = right.splitlines(True)
        rname = rname or "right"

        for l in difflib.unified_diff(left, right, lname, rname):
            if not l.endswith("\n"):
                l = l + "\n"
            yield l


class ColorShell(Shell):
    """
    A colored subclass of ``Shell`` that colorizes stdout, stderr, and diff
    outputs.
    """
    def write(self, msg, **opts):
        color = opts.pop("color", None)
        Shell.write(self, util.colorize(msg, color=color), **opts)

    def write_err(self, msg, **opts):
        color = opts.pop("color", None)
        Shell.write_err(self, util.colorize(msg, color=color), **opts)

    def diff(self, left, right, lname=None, rname=None):
        for l in self._diff(left, right, lname, rname):
            if l.startswith("-"):
                color = "*red*"
            elif l.startswith("+"):
                color = "*green*"
            elif l.startswith("@"):
                color = "*white*"
            else:
                color = None
            self.write(l, color=color)

