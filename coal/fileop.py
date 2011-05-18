# fileop.py

import error
import fnmatch
import types
import re
import StringIO
import util

from mako.template import Template
from path import path
from subprocess import Popen, STDOUT


var_re = re.compile(r"%(.+?)%")


class FileOp(object):
    def __init__(self, ui, srcroot, dstroot):
        self.ui = ui
        self.srcroot = path(srcroot)
        self.dstroot = path(dstroot)

        self.pretend = False
        self.force = False
        self.skip = False

        self.template_vars = {}

    def get(self, key, default=None):
        return self.template_vars.get(key, default)

    def __getitem__(self, key):
        """ Get the value of the template variable indicated by 'key' """
        return self.template_vars[key]

    def __setitem__(self, key, value):
        """ Set the value of the template variable 'key' to 'value' """
        self.template_vars[key] = value

    def src(self, p):
        return (self.srcroot / p).abspath()

    def dst(self, p):
        """
        Expands a destination path, expanding any variable fields as needed.

        A destination path may contain fields whose values are to be filled in
        by a value stored in the template variables dictionary. For example, the
        path 'path/to/%foo%.txt' will expand to 'path/to/bar.txt' if a template
        variable 'foo' exists and is set to 'bar'.

        Text between single '%' characters are variable fields to be expended.
        The character sequence '%%' is replaced with a single '%' character.
        Variable field names should not contain *any* '%' characters.
        """
        def fn(m):
            return self.get(m.group(1), m.group(1))
        p = "%".join((var_re.sub(fn, p_) for p_ in p.split("%%")))
        return (self.dstroot / p).abspath()

    def inside(self, p):
        """
        Set the destination root relative to the current destination root.

        A new context object is created that on entry updates the destination
        root path to that specified. On exit the original destination root path
        is restored. The new destination root may be specified as an absolute
        path or as a path relative to the current destination root.
        """
        dstroot = self.dstroot
        class context(object):
            def __enter__(self_):
                self.dstroot = self.dst(p)
            def __exit__(self_, exc_type, exc_value, exc_tb):
                self.dstroot = dstroot
        return context()

    def status(self, msg, p, color=None):
        self.ui.status("%s" % msg.lower().rjust(12), color=color)
        self.ui.status("  %s\n" % path(p).relpath())

    def cmd(self, cmd_, *args, **kw):
        """
        Executes a shell command respecting pretending.

        The command should be provided in the same way as commands are provided
        to the 'subprocess.Popen' class. If not working directory is specified,
        then the current destination root is used as the working directory.
        """
        cwd = kw.pop("cwd", self.dstroot)
        if not self.pretend:
            try:
                p = Popen([cmd_] + list(args), cwd=cwd, stderr=STDOUT)
            except OSError as e:
                if e.errno == 2:
                    raise OSError("FileOp %s not found (%s)" % (cmd_, e))
                raise
        args = [('"%s"' % a if " " in a else a) for a in args]
        self.ui.write("running: %s %s\n" % (cmd_, " ".join(args)))
        if not self.pretend:
            stderr, stdout = p.communicate()
            if p.returncode:
                self.ui.warn("command failed with exit code %s" %
                        p.returncode)

    def mkdir(self, p, mode=0755):
        """ Create a new directory and any parent directories required. """
        p = self.dst(p)
        if p.isdir():
            self.status("exist", p, color="*blue*")
        else:
            self.status("create", p, color="*green*")
            if not self.pretend:
                p.makedirs(mode)

    def rmdir(self, p):
        """ Delete and directory tree and all files contained within. """
        p = self.dst(p)
        if p.isdir():
            self.status("remove", p, color="*red*")
            if not self.pretend:
                p.removedirs()

    def _conflict(self, srcdata, dst, dstdata):
        """
        Present the user with a menu to resolve file conflicts.

        In the case that the user has not specified to force or skip file
        conflicts, and the destination file exists but does not match the source
        file contents, this method can be used to present the user with a menu
        that provides options on how to resolve the file conflict.

        The user may select to overwrite the existing file with the new file
        contents, to skip the over the file and proceed, or abor the entire
        process.

        The user may also select to render the contents of the source file to
        the console for viewing or to diff the new file contents against the old
        file contents and present a unified diff on the console. Rendering or
        showing the diff does not resolve the conflict and the user will be
        presented with the conflict menu again.

        Parameters:
          - srcdata: The contents of the source file.
          - dst: The path to the destination file; this is only used for
              displaying the destination path on the console, the file is not
              actually opened and read by this method.
          - dstdata: The contents of the destination file.
        """
        dst = dst.relpath()
        while True:
            choice = self.ui.choose(
                    "How do you wish to proceed with this file?\n"
                    "over(w)rite, (s)kip, (r)ender, (d)iff, (a)bort: ",
                    ["w", "s", "r", "d", "a"])
            if choice == "w":
                self.ui.write("Overwritten\n")
                return True
            elif choice == "s":
                self.ui.write("Skipped\n")
                return False
            elif choice == "r":
                self.ui.write("Rendering %s\n\n%s\n" % (dst, srcdata))
            elif choice == "d":
                self.ui.write("Showing differences for %s\n\n" % dst)
                self.ui.diff(dstdata, srcdata, "old", "new")
                self.ui.write("\n")
            elif choice == "a":
                raise error.AbortError("user")

    def _file(self, srcfn, dst, mode=None):
        """
        Internal method to create a file and set the file mode.

        This internal method uses the provided read-source function to generate
        the contents of the destination file, compare the contents of the source
        file with the contents of the original file if exists and take the
        needed action, including showing a conflict-resolution menu. If the file
        doesn't exist, then the file is created and the contents of the source
        file are written to it.

        The mode of the source file is also checked and replicated to the
        destination file IF AND ONLY IF the destination file is being created or
        overwritten. If the contents of the source and destination files are the
        same, they still may differ with regards to their mode without causing
        the original file to be overwritten.

        Parameters:
          - srcfn: Function to generate the source content; not called if the
              command is being revoked.
          - dst: Path to the destination file.
          - chmod: The mode to make the destination file if created or
              overwritten.        
        """
        srcdata = srcfn()
        dstdata = dst.exists() and dst.bytes() or None

        def invoke():
            if not self.pretend:
                dst.dirname().makedirs_p(0755)
                dst.write_bytes(srcdata)
                if mode is not None:
                    dst.chmod(mode)
        
        if dstdata is None:
            self.status("create", dst, color="*green*")
            invoke()
        elif dstdata == srcdata:
            self.status("identical", dst, color="*blue*")
        elif self.skip:
            self.status("skip", dst, color="*yellow*")
        elif self.force:
            self.status("force", dst, color="*yellow*")
            invoke()
        else:
            self.status("conflict", dst, color="*red*")
            if self._conflict(srcdata, dst, dstdata):
                invoke()

    def copy_file(self, src, dst=None, mode=None):
        """
        Copy a source file to the specified destination file.

        If the destination file already exists, then the contents of the source
        file are compared to the contents of the destination file. If they
        differ and the user has not specified to force or skip file operations,
        the user is presented with a conflict menu allowing the user to perform
        various operations to determine how to handle the conflict.

        If not destination is provided, it is assumed to be the same as the
        source path, but relative to the destination root.

        Parameters:
          - src: The source file to copy.
          - dst: The file to copy the source file to.
          - mode: The file mode to change the output file to; or None if the
              file mode should be left unchanged.        
        """
        dst = self.dst(dst or src)
        src = self.src(src)
        def srcfn():
            with src.open('r') as f:
                return f.read()
        return self._file(srcfn, dst, mode=(mode or src.stat().st_mode))

    def create_file(self, dst, mode=None):
        """
        Create a new file whose content is provided via a file context.

        This method provides a means to create a new file in the destination
        root path whose content is provided as if writing to a new file. The new
        file is only created if the file does not exist. If the file exists but
        contains different content, then the user is presented with a confclit
        menu similar to the 'copy_file' operation.

        Example::

          c = FileOp()
          with c.create_file('path/to/file.txt') as f:
              f.write('Hello World!\n')

        Parameters:
          - dst: The destination file path.
          - mode: The file mode to change the output file to; or None if the
              file mode should be left unchanged.
        """
        srcbuf = StringIO.StringIO()
        class _context(object):
            def __enter__(self_):
                return srcbuf
            def __exit__(self, exc_type, exc_value, exc_tb):
                self._file(srcbuf.getvalue, dst, mode=mode)
        return _context()

    def remove_file(self, p):
        """ Remove the specified file, relative to the destination root. """
        p = self.dst(p)
        if p.exists():
            self.status('remove', p, color='*red*')
            if not self.pretend:
                p.remove()

    def template(self, src, dst=None, mode=None):
        """
        Processes a template and writes the result to the destination file.

        The source file is read and treated as a Mako template. The template is
        processed, using the current FileOp's 'vars' attribute as the context to
        process the template in. The template is written out to the specified
        destination file if the rendered content does not equal the current
        content of the output file or the output file does not exist.

        If the output file exists but the content does not match the processed
        Mako template output, and the user has not specified to force or skip
        file operations, a conflict menu is presented allowing the user to
        perform various options to determine how to proceed.

        Parameters:
          - src: The Mako template source file.
          - dst: The file to write the processed template to.
          - chmod: The file mode to change the output file to; or None if the
              file mode should be left unchanged.
        """
        dst = self.dst(dst or src)
        src = self.src(src)
        def srcfn():
            try:
                d = Template(filename=str(src)).render(**self.template_vars)
            except NameError as e:
                raise error.TemplateRenderError(src)
            return d
        self._file(srcfn, dst, mode=(mode or src.stat().st_mode))

    def copy_directory(self, src, dst=None, templates=None):
        """
        Replicates a source directory/file tree at a specified destination.

        The specified source directory and file tree is replicated at the
        specified destination. All files matching any glob style file names
        listed in the ``templates`` keyword argument are treated as templates
        and rendered as such. By default all files are considered templates. An
        empty directory should contain a single file named ``.empty_directory``.

        Paramers:
          - src: The source tree to replicate.
          - dst: The destination to replicated the source tree at.
          - templates: A list of file globs for files to treat as templates.
        """
        dst = self.dst(dst or src)
        src = self.src(src)
        templates = ["*"] if templates is None else templates
        for f in src.walkfiles():
            if f.basename() == '.empty_directory':
                self.directory(dst / src.relpathto(f.parent))
            elif any(f.fnmatch(pat) for pat in templates):
                self.template(f, dst / src.relpathto(f))
            else:
                self.copy_file(f, dst / src.relpathto(f))

    def _inject(self, srcdata, p, re_, repl, color=None):
        self.status('update', p, color=color)
        if not self.pretend:
            re_ = re.compile(re_, flags=(re.MULTILINE | re.DOTALL))
            p.write_bytes(re_.sub(repl, srcdata))


    def _inject_op(fn):
        def decorated(self, p, txt, after=None, before=None, **kw):
            if after and before:
                raise error.ArgumentError('cannot specify both \'after\' and \'before\'')
            if after is None and before is None:
                raise error.ArgumentError('must specify either \'after\' or \'before\'')
            p = self.dst(p)
            return fn(self, p, p.bytes(), txt, after=after, before=before, **kw)
        return decorated

    @_inject_op
    def inject(self, p, srcdata, txt, after=None, before=None, force=False):
        """
        Injects text into a file before or after a marker.

        This file operation allowes a destination file to be specified and
        searched for a particular piece of text. The marker text is specified
        via a regex (may be a multi-line regex). The operation may specify
        to insert the new text after the marker (by specifying the marker text
        with the 'after' keyword) or before the marker (by speciyfing the marker
        text with the 'before' keyword).

        If the text to be inserted is already found in the file, then the new
        text will not be inserted again unless 'force' is set to True.

        Example::

          c = FileOp(...)
          with c.inject("path/to/file.txt", after="--start--") as f:
              f.write("\n    'new text'")

        Parameters:
          - dst: The file to insert text into.
          - after: Keyword option used to specify the regex to insert after.
          - before: Keyword option used to specify the regex to insert before.
          - force: For the text to be inserted even if it exists.
        """
        if force or txt not in srcdata:
            if after:
                mark, repl = after, r'\1%s'
            else:
                mark, repl = before, r'%s\1'
            self._inject(srcdata, p, r'(%s)' % mark, repl % txt, color='*green*')

    @_inject_op
    def erase(self, p, srcdata, txt, after=None, before=None):
        """ The inverse of the 'inject' operation. """
        if txt in srcdata:
            if after:
                mark, repl = (after, txt), r'\1\2'
            else:
                mark, repl = (txt, before), r'\2\3'
            self._inject(srcdata, p, r'(%s)(.*?)(%s)' % mark, repl, color='*red*')

