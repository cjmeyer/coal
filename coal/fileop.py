# fileop.py

import error
import fnmatch
import os
import types
import re
import StringIO
import util

from mako.template import Template

from subprocess import Popen, STDOUT


var_re = re.compile(r"%(.+?)%")


class FileOp(object):
    def __init__(self, ui, srcroot, dstroot):
        self.ui = ui
        self.srcroot = str(srcroot)
        self.dstroot = str(dstroot)

        self.pretend = False
        self.revoke = False
        self.force = False
        self.skip = False

        self.cmdfn = None
        self.cmdargs = []
        self.cmdopts = {}

        self.template_vars = {}

    def __getitem__(self, key):
        return self.template_vars[key]

    def __setitem__(self, key, value):
        self.template_vars[key] = value

    def expandsrc(self, p):
        return os.path.abspath(os.path.join(self.srcroot, p))

    def expanddst(self, p):
        """
        Expands a destination path, expanding any variable fields as needed.

        A destination path may contain fields whose values are to be filled in
        by the value stored in the FileOp 'vars' dictionary. For examples, if
        'vars["foo"] = "bar"', and the destination base directory is set to
        '/dst/root', then the path 'path/to/%foo%.txt' expands to the path
        '/dst/root/path/to/bar.txt'.

        Text between single '%' characters are variable fields to be be
        expanded. The character sequence '%%' is replaced with a single '%'
        character (so the '%' is acting as an escape character). Variable field
        names should not contain any '%' characters.

        Parameters:
          - p: The path to expand.
        """
        def fn(m):
            return self.template_vars.get(m.group(1), m.group(1))
        p = "%".join((var_re.sub(fn, p_) for p_ in p.split("%%")))
        return os.path.abspath(os.path.join(self.dstroot, p))

    def status(self, msg, p, color=None):
        self.ui.status("%s" % msg.lower().rjust(12), color=color)
        self.ui.status("  %s\n" % os.path.relpath(p))

    def cmd(self, cmd_, *args, **kw):
        """
        Executes a invoke or revoke ui command respecting pretending.

        The command should be provided in the same way as commands are provided
        to the 'subprocess.Popen' class. If no working directory is specified,
        then the current FileOp destination root is used.

        FileOps are always executed regardless of the state of 'self.revoke'.
        Since commands are executed by the ui and 'FileOp' has no knowledge
        of their result or operation, it is up to the caller to determine if the
        command should be executed based on the value of 'self.revoke'.
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
                self.ui.warn("socgen: command failed with exit code %s" %
                        p.returncode)

    def inside(self, p):
        """
        Sets the destination directory to new path while in a context.

        A new context object is created that on entry updates the destination
        path to that specified and on exit sets it back to the original path.
        The specified path may be a path relative to the current destination
        path or an absolute path.
        """
        dstroot = self.dstroot
        class context(object):
            def __enter__(self_):
                self.dstroot = self.expanddst(p)
            def __exit__(self_, exc_type, exc_value, exc_tb):
                self.dstroot = dstroot
        return context()

    def directory(self, dst, chmod=None):
        """
        Create a directory and all parent directories.

        If the specified destination directory does not exist, it is created.
        Any parent directories that are needed are also created. When being
        revoked, the destination directory is first checked to see if it is
        empty; if it is then the directory is removed and if it is not empty
        then it is left untouched.

        Parameters:
          - dst: The destination directory to create.
          - chmod: The file mode to apply to the directory; if None then the
              directory file mode is not changed.
        """
        dst = self.expanddst(dst)
        if self.revoke:
            if os.path.isdir(dst) and not os.listdir(dst):
                self.status("remove", dst, color="*red*")
                if not self.pretend:
                    os.removedirs(dst)
        elif os.path.isdir(dst):
            self.status("exist", dst, color="*blue*")
        else:
            self.status("create", dst, color="*green*")
            if not self.pretend:
                util.mkdir(dst)
                if chmod is not None:
                    os.chmod(dst, chmod)

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
        dst = os.path.relpath(dst)
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

    def _file(self, srcfn, dst, chmod=None):
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
        dst = self.expanddst(dst)
        if self.revoke:
            if os.path.exists(dst):
                self.status("remove", dst, color="*red*")
                if not self.pretend:
                    os.remove(dst)
        else:
            srcdata = srcfn()
            dstdata = None
            if os.path.exists(dst):
                with open(dst, "r") as f:
                    dstdata = f.read()

            def invoke():
                if not self.pretend:
                    util.mkdir(os.path.dirname(dst))
                    with open(dst, "w") as f:
                        f.write(srcdata)
                    if chmod is not None:
                        os.chmod(dst, chmod)
            
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

    def file(self, src, dst, chmod=None):
        """
        Copy a source file to the specified destination.

        If the destination file already exists, then the contents of the source
        file are compared to the contents of the destination file. If they
        differ and the user has not specified to force or skip file operations,
        the user is presetend with a conflict menu allowing the user to perform
        various options to determine how to proceed.

        Parameters:
          - src: The source file to copy.
          - dst: The file to copy the source file to.
          - chmod: The file mode to change the output file to; or None if the
              file mode should be left unchanged.
        """
        src = self.expandsrc(src)
        def srcfn():
            with open(src, "r") as f:
                srcdata = f.read()
            return srcdata
        self._file(srcfn, dst, chmod=(chmod or os.stat(src).st_mode))

    def mkfile(self, dst, chmod=None):
        """
        Create a file whose content is provided via a file context.

        This method provides a way to create a new files whose content is not
        provided via a source file or a template file, but rather directly from
        the caller through the use of a file like context object. This method
        can be thought of as a replacment of the builtin 'open' command where
        the content written to the file is only actually written if not already
        in the file and provides the ability to 'revoke' the action.

        Example::

          c = FileOp()
          with c.mkfile('path/to/file.txt') as f:
              f.write('Hello World!\n')

        Parameters:
          - dst: The destination file path.
          - chmod: The file mode to change the output file to; or None if the
              file mode should be left unchanged.
        """
        srcbuf = StringIO.StringIO()
        class _context(object):
            def __enter__(self_):
                return srcbuf
            def __exit__(self_, exc_type, exc_value, exc_tb):
                self._file(srcbuf.getvalue, dst, chmod=chmod)
        return _context()

    def template(self, src, dst, chmod=None):
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
        src = self.expandsrc(src)
        def srcfn():
            try:
                srcdata = Template(filename=src).render(**self.template_vars)
            except NameError as e:
                raise error.TemplateRenderError(src)
            return srcdata
        self._file(srcfn, dst, chmod=(chmod or os.stat(src).st_mode))

    def glob(self, src, dst, templates=None):
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
        src = self.expandsrc(src)
        dst = self.expanddst(dst)

        templates = ["*"] if templates is None else templates

        for root, dirs, files in os.walk(src):
            root = os.path.relpath(root, src)
            for f in files:
                if f == ".empty_directory":
                    self.directory(os.path.join(dst, root))
                else:
                    src_ = os.path.join(src, root, f)
                    dst_ = os.path.join(dst, root, f)
                    if any(fnmatch.fnmatch(f, pat) for pat in templates):
                        self.template(src_, dst_)
                    else:
                        self.file(src_, dst_)

    def inject(self, dst, after=None, before=None, force=False):
        """
        Injects text into a file before or after a marker.

        This file operation allowes a destination file to be specified and
        searched for a particular piece of text. The marker text is specified
        via a regex (may be a multi-line regex). The operation may specify
        to insert the new text after the marker (by specifying the marker text
        with the 'after' keyword) or before the marker (by speciyfing the marker
        text with the 'before' keyword).

        This operation can also be reversed or revoked.

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
        if after and before:
            raise error.ArgumentError(
                    "cannot specify both 'after' and 'before'")

        dst = self.expanddst(dst)
        buf = StringIO.StringIO()

        def _replace(regex, repl, srcdata, color=None):
            self.status("update", dst, color=color)
            regex = re.compile(regex, flags=(re.MULTILINE | re.DOTALL))
            with open(dst, "w") as f:
                f.write(regex.sub(repl, srcdata))

        class _context(object):
            def __enter__(self_):
                return buf

            def __exit__(self_, exc_type, exc_value, exc_tb):
                if not self.pretend and os.path.isfile(dst):
                    with open(dst, "r") as f:
                        srcdata = f.read()
                    data = buf.getvalue()
                    if self.revoke:
                        if after:
                            mark, repl = (after, data), r"\1\2"
                        else:
                            mark, repl = (data, before), r"\2\3"
                        _replace(r"(%s)(.*?)(%s)" % mark, repl, srcdata,
                                 color="*red*")
                    elif force or data not in srcdata:
                        if after:
                            mark, repl = after, r"\1%s"
                        else:
                            mark, repl = before, r"%s\1"
                        _replace(r"(%s)" % mark, repl % data, srcdata,
                                 color="*green*")

        return _context()

