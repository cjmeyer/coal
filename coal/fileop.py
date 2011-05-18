# fileop.py

import error
import fnmatch
#import os
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
        return self.template_vars[key]

    def __setitem__(self, key, value):
        self.template_vars[key] = value

    def src(self, p):
        return (self.srcroot / p).abspath()

    def dst(self, p):
        def fn(m):
            return self.get(m.group(1), m.group(1))
        p = "%".join((var_re.sub(fn, p_) for p_ in p.split("%%")))
        return (self.dstroot / p).abspath()

    def inside(self, p):
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
        p = self.dst(p)
        if p.isdir():
            self.status("exist", p, color="*blue*")
        else:
            self.status("create", p, color="*green*")
            if not self.pretend:
                p.makedirs(mode)

    def rmdir(self, p):
        p = self.dst(p)
        if p.isdir():
            self.status("remove", p, color="*red*")
            if not self.pretend:
                p.removedirs()

    def _conflict(self, srcdata, dst, dstdata):
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
        dst = self.dst(dst or src)
        src = self.src(src)
        def srcfn():
            with src.open('r') as f:
                return f.read()
        return self._file(srcfn, dst, mode=(mode or src.stat().st_mode))

    def remove_file(self, p):
        p = self.dst(p)
        if p.exists():
            self.status('remove', p, color='*red*')
            if not self.pretend:
                p.remove()

    def template(self, src, dst=None, mode=None):
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
        if force or txt not in srcdata:
            if after:
                mark, repl = after, r'\1%s'
            else:
                mark, repl = before, r'%s\1'
            self._inject(srcdata, p, r'(%s)' % mark, repl % txt, color='*green*')

    @_inject_op
    def erase(self, p, srcdata, txt, after=None, before=None):
        if txt in srcdata:
            if after:
                mark, repl = (after, txt), r'\1\2'
            else:
                mark, repl = (txt, before), r'\2\3'
            self._inject(srcdata, p, r'(%s)(.*?)(%s)' % mark, repl, color='*red*')

